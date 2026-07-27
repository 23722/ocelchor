"""Diagnostics D1–D13 (spec B8, regrouped 2026-07-10) → `diagnostics.json`.

Four groups following the argument arc *trust the data → trust the typing →
trust the control flow → read the findings*:

  I   D1–D4   encoding & data trust        (validates the interface contract)
  II  D5–D8   typing & generalization      (quantifies the typing decisions)
  III D9–D11  control-flow trust           (IM fallthrough audit; signature-
              based on tree + buckets — no pm4py internals hooked)
  IV  D12–D13 process findings             (recursion case study + contrast)

Diagnostics NEVER change the model. Everything here is computed from the
loaded model, the discovery result, and a recomputed projection — all
deterministic, all plain OCEL-level constructs (no domain knowledge).
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from ocelchormodel_rad import __version__
from ocelchormodel_rad.discover import Discovery, TreeNode, project
from ocelchormodel_rad.layout import message_label
from ocelchormodel_rad.reader import Model, order_key
from ocelchormodel_rad.typing import ScopeType, TaskType, scope_certified, task_type

_REQUEST = "Request "
_RESPOND = "Respond to "
MAX_EXAMPLES = 5


# ---------------------------------------------------------------------------
# execType helpers (I1 format: [kind prefix +] activity " [" discriminator "]")
# ---------------------------------------------------------------------------

def _strip_kind(exec_type: str) -> str:
    for pfx in (_REQUEST, _RESPOND):
        if exec_type.startswith(pfx):
            return exec_type[len(pfx):]
    return exec_type


def _bare_name(exec_type: str) -> str:
    """Activity name without kind prefix and without the discriminator suffix."""
    t = _strip_kind(exec_type)
    if t.endswith("]") and " [" in t:
        return t.rsplit(" [", 1)[0]
    return t


def _discriminator(exec_type: str) -> str | None:
    """The ` [X]` suffix content, or None for undiscriminated types (e.g. XES)."""
    t = _strip_kind(exec_type)
    if t.endswith("]") and " [" in t:
        return t.rsplit(" [", 1)[1][:-1]
    return None


# ---------------------------------------------------------------------------
# tree walkers
# ---------------------------------------------------------------------------

def _walk_with_context(tree: TreeNode):
    """Yield (node, context) for every node; context = tuple of enclosing
    ScopeTypes (the bucket key of the node's discovery sublog)."""
    def rec(node: TreeNode, ctx: tuple):
        yield node, ctx
        child_ctx = ctx + (node.label,) if node.op == "NS" else ctx
        for c in node.children:
            yield from rec(c, child_ctx)
    yield from rec(tree, ())


def _leaf_task_types(node: TreeNode) -> set[TaskType]:
    out: set[TaskType] = set()
    if node.op is None and isinstance(node.label, TaskType):
        out.add(node.label)
    for c in node.children:
        out |= _leaf_task_types(c)
    return out


def _branch_alphabet(node: TreeNode) -> set:
    """Bucket-level symbols of a subtree: leaf TaskTypes plus NS ScopeTypes.
    Does NOT descend into NS children — those belong to child buckets."""
    if node.op == "NS":
        return {node.label}
    if node.op is None:
        return {node.label} if isinstance(node.label, TaskType) else set()
    out: set = set()
    for c in node.children:
        out |= _branch_alphabet(c)
    return out


def _first_initiating_role(node: TreeNode) -> str | None:
    """Initiating role of a branch's first element (D11)."""
    if node.op is None:
        return node.label.init_role if isinstance(node.label, TaskType) else None
    if node.op == "NS":
        return node.label.init_role
    for c in node.children:
        role = _first_initiating_role(c)
        if role is not None:
            return role
    return None


def _sym_name(sym) -> str:
    return sym.label if isinstance(sym, ScopeType) else sym.exec_type


# ---------------------------------------------------------------------------
# Group I — encoding & data trust
# ---------------------------------------------------------------------------

def _d01_ordering(model: Model) -> dict:
    ties = 0
    examples = []
    for inst in model.instances:
        seen: dict = {}
        for e in model.events_of_instance(inst):
            k = order_key(e)
            if k in seen:
                ties += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append({"instance": inst, "events": [seen[k], e.id]})
            seen[k] = e.id
    return {"residual_ties": ties, "examples": examples, "passed": ties == 0}


def _d02_scope_openers(model: Model) -> dict:
    """Certification of the role/label derivation: the scope's first task
    event should be its request bracket (branch-invariant). Applies on both
    label rungs — a stored name does not exempt the roles (spec §B2.3)."""
    bad = [s for s in model.scopes if not scope_certified(model, s)]
    return {"non_request_openers": len(bad), "examples": bad[:MAX_EXAMPLES]}


def _d03_bracket_completeness(model: Model) -> dict:
    expected, unexpected = [], []
    for s in model.scopes:
        # a scope's own closing bracket is DIRECTLY contained in it (I3)
        kinds = {model.kind(e) for e in model.direct_events(s)}
        if "response" not in kinds:
            (expected if model.scope_parent.get(s) is None else unexpected).append(s)
    return {
        "expected_missing_response": len(expected),   # root-scope asymmetry
        "unexpected_missing_response": len(unexpected),
        "unexpected_examples": unexpected[:MAX_EXAMPLES],
    }


def _d04_identity_labels(model: Model) -> dict:
    hits = {}
    for e in model.events.values():
        disc = _discriminator(e.type)
        if disc is not None and disc in model.objtype:
            hits.setdefault(e.type, 0)
            hits[e.type] += 1
    return {
        "exec_types": len(hits),
        "occurrences": sum(hits.values()),
        "examples": sorted(hits)[:MAX_EXAMPLES],
    }


# ---------------------------------------------------------------------------
# Group II — typing & generalization
# ---------------------------------------------------------------------------

def _d05_event_type_fanout(model: Model) -> list[dict]:
    by_name: dict[str, set[str]] = defaultdict(set)
    for e in model.events.values():
        by_name[_bare_name(e.type)].add(_strip_kind(e.type))
    return [
        {"name": n, "exec_types": len(ts), "examples": sorted(ts)[:MAX_EXAMPLES]}
        for n, ts in sorted(by_name.items()) if len(ts) > 1
    ]


def _d06_task_type_fanout(tree: TreeNode) -> list[dict]:
    by_exec: dict[str, set[tuple]] = defaultdict(set)
    for tt in _leaf_task_types(tree):
        by_exec[tt.exec_type].add((tt.init_role, tt.noninit_role))
    return [
        {"exec_type": x, "role_pairs": sorted(map(list, rp))}
        for x, rp in sorted(by_exec.items()) if len(rp) > 1
    ]


def _d07_scope_pooling(buckets: dict) -> dict:
    entries = []
    for key, subs in buckets.items():
        if not key:
            continue  # instance level
        variants = len({tuple(s) for s in subs})
        entries.append({
            "context": [st.label for st in key],
            "occurrences": len(subs),
            "variants": variants,
            "pooling_ratio": round(len(subs) / variants, 2),
        })
    entries.sort(key=lambda e: -e["pooling_ratio"])
    pooled = [e for e in entries if e["occurrences"] > e["variants"]]
    return {
        "buckets": len(entries),
        "total_scope_occurrences": sum(e["occurrences"] for e in entries),
        "buckets_with_pooling": len(pooled),
        "top": entries[:MAX_EXAMPLES],
    }


def _d08_message_merging(discovery: Discovery) -> list[dict]:
    out = []
    for key, entry in discovery.side_index.items():
        if not isinstance(key, TaskType):
            continue
        for direction in ("forward", "backward"):
            entries = entry.messages.get(direction) or []
            if not entries:
                continue
            _label, conflict = message_label(entries, direction)
            if not conflict:
                continue
            keysets = sorted({tuple(k for k in e["attrs"] if k) for e in entries})
            kinds = sorted({e["type"] for e in entries})
            cause = "payload-structures" if len(keysets) > 1 else "kinds"
            out.append({
                "exec_type": key.exec_type,
                "roles": [key.init_role, key.noninit_role],
                "direction": direction,
                "cause": cause,
                "structures": [list(k) for k in keysets][:MAX_EXAMPLES],
                "kinds": kinds[:MAX_EXAMPLES],
            })
    return out


# ---------------------------------------------------------------------------
# Group III — control-flow trust (IM fallthrough audit, signature-based)
# ---------------------------------------------------------------------------

def _witnesses(subs: list, alpha_a: set, alpha_b: set) -> tuple[int, int]:
    """Subtraces witnessing some a∈A before some b∈B, and vice versa
    (ANY-occurrence semantics)."""
    ab = ba = 0
    for sub in subs:
        pos_a = [i for i, s in enumerate(sub) if s in alpha_a]
        pos_b = [i for i, s in enumerate(sub) if s in alpha_b]
        if not pos_a or not pos_b:
            continue
        if min(pos_a) < max(pos_b):
            ab += 1
        if min(pos_b) < max(pos_a):
            ba += 1
    return ab, ba


def _d09_parallelism_witnesses(tree: TreeNode, buckets: dict) -> list[dict]:
    out = []
    for node, ctx in _walk_with_context(tree):
        if node.op != "∧":
            continue
        subs = buckets.get(ctx, [])
        alphabets = [_branch_alphabet(c) for c in node.children]
        pairs = []
        flagged = 0
        for i, j in combinations(range(len(alphabets)), 2):
            if not alphabets[i] or not alphabets[j]:
                continue  # tau branch
            ab, ba = _witnesses(subs, alphabets[i], alphabets[j])
            flag = ab == 0 or ba == 0
            flagged += flag
            pairs.append({
                "a": sorted(_sym_name(s) for s in alphabets[i])[:3],
                "b": sorted(_sym_name(s) for s in alphabets[j])[:3],
                "a_before_b": ab, "b_before_a": ba, "flagged": flag,
            })
        verdict = ("witnessed" if flagged == 0
                   else "unwitnessed" if flagged == len(pairs)
                   else "partially_witnessed")
        out.append({
            "context": [st.label for st in ctx],
            "branches": len(node.children),
            "subtraces": len(subs),
            "verdict": verdict,
            "flagged_pairs": flagged,
            "pairs": pairs,
        })
    return out


def _d10_unrestricted_repetition(tree: TreeNode) -> list[dict]:
    out = []
    for node, ctx in _walk_with_context(tree):
        if node.op != "↻" or not node.children:
            continue
        body = node.children[0]
        if body.op is None and body.label is None:  # τ body → strict-tau-loop/flower
            redo_alpha: set = set()
            for redo in node.children[1:]:
                redo_alpha |= _branch_alphabet(redo)
            out.append({
                "context": [st.label for st in ctx],
                "redo_alphabet": sorted(
                    _sym_name(s) for s in redo_alpha)[:MAX_EXAMPLES],
            })
    return out


def _d11_choice_realizability(tree: TreeNode) -> list[dict]:
    out = []
    for node, ctx in _walk_with_context(tree):
        if node.op != "×" or node is tree:  # root × = instantiation, no decision
            continue
        roles = {}
        for c in node.children:
            role = _first_initiating_role(c)
            if role is not None:
                roles.setdefault(role, 0)
                roles[role] += 1
        if len(roles) > 1:
            out.append({
                "context": [st.label for st in ctx],
                "branch_initiating_roles": sorted(roles),
            })
    return out


# ---------------------------------------------------------------------------
# Group IV — process findings
# ---------------------------------------------------------------------------

def _d12_recursion(discovery: Discovery) -> dict:
    findings = [{
        "label": f.label,
        "noninit_role": f.noninit_role,
        "context_path": list(f.context_path),
        "first_depth": f.first_depth,
        "recurrence_depth": f.recurrence_depth,
        "direct": f.direct,
    } for f in discovery.recursion]
    return {
        "findings": findings,
        "direct": sum(1 for f in discovery.recursion if f.direct),
        "indirect": sum(1 for f in discovery.recursion if not f.direct),
        "max_depth_delta": max(
            (f.recurrence_depth - f.first_depth for f in discovery.recursion),
            default=0),
    }


def _d13_cross_depth_participants(model: Model) -> dict:
    # concrete participants + their taskTypes per scope (direct events only)
    per_scope: dict[str, dict[str, set]] = {}
    for s in model.scopes:
        d: dict[str, set] = defaultdict(set)
        for e in model.direct_events(s):
            tt = task_type(model, e)
            for obj in (e.initiator, e.participant):
                if obj is not None:
                    d[obj].add(tt)
        per_scope[s] = d

    def descendants(s: str):
        for c in model.scope_contains.get(s, []):
            yield c
            yield from descendants(c)

    count = 0
    examples = []
    for s in model.scopes:
        for dsc in descendants(s):
            # sorted: set-intersection order is hash-seed dependent, and the
            # bounded examples must be deterministic across runs
            for obj in sorted(per_scope[s].keys() & per_scope[dsc].keys()):
                if per_scope[s][obj] != per_scope[dsc][obj]:
                    count += 1
                    if len(examples) < MAX_EXAMPLES:
                        examples.append({
                            "object": obj,
                            "ancestor_scope": s,
                            "descendant_scope": dsc,
                            "ancestor_task_types": sorted(
                                t.exec_type for t in per_scope[s][obj]),
                            "descendant_task_types": sorted(
                                t.exec_type for t in per_scope[dsc][obj]),
                        })
    return {"pairs": count, "examples": examples}


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def compute_diagnostics(model: Model, discovery: Discovery,
                        log_name: str = "") -> dict:
    buckets, _side = project(model)
    return {
        "log": log_name,
        "generated_by": f"ocelchormodel-rad {__version__}",
        # Reaching here implies the gates held. C3 is gated by shape: events
        # with an *unrecorded* receiver (|noninit| = 0) are tolerated — typed
        # with the reserved empty role, reported here, never repaired.
        "hard_gates": {
            "passed": True,
            "tolerated_missing_receiver_events": model.missing_receiver_events,
        },
        "constraints": {
            cid: {"checked": r.elements_checked, "violations": r.num_violations}
            for cid, r in sorted(model.constraints.items())
        },
        "d01_ordering_determinism": _d01_ordering(model),
        "d02_scope_openers": _d02_scope_openers(model),
        "d03_bracket_completeness": _d03_bracket_completeness(model),
        "d04_identity_labels": _d04_identity_labels(model),
        "d05_event_type_fanout": _d05_event_type_fanout(model),
        "d06_task_type_fanout": _d06_task_type_fanout(discovery.tree),
        "d07_scope_pooling": _d07_scope_pooling(buckets),
        "d08_message_merging": _d08_message_merging(discovery),
        "d09_parallelism_witnesses": _d09_parallelism_witnesses(
            discovery.tree, buckets),
        "d10_unrestricted_repetition": _d10_unrestricted_repetition(discovery.tree),
        "d11_choice_realizability": _d11_choice_realizability(discovery.tree),
        "d12_recursion": _d12_recursion(discovery),
        "d13_cross_depth_participants": _d13_cross_depth_participants(model),
    }
