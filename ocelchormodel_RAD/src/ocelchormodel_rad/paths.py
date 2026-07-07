"""≻ ordering, per-instance flattening, and event paths (spec §B2.4).

Each instance flattens to exactly one hierarchical trace: its events in ≻ order,
each mapped to its event path ⟨scopeType(s_1) … scopeType(s_k), taskType(e)⟩
with s_1 … s_k the enclosing scopes outermost → innermost.
"""

from __future__ import annotations

from ocelchormodel_rad.hierarchy import enclosing_scopes
from ocelchormodel_rad.reader import Event, Model, OrderingTie, order_key
from ocelchormodel_rad.typing import ScopeType, TaskType, scope_type, task_type

# One event path: the enclosing scope types (outermost → innermost) then the leaf.
EventPath = tuple[ScopeType | TaskType, ...]


def instance_order(model: Model, instance_id: str) -> list[Event]:
    """Events of one instance in ≻ order; a residual timestamp tie is D9 (hard)."""
    events = sorted(model.events_of_instance(instance_id), key=order_key)
    seen: dict[str, Event] = {}
    for e in events:
        k = order_key(e)
        if k in seen:
            raise OrderingTie(
                f"Instance {instance_id!r}: events {seen[k].id!r} and {e.id!r} "
                f"share timestamp {k!r} (spec §I6/D9)."
            )
        seen[k] = e
    return events


def event_path(model: Model, e: Event) -> EventPath:
    """eventPath(e) = ⟨scopeType(s_1) … scopeType(s_k), taskType(e)⟩ (spec §B2.4)."""
    scopes = enclosing_scopes(model, e)
    return tuple(scope_type(model, s) for s in scopes) + (task_type(model, e),)


def hierarchical_trace(model: Model, instance_id: str) -> list[EventPath]:
    """The single hierarchical trace of one instance: event paths in ≻ order."""
    return [event_path(model, e) for e in instance_order(model, instance_id)]


def all_traces(model: Model) -> dict[str, list[EventPath]]:
    """One hierarchical trace per choreography instance (unit of discovery: the log)."""
    return {inst: hierarchical_trace(model, inst) for inst in model.instances}
