"""Two typing layers: execType (log artifact) and taskType/scopeType (model).

Spec §B2. Keep the layers sharp:
  - execType(e)  — the OCEL event.type string, verbatim, opaque to the miner.
  - taskType(e)  — ⟨execType, objtype(init), objtype(noninit)⟩; the tree-leaf label.
  - scopeType(o) — taskType of the scope's ≻-first (opening) event; named-subtree label.

TaskType / ScopeType are frozen and hashable and carry NOTHING occurrence-varying
(no messages, concrete objects, or timestamps) — that would shatter the
equivalence classes (spec §B2.2). Occurrence data goes to the side index (§B4).
"""

from __future__ import annotations

from dataclasses import dataclass

from ocelchormodel_rad.reader import Event, Model, order_key


@dataclass(frozen=True)
class TaskType:
    """Choreography task type — the process-tree leaf label (spec §B2.2)."""

    exec_type: str  # event.type, verbatim (§I1)
    init_role: str  # objtype(init(e))
    noninit_role: str  # objtype(noninit(e))


@dataclass(frozen=True)
class ScopeType:
    """Scope type — the named-subtree label (spec §B2.3)."""

    opener: TaskType  # taskType(firstIn(o_sub))
    opener_is_request: bool  # False → diagnostic D2 (branch-invariance not guaranteed)


def exec_type(e: Event) -> str:
    """execType(e) = e.type, verbatim (spec §B2.1)."""
    return e.type


def task_type(model: Model, e: Event) -> TaskType:
    """taskType(e) — asserts the C2/C3 singletons on load (spec §B2.2/§B10)."""
    assert e.initiator is not None, f"C2 violated: event {e.id!r} has no single initiator"
    assert e.participant is not None, f"C3 violated: event {e.id!r} has no single participant"
    return TaskType(
        exec_type=exec_type(e),
        init_role=model.role_of(e.initiator),
        noninit_role=model.role_of(e.participant),
    )


def first_in(model: Model, scope_id: str) -> Event:
    """firstIn(o_sub) — the ≻-minimal event of allevents(o_sub) (spec §B2.3)."""
    events = model.all_events(scope_id)
    assert events, f"C12 violated: scope {scope_id!r} is empty"
    return min(events, key=order_key)


def scope_type(model: Model, scope_id: str) -> ScopeType:
    """scopeType(o_sub) = taskType(firstIn(o_sub)); records opener_is_request (§B2.3)."""
    opener = first_in(model, scope_id)
    return ScopeType(
        opener=task_type(model, opener),
        opener_is_request=(model.kind(opener) == "request"),
    )
