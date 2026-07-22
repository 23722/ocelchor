"""Export: process tree + side index → BPMN 2.0 choreography XML (spec §B5/§B6).

Consumes only the discovered tree and the side index (never the log). Per node:
  leaf (TaskType)      → choreographyTask (roles as bands, one participant/role)
  named subtree ('NS') → subChoreography (brackets inside, bands = union of roles)
  '→'                  → sequence flow
  '×'  root-level      → N unlabeled start events (alternative instantiation)
  '×'  interior        → exclusive gateways (split + merge)
  '∧'                  → parallel gateways
  '↻'  single-element  → standardLoopCharacteristics marker
  '↻'  multi-element   → exclusive gateways with a back edge
Artificial start/end events per scope. Names per I5 (task = verbatim execType;
subChoreography = execType minus the kind prefix). Roles are bands, never names.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ocelchormodel_rad.discover import SideIndex, TreeNode
from ocelchormodel_rad.typing import ScopeType, TaskType

BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
ET.register_namespace("bpmn2", BPMN)
ET.register_namespace("bpmndi", BPMNDI)
ET.register_namespace("dc", DC)
ET.register_namespace("di", DI)

# Layout constants (mirror ocelchormodel/layout.py so DI matches the per-instance
# converter's band-shape geometry that chor-js accepts).
TASK_W, TASK_H, BAND_H, EVENT, HGAP, VGAP, PADX, PADY, GW = 100, 80, 20, 36, 60, 60, 30, 40, 50

_REQUEST = "Request "
_RESPOND = "Respond to "

_FLOW = {"choreographyTask", "subChoreography", "exclusiveGateway", "parallelGateway"}


def _b(tag: str) -> str:
    return f"{{{BPMN}}}{tag}"


def _ln(el: ET.Element) -> str:
    return el.tag.replace(f"{{{BPMN}}}", "")


def _ncname(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", s)


def scope_display_name(st: ScopeType) -> str:
    """subChoreography name per I5: the opener's execType minus its kind prefix."""
    t = st.opener.exec_type
    for pfx in (_REQUEST, _RESPOND):
        if t.startswith(pfx):
            return t[len(pfx):]
    return t


class _Exporter:
    def __init__(self, tree: TreeNode, side_index: SideIndex) -> None:
        self.tree = tree
        self.side = side_index
        self._n = 0
        self.roles: dict[str, str] = {}  # role → participant bpmn id

    def _uid(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}_{self._n}"

    def _participant(self, role: str) -> str:
        if role not in self.roles:
            self.roles[role] = f"P_{_ncname(role)}"
        return self.roles[role]

    # -- role collection (for the <participant> declarations) ----------------

    def _collect_roles(self, node: TreeNode) -> None:
        if node.op is None and isinstance(node.label, TaskType):
            self._participant(node.label.init_role)
            self._participant(node.label.noninit_role)
        for c in node.children:
            self._collect_roles(c)

    @staticmethod
    def _roles_of(node: TreeNode) -> list[str]:
        """Union of roles of all interactions in a subtree (band membership)."""
        seen: list[str] = []
        def walk(n: TreeNode) -> None:
            if n.op is None and isinstance(n.label, TaskType):
                for r in (n.label.init_role, n.label.noninit_role):
                    if r not in seen:
                        seen.append(r)
            for c in n.children:
                walk(c)
        walk(node)
        return seen

    # -- element emission ----------------------------------------------------

    def _emit_task(self, parent: ET.Element, node: TreeNode) -> tuple[str, str]:
        tt: TaskType = node.label
        tid = self._uid("Task")
        el = ET.SubElement(parent, _b("choreographyTask"), {
            "id": tid,
            "name": tt.exec_type,  # verbatim execType (I5)
            "initiatingParticipantRef": self._participant(tt.init_role),
        })
        ET.SubElement(el, _b("participantRef")).text = self._participant(tt.init_role)
        ET.SubElement(el, _b("participantRef")).text = self._participant(tt.noninit_role)
        doc = ET.SubElement(el, _b("documentation"))
        doc.text = tt.exec_type
        return tid, tid

    def _emit_scope(self, parent: ET.Element, node: TreeNode) -> tuple[str, str]:
        st: ScopeType = node.label
        sid = self._uid("Sub")
        bands = self._roles_of(node)
        el = ET.SubElement(parent, _b("subChoreography"), {
            "id": sid,
            "name": scope_display_name(st),
            "initiatingParticipantRef": self._participant(st.opener.init_role),
        })
        for r in bands:
            ET.SubElement(el, _b("participantRef")).text = self._participant(r)
        # brackets + body render INSIDE, with an artificial start/end per scope.
        self._emit_container(el, node.children[0])
        return sid, sid

    def _emit_container(self, parent: ET.Element, body: TreeNode) -> None:
        """A scope/root body: artificial start → body flow → artificial end."""
        start = ET.SubElement(parent, _b("startEvent"), {"id": self._uid("Start")})
        entry, exit_ = self._emit_flow(parent, body)
        end = ET.SubElement(parent, _b("endEvent"), {"id": self._uid("End")})
        if entry:
            self._seq(parent, start.get("id"), entry)
            self._seq(parent, exit_, end.get("id"))
        else:
            self._seq(parent, start.get("id"), end.get("id"))

    def _emit_flow(self, parent: ET.Element, node: TreeNode) -> tuple[str | None, str | None]:
        """Emit a node's flow elements into *parent*; return (entry_id, exit_id)."""
        op = node.op
        if op is None:
            if node.label is None:
                return None, None  # tau — silent
            if isinstance(node.label, TaskType):
                return self._emit_task(parent, node)
            # a bare ScopeType leaf should not survive composition
            raise AssertionError(f"unexpanded scope leaf {node.label!r}")
        if op == "NS":
            return self._emit_scope(parent, node)
        if op == "→":
            return self._emit_sequence(parent, node.children)
        if op == "×":
            return self._emit_xor(parent, node.children)
        if op == "∧":
            return self._emit_parallel(parent, node.children)
        if op == "↻":
            return self._emit_loop(parent, node)
        raise AssertionError(f"unknown operator {op!r}")

    def _emit_sequence(self, parent, children) -> tuple[str | None, str | None]:
        entry = prev_exit = None
        for c in children:
            e, x = self._emit_flow(parent, c)
            if e is None:
                continue  # tau
            if entry is None:
                entry = e
            if prev_exit is not None:
                self._seq(parent, prev_exit, e)
            prev_exit = x
        return entry, prev_exit

    def _emit_xor(self, parent, children) -> tuple[str, str]:
        split = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("XorSplit")})
        merge = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("XorMerge")})
        for c in children:
            e, x = self._emit_flow(parent, c)
            if e is None:  # tau branch: split → merge directly
                self._seq(parent, split.get("id"), merge.get("id"))
            else:
                self._seq(parent, split.get("id"), e)
                self._seq(parent, x, merge.get("id"))
        return split.get("id"), merge.get("id")

    def _emit_parallel(self, parent, children) -> tuple[str, str]:
        split = ET.SubElement(parent, _b("parallelGateway"), {"id": self._uid("AndSplit")})
        merge = ET.SubElement(parent, _b("parallelGateway"), {"id": self._uid("AndMerge")})
        for c in children:
            e, x = self._emit_flow(parent, c)
            if e is None:
                self._seq(parent, split.get("id"), merge.get("id"))
            else:
                self._seq(parent, split.get("id"), e)
                self._seq(parent, x, merge.get("id"))
        return split.get("id"), merge.get("id")

    def _emit_loop(self, parent, node) -> tuple[str | None, str | None]:
        # pm4py loop *(body, redo) = body (redo body)* : do body, then optionally
        # repeat (redo then body). The redo child is REAL flow — never drop it.
        body = node.children[0]
        redo = node.children[1] if len(node.children) > 1 else TreeNode(None, None, [])
        redo_is_tau = redo.is_tau()
        body_single = body.op == "NS" or (body.op is None and isinstance(body.label, TaskType))

        # Simple self-loop (redo = tau) over a single element → loop marker (B5).
        if redo_is_tau and body_single:
            e, x = self._emit_flow(parent, body)
            ET.SubElement(_find_by_id(parent, e), _b("standardLoopCharacteristics"))
            return e, x

        # General loop → exclusive gateways with a back edge. The redo path (when
        # non-tau) carries its own flow elements, so nothing is lost.
        merge = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("LoopJoin")})
        be, bx = self._emit_flow(parent, body)
        split = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("LoopSplit")})
        if be is not None:
            self._seq(parent, merge.get("id"), be)
            self._seq(parent, bx, split.get("id"))
        else:
            self._seq(parent, merge.get("id"), split.get("id"))
        if redo_is_tau:
            self._seq(parent, split.get("id"), merge.get("id"))  # repeat body directly
        else:
            re, rx = self._emit_flow(parent, redo)
            self._seq(parent, split.get("id"), re)  # back path runs redo…
            self._seq(parent, rx, merge.get("id"))  # …then loops to body
        return merge.get("id"), split.get("id")

    def _seq(self, parent, src, tgt) -> None:
        ET.SubElement(parent, _b("sequenceFlow"), {
            "id": self._uid("Flow"), "sourceRef": src, "targetRef": tgt,
        })

    # -- top level -----------------------------------------------------------

    def build(self) -> ET.Element:
        self._collect_roles(self.tree)
        defs = ET.Element(_b("definitions"), {
            "id": "Definitions_discovered",
            "targetNamespace": "http://ocelchor/discovered",
        })
        choreo = ET.SubElement(defs, _b("choreography"), {"id": "Choreography_discovered"})
        for role, pid in self.roles.items():
            ET.SubElement(choreo, _b("participant"), {"id": pid, "name": role})

        # Root-level XOR → N unlabeled start events (alternative instantiation),
        # each on its own branch with its own end event (spec §B5: no rejoin, so
        # N end events — avoids a single shared end fanning in from every branch).
        if self.tree.op == "×":
            for branch in self.tree.children:
                start = ET.SubElement(choreo, _b("startEvent"), {"id": self._uid("Start")})
                e, x = self._emit_flow(choreo, branch)
                end = ET.SubElement(choreo, _b("endEvent"), {"id": self._uid("End")})
                if e is None:
                    self._seq(choreo, start.get("id"), end.get("id"))
                else:
                    self._seq(choreo, start.get("id"), e)
                    self._seq(choreo, x, end.get("id"))
        else:
            self._emit_container(choreo, self.tree)
        return defs


# ---------------------------------------------------------------------------
# Diagram interchange (DI): layout + BPMNShape/BPMNEdge, read off the semantic
# tree (which carries initiatingParticipantRef + participantRefs). Mirrors the
# per-instance converter's band-shape format so bpmn-js / chor-js can render it.
# ---------------------------------------------------------------------------

def _measure(el: ET.Element) -> tuple[float, float, dict]:
    """Measure an element; return (w, h, positions) with positions relative to
    the element's top-left. Subs recurse into a layered inner layout."""
    k = _ln(el)
    if k == "choreographyTask":
        return TASK_W, TASK_H, {el.get("id"): (0, 0, TASK_W, TASK_H)}
    if k in ("startEvent", "endEvent"):
        return EVENT, EVENT, {el.get("id"): (0, 0, EVENT, EVENT)}
    if k in ("exclusiveGateway", "parallelGateway"):
        return GW, GW, {el.get("id"): (0, 0, GW, GW)}
    # subChoreography: inner layered layout + band/padding frame.
    refs = [c.text for c in el if _ln(c) == "participantRef"]
    n = len(refs)
    n_top, n_bot = (n + 1) // 2, n // 2
    iw, ih, ipos = _layout_flow(el)
    top_off = n_top * BAND_H + PADY
    w = max(iw + 2 * PADX, TASK_W)
    h = top_off + max(ih, TASK_H) + n_bot * BAND_H + PADY
    pos = {el.get("id"): (0, 0, w, h)}
    for cid, (cx, cy, cw, ch) in ipos.items():
        pos[cid] = (cx + PADX, cy + top_off, cw, ch)
    return w, h, pos


def _layered(ids: set, size: dict, sub_pos: dict, adj: dict) -> tuple[float, float, dict]:
    """Rank-based layout of one connected flow region: rank = longest path from a
    source (columns left→right); a column's elements stack, centred on a shared
    centreline so linear chains get aligned centres (straight arcs)."""
    adj = {i: [v for v in adj.get(i, []) if v in ids] for i in ids}
    indeg = {i: 0 for i in ids}
    for i in ids:
        for v in adj[i]:
            indeg[v] += 1
    rank = {i: 0 for i in ids}
    ind = dict(indeg)
    queue = [i for i in ids if ind[i] == 0] or list(ids)
    seen: set = set()
    while queue:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        for v in adj[u]:
            rank[v] = max(rank[v], rank[u] + 1)
            ind[v] -= 1
            if ind[v] <= 0 and v not in seen:
                queue.append(v)

    columns: dict[int, list] = {}
    for i in ids:
        columns.setdefault(rank[i], []).append(i)
    col_h = {rk: sum(size[c][1] for c in col) + VGAP * (len(col) - 1)
             for rk, col in columns.items()}
    global_h = max(col_h.values(), default=TASK_H)
    cy = global_h / 2

    pos: dict[str, tuple] = {}
    x = 0.0
    for rk in sorted(columns):
        col = columns[rk]
        col_w = max(size[c][0] for c in col)
        y = cy - col_h[rk] / 2
        for cid in col:
            w, h = size[cid]
            for iid, (ix, iy, iw, ih) in sub_pos[cid].items():
                pos[iid] = (x + ix, y + iy, iw, ih)
            y += h + VGAP
        x += col_w + HGAP
    return x, global_h, pos


def _reachable(start: str, adj: dict) -> set:
    out, stack = set(), [start]
    while stack:
        u = stack.pop()
        if u in out:
            continue
        out.add(u)
        stack.extend(adj.get(u, []))
    return out


def _layout_flow(container: ET.Element) -> tuple[float, float, dict]:
    """Layout a container's flow. A single entry → one layered region. Multiple
    start events (root-level XOR) → each branch on its own horizontal lane,
    stacked vertically, so alternative entries read as clean parallel rows."""
    kids = [c for c in container if _ln(c) in _FLOW or _ln(c) in ("startEvent", "endEvent")]
    if not kids:
        return TASK_W, TASK_H, {}
    ids = {c.get("id") for c in kids}
    size, sub_pos = {}, {}
    for c in kids:
        w, h, p = _measure(c)
        size[c.get("id")] = (w, h)
        sub_pos[c.get("id")] = p

    adj: dict[str, list[str]] = {i: [] for i in ids}
    for sf in container.findall(_b("sequenceFlow")):
        s, t = sf.get("sourceRef"), sf.get("targetRef")
        if s in ids and t in ids:
            adj[s].append(t)

    starts = [c.get("id") for c in kids if _ln(c) == "startEvent"]
    if len(starts) <= 1:
        return _layered(ids, size, sub_pos, adj)

    # Branch-lane layout: one lane per start event (root-level XOR entries).
    pos: dict[str, tuple] = {}
    y = 0.0
    maxw = 0.0
    assigned: set = set()
    for s in starts:
        part = _reachable(s, adj) - assigned
        if not part:
            continue
        assigned |= part
        w, h, p = _layered(part, size, sub_pos, adj)
        for iid, (px, py, pw, ph) in p.items():
            pos[iid] = (px, y + py, pw, ph)
        y += h + 2 * VGAP
        maxw = max(maxw, w)
    return maxw, y, pos


def _layout_container(container: ET.Element, x0: float, y0: float, bounds: dict) -> tuple[float, float]:
    w, h, pos = _layout_flow(container)
    for cid, (px, py, pw, ph) in pos.items():
        bounds[cid] = (x0 + px, y0 + py, pw, ph)
    return w, h


def _shape(plane, sid, ref, xywh, **extra):
    sh = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNShape",
                       {"id": sid, "bpmnElement": ref, **extra})
    x, y, w, h = xywh
    ET.SubElement(sh, f"{{{DC}}}Bounds",
                  {"x": f"{x:.0f}", "y": f"{y:.0f}", "width": f"{w:.0f}", "height": f"{h:.0f}"})
    return sh


def _emit_bands(plane, el, xywh):
    """Emit participant band sub-shapes for a task/sub (spec §B5, chor-js format)."""
    x, y, w, h = xywh
    init = el.get("initiatingParticipantRef")
    refs = [c.text for c in el if _ln(c) == "participantRef"]
    if _ln(el) == "choreographyTask":
        other = next((r for r in refs if r != init), init)
        _shape(plane, f"{el.get('id')}_di_top", init, (x, y, w, BAND_H),
               participantBandKind="top_initiating", isMessageVisible="false",
               choreographyActivityShape=f"{el.get('id')}_di")
        _shape(plane, f"{el.get('id')}_di_bot", other, (x, y + h - BAND_H, w, BAND_H),
               participantBandKind="bottom_non_initiating", isMessageVisible="false",
               choreographyActivityShape=f"{el.get('id')}_di")
        return
    ordered = ([init] if init else []) + [r for r in refs if r != init]
    top, bot = ordered[0::2], ordered[1::2]
    for i, p in enumerate(top):
        kind = "top_initiating" if i == 0 else "middle_non_initiating"
        _shape(plane, f"{el.get('id')}_di_t{i}", p, (x, y + i * BAND_H, w, BAND_H),
               participantBandKind=kind, isMessageVisible="false",
               choreographyActivityShape=f"{el.get('id')}_di")
    for j, p in enumerate(bot):
        kind = "bottom_non_initiating" if j == 0 else "middle_non_initiating"
        _shape(plane, f"{el.get('id')}_di_b{j}", p, (x, y + h - (j + 1) * BAND_H, w, BAND_H),
               participantBandKind=kind, isMessageVisible="false",
               choreographyActivityShape=f"{el.get('id')}_di")


def _add_di(defs: ET.Element, choreo: ET.Element) -> None:
    bounds: dict[str, tuple] = {}
    _layout_container(choreo, 100, 100, bounds)

    diagram = ET.SubElement(defs, f"{{{BPMNDI}}}BPMNDiagram", {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI}}}BPMNPlane",
                          {"id": "BPMNPlane_1", "bpmnElement": choreo.get("id")})

    for el in choreo.iter():
        k = _ln(el)
        eid = el.get("id")
        if k in ("startEvent", "endEvent") and eid in bounds:
            _shape(plane, f"{eid}_di", eid, bounds[eid])
        elif k in ("exclusiveGateway", "parallelGateway") and eid in bounds:
            _shape(plane, f"{eid}_di", eid, bounds[eid])
        elif k == "choreographyTask" and eid in bounds:
            _shape(plane, f"{eid}_di", eid, bounds[eid])
            _emit_bands(plane, el, bounds[eid])
        elif k == "subChoreography" and eid in bounds:
            _shape(plane, f"{eid}_di", eid, bounds[eid], isExpanded="true")
            _emit_bands(plane, el, bounds[eid])

    # Edges: orthogonal (Manhattan) routing. Forward edges route via a mid-x
    # dogleg; back edges (loop returns, target left of source) route *below* the
    # elements so they don't cut diagonally across the flow.
    for sf in choreo.iter(_b("sequenceFlow")):
        s, t = sf.get("sourceRef"), sf.get("targetRef")
        if s not in bounds or t not in bounds:
            continue
        sx, sy, sw, sh = bounds[s]
        tx, ty, tw, th = bounds[t]
        edge = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNEdge",
                             {"id": f"{sf.get('id')}_di", "bpmnElement": sf.get("id")})
        scy, tcy = sy + sh / 2, ty + th / 2
        if tx >= sx + sw - 1:  # forward
            if abs(scy - tcy) < 2:
                pts = [(sx + sw, scy), (tx, tcy)]
            else:
                mx = (sx + sw + tx) / 2
                pts = [(sx + sw, scy), (mx, scy), (mx, tcy), (tx, tcy)]
        else:  # back edge → drop below and route left
            below = max(sy + sh, ty + th) + 25
            pts = [(sx + sw / 2, sy + sh), (sx + sw / 2, below),
                   (tx + tw / 2, below), (tx + tw / 2, ty + th)]
        for px, py in pts:
            ET.SubElement(edge, f"{{{DI}}}waypoint", {"x": f"{px:.0f}", "y": f"{py:.0f}"})


def to_bpmn(tree: TreeNode, side_index: SideIndex, *, include_di: bool = True) -> str:
    # Delegated to the structural layout engine (tree-driven track assignment).
    from ocelchormodel_rad import layout
    return layout.build_bpmn(tree, side_index, include_di=include_di)


def _find_by_id(parent: ET.Element, eid: str) -> ET.Element:
    for el in parent.iter():
        if el.get("id") == eid:
            return el
    raise KeyError(eid)


# ---------------------------------------------------------------------------
# Process-tree serialization — indented s-expression in the inductive-miner
# literature's notation: operators → × ↻ ∧, τ for silent steps, and RAD's
# ∇_{scope} for named subtrees. Leaves show the FULL discovery alphabet
# symbol — 'execType' ⟨initRole→noninitRole⟩ — i.e. the participant
# annotation exactly as it drives pooling (spec §B2.2).
# ---------------------------------------------------------------------------

def tree_sexpr(node: TreeNode, indent: int = 0) -> str:
    """Render the discovered choreography tree as an indented s-expression.

    The first line is not indented; nested children indent by two spaces per
    level. Emitted per log as ``process_tree.txt`` next to the discovered
    model.

    Every symbol prints its full type: ``'execType' ⟨init→noninit⟩`` for
    tasks, ``∇_{name} ⟨init→noninit⟩`` for scopes (the opener's role pair —
    scopeType = taskType(opener)). Without the pair, scopes of the same
    display name but different opener roles (e.g. an outer call vs. a
    re-entrant self-call) would be indistinguishable on the ∇ line.
    """
    if node.op is None:
        if node.label is None:
            return "τ"
        tt = node.label
        return f"'{tt.exec_type}' ⟨{tt.init_role}→{tt.noninit_role}⟩"
    if node.op == "NS":
        op = node.label.opener
        head = (f"∇_{{{scope_display_name(node.label)}}}"
                f" ⟨{op.init_role}→{op.noninit_role}⟩")
    else:
        head = node.op
    pad = "  " * (indent + 1)
    children = ",\n".join(pad + tree_sexpr(c, indent + 1) for c in node.children)
    return f"{head}(\n{children})"


# ---------------------------------------------------------------------------
# Structural signature — tree isomorphism over (element type, name, band
# multiset), ignoring ids and coordinates (spec §B5 round-trip).
# ---------------------------------------------------------------------------

_ELEMENTS = {"choreographyTask", "subChoreography", "startEvent", "endEvent"}


def _role_of_display(name: str) -> str:
    """Normalise a band participant display to its role/type.

    The per-instance converter names generic bands ``"<Type> …<suffix>"``
    (ocelchormodel._display_name); named contracts use the type verbatim. The
    discovered model already carries roles. Splitting on the em-space marker
    maps both to the role, so band multisets compare across the two models.
    """
    return name.split(" …")[0]


def structural_signature(root: ET.Element) -> tuple:
    """Normalise a BPMN choreography to a nested (kind, name, band-set) tuple."""
    choreo = next((e for e in root.iter() if e.tag == _b("choreography")), root)
    pid_role: dict[str, str] = {}
    for p in choreo:
        if p.tag == _b("participant"):
            pid_role[p.get("id")] = _role_of_display(p.get("name", ""))

    def bands(el: ET.Element) -> frozenset[str]:
        return frozenset(
            pid_role.get(c.text, c.text)
            for c in el if c.tag == _b("participantRef")
        )

    def node(el: ET.Element):
        tag = el.tag.replace(f"{{{BPMN}}}", "")
        if tag == "startEvent":
            return ("start",)
        if tag == "endEvent":
            return ("end",)
        if tag == "choreographyTask":
            loop = el.get("loopType") == "Standard" or any(
                c.tag == _b("standardLoopCharacteristics") for c in el)
            return ("task", el.get("name"), bands(el), loop)
        if tag == "subChoreography":
            loop = el.get("loopType") == "Standard" or any(
                c.tag == _b("standardLoopCharacteristics") for c in el)
            return ("sub", el.get("name"), bands(el), loop, _children(el))
        return None

    def _children(container: ET.Element) -> tuple:
        out = []
        for c in container:
            tag = c.tag.replace(f"{{{BPMN}}}", "")
            if tag in _ELEMENTS:
                out.append(node(c))
        return tuple(out)

    return _children(choreo)


def structural_signature_xml(xml: str) -> tuple:
    return structural_signature(ET.fromstring(xml))


def _strip_loop(node: tuple) -> tuple:
    if node[0] == "task":
        return ("task", node[1], node[2], False)
    if node[0] == "sub":
        return ("sub", node[1], node[2], False, node[4])
    return node


def _set_loop(node: tuple) -> tuple:
    if node[0] == "task":
        return ("task", node[1], node[2], True)
    if node[0] == "sub":
        return ("sub", node[1], node[2], True, node[4])
    return node


def collapse_loops(sig: tuple) -> tuple:
    """Isomorphism modulo loop unrolling: a discovered loop over one element
    (loop marker, single copy) is equivalent to a run of ≥2 identical siblings
    in the per-instance converter output. Recursively collapse consecutive
    duplicate siblings into a single loop-marked element so the discovered and
    reference signatures compare (spec §B5 round-trip)."""
    # First recurse into subChoreographies.
    normed = []
    for n in sig:
        if n[0] == "sub":
            n = ("sub", n[1], n[2], n[3], collapse_loops(n[4]))
        normed.append(n)
    # Then merge maximal runs of identical (loop-agnostic) adjacent nodes.
    out: list[tuple] = []
    i = 0
    while i < len(normed):
        j = i
        while j + 1 < len(normed) and _strip_loop(normed[j + 1]) == _strip_loop(normed[i]):
            j += 1
        node = normed[i]
        if j > i:  # a run of ≥2 identical siblings → one looped element
            node = _set_loop(node)
        out.append(node)
        i = j + 1
    return tuple(out)
