"""OCEL 2.0 choreography log → in-memory model; run validator; assert hard gates.

Spec §B8/§B9/§B10. The miner never repairs contract violations: the hard gates
(C0, C2, C3, C11, C12, C14) abort on violation; every other constraint result is
kept for diagnostics but is non-blocking.
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
    """Two distinct events of one instance share a timestamp (spec §I6/D9).

    OCEL 2.0 has no secondary ordering attribute, so this is unresolvable and a
    hard error — an extractor bug, not something the miner works around."""


@dataclass
class Event:
    """One task occurrence — a single OCEL event (spec §B1)."""

    id: str
    type: str  # execType, verbatim event.type (spec §I1/§B2.1)
    time: str
    trace_order: int
    initiator: str | None  # object id via choreo:initiator
    participant: str | None  # object id via choreo:participant (noninit)
    message_ids: list[str]
    scope_id: str | None  # choreo:contained-by (≤1, C11)
    instance_id: str | None  # choreo:instance (exactly one, C0)


@dataclass
class Model:
    """In-memory view of one OCEL 2.0 choreography log."""

    ocel: dict
    events: dict[str, Event]
    objtype: dict[str, str]  # object id → OCEL object type (= role)
    scope_contains: dict[str, list[str]]  # parent scope id → [child scope ids]
    scope_parent: dict[str, str]  # child scope id → parent scope id
    instances: list[str]  # choreographyInstance object ids
    scopes: list[str]  # subchoreographyInstance object ids
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

    events: dict[str, Event] = {}
    for e in ocel["events"]:
        to = _attr(e, "trace_order", 0)
        events[e["id"]] = Event(
            id=e["id"],
            type=e["type"],
            time=e.get("time", ""),
            trace_order=int(to) if to is not None else 0,
            initiator=_rel(e, Q_INITIATOR),
            participant=_rel(e, Q_PARTICIPANT),
            message_ids=_rels(e, Q_MESSAGE),
            scope_id=_rel(e, Q_CONTAINED_BY),
            instance_id=_rel(e, Q_INSTANCE),
        )

    scope_contains: dict[str, list[str]] = {}
    scope_parent: dict[str, str] = {}
    scopes = [o["id"] for o in ocel["objects"] if o.get("type") == TYPE_SCOPE]
    for o in ocel["objects"]:
        if o.get("type") != TYPE_SCOPE:
            continue
        for child in _rels(o, Q_CONTAINS):
            scope_contains.setdefault(o["id"], []).append(child)
            scope_parent[child] = o["id"]

    instances = [o["id"] for o in ocel["objects"] if o.get("type") == TYPE_INSTANCE]

    constraints: dict[str, ConstraintResult] = {}
    if run_validator:
        constraints = validate_all(build_index(ocel))
        failed = [
            cid for cid in HARD_GATES
            if cid in constraints and not constraints[cid].passed
        ]
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
        constraints=constraints,
    )


def load(path: str | Path, *, run_validator: bool = True) -> Model:
    """Load an OCEL 2.0 JSON file into a Model."""
    with open(path) as f:
        ocel = json.load(f)
    return build_model(ocel, run_validator=run_validator)
