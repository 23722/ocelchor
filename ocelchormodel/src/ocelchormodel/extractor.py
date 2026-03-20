"""Extract choreography instances from a raw OCEL 2.0 dict.

Implements the mapping from paper Section 4.2:
- Events are choreography tasks (E2O: choreo:initiator, choreo:participant,
  choreo:message, choreo:instance, choreo:contained-by)
- Subchoreographies are scoping objects (O2O: choreo:contains)
- Messages carry O2O: choreo:source, choreo:target
"""

from __future__ import annotations

import re

from ocelchormodel.model import (
    ChoreoInstance,
    ChoreoTask,
    Message,
    Participant,
    SubChoreo,
)

# ---------------------------------------------------------------------------
# Qualifier constants (must match trace2choreo output / paper Section 4.2)
# ---------------------------------------------------------------------------

_INSTANCE = "choreo:instance"
_INITIATOR = "choreo:initiator"
_PARTICIPANT = "choreo:participant"
_MESSAGE = "choreo:message"
_SOURCE = "choreo:source"
_TARGET = "choreo:target"
_CONTAINED_BY = "choreo:contained-by"
_CONTAINS = "choreo:contains"

_TYPE_CHOREO_INSTANCE = "choreographyInstance"
_TYPE_SUBCHOREOGRAPHY = "subchoreographyInstance"
_GENERIC_TYPES = {"EOA", "CA"}


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _xml_id(prefix: str, ocel_id: str) -> str:
    """Return a valid XML NCName from an OCEL id."""
    safe = re.sub(r"[^a-zA-Z0-9_.\-]", "_", ocel_id)
    return f"{prefix}_{safe}"


def _display_name(ocel_type: str, ocel_id: str) -> str:
    """Human-readable participant name."""
    if ocel_type not in _GENERIC_TYPES:
        return ocel_type
    suffix = ocel_id[-6:] if len(ocel_id) >= 6 else ocel_id
    return f"{ocel_type} \u2026{suffix}"


def _short_id(instance_ocel_id: str) -> str:
    """Extract the last 8 hex chars of the tx hash from an instance id."""
    hex_part = instance_ocel_id.split("0x", 1)[-1] if "0x" in instance_ocel_id else instance_ocel_id
    return hex_part[-8:] if len(hex_part) >= 8 else hex_part


# ---------------------------------------------------------------------------
# Internal helpers for event/object dicts
# ---------------------------------------------------------------------------

def _rels(item: dict, qualifier: str) -> list[str]:
    """Return all object IDs for a given qualifier on an event or object."""
    return [
        r["objectId"]
        for r in item.get("relationships", [])
        if r["qualifier"] == qualifier
    ]


def _rel(item: dict, qualifier: str) -> str | None:
    """Return the first object ID for a qualifier, or None."""
    targets = _rels(item, qualifier)
    return targets[0] if targets else None


def _obj_attr(obj: dict, attr_name: str) -> str | None:
    """Return the value of a named attribute on an OCEL object, or None."""
    for attr in obj.get("attributes", []):
        if attr["name"] == attr_name:
            return attr["value"]
    return None


def _trace_order(event: dict) -> int:
    """Return the trace_order attribute as an int (default: 0)."""
    for attr in event.get("attributes", []):
        if attr["name"] == "trace_order":
            return int(attr["value"])
    return 0


def _timestamp(event: dict) -> str:
    """Return the event timestamp (default: empty string)."""
    return event.get("time", "")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_instances(ocel: dict) -> list[tuple[str, str]]:
    """Return [(ocel_id, short_id), …] for all choreographyInstance objects."""
    results = []
    for obj in ocel["objects"]:
        if obj.get("type") == _TYPE_CHOREO_INSTANCE:
            oid = obj["id"]
            results.append((oid, _short_id(oid)))
    results.sort(key=lambda x: x[0])
    return results


def extract_instance(ocel: dict, instance_id: str, *, order_by: str = "timestamp") -> ChoreoInstance:
    """Build a ChoreoInstance from the OCEL dict for the given instance_id.

    Follows the paper's mapping (Section 4.2):
    - All events are choreography tasks.
    - Subchoreographies are scoping objects linked via choreo:contained-by
      (E2O, event → scope) and choreo:contains (O2O, parent scope → child).

    Args:
        order_by: "timestamp" (default) or "trace_order".

    Raises:
        ValueError: if the instance_id is not found in the log.
    """
    _sort_key = _timestamp if order_by == "timestamp" else _trace_order

    # --- Verify the instance exists ---
    all_ids = {oid for oid, _ in list_instances(ocel)}
    if instance_id not in all_ids:
        raise ValueError(
            f"Instance '{instance_id}' not found. "
            f"Available: {sorted(all_ids)}"
        )

    # --- Index objects by id ---
    objects: dict[str, dict] = {obj["id"]: obj for obj in ocel["objects"]}

    # --- Index object type attributes (for message display names) ---
    _type_attrs: dict[str, list[str]] = {}
    for ot in ocel.get("objectTypes", []):
        attr_names = [a["name"] for a in ot.get("attributes", [])]
        if attr_names:
            _type_attrs[ot["name"]] = attr_names

    # --- Filter events that belong to this instance ---
    instance_events: list[dict] = [
        e for e in ocel["events"]
        if instance_id in _rels(e, _INSTANCE)
    ]

    # --- Collect all subchoreographyInstance scope objects ---
    scope_objects: dict[str, dict] = {
        obj["id"]: obj
        for obj in ocel["objects"]
        if obj.get("type") == _TYPE_SUBCHOREOGRAPHY
    }

    # --- Build scope hierarchy from choreo:contains O2O (parent → child) ---
    # child_to_parent[child_scope_id] = parent_scope_id
    child_to_parent: dict[str, str] = {}
    # parent_to_children[parent_scope_id] = [child_scope_id, ...]
    parent_to_children: dict[str, list[str]] = {}
    for scope_id, scope_obj in scope_objects.items():
        for child_id in _rels(scope_obj, _CONTAINS):
            child_to_parent[child_id] = scope_id
            parent_to_children.setdefault(scope_id, []).append(child_id)

    # --- Assign events to their immediate scope via choreo:contained-by ---
    # scope_events[scope_id] = [event, ...] for direct children
    scope_events: dict[str, list[dict]] = {}
    top_level_events: list[dict] = []

    for event in instance_events:
        scope_id = _rel(event, _CONTAINED_BY)
        if scope_id is not None:
            scope_events.setdefault(scope_id, []).append(event)
        else:
            top_level_events.append(event)

    # --- Filter scopes to only those relevant to this instance ---
    # Walk up from scopes referenced by instance events to find root scopes
    instance_scope_ids: set[str] = set()
    for sid in scope_events:
        cur = sid
        while cur and cur not in instance_scope_ids:
            instance_scope_ids.add(cur)
            cur = child_to_parent.get(cur)

    root_scope_ids = instance_scope_ids - set(child_to_parent.keys())

    # --- Build participant cache (deduplicated by ocel_id) ---
    _participant_cache: dict[str, Participant] = {}

    def _get_participant(pid: str) -> Participant:
        if pid not in _participant_cache:
            obj = objects.get(pid, {})
            ocel_type = obj.get("type", "CA")
            _participant_cache[pid] = Participant(
                ocel_id=pid,
                ocel_type=ocel_type,
                display_name=_display_name(ocel_type, pid),
                bpmn_id=_xml_id("P", pid),
            )
        return _participant_cache[pid]

    # --- Build message objects ---
    def _get_message(msg_obj_id: str, initiator_id: str) -> Message:
        obj = objects.get(msg_obj_id, {})
        source_id = _rel(obj, _SOURCE)
        target_id = _rel(obj, _TARGET)
        is_init = source_id == initiator_id
        source = _get_participant(source_id) if source_id else _get_participant(initiator_id)
        target = _get_participant(target_id) if target_id else _get_participant(initiator_id)
        msg_bpmn_id = _xml_id("Msg", msg_obj_id)
        return Message(
            ocel_id=msg_obj_id,
            name=", ".join(_type_attrs.get(obj.get("type", ""), [])) or obj.get("type", "call"),
            is_initiating=is_init,
            source=source,
            target=target,
            bpmn_id=msg_bpmn_id,
            mf_id=_xml_id("MF", msg_obj_id),
        )

    # --- Build a ChoreoTask from an event ---
    def _build_task(event: dict) -> ChoreoTask:
        initiator_id = _rel(event, _INITIATOR) or ""
        participant_id = _rel(event, _PARTICIPANT) or ""
        msg_ids = _rels(event, _MESSAGE)

        initiator = _get_participant(initiator_id) if initiator_id else _get_participant(participant_id)
        participant = _get_participant(participant_id) if participant_id else initiator

        messages = [_get_message(mid, initiator_id) for mid in msg_ids]
        initiating_msg = next((m for m in messages if m.is_initiating), None)
        returning_msg = next((m for m in messages if not m.is_initiating), None)

        return ChoreoTask(
            bpmn_id=_xml_id("Task", event["id"]),
            name=event["type"],
            initiator=initiator,
            participant=participant,
            initiating_msg=initiating_msg,
            returning_msg=returning_msg,
            trace_order=_trace_order(event),
        )

    # --- Build a SubChoreo from a scoping object ---
    def _build_scope(scope_id: str) -> SubChoreo:
        scope_obj = scope_objects[scope_id]
        name = _obj_attr(scope_obj, "name") or scope_obj.get("type", "subchoreographyInstance")

        # Collect direct child elements: task events + nested scopes
        direct_events = scope_events.get(scope_id, [])
        child_scope_ids = parent_to_children.get(scope_id, [])

        children = _build_level(direct_events, child_scope_ids)

        return SubChoreo(
            bpmn_id=_xml_id("Sub", scope_id),
            name=name,
            scope_ocel_id=scope_id,
            children=children,
        )

    # --- Build a level: interleave tasks and child scopes, sorted ---
    def _build_level(
        events: list[dict],
        child_scope_ids: list[str],
    ) -> list[ChoreoTask | SubChoreo]:
        # Build tasks
        task_items: list[tuple[object, ChoreoTask | SubChoreo]] = []
        for event in events:
            task = _build_task(event)
            sort_val = _sort_key(event)
            task_items.append((sort_val, task))

        # Build child scopes, positioned by their earliest event's sort key
        for cid in child_scope_ids:
            sub = _build_scope(cid)
            sort_val = _scope_sort_key(cid, _sort_key)
            task_items.append((sort_val, sub))

        # Sort all elements together
        task_items.sort(key=lambda x: x[0])
        return [item for _, item in task_items]

    # --- Determine a scope's sort key from its earliest contained event ---
    def _scope_sort_key(scope_id: str, key_fn: object) -> object:
        """Return the minimum sort key among all events (recursively)
        contained in this scope."""
        direct = scope_events.get(scope_id, [])
        keys = [key_fn(e) for e in direct]
        for cid in parent_to_children.get(scope_id, []):
            keys.append(_scope_sort_key(cid, key_fn))
        return min(keys) if keys else ""

    # --- Build top-level elements ---
    elements = _build_level(top_level_events, list(root_scope_ids))

    return ChoreoInstance(
        ocel_id=instance_id,
        short_id=_short_id(instance_id),
        elements=elements,
    )
