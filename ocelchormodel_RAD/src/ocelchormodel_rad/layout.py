"""Structural layout: process tree → positioned BPMN choreography (XML + DI).

Unlike a generic graph layout, this lays out *from the tree*, so it knows what
is a sequence, an exclusive choice, a loop (and which side is the body vs the
redo), and a nested scope. Each construct composes via left/right connection
ports on a shared centreline, so sequences are straight, choices fan out
symmetrically, loop redo paths get their own track below the body, and back
edges route beneath everything they span. Emits the same semantic elements as
the plain exporter (so structural_signature still applies) plus DI shapes/edges
that bpmn-js / chor-js render.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from ocelchormodel_rad.discover import SideIndex, TreeNode
from ocelchormodel_rad.export_bpmn import (
    BAND_H, BPMN, BPMNDI, DC, DI, EVENT, GW, HGAP, PADX, PADY, TASK_H, TASK_W, VGAP,
    _ncname, scope_display_name,
)
from ocelchormodel_rad.typing import TaskType


def _b(t: str) -> str:
    return f"{{{BPMN}}}{t}"


# ---------------------------------------------------------------------------
# Geometry model
# ---------------------------------------------------------------------------

@dataclass
class Shape:
    id: str
    kind: str          # task | scope | start | end | xgw | pgw
    node: TreeNode | None = None
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    loop: bool = False
    container: str | None = None  # parent scope id (None = choreography root)
    # y-offset of the left/right connection port from the shape's top edge.
    # Atoms connect at their geometric centre; a scope connects on its INNER
    # FLOW LINE, which sits half a band off-centre when its band count is odd.
    port_dy: float | None = None  # None → h/2


@dataclass
class Edge:
    id: str
    src: str
    tgt: str
    container: str | None = None
    # Routing hint, derived from the construct that created the edge
    # (conventions extracted from the user's hand-arranged reference model):
    #   None         — plain forward edge (straight or dogleg)
    #   'loop-enter' — split → redo    (vertical drop into the redo's TOP,
    #                  or RIGHT-side entry for a small single-task redo)
    #   'loop-back'  — redo → merge    (out the redo's LEFT, into merge BOTTOM)
    #   'gw-out'     — gateway → off-row branch (gateway TOP/BOTTOM port,
    #                  horizontal into the branch's LEFT)
    #   'gw-in'      — off-row branch → gateway (branch RIGHT, into gateway
    #                  TOP/BOTTOM port)
    hint: str | None = None


@dataclass
class Frag:
    w: float
    h: float
    cy: float                 # connection y (left/right port), relative to top
    shapes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    members: list = field(default_factory=list)  # direct flow-element ids at this level
    entry: str | None = None
    exit: str | None = None


def _shift(frag: Frag, dx: float, dy: float) -> None:
    for s in frag.shapes:
        s.x += dx
        s.y += dy


# ---------------------------------------------------------------------------
# Role helpers (bands)
# ---------------------------------------------------------------------------

def _init_role(node: TreeNode) -> str | None:
    if node.op is None and isinstance(node.label, TaskType):
        return node.label.init_role
    if node.op == "NS":
        return node.label.opener.init_role
    return None


def _band_roles(node: TreeNode) -> list[str]:
    seen: list[str] = []

    def walk(n: TreeNode) -> None:
        if n.op is None and isinstance(n.label, TaskType):
            for r in (n.label.init_role, n.label.noninit_role):
                if r not in seen:
                    seen.append(r)
        for c in n.children:
            walk(c)

    walk(node)
    init = _init_role(node)
    if init and init in seen:
        seen = [init] + [r for r in seen if r != init]
    return seen


# ---------------------------------------------------------------------------
# Structural layout
# ---------------------------------------------------------------------------

class _Layout:
    def __init__(self) -> None:
        self._n = 0

    def uid(self, p: str) -> str:
        self._n += 1
        return f"{p}_{self._n}"

    # -- leaf shapes ---------------------------------------------------------

    def _atom(self, kind: str, w: float, h: float, node=None) -> Frag:
        s = Shape(self.uid(kind), kind, node, 0, 0, w, h)
        return Frag(w, h, h / 2, [s], [], [s.id], s.id, s.id)

    def flow(self, node: TreeNode) -> Frag:
        op = node.op
        if op is None:
            if node.label is None:
                return Frag(0, 0, 0, [], [], [], None, None)  # tau
            if isinstance(node.label, TaskType):
                return self._atom("task", TASK_W, TASK_H, node)
            raise AssertionError("unexpanded scope leaf")
        if op == "NS":
            return self._scope(node)
        if op == "→":
            return self._seq(node.children)
        if op == "×":
            return self._branch(node.children, "xgw")
        if op == "∧":
            return self._branch(node.children, "pgw")
        if op == "↻":
            return self._loop(node)
        raise AssertionError(f"unknown op {op!r}")

    # -- sequence ------------------------------------------------------------

    def _seq(self, children) -> Frag:
        frags = [f for f in (self.flow(c) for c in children) if f.entry]
        if not frags:
            return Frag(0, 0, 0, [], [], [], None, None)
        cy = max(f.cy for f in frags)
        x = 0.0
        shapes, edges, members = [], [], []
        entry = prev = None
        for f in frags:
            _shift(f, x, cy - f.cy)
            shapes += f.shapes
            edges += f.edges
            members += f.members
            if entry is None:
                entry = f.entry
            if prev is not None:
                edges.append(Edge(self.uid("Flow"), prev, f.entry))
            prev = f.exit
            x += f.w + HGAP
        h = max((s.y + s.h for s in shapes), default=TASK_H)
        return Frag(x - HGAP, h, cy, shapes, edges, members, entry, prev)

    # -- exclusive / parallel branches --------------------------------------

    def _branch(self, children, gw) -> Frag:
        split = Shape(self.uid(gw), gw, None, 0, 0, GW, GW)
        merge = Shape(self.uid(gw), gw, None, 0, 0, GW, GW)
        frags = [self.flow(c) for c in children]
        # Smallest branch first: the through-line row stays simple and big
        # branches hang below it (convention from the user's reference model).
        frags.sort(key=lambda f: f.h)
        bx = GW + HGAP
        shapes, edges, members = [], [], [split.id, merge.id]
        y = 0.0
        maxw = TASK_W
        cy = None  # gateway row = the FIRST branch's port row (straight line)
        for f in frags:
            if not f.entry:  # tau branch: split → merge skip edge (bypass arc)
                edges.append(Edge(self.uid("Flow"), split.id, merge.id, hint="gw-skip"))
                continue
            _shift(f, bx, y)
            if cy is None:
                cy = y + f.cy
            shapes += f.shapes
            edges += f.edges
            members += f.members
            edges.append(Edge(self.uid("Flow"), split.id, f.entry, hint="gw-out"))
            edges.append(Edge(self.uid("Flow"), f.exit, merge.id, hint="gw-in"))
            y += f.h + VGAP
            maxw = max(maxw, f.w)
        total_h = max(y - VGAP, GW)
        if cy is None:
            cy = GW / 2
        split.x, split.y = 0, cy - GW / 2
        merge.x, merge.y = bx + maxw + HGAP, cy - GW / 2
        shapes = [split] + shapes + [merge]
        return Frag(merge.x + GW, total_h, cy, shapes, edges, members, split.id, merge.id)

    # -- loop ----------------------------------------------------------------

    def _loop(self, node) -> Frag:
        body = node.children[0]
        redo = node.children[1] if len(node.children) > 1 else TreeNode(None, None, [])
        redo_tau = redo.op is None and redo.label is None
        body_single = body.op == "NS" or (body.op is None and isinstance(body.label, TaskType))

        # Simple self-loop over a single element → loop marker on it (spec §B5).
        if redo_tau and body_single:
            fb = self.flow(body)
            for s in fb.shapes:
                if s.id == fb.entry:
                    s.loop = True
            return fb

        merge = Shape(self.uid("xgw"), "xgw", None, 0, 0, GW, GW)
        split = Shape(self.uid("xgw"), "xgw", None, 0, 0, GW, GW)
        fb = self.flow(body)
        cy = max(GW / 2, fb.cy)
        merge.x, merge.y = 0, cy - GW / 2
        bdx = GW + HGAP
        _shift(fb, bdx, cy - fb.cy)
        split.x, split.y = bdx + fb.w + HGAP, cy - GW / 2
        shapes = [merge] + fb.shapes + [split]
        edges = fb.edges + [Edge(self.uid("Flow"), merge.id, fb.entry),
                            Edge(self.uid("Flow"), fb.exit, split.id)]
        members = [merge.id] + fb.members + [split.id]
        top_bottom = max(cy + GW / 2, max((s.y + s.h for s in fb.shapes), default=0))

        if redo_tau:
            edges.append(Edge(self.uid("Flow"), split.id, merge.id))
            return Frag(split.x + GW, top_bottom, cy, shapes, edges, members, merge.id, split.id)

        # Redo carries flow: put it on its own track below the body.
        fr = self.flow(redo)
        redo_y = top_bottom + 2 * VGAP
        _shift(fr, bdx, redo_y)
        shapes += fr.shapes
        edges += fr.edges
        members += fr.members
        # Single-shape redos support side entry/exit; a multi-element redo must
        # be approached via the channels above/below its track, otherwise the
        # arcs would cut through the redo's own siblings.
        multi = "-multi" if len(fr.members) > 1 else ""
        edges.append(Edge(self.uid("Flow"), split.id, fr.entry, hint=f"loop-enter{multi}"))
        edges.append(Edge(self.uid("Flow"), fr.exit, merge.id, hint=f"loop-back{multi}"))
        w = max(split.x + GW, bdx + fr.w)
        h = redo_y + fr.h
        return Frag(w, h, cy, shapes, edges, members, merge.id, split.id)

    # -- container (start … flow … end) -------------------------------------

    def container(self, body: TreeNode) -> Frag:
        start = Shape(self.uid("Start"), "start", None, 0, 0, EVENT, EVENT)
        fb = self.flow(body)
        end = Shape(self.uid("End"), "end", None, 0, 0, EVENT, EVENT)
        cy = max(EVENT / 2, fb.cy)
        start.x, start.y = 0, cy - EVENT / 2
        dx = EVENT + HGAP
        if fb.entry:
            _shift(fb, dx, cy - fb.cy)
            end.x = dx + fb.w + HGAP
            edges = fb.edges + [Edge(self.uid("Flow"), start.id, fb.entry),
                                Edge(self.uid("Flow"), fb.exit, end.id)]
        else:
            end.x = dx
            edges = [Edge(self.uid("Flow"), start.id, end.id)]
        end.y = cy - EVENT / 2
        shapes = [start] + fb.shapes + [end]
        members = [start.id] + fb.members + [end.id]
        h = max((s.y + s.h for s in shapes), default=EVENT)
        return Frag(end.x + EVENT, h, cy, shapes, edges, members, start.id, end.id)

    # -- scope (nested subChoreography) -------------------------------------

    def _scope(self, node) -> Frag:
        inner = self.container(node.children[0])
        roles = _band_roles(node)
        n = len(roles)
        n_top, n_bot = (n + 1) // 2, n // 2
        top_off = n_top * BAND_H + PADY
        _shift(inner, PADX, top_off)
        sid = self.uid("Sub")
        member_ids = set(inner.members)
        for s in inner.shapes:
            if s.id in member_ids:
                s.container = sid
        for e in inner.edges:
            if e.container is None:
                e.container = sid
        w = inner.w + 2 * PADX
        h = top_off + inner.h + n_bot * BAND_H + PADY
        scope_shape = Shape(sid, "scope", node, 0, 0, w, h,
                        port_dy=top_off + inner.cy)
        shapes = [scope_shape] + inner.shapes
        return Frag(w, h, top_off + inner.cy, shapes, inner.edges, [sid], sid, sid)


# ---------------------------------------------------------------------------
# Build: layout → semantic XML + DI
# ---------------------------------------------------------------------------

class _Participants:
    """role → participant id, plus a same-named doppelgänger for same-role
    interactions.

    chor-js (bpmn-js) aborts its import walk on a choreography activity whose
    two bands reference the SAME participant — which the discovered model
    produces whenever both sides of an interaction share a role (CA→CA calls,
    self-calls). BPMN participant names need not be unique, so such tasks get a
    second participant element with the same display name: bands render as
    e.g. "CA | CA" and the import survives. Purely presentational."""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}       # role → primary participant id
        self.alt_ids: dict[str, str] = {}   # role → doppelgänger id (lazy)

    def get(self, role: str) -> str:
        return self.ids.setdefault(role, f"P_{_ncname(role)}")

    def alt(self, role: str) -> str:
        self.get(role)
        return self.alt_ids.setdefault(role, f"P_{_ncname(role)}_2")

    def declared(self) -> list[tuple[str, str]]:
        out = [(pid, role) for role, pid in self.ids.items()]
        out += [(pid, role) for role, pid in self.alt_ids.items()]
        return out


def _participant_map(shapes) -> _Participants:
    parts = _Participants()
    for s in shapes:
        if s.kind == "task":
            for r in (s.node.label.init_role, s.node.label.noninit_role):
                parts.get(r)
    return parts


def _route(edge: Edge, by_id: dict, in_container: dict,
           channels: dict | None = None) -> list[tuple]:
    """Waypoints per edge kind. Conventions follow the user's hand-arranged
    reference (discovered_model_rearranged_v2): activities enter LEFT / exit
    RIGHT; gateways take off-row branches via TOP/BOTTOM ports; a loop's redo
    is entered by a vertical drop into its TOP (or its RIGHT when it is a
    single small task) and returns from its LEFT into the merge's BOTTOM."""
    s, t = by_id[edge.src], by_id[edge.tgt]

    def port_y(shape) -> float:
        off = shape.port_dy if shape.port_dy is not None else shape.h / 2
        return shape.y + off

    scx, scy = s.x + s.w / 2, port_y(s)
    tcx, tcy = t.x + t.w / 2, port_y(t)

    def _channel(base: float) -> float:
        """Allocate a distinct horizontal channel per back edge and container,
        so parallel return arcs never coincide."""
        if channels is None:
            return base + 25
        off = channels.get(edge.container, 25)
        channels[edge.container] = off + 20
        return base + off

    if edge.hint == "loop-enter":
        # split (above, right of body) → single-shape redo below.
        if t.kind == "task" and t.x + t.w < s.x:
            # small redo task: circular rework flow, enter on its RIGHT
            return [(scx, s.y + s.h), (scx, tcy), (t.x + t.w, tcy)]
        if t.x + 10 <= scx <= t.x + t.w - 10:
            # straight vertical drop into the redo's TOP (v2 convention)
            return [(scx, s.y + s.h), (scx, t.y)]
        # split not above the redo: dogleg in the channel above the redo
        ch_y = t.y - VGAP
        entry_x = min(max(scx, t.x + 30), t.x + t.w - 30)
        return [(scx, s.y + s.h), (scx, ch_y), (entry_x, ch_y), (entry_x, t.y)]

    if edge.hint == "loop-enter-multi":
        # multi-element redo: drop into the FIRST element's TOP via the channel
        # above the redo track (never sideways through its siblings).
        ch_y = t.y - VGAP
        return [(scx, s.y + s.h), (scx, ch_y), (tcx, ch_y), (tcx, t.y)]

    def _down_exit(below: float) -> list[tuple]:
        """Descend from the source into a below-channel. A gateway source exits
        via its RIGHT corner (its bottom port is reserved for incoming
        returns); anything else drops straight from its bottom."""
        if s.kind in ("xgw", "pgw"):
            dx = s.x + s.w + 15
            return [(s.x + s.w, scy), (dx, scy), (dx, below)]
        return [(scx, s.y + s.h), (scx, below)]

    if edge.hint == "loop-back-multi":
        # multi-element redo: leave the LAST element via the channel BELOW the
        # redo track, then up into the merge's BOTTOM.
        below = _channel(max(s.y + s.h, t.y + t.h))
        return _down_exit(below) + [(tcx, below), (tcx, t.y + t.h)]

    if edge.hint == "loop-back":
        # redo → merge: out the redo's LEFT, then up into the merge's BOTTOM.
        if t.x + t.w < s.x:
            return [(s.x, scy), (tcx, scy), (tcx, t.y + t.h)]
        # fallback: below everything, then up into merge bottom
        below = _channel(max(s.y + s.h, t.y + t.h))
        return [(scx, s.y + s.h), (scx, below), (tcx, below), (tcx, t.y + t.h)]

    if edge.hint == "gw-skip":
        # tau branch: bypass arc below everything between split and merge,
        # entering the merge's BOTTOM (never along the through-line row).
        lo, hi = s.x, t.x + t.w
        peers = in_container.get(edge.container, [])
        below = _channel(max((p.y + p.h for p in peers
                              if p.x < hi and p.x + p.w > lo),
                             default=max(s.y + s.h, t.y + t.h)))
        return _down_exit(below) + [(tcx, below), (tcx, t.y + t.h)]

    if edge.hint == "gw-out" and abs(scy - tcy) >= 2:
        # gateway → off-row branch: TOP/BOTTOM port, horizontal into branch LEFT
        port_y = s.y if tcy < scy else s.y + s.h
        return [(scx, port_y), (scx, tcy), (t.x, tcy)]

    if edge.hint == "gw-in" and abs(scy - tcy) >= 2:
        # off-row branch → gateway: branch RIGHT, into gateway TOP/BOTTOM port
        port_y = t.y if scy < tcy else t.y + t.h
        return [(s.x + s.w, scy), (tcx, scy), (tcx, port_y)]

    p0 = (s.x + s.w, scy)
    pn = (t.x, tcy)
    if t.x >= s.x + s.w - 1:  # forward
        if abs(p0[1] - pn[1]) < 2:
            return [p0, pn]
        mx = (p0[0] + pn[0]) / 2
        return [p0, (mx, p0[1]), (mx, pn[1]), pn]
    # generic back edge → drop below everything it spans in the same container
    lo, hi = min(t.x, s.x), max(t.x + t.w, s.x + s.w)
    peers = in_container.get(edge.container, [])
    below = _channel(max((p.y + p.h for p in peers
                          if p.x < hi and p.x + p.w > lo),
                         default=max(s.y + s.h, t.y + t.h)))
    if s.kind in ("xgw", "pgw"):
        # leave via the gateway's RIGHT corner: its bottom port is reserved for
        # incoming branch returns (avoids opposite-direction line sharing)
        dx = s.x + s.w + 15
        return [(s.x + s.w, scy), (dx, scy), (dx, below), (tcx, below), (tcx, t.y + t.h)]
    return [(scx, s.y + s.h), (scx, below), (tcx, below), (tcx, t.y + t.h)]


def build_bpmn(tree: TreeNode, side_index: SideIndex, *, include_di: bool = True) -> str:
    lay = _Layout()
    if tree.op == "×":
        # Root-level XOR: each entry on its own lane, its own start/end.
        shapes, edges = [], []
        y = 0.0
        for branch in tree.children:
            frag = lay.container(branch)
            _shift(frag, 0, y)
            shapes += frag.shapes
            edges += frag.edges
            y += frag.h + 3 * VGAP
    else:
        frag = lay.container(tree)
        shapes, edges = frag.shapes, frag.edges

    # translate to a positive margin
    for s in shapes:
        s.x += 100
        s.y += 100

    roles = _participant_map(shapes)

    # --- semantic XML ---
    defs = ET.Element(_b("definitions"),
                      {"id": "Definitions_discovered", "targetNamespace": "http://ocelchor/discovered"})
    choreo = ET.SubElement(defs, _b("choreography"), {"id": "Choreography_discovered"})

    # Build all elements first: same-role tasks/subs lazily create their
    # doppelgänger participants, which must exist before we declare participants.
    elmap: dict[str, ET.Element] = {}
    for s in shapes:
        elmap[s.id] = _make_element(s, roles)

    for pid, role in roles.declared():
        ET.SubElement(choreo, _b("participant"), {"id": pid, "name": role})

    by_container: dict[str | None, list] = {}
    for s in shapes:
        by_container.setdefault(s.container, []).append(s)

    def attach(cid, parent):
        for s in sorted(by_container.get(cid, []), key=lambda s: s.x):
            parent.append(elmap[s.id])
            if s.kind == "scope":
                attach(s.id, elmap[s.id])

    attach(None, choreo)
    for e in edges:
        parent = choreo if e.container is None else elmap[e.container]
        ET.SubElement(parent, _b("sequenceFlow"),
                      {"id": e.id, "sourceRef": e.src, "targetRef": e.tgt})

    if include_di:
        _emit_di(defs, choreo, shapes, edges, roles)

    ET.indent(defs)
    return ET.tostring(defs, encoding="unicode", xml_declaration=True)


def _make_element(s: Shape, roles: dict) -> ET.Element:
    if s.kind == "start":
        return ET.Element(_b("startEvent"), {"id": s.id})
    if s.kind == "end":
        return ET.Element(_b("endEvent"), {"id": s.id})
    if s.kind == "xgw":
        return ET.Element(_b("exclusiveGateway"), {"id": s.id})
    if s.kind == "pgw":
        return ET.Element(_b("parallelGateway"), {"id": s.id})
    if s.kind == "task":
        tt = s.node.label
        el = ET.Element(_b("choreographyTask"),
                        {"id": s.id, "name": tt.exec_type,
                         "initiatingParticipantRef": roles.get(tt.init_role)})
        ET.SubElement(el, _b("participantRef")).text = roles.get(tt.init_role)
        # Same-role interaction → doppelgänger for the non-initiating side.
        noninit = (roles.alt(tt.noninit_role) if tt.noninit_role == tt.init_role
                   else roles.get(tt.noninit_role))
        ET.SubElement(el, _b("participantRef")).text = noninit
        ET.SubElement(el, _b("documentation")).text = tt.exec_type
        if s.loop:
            # Choreography activities mark loops via the loopType attribute
            # (BPMN 11.5.3); standardLoopCharacteristics is process-only and
            # chor-js ignores it.
            el.set("loopType", "Standard")
        return el
    # scope
    node = s.node
    el = ET.Element(_b("subChoreography"),
                    {"id": s.id, "name": scope_display_name(node.label),
                     "initiatingParticipantRef": roles.get(node.label.opener.init_role)})
    band_roles = _band_roles(node)
    refs = [roles.get(r) for r in band_roles]
    if len(refs) == 1:  # all interactions inside share one role → need a 2nd band
        refs.append(roles.alt(band_roles[0]))
    for ref in refs:
        ET.SubElement(el, _b("participantRef")).text = ref
    if s.loop:
        el.set("loopType", "Standard")
    return el


def _add_shape(plane, sid, ref, xywh, **extra):
    sh = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNShape", {"id": sid, "bpmnElement": ref, **extra})
    x, y, w, h = xywh
    ET.SubElement(sh, f"{{{DC}}}Bounds",
                  {"x": f"{x:.0f}", "y": f"{y:.0f}", "width": f"{w:.0f}", "height": f"{h:.0f}"})


def _emit_bands(plane, s: Shape, roles: "_Participants"):
    x, y, w, h = s.x, s.y, s.w, s.h
    if s.kind == "task":
        tt = s.node.label
        noninit = (roles.alt(tt.noninit_role) if tt.noninit_role == tt.init_role
                   else roles.get(tt.noninit_role))
        _add_shape(plane, f"{s.id}_top", roles.get(tt.init_role), (x, y, w, BAND_H),
                   participantBandKind="top_initiating", isMessageVisible="false",
                   choreographyActivityShape=f"{s.id}_di")
        _add_shape(plane, f"{s.id}_bot", noninit, (x, y + h - BAND_H, w, BAND_H),
                   participantBandKind="bottom_non_initiating", isMessageVisible="false",
                   choreographyActivityShape=f"{s.id}_di")
        return
    band_roles = _band_roles(s.node)
    ordered = [roles.get(r) for r in band_roles]
    if len(ordered) == 1:  # mirror the doppelgänger ref of _make_element
        ordered.append(roles.alt(band_roles[0]))
    top, bot = ordered[0::2], ordered[1::2]
    for i, p in enumerate(top):
        kind = "top_initiating" if i == 0 else "middle_non_initiating"
        _add_shape(plane, f"{s.id}_t{i}", p, (x, y + i * BAND_H, w, BAND_H),
                   participantBandKind=kind, isMessageVisible="false",
                   choreographyActivityShape=f"{s.id}_di")
    for j, p in enumerate(bot):
        kind = "bottom_non_initiating" if j == 0 else "middle_non_initiating"
        _add_shape(plane, f"{s.id}_b{j}", p, (x, y + h - (j + 1) * BAND_H, w, BAND_H),
                   participantBandKind=kind, isMessageVisible="false",
                   choreographyActivityShape=f"{s.id}_di")


def _emit_di(defs, choreo, shapes, edges, roles: "_Participants"):
    diagram = ET.SubElement(defs, f"{{{BPMNDI}}}BPMNDiagram", {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI}}}BPMNPlane",
                          {"id": "BPMNPlane_1", "bpmnElement": choreo.get("id")})
    for s in shapes:
        extra = {}
        if s.kind == "scope":
            extra["isExpanded"] = "true"
        elif s.kind == "xgw":
            extra["isMarkerVisible"] = "true"  # render the X marker on XOR gateways
        _add_shape(plane, f"{s.id}_di", s.id, (s.x, s.y, s.w, s.h), **extra)
        if s.kind in ("task", "scope"):
            _emit_bands(plane, s, roles)
    by_id = {s.id: s for s in shapes}
    in_container: dict = {}
    for s in shapes:
        in_container.setdefault(s.container, []).append(s)
    channels: dict = {}  # container id → next back-edge channel offset
    for e in edges:
        pts = _route(e, by_id, in_container, channels)
        edge = ET.SubElement(plane, f"{{{BPMNDI}}}BPMNEdge",
                             {"id": f"{e.id}_di", "bpmnElement": e.id})
        for px, py in pts:
            ET.SubElement(edge, f"{{{DI}}}waypoint", {"x": f"{px:.0f}", "y": f"{py:.0f}"})
