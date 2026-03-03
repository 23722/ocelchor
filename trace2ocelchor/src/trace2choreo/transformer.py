"""Trace-to-OCEL transformation logic (choreography mining)."""

from __future__ import annotations

import logging
from datetime import timedelta

from trace2choreo.models import (
    CHOREO_CONTAINED_BY,
    CHOREO_CONTAINS,
    CHOREO_INITIATOR,
    CHOREO_INSTANCE,
    CHOREO_MESSAGE,
    CHOREO_PARTICIPANT,
    CHOREO_SOURCE,
    CHOREO_TARGET,
    CallFrame,
    E2O,
    O2O,
    OcelEvent,
    OcelObject,
    Trace,
)

log = logging.getLogger(__name__)


def _tx_hash_id(tx_hash: str) -> str:
    """Full transaction hash without 0x prefix, used as the ID component."""
    return tx_hash.removeprefix("0x")


def _make_time(trace: Trace, trace_order: int):
    """Create an event timestamp offset by trace_order milliseconds."""
    return trace.timestamp + timedelta(milliseconds=trace_order)


def _participant_type(trace: Trace, address: str) -> str:
    """Determine the OCEL object type for a participant address."""
    if address == trace.sender:
        return "EOA"
    return "CA"


def _request_message_type(activity: str) -> str:
    """Request message object type: '<activity> call'."""
    return f"{activity} call"


def _response_message_type(activity: str) -> str:
    """Response message object type: '<activity> call response'."""
    return f"{activity} call response"


def _make_participant(address: str, obj_type: str, seen: dict) -> OcelObject | None:
    """Create a participant object if not already seen. Returns None if duplicate."""
    if address in seen:
        return None
    obj = OcelObject(id=address, type=obj_type)
    seen[address] = obj
    return obj


def _make_message(
    msg_id: str,
    msg_type: str,
    source: str,
    target: str,
    attributes: dict | None = None,
) -> OcelObject:
    """Create a message object with source/target O2O relations and optional attributes."""
    return OcelObject(
        id=msg_id,
        type=msg_type,
        attributes=attributes or {},
        o2o=[
            O2O(source_id=msg_id, target_id=source, qualifier=CHOREO_SOURCE),
            O2O(source_id=msg_id, target_id=target, qualifier=CHOREO_TARGET),
        ],
    )


def _input_attrs(params, inputs_call=None) -> dict:
    """Build attribute dict from decoded input params, falling back to raw inputsCall."""
    if params:
        return {p.name: p.value for p in params}
    if inputs_call:
        return {"inputsCall": inputs_call}
    return {}


def _output_attrs(output) -> dict:
    """Build attribute dict from a call output value (present even when empty/None)."""
    return {"output": output}


def transform_traces(
    traces: list[Trace],
    call_types: set[str] | None = None,
    include_reverted: bool = False,
    include_metadata: bool = False,
) -> tuple[list[OcelEvent], list[OcelObject]]:
    """Transform parsed traces into OCEL 2.0 events and objects.

    # TODO (future): implement call_types filtering — skip CallFrames whose
    #   call_type is not in the provided set (requirements.md §4.7).
    # TODO (future): implement include_reverted — skip/include call frames
    #   with a non-empty error field (requirements.md §4.8).
    # TODO (future): implement include_metadata — attach gasUsed, value,
    #   callId, depth, blockNumber as event attributes (requirements.md §5.2).
    """
    if not traces:
        return [], []

    all_events: list[OcelEvent] = []
    all_objects: list[OcelObject] = []
    seen_participants: dict[str, OcelObject] = {}

    for trace in traces:
        events, objects = _transform_single(trace, seen_participants)
        all_events.extend(events)
        all_objects.extend(objects)

    return all_events, all_objects


def _transform_single(
    trace: Trace,
    seen_participants: dict[str, OcelObject],
) -> tuple[list[OcelEvent], list[OcelObject]]:
    """Transform a single transaction trace."""
    txid = _tx_hash_id(trace.transaction_hash)
    choreo_inst_id = f"choreoInst:{trace.transaction_hash}"

    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    scoping: dict[str, OcelObject] = {}

    if not trace.internal_txs:
        # Section 4.3: empty internalTxs → single choreography task
        e, objs = _create_root_task_simple(trace, txid, choreo_inst_id, seen_participants)
        events.append(e)
        objects.extend(objs)
    else:
        # Section 4.3: non-empty internalTxs → request + subchoreography (no response, EOA)
        evts, objs, _ = _create_root_split(trace, txid, choreo_inst_id, seen_participants, scoping)
        events.extend(evts)
        objects.extend(objs)

    # Add choreography instance object
    objects.append(OcelObject(id=choreo_inst_id, type="ChoreographyInstance"))

    return events, objects


def _create_root_task_simple(
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    seen: dict,
) -> tuple[OcelEvent, list[OcelObject]]:
    """Root with no internal calls → single choreography task event."""
    event_id = f"e:{txid}:root"
    req_msg_id = f"call:req:{txid}:root"

    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(trace.sender, "EOA", seen)
    if p:
        objects.append(p)
    p = _make_participant(trace.contract_address, "CA", seen)
    if p:
        objects.append(p)

    # Request message (no response for EOA root)
    objects.append(_make_message(
        req_msg_id, _request_message_type(trace.function_name),
        trace.sender, trace.contract_address,
        attributes=_input_attrs(trace.inputs),
    ))

    # Event
    event = OcelEvent(
        id=event_id,
        type=trace.function_name,
        time=_make_time(trace, 0),
        attributes={"trace_order": 0},
        e2o=[
            E2O(event_id, trace.sender, CHOREO_INITIATOR),
            E2O(event_id, trace.contract_address, CHOREO_PARTICIPANT),
            E2O(event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    )

    return event, objects


def _create_root_split(
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    seen: dict,
    scoping: dict[str, OcelObject],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Root with internal calls → request event + scoping object, then recurse children."""
    req_event_id = f"e:{txid}:root:request"
    req_msg_id = f"call:req:{txid}:root"
    sub_obj_id = f"sub:{txid}:root"

    trace_order = 0
    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(trace.sender, "EOA", seen)
    if p:
        objects.append(p)
    p = _make_participant(trace.contract_address, "CA", seen)
    if p:
        objects.append(p)

    # Request message (no response for EOA root)
    objects.append(_make_message(
        req_msg_id, _request_message_type(trace.function_name),
        trace.sender, trace.contract_address,
        attributes=_input_attrs(trace.inputs),
    ))

    # Scoping object
    sub_obj = OcelObject(
        id=sub_obj_id, type="Subchoreography",
        attributes={"name": f"subchoreography {trace.function_name}"},
    )
    objects.append(sub_obj)
    scoping[sub_obj_id] = sub_obj

    # Request event (no choreo:contained-by — outermost, no parent scope)
    events.append(OcelEvent(
        id=req_event_id,
        type=f"Request {trace.function_name}",
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(req_event_id, trace.sender, CHOREO_INITIATOR),
            E2O(req_event_id, trace.contract_address, CHOREO_PARTICIPANT),
            E2O(req_event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(req_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    # Process children in callId order
    for child in trace.internal_txs:
        child_events, child_objects, trace_order = _process_call_frame(
            child, trace, txid, choreo_inst_id, sub_obj_id, seen, trace_order, scoping,
        )
        events.extend(child_events)
        objects.extend(child_objects)

    return events, objects, trace_order


def _process_call_frame(
    frame: CallFrame,
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    parent_sub_id: str,
    seen: dict,
    trace_order: int,
    scoping: dict[str, OcelObject],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Recursively process a call frame. Returns events, objects, updated trace_order."""
    if frame.calls:
        return _create_subchoreography(
            frame, trace, txid, choreo_inst_id, parent_sub_id, seen, trace_order, scoping,
        )
    else:
        events, objects = _create_leaf_task(
            frame, trace, txid, choreo_inst_id, parent_sub_id, seen, trace_order,
        )
        return events, objects, trace_order + 1


def _create_leaf_task(
    frame: CallFrame,
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    parent_sub_id: str,
    seen: dict,
    trace_order: int,
) -> tuple[list[OcelEvent], list[OcelObject]]:
    """Create OCEL events/objects for a leaf choreography task (section 4.4)."""
    event_id = f"e:{txid}:{frame.call_id}"
    req_msg_id = f"call:req:{txid}:{frame.call_id}"
    res_msg_id = f"call:res:{txid}:{frame.call_id}"

    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(frame.from_addr, _participant_type(trace, frame.from_addr), seen)
    if p:
        objects.append(p)

    to_type = frame.contract_called_name or _participant_type(trace, frame.to_addr)
    p = _make_participant(frame.to_addr, to_type, seen)
    if p:
        objects.append(p)

    # Request + response messages
    objects.append(_make_message(
        req_msg_id, _request_message_type(frame.activity),
        frame.from_addr, frame.to_addr,
        attributes=_input_attrs(frame.inputs, frame.inputs_call),
    ))
    objects.append(_make_message(
        res_msg_id, _response_message_type(frame.activity),
        frame.to_addr, frame.from_addr,
        attributes=_output_attrs(frame.output),
    ))

    # Single event with both messages
    event = OcelEvent(
        id=event_id,
        type=frame.activity,
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(event_id, frame.from_addr, CHOREO_INITIATOR),
            E2O(event_id, frame.to_addr, CHOREO_PARTICIPANT),
            E2O(event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(event_id, res_msg_id, CHOREO_MESSAGE),
            E2O(event_id, parent_sub_id, CHOREO_CONTAINED_BY),
            E2O(event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    )

    return [event], objects


def _create_subchoreography(
    frame: CallFrame,
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    parent_sub_id: str,
    seen: dict,
    trace_order: int,
    scoping: dict[str, OcelObject],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Create request/response events for a non-leaf call with scoping object."""
    req_event_id = f"e:{txid}:{frame.call_id}:request"
    res_event_id = f"e:{txid}:{frame.call_id}:response"
    req_msg_id = f"call:req:{txid}:{frame.call_id}"
    res_msg_id = f"call:res:{txid}:{frame.call_id}"
    sub_obj_id = f"sub:{txid}:{frame.call_id}"

    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(frame.from_addr, _participant_type(trace, frame.from_addr), seen)
    if p:
        objects.append(p)

    to_type = frame.contract_called_name or _participant_type(trace, frame.to_addr)
    p = _make_participant(frame.to_addr, to_type, seen)
    if p:
        objects.append(p)

    # Messages
    objects.append(_make_message(
        req_msg_id, _request_message_type(frame.activity),
        frame.from_addr, frame.to_addr,
        attributes=_input_attrs(frame.inputs, frame.inputs_call),
    ))
    objects.append(_make_message(
        res_msg_id, _response_message_type(frame.activity),
        frame.to_addr, frame.from_addr,
        attributes=_output_attrs(frame.output),
    ))

    # Scoping object (C14: parent contains child)
    sub_obj = OcelObject(
        id=sub_obj_id, type="Subchoreography",
        attributes={"name": f"subchoreography {frame.activity}"},
    )
    objects.append(sub_obj)
    scoping[sub_obj_id] = sub_obj

    # Add choreo:contains O2O to the *parent* scoping object
    scoping[parent_sub_id].o2o.append(
        O2O(parent_sub_id, sub_obj_id, CHOREO_CONTAINS)
    )

    # Request event
    events.append(OcelEvent(
        id=req_event_id,
        type=f"Request {frame.activity}",
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(req_event_id, frame.from_addr, CHOREO_INITIATOR),
            E2O(req_event_id, frame.to_addr, CHOREO_PARTICIPANT),
            E2O(req_event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(req_event_id, parent_sub_id, CHOREO_CONTAINED_BY),
            E2O(req_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    # Recurse into children
    for child in frame.calls:
        child_events, child_objects, trace_order = _process_call_frame(
            child, trace, txid, choreo_inst_id, sub_obj_id, seen, trace_order, scoping,
        )
        events.extend(child_events)
        objects.extend(child_objects)

    # Response event (after all children)
    events.append(OcelEvent(
        id=res_event_id,
        type=f"Respond to {frame.activity}",
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(res_event_id, frame.to_addr, CHOREO_INITIATOR),
            E2O(res_event_id, frame.from_addr, CHOREO_PARTICIPANT),
            E2O(res_event_id, res_msg_id, CHOREO_MESSAGE),
            E2O(res_event_id, parent_sub_id, CHOREO_CONTAINED_BY),
            E2O(res_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    return events, objects, trace_order
