"""XES → OCEL 2.0 choreography extraction (spec §4).

Transformation rules:

- One ``send`` event in a trace becomes exactly one choreography task event.
- The receiver(s) of that task are the distinct ``org:group`` values of all
  ``receive`` events sharing the same ``(trace, msgInstanceId)``.
- Unmatched sends keep their initiator and message but get no
  ``choreo:participant`` / ``choreo:target`` edges (validator surfaces them).
- Internal events (no ``msgType``) are dropped by default.

See ``IMPLEMENTATION_SPEC_xes_to_ocel_choreography.md`` §4 for the design.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from xescol2ocelchor.models import (
    CHOREO_INITIATOR,
    CHOREO_INSTANCE,
    CHOREO_MESSAGE,
    CHOREO_PARTICIPANT,
    CHOREO_SOURCE,
    CHOREO_TARGET,
    COLLAB_INSTANCE,
    E2O,
    O2O,
    OcelEvent,
    OcelObject,
    XesEvent,
    XesTrace,
)

logger = logging.getLogger(__name__)

# Strip a trailing _<digits> suffix when deriving a message type from msgInstanceId
_MSG_TYPE_SUFFIX_RE = re.compile(r"_\d+$")


@dataclass
class ExtractionStats:
    """Per-extraction counters used by tests and the optional summary print.

    The "send_events" counts are per-task-event; the "msg_ids" counts are per
    distinct ``(trace, msgInstanceId)``. When a flagged flow repeats within a
    trace, the event-level count exceeds the msg-id count (see spec §4.4).
    Spec §5's expected flag counts use the msg-id level.
    """
    traces: int = 0
    task_events: int = 0
    message_objects: int = 0
    participant_objects: int = 0
    internal_events_dropped: int = 0
    internal_events_kept: int = 0
    unmatched_send_events: int = 0
    broadcast_send_events: int = 0
    unmatched_msg_ids: int = 0
    broadcast_msg_ids: int = 0
    e2o: int = 0
    o2o: int = 0
    participants_by_name: list[str] = field(default_factory=list)


def extract(
    traces: list[XesTrace],
    keep_internal_events: bool = False,
) -> tuple[list[OcelEvent], list[OcelObject], ExtractionStats]:
    """Transform parsed XES traces into OCEL 2.0 events and objects.

    Returns ``(events, objects, stats)``. Participants are deduplicated
    globally across traces (one object per ``org:group`` name).
    """
    all_events: list[OcelEvent] = []
    all_objects: list[OcelObject] = []
    seen_participants: dict[str, OcelObject] = {}
    stats = ExtractionStats(traces=len(traces))

    for trace in traces:
        _transform_trace(
            trace, seen_participants, all_events, all_objects, stats,
            keep_internal_events=keep_internal_events,
        )

    # Deterministic output: stable ordering for diffability (spec §8)
    all_events.sort(key=lambda e: e.id)
    all_objects.sort(key=lambda o: (o.type, o.id))

    stats.participant_objects = len(seen_participants)
    stats.participants_by_name = sorted(seen_participants.keys())
    stats.e2o = sum(len(e.e2o) for e in all_events)
    stats.o2o = sum(len(o.o2o) for o in all_objects)
    return all_events, all_objects, stats


def _transform_trace(
    trace: XesTrace,
    seen_participants: dict[str, OcelObject],
    events_out: list[OcelEvent],
    objects_out: list[OcelObject],
    stats: ExtractionStats,
    keep_internal_events: bool = False,
) -> None:
    """Convert one trace and append produced events/objects into the buffers."""
    inst_id = _instance_id(trace.concept_name)

    # The choreography instance object exists once per trace.
    objects_out.append(OcelObject(id=inst_id, type="choreographyInstance"))

    # Flat case-notion object: only created when keeping internal events.
    # When active, every event in this trace (task + internal) is linked to it
    # via collab:instance — outside of E_T, so no choreography constraints fire.
    collab_inst_id: str | None = None
    if keep_internal_events:
        collab_inst_id = _collaboration_instance_id(trace.concept_name)
        objects_out.append(OcelObject(id=collab_inst_id, type="collaborationInstance"))

    # Build per-msgInstanceId lookup of receivers within this trace.
    receivers_by_msg: dict[str, list[str]] = {}
    for ev in trace.events:
        if ev.msg_type == "receive" and ev.msg_instance_id:
            # Distinct receivers per (trace, msgInstanceId), preserving order.
            existing = receivers_by_msg.setdefault(ev.msg_instance_id, [])
            if ev.org_group and ev.org_group not in existing:
                existing.append(ev.org_group)

    # Iterate sends in (timestamp, doc_order) order per spec §4.7.
    sends = [e for e in trace.events if e.msg_type == "send"]
    sends.sort(key=lambda e: (e.timestamp, e.doc_order))

    # Per-msg-id flag counts (one increment per distinct (trace, msgId)).
    # Also used to dedupe the message OcelObject: a msgInstanceId reused
    # across sends in the same trace refers to the SAME message object
    # (spec §4.6 keys messages by (trace, msgInstanceId)).
    seen_msg_ids: dict[str, OcelObject] = {}
    for ev in sends:
        mid = ev.msg_instance_id or ev.concept_name
        receivers = receivers_by_msg.get(mid, [])
        if mid not in seen_msg_ids:
            if not receivers:
                stats.unmatched_msg_ids += 1
            elif len(receivers) > 1:
                stats.broadcast_msg_ids += 1
        _emit_task(
            trace, ev, receivers, inst_id, collab_inst_id,
            seen_participants, seen_msg_ids, events_out, objects_out, stats,
        )

    # Internal events: drop or keep, depending on flag.
    for ev in trace.events:
        if ev.msg_type is None:
            if keep_internal_events:
                _emit_internal_event(trace, ev, collab_inst_id, events_out, stats)
            else:
                stats.internal_events_dropped += 1


def _emit_task(
    trace: XesTrace,
    send: XesEvent,
    receivers: list[str],
    inst_id: str,
    collab_inst_id: str | None,
    seen_participants: dict[str, OcelObject],
    seen_msg_ids: dict[str, OcelObject],
    events_out: list[OcelEvent],
    objects_out: list[OcelObject],
    stats: ExtractionStats,
) -> None:
    """Emit one choreography task event from a single send event."""
    sender = send.org_group
    if not sender:
        logger.warning(
            "Send event %r in trace %r has no org:group; skipping",
            send.concept_name, trace.concept_name,
        )
        return

    if not receivers:
        stats.unmatched_send_events += 1
    elif len(receivers) > 1:
        stats.broadcast_send_events += 1

    # Participant objects (global dedup).
    initiator_obj = _ensure_participant(sender, seen_participants, objects_out)
    receiver_objs = [
        _ensure_participant(r, seen_participants, objects_out) for r in receivers
    ]

    # Message object: one per (trace, msgInstanceId) — reused across repeat
    # sends of the same id within the same trace.
    mid_key = send.msg_instance_id or send.concept_name
    msg_id = _message_id(trace.concept_name, mid_key)
    msg_obj = seen_msg_ids.get(mid_key)
    if msg_obj is None:
        msg_obj = OcelObject(
            id=msg_id, type=_message_type(send),
            o2o=[O2O(msg_id, initiator_obj.id, CHOREO_SOURCE)] + [
                O2O(msg_id, r.id, CHOREO_TARGET) for r in receiver_objs
            ],
        )
        seen_msg_ids[mid_key] = msg_obj
        objects_out.append(msg_obj)
        stats.message_objects += 1

    # Event.
    event_id = _event_id(trace.concept_name, send.doc_order)
    event_attrs = _event_attributes(send)
    e2o = [
        E2O(event_id, inst_id, CHOREO_INSTANCE),
        E2O(event_id, initiator_obj.id, CHOREO_INITIATOR),
        E2O(event_id, msg_id, CHOREO_MESSAGE),
    ] + [E2O(event_id, r.id, CHOREO_PARTICIPANT) for r in receiver_objs]
    if collab_inst_id is not None:
        e2o.append(E2O(event_id, collab_inst_id, COLLAB_INSTANCE))

    events_out.append(OcelEvent(
        id=event_id,
        type=send.concept_name,
        time=send.timestamp,
        attributes=event_attrs,
        e2o=e2o,
    ))
    stats.task_events += 1


def _emit_internal_event(
    trace: XesTrace,
    ev: XesEvent,
    collab_inst_id: str | None,
    events_out: list[OcelEvent],
    stats: ExtractionStats,
) -> None:
    """Emit one OCEL event for a kept internal (non-message) XES event.

    The event carries no choreo:* qualifiers — it is intentionally outside E_T
    (paper Definition 3) so it does not trigger C0/C2/C3. Its only E2O link is
    to the trace's collaborationInstance via collab:instance.
    """
    if collab_inst_id is None:
        # Defensive — _transform_trace only calls this when the flag is active.
        return
    event_id = _event_id(trace.concept_name, ev.doc_order)
    attrs: dict = {"concept:name": ev.concept_name, "org:group": ev.org_group}
    for k, v in ev.attributes.items():
        attrs.setdefault(k, v)
    events_out.append(OcelEvent(
        id=event_id,
        type=ev.concept_name,
        time=ev.timestamp,
        attributes=attrs,
        e2o=[E2O(event_id, collab_inst_id, COLLAB_INSTANCE)],
    ))
    stats.internal_events_kept += 1


def _ensure_participant(
    name: str,
    seen: dict[str, OcelObject],
    objects_out: list[OcelObject],
) -> OcelObject:
    """Return the global participant object for ``name``, creating it on first use."""
    if name in seen:
        return seen[name]
    obj = OcelObject(id=_participant_id(name), type="participant",
                     attributes={"name": name})
    seen[name] = obj
    objects_out.append(obj)
    return obj


# ---------------------------------------------------------------------------
# ID and type helpers (spec §4.6, D7, D8)
# ---------------------------------------------------------------------------

def _instance_id(trace_concept_name: str) -> str:
    return f"choreographyInstance:{trace_concept_name}"


def _collaboration_instance_id(trace_concept_name: str) -> str:
    return f"collaborationInstance:{trace_concept_name}"


def _participant_id(name: str) -> str:
    return f"participant:{name}"


def _message_id(trace_concept_name: str, msg_instance_id: str) -> str:
    return f"message:{trace_concept_name}:{msg_instance_id}"


def _event_id(trace_concept_name: str, doc_order: int) -> str:
    return f"e:{trace_concept_name}:{doc_order}"


def _message_type(send: XesEvent) -> str:
    """Derive a message object type per spec §4.6:

    1. ``msgName`` (or ``msgFlow``, surfaced as ``msg_name`` by the reader);
    2. otherwise the ``msgInstanceId`` stripped of any trailing ``_<digits>``;
    3. otherwise the literal ``message``.
    """
    if send.msg_name:
        return send.msg_name
    if send.msg_instance_id:
        return _MSG_TYPE_SUFFIX_RE.sub("", send.msg_instance_id) or "message"
    return "message"


def _event_attributes(send: XesEvent) -> dict:
    """Preserve XES event metadata as OCEL event attributes (D9)."""
    out: dict = {"concept:name": send.concept_name, "org:group": send.org_group}
    if send.msg_instance_id:
        out["msgInstanceId"] = send.msg_instance_id
    if send.msg_name:
        out["msgName"] = send.msg_name
    # Carry forward any other XES attributes that survived the reader's pop()s.
    for k, v in send.attributes.items():
        out.setdefault(k, v)
    return out
