"""Constraint checks C0–C16 for OCEL 2.0 choreography logs."""

from __future__ import annotations

from dataclasses import dataclass, field

from ocelchorvalidator.index import OcelIndex


@dataclass
class Violation:
    """A single constraint violation."""

    constraint: str  # "C0", "C1", ..., "C15"
    message: str
    event_id: str | None = None
    object_id: str | None = None


@dataclass
class ConstraintResult:
    """Result of checking one constraint."""

    constraint_id: str
    elements_checked: int
    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    @property
    def num_violations(self) -> int:
        return len(self.violations)


# ---------------------------------------------------------------------------
# Helper: extract relations by qualifier
# ---------------------------------------------------------------------------

def _e2o_by_qualifier(idx: OcelIndex, event_id: str, qualifier: str) -> list[str]:
    """Return object IDs linked to event_id with the given qualifier."""
    return [oid for oid, q in idx.e2o.get(event_id, []) if q == qualifier]


def _o2o_by_qualifier(idx: OcelIndex, object_id: str, qualifier: str) -> list[str]:
    """Return target object IDs linked from object_id with the given qualifier."""
    return [oid for oid, q in idx.o2o.get(object_id, []) if q == qualifier]


# ---------------------------------------------------------------------------
# C0 — Instance linking
# ---------------------------------------------------------------------------

def check_c0(idx: OcelIndex) -> ConstraintResult:
    """Every choreography event has exactly one choreo:instance relation."""
    violations: list[Violation] = []
    for eid in idx.events:
        instances = _e2o_by_qualifier(idx, eid, "choreo:instance")
        if len(instances) != 1:
            violations.append(Violation(
                constraint="C0",
                message=f"Event has {len(instances)} choreo:instance relations (expected 1)",
                event_id=eid,
            ))
    return ConstraintResult("C0", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C1 — Message participation
# ---------------------------------------------------------------------------

def check_c1(idx: OcelIndex) -> ConstraintResult:
    """Message source/target must be initiator or participant of the same event."""
    violations: list[Violation] = []
    checked = 0
    for eid in idx.events:
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        initiators = set(_e2o_by_qualifier(idx, eid, "choreo:initiator"))
        participants = set(_e2o_by_qualifier(idx, eid, "choreo:participant"))
        roles = initiators | participants
        for mid in messages:
            checked += 1
            sources = _o2o_by_qualifier(idx, mid, "choreo:source")
            for src in sources:
                if src not in roles:
                    violations.append(Violation(
                        constraint="C1",
                        message=f"Message source {src} is not initiator or participant of event",
                        event_id=eid,
                        object_id=mid,
                    ))
            targets = _o2o_by_qualifier(idx, mid, "choreo:target")
            for tgt in targets:
                if tgt not in roles:
                    violations.append(Violation(
                        constraint="C1",
                        message=f"Message target {tgt} is not initiator or participant of event",
                        event_id=eid,
                        object_id=mid,
                    ))
    return ConstraintResult("C1", checked, violations)


# ---------------------------------------------------------------------------
# C2 — Single initiator
# ---------------------------------------------------------------------------

def check_c2(idx: OcelIndex) -> ConstraintResult:
    """Each choreography event has exactly one choreo:initiator relation."""
    violations: list[Violation] = []
    for eid in idx.events:
        initiators = _e2o_by_qualifier(idx, eid, "choreo:initiator")
        if len(initiators) != 1:
            violations.append(Violation(
                constraint="C2",
                message=f"Event has {len(initiators)} choreo:initiator relations (expected 1)",
                event_id=eid,
            ))
    return ConstraintResult("C2", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C3 — Single participant
# ---------------------------------------------------------------------------

def check_c3(idx: OcelIndex) -> ConstraintResult:
    """Each choreography event has exactly one choreo:participant relation."""
    violations: list[Violation] = []
    for eid in idx.events:
        participants = _e2o_by_qualifier(idx, eid, "choreo:participant")
        if len(participants) != 1:
            violations.append(Violation(
                constraint="C3",
                message=f"Event has {len(participants)} choreo:participant relations (expected 1)",
                event_id=eid,
            ))
    return ConstraintResult("C3", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C4 — Role exclusivity
# ---------------------------------------------------------------------------

def check_c4(idx: OcelIndex) -> ConstraintResult:
    """Initiator and participant of same event must be different objects."""
    violations: list[Violation] = []
    for eid in idx.events:
        initiators = set(_e2o_by_qualifier(idx, eid, "choreo:initiator"))
        participants = set(_e2o_by_qualifier(idx, eid, "choreo:participant"))
        overlap = initiators & participants
        for oid in overlap:
            violations.append(Violation(
                constraint="C4",
                message="Object is both initiator and participant of the same event",
                event_id=eid,
                object_id=oid,
            ))
    return ConstraintResult("C4", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C5 — Message source uniqueness
# ---------------------------------------------------------------------------

def check_c5(idx: OcelIndex) -> ConstraintResult:
    """Each message linked to an event has exactly one choreo:source."""
    violations: list[Violation] = []
    checked = 0
    for eid in idx.events:
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        for mid in messages:
            checked += 1
            sources = _o2o_by_qualifier(idx, mid, "choreo:source")
            if len(sources) != 1:
                violations.append(Violation(
                    constraint="C5",
                    message=f"Message has {len(sources)} choreo:source relations (expected 1)",
                    event_id=eid,
                    object_id=mid,
                ))
    return ConstraintResult("C5", checked, violations)


# ---------------------------------------------------------------------------
# C6 — Message target uniqueness
# ---------------------------------------------------------------------------

def check_c6(idx: OcelIndex) -> ConstraintResult:
    """Each message linked to an event has exactly one choreo:target."""
    violations: list[Violation] = []
    checked = 0
    for eid in idx.events:
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        for mid in messages:
            checked += 1
            targets = _o2o_by_qualifier(idx, mid, "choreo:target")
            if len(targets) != 1:
                violations.append(Violation(
                    constraint="C6",
                    message=f"Message has {len(targets)} choreo:target relations (expected 1)",
                    event_id=eid,
                    object_id=mid,
                ))
    return ConstraintResult("C6", checked, violations)


# ---------------------------------------------------------------------------
# C7 — Initiating message
# ---------------------------------------------------------------------------

def check_c7(idx: OcelIndex) -> ConstraintResult:
    """Each event has exactly one message whose source is the initiator."""
    violations: list[Violation] = []
    for eid in idx.events:
        initiators = _e2o_by_qualifier(idx, eid, "choreo:initiator")
        if not initiators:
            continue  # C2 handles missing initiator
        initiator = initiators[0]
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        init_msgs = [
            mid for mid in messages
            if initiator in _o2o_by_qualifier(idx, mid, "choreo:source")
        ]
        if len(init_msgs) != 1:
            violations.append(Violation(
                constraint="C7",
                message=f"Event has {len(init_msgs)} initiating messages (expected 1)",
                event_id=eid,
            ))
    return ConstraintResult("C7", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C8 — At most one return message
# ---------------------------------------------------------------------------

def check_c8(idx: OcelIndex) -> ConstraintResult:
    """Each event has at most one message whose source is the participant."""
    violations: list[Violation] = []
    for eid in idx.events:
        participants = _e2o_by_qualifier(idx, eid, "choreo:participant")
        if not participants:
            continue  # C3 handles missing participant
        participant = participants[0]
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        return_msgs = [
            mid for mid in messages
            if participant in _o2o_by_qualifier(idx, mid, "choreo:source")
        ]
        if len(return_msgs) > 1:
            violations.append(Violation(
                constraint="C8",
                message=f"Event has {len(return_msgs)} return messages (expected at most 1)",
                event_id=eid,
            ))
    return ConstraintResult("C8", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C9 — Initiating message target
# ---------------------------------------------------------------------------

def check_c9(idx: OcelIndex) -> ConstraintResult:
    """The initiating message (source=initiator) must target the participant."""
    violations: list[Violation] = []
    checked = 0
    for eid in idx.events:
        initiators = _e2o_by_qualifier(idx, eid, "choreo:initiator")
        participants = _e2o_by_qualifier(idx, eid, "choreo:participant")
        if not initiators or not participants:
            continue
        initiator = initiators[0]
        participant = participants[0]
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        for mid in messages:
            sources = _o2o_by_qualifier(idx, mid, "choreo:source")
            if initiator in sources:
                checked += 1
                targets = _o2o_by_qualifier(idx, mid, "choreo:target")
                if participant not in targets:
                    violations.append(Violation(
                        constraint="C9",
                        message="Initiating message does not target the participant",
                        event_id=eid,
                        object_id=mid,
                    ))
    return ConstraintResult("C9", checked, violations)


# ---------------------------------------------------------------------------
# C10 — Return message target
# ---------------------------------------------------------------------------

def check_c10(idx: OcelIndex) -> ConstraintResult:
    """The return message (source=participant) must target the initiator."""
    violations: list[Violation] = []
    checked = 0
    for eid in idx.events:
        initiators = _e2o_by_qualifier(idx, eid, "choreo:initiator")
        participants = _e2o_by_qualifier(idx, eid, "choreo:participant")
        if not initiators or not participants:
            continue
        initiator = initiators[0]
        participant = participants[0]
        messages = _e2o_by_qualifier(idx, eid, "choreo:message")
        for mid in messages:
            sources = _o2o_by_qualifier(idx, mid, "choreo:source")
            if participant in sources:
                checked += 1
                targets = _o2o_by_qualifier(idx, mid, "choreo:target")
                if initiator not in targets:
                    violations.append(Violation(
                        constraint="C10",
                        message="Return message does not target the initiator",
                        event_id=eid,
                        object_id=mid,
                    ))
    return ConstraintResult("C10", checked, violations)


# ---------------------------------------------------------------------------
# C11 — Containment uniqueness
# ---------------------------------------------------------------------------

def check_c11(idx: OcelIndex) -> ConstraintResult:
    """Each event has at most one choreo:contained-by relation."""
    violations: list[Violation] = []
    for eid in idx.events:
        containers = _e2o_by_qualifier(idx, eid, "choreo:contained-by")
        if len(containers) > 1:
            violations.append(Violation(
                constraint="C11",
                message=f"Event has {len(containers)} choreo:contained-by relations (expected at most 1)",
                event_id=eid,
            ))
    return ConstraintResult("C11", len(idx.events), violations)


# ---------------------------------------------------------------------------
# C12 — Non-empty scope
# ---------------------------------------------------------------------------

def check_c12(idx: OcelIndex) -> ConstraintResult:
    """Every scoping object has at least one contained event."""
    # Build reverse map: scoping_object_id → set of contained event IDs
    contained_by: dict[str, list[str]] = {}
    for eid in idx.events:
        for sub_id in _e2o_by_qualifier(idx, eid, "choreo:contained-by"):
            contained_by.setdefault(sub_id, []).append(eid)

    violations: list[Violation] = []
    for sub_id in idx.scoping_objects:
        if sub_id not in contained_by:
            violations.append(Violation(
                constraint="C12",
                message="Scoping object has no contained events",
                object_id=sub_id,
            ))
    return ConstraintResult("C12", len(idx.scoping_objects), violations)


# ---------------------------------------------------------------------------
# C13 — Instance consistency
# ---------------------------------------------------------------------------

def check_c13(idx: OcelIndex) -> ConstraintResult:
    """All events in allevents(o_sub) (transitively enclosed) link to the same instance."""
    violations: list[Violation] = []
    for sub_id in idx.scoping_objects:
        eids = _allevents(sub_id, idx)
        instances: set[str] = set()
        for eid in eids:
            for inst_id in _e2o_by_qualifier(idx, eid, "choreo:instance"):
                instances.add(inst_id)
        if len(instances) > 1:
            violations.append(Violation(
                constraint="C13",
                message=f"Scoping object contains events linking to {len(instances)} different instances",
                object_id=sub_id,
            ))
    return ConstraintResult("C13", len(idx.scoping_objects), violations)


# ---------------------------------------------------------------------------
# C14 — Nesting structure
# ---------------------------------------------------------------------------

def check_c14(idx: OcelIndex) -> ConstraintResult:
    """Validate nesting structure: unique parent and acyclicity (DAG)."""
    violations: list[Violation] = []

    # Build reverse map (child → parents) from choreo:contains
    child_to_parents: dict[str, list[str]] = {}
    for sub_id in idx.scoping_objects:
        for child_id in _o2o_by_qualifier(idx, sub_id, "choreo:contains"):
            child_to_parents.setdefault(child_id, []).append(sub_id)

    # Check 1: each scoping object has at most one incoming choreo:contains
    for child_id in idx.scoping_objects:
        parents = child_to_parents.get(child_id, [])
        if len(parents) > 1:
            violations.append(Violation(
                constraint="C14",
                message=f"Scoping object has {len(parents)} parent scopes (expected at most 1)",
                object_id=child_id,
            ))

    # Check 2: acyclicity — DFS cycle detection on choreo:contains graph
    visited: set[str] = set()
    in_stack: set[str] = set()

    def _has_cycle(node: str) -> bool:
        if node in in_stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        in_stack.add(node)
        for child in _o2o_by_qualifier(idx, node, "choreo:contains"):
            if _has_cycle(child):
                return True
        in_stack.discard(node)
        return False

    for sub_id in idx.scoping_objects:
        if sub_id not in visited:
            if _has_cycle(sub_id):
                violations.append(Violation(
                    constraint="C14",
                    message="Cycle detected in choreo:contains graph",
                    object_id=sub_id,
                ))
                break  # one cycle violation is enough

    return ConstraintResult("C14", len(idx.scoping_objects), violations)


# ---------------------------------------------------------------------------
# C15 — Initiator continuity
# ---------------------------------------------------------------------------

def _get_scope(idx: OcelIndex, eid: str) -> str | None:
    """Return the scoping object for an event, or None if top-level."""
    containers = _e2o_by_qualifier(idx, eid, "choreo:contained-by")
    return containers[0] if containers else None


def _get_parent_map(idx: OcelIndex) -> dict[str, str]:
    """Build child → parent map from choreo:contains O2O relations."""
    parent_map: dict[str, str] = {}
    for sub_id in idx.scoping_objects:
        for child_id in _o2o_by_qualifier(idx, sub_id, "choreo:contains"):
            parent_map[child_id] = sub_id
    return parent_map


def _ancestors(scope: str, parent_map: dict[str, str]) -> list[str]:
    """Return list of ancestor scopes from immediate parent to root."""
    result: list[str] = []
    current = scope
    while current in parent_map:
        current = parent_map[current]
        result.append(current)
    return result


def _root_ancestor(scope: str, parent_map: dict[str, str]) -> str:
    """Return the root ancestor of a scope (or itself if no parent)."""
    current = scope
    while current in parent_map:
        current = parent_map[current]
    return current


def _descendants(scope: str, idx: OcelIndex) -> set[str]:
    """Return all descendant scopes reachable via choreo:contains."""
    result: set[str] = set()
    stack = [scope]
    while stack:
        current = stack.pop()
        for child in _o2o_by_qualifier(idx, current, "choreo:contains"):
            if child not in result:
                result.add(child)
                stack.append(child)
    return result


def _allevents(scope_id: str, idx: OcelIndex) -> set[str]:
    """Return all event IDs transitively enclosed by scope_id (direct + descendant scopes)."""
    scopes = {scope_id} | _descendants(scope_id, idx)
    return {eid for eid in idx.events if _get_scope(idx, eid) in scopes}


def _involved_in_scope_tree(scope: str, idx: OcelIndex) -> set[str]:
    """Return all objects appearing as initiator or participant in events
    enclosed by scope or any of its descendant scopes."""
    involved: set[str] = set()
    for eid in _allevents(scope, idx):
        involved.update(_e2o_by_qualifier(idx, eid, "choreo:initiator"))
        involved.update(_e2o_by_qualifier(idx, eid, "choreo:participant"))
    return involved


def check_c15(idx: OcelIndex) -> ConstraintResult:
    """Initiator continuity: initiator of e_2 must have been involved in e_1's context."""
    # Group events by instance and sort by time
    instance_events: dict[str, list[dict]] = {}
    for e in idx.choreo_events:
        instances = _e2o_by_qualifier(idx, e["id"], "choreo:instance")
        if not instances:
            continue
        inst_id = instances[0]
        instance_events.setdefault(inst_id, []).append(e)

    for events in instance_events.values():
        events.sort(key=lambda e: e["time"])

    parent_map = _get_parent_map(idx)
    violations: list[Violation] = []
    checked = 0

    for events in instance_events.values():
        for i in range(len(events) - 1):
            e1 = events[i]
            e2 = events[i + 1]
            checked += 1

            initiators_e2 = _e2o_by_qualifier(idx, e2["id"], "choreo:initiator")
            if not initiators_e2:
                continue  # C2 handles missing initiator
            o_i = initiators_e2[0]

            scope_e1 = _get_scope(idx, e1["id"])
            scope_e2 = _get_scope(idx, e2["id"])

            # Determine which case applies
            if scope_e2 is not None and scope_e1 is not None:
                ancestors_e1 = _ancestors(scope_e1, parent_map)
                if scope_e2 in ancestors_e1:
                    # Case 1: ascending into ancestor scope (one level down)
                    # Find o_sub-1(e_2): the child of scope_e2 on the path to scope_e1
                    path = [scope_e1] + ancestors_e1  # scope_e1, ..., scope_e2
                    idx_in_path = path.index(scope_e2)
                    child_scope = path[idx_in_path - 1]  # one level below scope_e2
                    involved = _involved_in_scope_tree(child_scope, idx)
                    if involved and o_i not in involved:
                        violations.append(Violation(
                            constraint="C15",
                            message=f"Initiator {o_i} not involved in child scope {child_scope}",
                            event_id=e2["id"],
                        ))
                    continue

            if scope_e1 is not None and scope_e2 is None:
                # Case 2: exiting to top level
                root = _root_ancestor(scope_e1, parent_map)
                involved = _involved_in_scope_tree(root, idx)
                if involved and o_i not in involved:
                    violations.append(Violation(
                        constraint="C15",
                        message=f"Initiator {o_i} not involved in root scope {root}",
                        event_id=e2["id"],
                    ))
                continue

            # Case 3: same scope, descending, or both top-level
            roles_e1 = set(_e2o_by_qualifier(idx, e1["id"], "choreo:initiator"))
            roles_e1.update(_e2o_by_qualifier(idx, e1["id"], "choreo:participant"))
            if o_i not in roles_e1:
                violations.append(Violation(
                    constraint="C15",
                    message=f"Initiator {o_i} not initiator or participant of previous event",
                    event_id=e2["id"],
                ))

    return ConstraintResult("C15", checked, violations)


# ---------------------------------------------------------------------------
# C16 — Scope re-entry
# ---------------------------------------------------------------------------

def check_c16(idx: OcelIndex) -> ConstraintResult:
    """Sequence flow cannot re-enter a sub-choreography scope once it has left.

    For each (o_sub, instance) pair: once an event of that instance is observed
    outside allevents(o_sub) after being inside, no later event may be inside.
    """
    # Pre-compute allevents for each scoping object
    scope_allevents: dict[str, set[str]] = {
        sub_id: _allevents(sub_id, idx)
        for sub_id in idx.scoping_objects
    }

    # Group events by instance, sorted by time
    instance_events: dict[str, list[dict]] = {}
    for e in idx.choreo_events:
        inst_ids = _e2o_by_qualifier(idx, e["id"], "choreo:instance")
        if inst_ids:
            instance_events.setdefault(inst_ids[0], []).append(e)
    for events in instance_events.values():
        events.sort(key=lambda e: e["time"])

    violations: list[Violation] = []
    checked = 0

    for sub_id, ae in scope_allevents.items():
        for inst_id, events in instance_events.items():
            # Determine if this instance ever touches this scope
            if not any(e["id"] in ae for e in events):
                continue
            checked += 1
            exited = False
            was_inside = False
            for e in events:
                inside = e["id"] in ae
                if inside:
                    if exited:
                        violations.append(Violation(
                            constraint="C16",
                            message=f"Instance re-entered scope {sub_id} after leaving it",
                            event_id=e["id"],
                            object_id=sub_id,
                        ))
                    else:
                        was_inside = True
                else:
                    if was_inside:
                        exited = True

    return ConstraintResult("C16", checked, violations)


# ---------------------------------------------------------------------------
# Registry + public API
# ---------------------------------------------------------------------------

_CHECKS = {
    "C0": check_c0,
    "C1": check_c1,
    "C2": check_c2,
    "C3": check_c3,
    "C4": check_c4,
    "C5": check_c5,
    "C6": check_c6,
    "C7": check_c7,
    "C8": check_c8,
    "C9": check_c9,
    "C10": check_c10,
    "C11": check_c11,
    "C12": check_c12,
    "C13": check_c13,
    "C14": check_c14,
    "C15": check_c15,
    "C16": check_c16,
}


def validate_all(idx: OcelIndex) -> dict[str, ConstraintResult]:
    """Check all constraints. Returns mapping from constraint ID to result."""
    return {cid: fn(idx) for cid, fn in _CHECKS.items()}


def validate(
    idx: OcelIndex,
    constraint_ids: list[str] | None = None,
) -> dict[str, ConstraintResult]:
    """Check specified constraints (or all if None)."""
    if constraint_ids is None:
        return validate_all(idx)
    return {cid: _CHECKS[cid](idx) for cid in constraint_ids if cid in _CHECKS}
