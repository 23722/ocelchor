"""OCEL 2.0 choreography log → in-memory model; run validator; assert hard gates.

Spec §B8/§B9/§B10. The miner never repairs contract violations: the hard gates
(C0, C2, C3, C11, C12, C14) abort on violation; every other constraint result is
kept for diagnostics but is non-blocking.

C3 is gated by shape: |noninit(e)| > 1 (multicast) aborts — which role enters
the taskType tuple is genuinely undefined, and any choice would silently drop
a receiver. |noninit(e)| = 0 is an *unrecorded* receiver (an incompleteness of
the record, not a positive assertion): the event is typed with the reserved
empty participant role "", the C3 violation stays visible in the constraints
summary, and the CLI writes a warnings note. The event is routed INTO typing,
never dropped into the non-task count — filtering it would silently shift the
enclosing scope's ``first_task_in`` and corrupt the scope's type.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ocelchorvalidator.constraints import ConstraintResult, validate_all
from ocelchorvalidator.index import build_index

# E2O / O2O qualifiers (interface contract §I4 — exactly the published mapping).
Q_INSTANCE = "choreo:instance"
Q_INITIATOR = "choreo:initiator"
Q_PARTICIPANT = "choreo:participant"
Q_MESSAGE = "choreo:message"
Q_CONTAINED_BY = "choreo:contained-by"
Q_CONTAINS = "choreo:contains"
Q_SOURCE = "choreo:source"
Q_TARGET = "choreo:target"

TYPE_INSTANCE = "choreographyInstance"
TYPE_SCOPE = "subchoreographyInstance"

# Hard gates: assert and abort on violation (spec §B8).
HARD_GATES = ("C0", "C2", "C3", "C11", "C12", "C14")

# Event-kind prefixes (kind is carried by the type prefix only, spec §I2).
_REQUEST_PREFIX = "Request "
_RESPOND_PREFIX = "Respond to "


class ContractViolation(Exception):
    """A hard-gate constraint violation. The miner aborts; it never repairs."""


class OrderingTie(Exception):
    """Two distinct events of one instance share a timestamp (spec §I6/D1).

    OCEL 2.0 has no secondary ordering attribute, so this is unresolvable and a
    hard error — an extractor bug, not something the miner works around."""


class UntypeableScope(ContractViolation):
    """A scope contains (transitively) no choreography task event, so neither
    its roles nor a derived label exist. Reported, never repaired — no
    fallback type is invented (spec §B2.3)."""


@dataclass
class Event:
    """One task occurrence — a single OCEL event (spec §B1)."""

    id: str
    type: str  # execType, verbatim event.type (spec §I1/§B2.1)
    time: str
    trace_order: int
    initiator: str | None  # object id via choreo:initiator
    participant: str | None  # object id via choreo:participant (noninit);
    # "" = reserved empty role: the receiver is unrecorded (C3 reported, not
    # repaired) — compares equal to the ""-normalized message endpoints
    message_ids: list[str]
    scope_id: str | None  # choreo:contained-by (≤1, C11)
    instance_id: str | None  # choreo:instance (exactly one, C0)


@dataclass
class Model:
    """In-memory view of one OCEL 2.0 choreography log."""

    ocel: dict
    events: dict[str, Event]  # E_T only: choreography task events (see build_model)
    objtype: dict[str, str]  # object id → OCEL object type (= role)
    scope_contains: dict[str, list[str]]  # parent scope id → [child scope ids]
    scope_parent: dict[str, str]  # child scope id → parent scope id
    instances: list[str]  # choreographyInstance object ids
    scopes: list[str]  # subchoreographyInstance object ids
    scope_names: dict[str, str] = field(default_factory=dict)  # scope id → name attr
    non_task_events: int = 0  # events excluded from E_T (no initiator edge)
    # Task events typed with the reserved empty participant role because their
    # receiver is unrecorded (C3 missing-receiver shape, reported not repaired).
    missing_receiver_events: list[str] = field(default_factory=list)
    constraints: dict[str, ConstraintResult] = field(default_factory=dict)

    # -- accessors (spec §B2) ------------------------------------------------

    def kind(self, e: Event) -> str:
        """kind(e) ∈ {request, response, atomic}, parsed from the type prefix only."""
        if e.type.startswith(_REQUEST_PREFIX):
            return "request"
        if e.type.startswith(_RESPOND_PREFIX):
            return "response"
        return "atomic"

    def role_of(self, obj_id: str | None) -> str:
        """objtype(o) — the OCEL object type used as the choreography role."""
        if obj_id is None:
            return ""
        return self.objtype.get(obj_id, "")

    def scope_name(self, scope_id: str) -> str | None:
        """The scoping object's `name` attribute — scope-typing rung 1
        (an explicit sub-choreography label supplied at extraction)."""
        return self.scope_names.get(scope_id)

    def events_of_instance(self, instance_id: str) -> list[Event]:
        return [e for e in self.events.values() if e.instance_id == instance_id]

    def direct_events(self, scope_id: str) -> list[Event]:
        """Events whose choreo:contained-by is exactly this scope."""
        return [e for e in self.events.values() if e.scope_id == scope_id]

    def all_events(self, scope_id: str) -> list[Event]:
        """Directly contained events plus events of all descendant scopes
        (transitive over contains/contained-by) — spec §B2.3 allevents(o_sub)."""
        result = list(self.direct_events(scope_id))
        for child in self.scope_contains.get(scope_id, []):
            result.extend(self.all_events(child))
        return result


def order_key(e: Event) -> str:
    """≻ ordering key — the event timestamp alone (spec §I6, domain-agnostic).

    OCEL 2.0 offers no secondary ordering attribute, so ordering relies purely
    on ``time``. This is total per instance for every supported log family: the
    trace2ocelchor extractor bakes call order into the timestamp (base +
    trace_order ms, serialized at millisecond resolution), and the XES-derived
    logs carry distinct real event times. ``trace_order`` is a blockchain-only
    attribute and is deliberately NOT used here (it would leak domain specifics
    into a domain-agnostic miner). A residual tie — two distinct events of one
    instance sharing a timestamp — is an extractor bug and a hard error (D9).

    The ISO-8601 ``YYYY-MM-DDTHH:MM:SS.mmmZ`` form is fixed-width, so lexical
    string order coincides with chronological order.
    """
    return e.time


def _rels(item: dict, qualifier: str) -> list[str]:
    return [r["objectId"] for r in item.get("relationships", []) if r["qualifier"] == qualifier]


def _rel(item: dict, qualifier: str) -> str | None:
    got = _rels(item, qualifier)
    return got[0] if got else None


def _attr(item: dict, name: str, default=None):
    for a in item.get("attributes", []):
        if a["name"] == name:
            return a["value"]
    return default


def build_model(ocel: dict, *, run_validator: bool = True) -> Model:
    """Build the in-memory model and assert the hard gates (spec §B8/§B10)."""
    objtype = {o["id"]: o.get("type", "") for o in ocel["objects"]}

    # E_T filter: the miner's alphabet is choreography task events — events
    # carrying an initiator edge. Internal non-choreography events supply no
    # roles and are excluded up front, counted for diagnostics (never
    # silently: the count is reported). A task event whose *participant* edge
    # is missing is NOT filtered: its receiver is unrecorded (C3 shape
    # |noninit| = 0) and it is typed with the reserved empty role "" —
    # dropping it would silently shift the enclosing scope's first_task_in.
    # A multicast event (|noninit| > 1) aborts here: which role enters the
    # taskType tuple is undefined, and any choice silently drops a receiver.
    events: dict[str, Event] = {}
    non_task = 0
    missing_receiver: list[str] = []
    for e in ocel["events"]:
        initiator = _rel(e, Q_INITIATOR)
        participants = _rels(e, Q_PARTICIPANT)
        if initiator is None:
            non_task += 1
            continue
        if len(participants) > 1:
            raise ContractViolation(
                f"C3 multicast shape: event {e['id']!r} has "
                f"{len(participants)} receivers — the taskType tuple is "
                "undefined; the miner aborts (spec §B8)"
            )
        if not participants:
            missing_receiver.append(e["id"])
        to = _attr(e, "trace_order", 0)
        events[e["id"]] = Event(
            id=e["id"],
            type=e["type"],
            time=e.get("time", ""),
            trace_order=int(to) if to is not None else 0,
            initiator=initiator,
            participant=participants[0] if participants else "",
            message_ids=_rels(e, Q_MESSAGE),
            scope_id=_rel(e, Q_CONTAINED_BY),
            instance_id=_rel(e, Q_INSTANCE),
        )

    scope_contains: dict[str, list[str]] = {}
    scope_parent: dict[str, str] = {}
    scope_names: dict[str, str] = {}
    scopes = [o["id"] for o in ocel["objects"] if o.get("type") == TYPE_SCOPE]
    for o in ocel["objects"]:
        if o.get("type") != TYPE_SCOPE:
            continue
        name = _attr(o, "name")
        if name:
            scope_names[o["id"]] = name
        for child in _rels(o, Q_CONTAINS):
            scope_contains.setdefault(o["id"], []).append(child)
            scope_parent[child] = o["id"]

    instances = [o["id"] for o in ocel["objects"] if o.get("type") == TYPE_INSTANCE]

    constraints: dict[str, ConstraintResult] = {}
    if run_validator:
        constraints = validate_all(build_index(ocel))
        failed = [
            cid for cid in HARD_GATES
            if cid != "C3" and cid in constraints and not constraints[cid].passed
        ]
        # C3 shape split: multicast events already aborted above, so any C3
        # violation left is the missing-receiver shape — tolerated (typed
        # with the reserved empty role), reported in the constraints summary.
        # Verify that expectation instead of assuming it.
        if "C3" in constraints and not constraints["C3"].passed:
            raw = {e["id"]: e for e in ocel["events"]}
            unexplained = [
                v.event_id for v in constraints["C3"].violations
                if v.event_id not in missing_receiver
                and len(_rels(raw.get(v.event_id, {}), Q_PARTICIPANT)) != 0
            ]
            if unexplained:
                failed.append("C3")
        if failed:
            detail = "; ".join(
                f"{cid}: {constraints[cid].num_violations} violation(s)" for cid in failed
            )
            raise ContractViolation(
                f"Hard-gate constraint violation(s), miner aborts (spec §B8): {detail}"
            )

    return Model(
        ocel=ocel,
        events=events,
        objtype=objtype,
        scope_contains=scope_contains,
        scope_parent=scope_parent,
        instances=instances,
        scopes=scopes,
        scope_names=scope_names,
        non_task_events=non_task,
        missing_receiver_events=missing_receiver,
        constraints=constraints,
    )


def load(path: str | Path, *, run_validator: bool = True) -> Model:
    """Load an OCEL 2.0 JSON file into a Model."""
    with open(path) as f:
        ocel = json.load(f)
    return build_model(ocel, run_validator=run_validator)
