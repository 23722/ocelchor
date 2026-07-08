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
ET.register_namespace("bpmn2", BPMN)

_REQUEST = "Request "
_RESPOND = "Respond to "


def _b(tag: str) -> str:
    return f"{{{BPMN}}}{tag}"


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
        body = node.children[0]
        # Single-element body (task or data-encoded subChoreography) → loop marker.
        if body.op in ("NS",) or (body.op is None and isinstance(body.label, TaskType)):
            e, x = self._emit_flow(parent, body)
            # find the emitted element and attach standardLoopCharacteristics
            el = _find_by_id(parent, e)
            ET.SubElement(el, _b("standardLoopCharacteristics"))
            return e, x
        # Multi-element body → exclusive gateways with a back edge (rework pattern).
        merge = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("LoopJoin")})
        e, x = self._emit_flow(parent, body)
        split = ET.SubElement(parent, _b("exclusiveGateway"), {"id": self._uid("LoopSplit")})
        self._seq(parent, merge.get("id"), e)
        self._seq(parent, x, split.get("id"))
        self._seq(parent, split.get("id"), merge.get("id"))  # back edge
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

        # Root-level XOR → N unlabeled start events (alternative instantiation).
        if self.tree.op == "×":
            end = ET.SubElement(choreo, _b("endEvent"), {"id": self._uid("End")})
            for branch in self.tree.children:
                start = ET.SubElement(choreo, _b("startEvent"), {"id": self._uid("Start")})
                e, x = self._emit_flow(choreo, branch)
                if e is None:
                    self._seq(choreo, start.get("id"), end.get("id"))
                else:
                    self._seq(choreo, start.get("id"), e)
                    self._seq(choreo, x, end.get("id"))
        else:
            self._emit_container(choreo, self.tree)
        return defs


def to_bpmn(tree: TreeNode, side_index: SideIndex) -> str:
    root = _Exporter(tree, side_index).build()
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _find_by_id(parent: ET.Element, eid: str) -> ET.Element:
    for el in parent.iter():
        if el.get("id") == eid:
            return el
    raise KeyError(eid)


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
            loop = any(c.tag == _b("standardLoopCharacteristics") for c in el)
            return ("task", el.get("name"), bands(el), loop)
        if tag == "subChoreography":
            loop = any(c.tag == _b("standardLoopCharacteristics") for c in el)
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
