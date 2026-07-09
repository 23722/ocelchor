"""Discovery: projection → per-bucket Inductive Miner → post-order composition.

Spec §B4 and the worked example (README). Discovery is projection followed by
stock pm4py IM per sublog and a post-order composition — no IM internals are
hooked, no RAD code is ported, no recursion collapse. Recursion is detection
only (D5); each observed nesting depth is discovered from its own bucket, so the
model is the bounded unfolding, exactly as deep as the data.

Key structures (spec §B9):
  - TreeNode: '→' '×' '↻' '∧' operators; 'NS' named subtree (scope); None = leaf.
  - SideIndex: (TaskType | ScopeType) → {messages by direction, provenance};
    built during projection, consumed only by the exporter.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from pm4py.algo.discovery.inductive import algorithm as im
from pm4py.objects.log.obj import Event as PMEvent
from pm4py.objects.log.obj import EventLog, Trace as PMTrace
from pm4py.objects.process_tree.obj import Operator

from ocelchormodel_rad.hierarchy import scope_path
from ocelchormodel_rad.reader import Event, Model, order_key
from ocelchormodel_rad.typing import ScopeType, TaskType, scope_type, task_type

Symbol = TaskType | ScopeType
BucketKey = tuple[ScopeType, ...]  # context path root→scope; () = instance level


# ---------------------------------------------------------------------------
# Output structures
# ---------------------------------------------------------------------------

@dataclass
class TreeNode:
    """Process-tree / choreography-tree node (spec §B9).

    op ∈ {'→','×','↻','∧'} for control-flow operators, 'NS' for a named subtree
    (data-encoded scope; children == [body]), or None for a leaf. A leaf with a
    TaskType label is a choreography task; a leaf with label None is a silent
    tau. After composition no bare ScopeType leaf remains — each is wrapped 'NS'.
    """

    op: str | None
    label: Symbol | None
    children: list["TreeNode"] = field(default_factory=list)

    def is_tau(self) -> bool:
        return self.op is None and self.label is None


@dataclass
class SideEntry:
    # direction ('forward' = init→noninit, 'backward' = noninit→init) → [msg attr dicts]
    messages: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))
    provenance: list[dict] = field(default_factory=list)


class SideIndex(dict):
    """(TaskType | ScopeType) → SideEntry."""

    def entry(self, key: Symbol) -> SideEntry:
        if key not in self:
            self[key] = SideEntry()
        return self[key]


@dataclass
class RecursionFinding:
    """One D5 recursion finding: an execType reappearing on its own path."""

    exec_type: str
    context_path: tuple[str, ...]  # scopeType execTypes root→scope
    first_depth: int
    recurrence_depth: int
    direct: bool


# ---------------------------------------------------------------------------
# Projection (spec §B4.1 / worked-example step 2)
# ---------------------------------------------------------------------------

def _message_lookup(model: Model) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for o in model.ocel["objects"]:
        src = tgt = None
        for r in o.get("relationships", []):
            if r["qualifier"] == "choreo:source":
                src = r["objectId"]
            elif r["qualifier"] == "choreo:target":
                tgt = r["objectId"]
        if src is not None or tgt is not None:
            attrs = {a["name"]: a["value"] for a in o.get("attributes", [])}
            out[o["id"]] = {"source": src, "target": tgt, "attributes": attrs,
                            "type": o.get("type", "")}
    return out


def _index_event(model: Model, e: Event, msgs: dict[str, dict], side: SideIndex) -> None:
    tt = task_type(model, e)
    entry = side.entry(tt)
    for mid in e.message_ids:
        m = msgs.get(mid)
        if m is None:
            continue
        if m["source"] == e.initiator and m["target"] == e.participant:
            direction = "forward"  # init → noninit
        elif m["source"] == e.participant and m["target"] == e.initiator:
            direction = "backward"  # noninit → init
        else:
            direction = "other"
        entry.messages[direction].append(
            {"attrs": m["attributes"], "type": m["type"]})
    entry.provenance.append({
        "event_id": e.id,
        "instance_id": e.instance_id,
        "init": e.initiator,
        "noninit": e.participant,
    })


def _scope_min_key(model: Model, scope_id: str):
    return min(order_key(e) for e in model.all_events(scope_id))


def _subtrace_for_scope(model: Model, scope_id: str, side: SideIndex) -> list[Symbol]:
    """Direct children of a scope in ≻ order: events → taskType, child scopes → scopeType."""
    items: list[tuple] = []
    for e in model.direct_events(scope_id):
        items.append((order_key(e), task_type(model, e)))
    for child in model.scope_contains.get(scope_id, []):
        items.append((_scope_min_key(model, child), scope_type(model, child)))
    items.sort(key=lambda x: x[0])
    return [sym for _, sym in items]


def _subtrace_for_instance(model: Model, inst: str, side: SideIndex) -> list[Symbol]:
    """Top-level children of an instance: direct (unscoped) events + its root scopes."""
    items: list[tuple] = []
    for e in model.events.values():
        if e.instance_id == inst and e.scope_id is None:
            items.append((order_key(e), task_type(model, e)))
    for s in model.scopes:
        if model.scope_parent.get(s) is None and _scope_min_key(model, s):
            # a root scope belongs to inst iff its events do
            ev = model.all_events(s)
            if ev and ev[0].instance_id == inst:
                items.append((_scope_min_key(model, s), scope_type(model, s)))
    items.sort(key=lambda x: x[0])
    return [sym for _, sym in items]


def project(model: Model) -> tuple[dict[BucketKey, list[list[Symbol]]], SideIndex]:
    """Bucket subtraces by context path (spec §B4.1) and build the side index."""
    buckets: dict[BucketKey, list[list[Symbol]]] = defaultdict(list)
    side = SideIndex()

    # Side index: every event contributes messages + provenance to its taskType.
    msgs = _message_lookup(model)
    for e in model.events.values():
        _index_event(model, e, msgs, side)

    # Instance level (empty context key ε).
    for inst in model.instances:
        buckets[()].append(_subtrace_for_instance(model, inst, side))

    # One subtrace per scope object, filed under the scope's context path.
    for scope_id in model.scopes:
        key: BucketKey = tuple(scope_type(model, s) for s in scope_path(model, scope_id))
        buckets[key].append(_subtrace_for_scope(model, scope_id, side))
        # scope-type provenance
        opener = model.all_events(scope_id)
        opener = min(opener, key=order_key)
        side.entry(scope_type(model, scope_id)).provenance.append({
            "scope_id": scope_id,
            "instance_id": opener.instance_id,
            "init": opener.initiator,
            "noninit": opener.participant,
        })

    return buckets, side


# ---------------------------------------------------------------------------
# Per-bucket Inductive Miner (basic variant, no noise filtering — spec §B4)
# ---------------------------------------------------------------------------

_OP = {
    Operator.SEQUENCE: "→",
    Operator.XOR: "×",
    Operator.PARALLEL: "∧",
    Operator.LOOP: "↻",
}


def _mine_bucket(subtraces: list[list[Symbol]]) -> TreeNode:
    """Run stock pm4py IM over one bucket and convert the tree to a TreeNode."""
    label_of: dict[Symbol, str] = {}
    symbol_of: dict[str, Symbol] = {}
    log = EventLog()
    for sub in subtraces:
        tr = PMTrace()
        for sym in sub:
            lab = label_of.get(sym)
            if lab is None:
                lab = f"L{len(label_of)}"
                label_of[sym] = lab
                symbol_of[lab] = sym
            ev = PMEvent()
            ev["concept:name"] = lab
            tr.append(ev)
        log.append(tr)

    pt = im.apply(log, variant=im.Variants.IM)
    return _convert(pt, symbol_of)


def _convert(pt, symbol_of: dict[str, Symbol]) -> TreeNode:
    if pt.operator is None:
        if pt.label is None:
            return TreeNode(None, None, [])  # tau
        return TreeNode(None, symbol_of[pt.label], [])
    return TreeNode(_OP[pt.operator], None, [_convert(c, symbol_of) for c in pt.children])


def _collect_and(node: TreeNode, acc: list) -> None:
    """Collect every ∧ node of the composed tree for diagnostic D6
    (spec B4: the model is never changed — diagnostics report).
    Note the B4 correction: pm4py's fallthroughs (ActivityOncePerTrace) can
    emit ∧ even for a single totally ordered subtrace with non-adjacent
    repeats — D6 distinguishes witnessed parallelism from such artifacts."""
    if node.op == "∧":
        acc.append(node)
    for c in node.children:
        _collect_and(c, acc)


# ---------------------------------------------------------------------------
# Post-order composition (spec §B4.2 / worked-example step 4)
# ---------------------------------------------------------------------------

def _compose(buckets: dict[BucketKey, list[list[Symbol]]]) -> TreeNode:
    mined: dict[BucketKey, TreeNode] = {
        key: _mine_bucket(subs) for key, subs in buckets.items()
    }
    memo: dict[BucketKey, TreeNode] = {}

    def expand(key: BucketKey) -> TreeNode:
        if key in memo:
            return memo[key]
        result = _substitute(mined[key], key)
        memo[key] = result
        return result

    def _substitute(node: TreeNode, key: BucketKey) -> TreeNode:
        if node.op is None and isinstance(node.label, ScopeType):
            child_key = key + (node.label,)
            body = expand(child_key)
            return TreeNode("NS", node.label, [body])
        if node.op is None:
            return node  # task leaf or tau
        return TreeNode(node.op, node.label, [_substitute(c, key) for c in node.children])

    return expand(())


# ---------------------------------------------------------------------------
# Recursion detection (D5) — execType component on its own containment path
# ---------------------------------------------------------------------------

def detect_recursion(buckets: dict[BucketKey, list[list[Symbol]]]) -> list[RecursionFinding]:
    """A scopeType's execType reappearing on its own containment path (spec §B4).

    Uses the execType component (not the full ScopeType tuple) to match the
    audit: re-entrant frames typically have a different initiator than the outer
    frame, so full-tuple equality would miss exactly the case that matters.
    Detection is diagnostic-only; it never changes discovery.
    """
    findings: list[RecursionFinding] = []
    seen: set[tuple] = set()
    for key in buckets:
        if not key:
            continue
        execs = tuple(st.opener.exec_type for st in key)
        first: dict[str, int] = {}
        for depth, et in enumerate(execs):
            if et in first:
                # Record every recurrence (measured from the earliest occurrence),
                # so both direct (depth == first+1) and indirect repeats survive.
                sig = (et, execs, first[et], depth)
                if sig not in seen:
                    seen.add(sig)
                    findings.append(RecursionFinding(
                        exec_type=et,
                        context_path=execs,
                        first_depth=first[et],
                        recurrence_depth=depth,
                        direct=(depth == first[et] + 1),
                    ))
            else:
                first[et] = depth
    return findings


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

@dataclass
class Discovery:
    tree: TreeNode
    side_index: SideIndex
    recursion: list[RecursionFinding]
    # every ∧ node of the tree — audited by diagnostic D6 (witnessed
    # orderings vs. fallthrough artifact); the model is never changed
    and_nodes: list[TreeNode] = field(default_factory=list)


def discover(model: Model) -> Discovery:
    buckets, side = project(model)
    tree = _compose(buckets)
    recursion = detect_recursion(buckets)
    and_nodes: list[TreeNode] = []
    _collect_and(tree, and_nodes)
    return Discovery(tree=tree, side_index=side, recursion=recursion,
                     and_nodes=and_nodes)
