"""Two typing layers: execType (log artifact) and taskType/scopeType (model).

Spec §B2. Keep the layers sharp:
  - execType(e)  — the OCEL event.type string, verbatim, opaque to the miner.
  - taskType(e)  — ⟨execType, objtype(init), objtype(noninit)⟩; the tree-leaf label.
  - scopeType(o) — ⟨label, init_role, noninit_role⟩; the named-subtree label.
    The label resolves through a two-rung chain: (1) the scoping object's
    `name` attribute — an explicit sub-choreography label supplied at
    extraction; (2) derived from the first task event's type with the kind
    prefix stripped. Both roles ALWAYS come from the scope's ≻-first
    choreography task event (E_T — never an internal non-choreography event,
    which cannot supply them). D2 audits the derivation certificate: it holds
    when that first task event is a request bracket (branch-invariant opener).

TaskType / ScopeType are frozen and hashable and carry NOTHING occurrence-varying
(no messages, concrete objects, or timestamps) — that would shatter the
equivalence classes (spec §B2.2). Occurrence data goes to the side index (§B4).
Certification (D2) is deliberately NOT part of ScopeType identity: two scopes
with equal ⟨label, roles⟩ pool regardless of how their labels were obtained.
"""

from __future__ import annotations

from dataclasses import dataclass

from ocelchormodel_rad.reader import Event, Model, UntypeableScope, order_key

_KIND_PREFIXES = ("Request ", "Respond to ")


@dataclass(frozen=True)
class TaskType:
    """Choreography task type — the process-tree leaf label (spec §B2.2)."""

    exec_type: str  # event.type, verbatim (§I1)
    init_role: str  # objtype(init(e))
    noninit_role: str  # objtype(noninit(e))


@dataclass(frozen=True)
class ScopeType:
    """Scope type — the named-subtree label (spec §B2.3).

    Typed like a task: label + participants. `init_role`/`noninit_role` are
    the roles of the scope's first task event; for a call-scope the
    non-initiating role is the callee, which is why ⟨label, noninit_role⟩
    is the recursion-matching key (D12) even for undiscriminated labels.
    """

    label: str  # rung 1: scoping object's name attr; rung 2: derived (§B2.3)
    init_role: str  # objtype(init(firstTaskIn(o_sub)))
    noninit_role: str  # objtype(noninit(firstTaskIn(o_sub)))


def exec_type(e: Event) -> str:
    """execType(e) = e.type, verbatim (spec §B2.1)."""
    return e.type


def strip_kind(exec_type: str) -> str:
    """Drop the bracket-marker kind prefix (spec §I2) — used only for the
    rung-2 label derivation and diagnostics, never for display surgery."""
    for pfx in _KIND_PREFIXES:
        if exec_type.startswith(pfx):
            return exec_type[len(pfx):]
    return exec_type


def task_type(model: Model, e: Event) -> TaskType:
    """taskType(e) — asserts the C2/C3 singletons on load (spec §B2.2/§B10)."""
    assert e.initiator is not None, f"C2 violated: event {e.id!r} has no single initiator"
    assert e.participant is not None, f"C3 violated: event {e.id!r} has no single participant"
    return TaskType(
        exec_type=exec_type(e),
        init_role=model.role_of(e.initiator),
        noninit_role=model.role_of(e.participant),
    )


def first_task_in(model: Model, scope_id: str) -> Event:
    """firstTaskIn(o_sub) — the ≻-minimal E_T event of allevents(o_sub).

    The model's event universe is already E_T-filtered (reader), so this is
    the ≻-minimum of the contained task events. A scope with none is
    untypeable: reported, never repaired (spec §B2.3)."""
    events = model.all_events(scope_id)
    if not events:
        raise UntypeableScope(
            f"scope {scope_id!r} contains no choreography task event — "
            "roles and label are underivable; no fallback type is invented"
        )
    return min(events, key=order_key)


def scope_type(model: Model, scope_id: str) -> ScopeType:
    """scopeType(o_sub) — label chain rung 1/2 + first-task-event roles (§B2.3)."""
    first = first_task_in(model, scope_id)
    label = model.scope_name(scope_id) or strip_kind(first.type)
    return ScopeType(
        label=label,
        init_role=model.role_of(first.initiator),
        noninit_role=model.role_of(first.participant),
    )


def scope_certified(model: Model, scope_id: str) -> bool:
    """D2 certificate: the scope's first task event is its request bracket,
    making the role derivation branch-invariant. Checked on both label rungs
    (a stored name does not exempt the roles). Not part of type identity."""
    return model.kind(first_task_in(model, scope_id)) == "request"
