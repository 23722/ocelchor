"""Trace-to-OCEL transformation logic (choreography mining)."""

from __future__ import annotations

import logging
from datetime import timedelta

from trace2ocelchor.models import (
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


# ---------------------------------------------------------------------------
# Participant-aware event typing (spec §A1 / participant_aware_event_typing_outline.md)
#
# The event type is a participant-aware call key so that equally named function
# calls executed by different contracts are not merged by downstream miners:
#
#     event type = [kind prefix] + activity + " [" + called-contract disc + "]"
#
# Deliberate coarsening (documented for the paper): the discriminator omits
# parameter-type signatures, so overloaded functions on one contract share a
# type. Signature-based discrimination is left as future work.
# ---------------------------------------------------------------------------

def _participant_discriminator(contract_called_name: str | None, address: str) -> str:
    """Called-contract discriminator: the called-contract name, else its address.

    Call sites resolve the name through the LOG-WIDE map
    (_collect_contract_names), not the frame-local field, so event-type
    discriminators and participant object types can never disagree: a contract
    named anywhere in the log carries that name in every discriminator
    (spec I1). Never falls back to a generic type like "CA" (or "EOA") —
    generic types would merge unrelated participants.
    """
    return contract_called_name or address


def _call_key(activity: str, participant: str) -> str:
    """Participant-aware call key shared by event types and scope keys."""
    return f"{activity} [{participant}]"


def _event_type(activity: str, participant: str, kind: str = "atomic") -> str:
    """Event type from the call key plus the event kind prefix."""
    key = _call_key(activity, participant)
    if kind == "request":
        return f"Request {key}"
    if kind == "response":
        return f"Respond to {key}"
    return key


def _make_time(trace: Trace, trace_order: int):
    """Create an event timestamp offset by trace_order milliseconds."""
    return trace.timestamp + timedelta(milliseconds=trace_order)


def _collect_contract_names(traces: list[Trace]) -> dict[str, str]:
    """Address → contractCalledName over ALL traces of the log (first name wins).

    Names can surface anywhere: a contract may first appear unnamed (as the
    root or a caller) and only later as a named callee — possibly in a
    different trace. Collecting names up front keeps object typing consistent
    across the whole log (e.g. the MasterChefV3 root contract, whose name only
    appears on internal frames that call back into it).
    """
    names: dict[str, str] = {}

    def walk(frame: CallFrame) -> None:
        if frame.contract_called_name and frame.to_addr not in names:
            names[frame.to_addr] = frame.contract_called_name
        for child in frame.calls:
            walk(child)

    for trace in traces:
        if trace.contract_called_name and trace.contract_address not in names:
            names[trace.contract_address] = trace.contract_called_name
        for frame in trace.internal_txs:
            walk(frame)
    return names


def _collect_senders(traces: list[Trace]) -> set[str]:
    """All transaction senders of the log (EOAs), collected up front so the
    EOA/contract distinction is deterministic and independent of the order in
    which an address is first encountered (an address may participate in an
    earlier trace before sending its own transaction in a later one)."""
    return {trace.sender for trace in traces}


def _participant_type(address: str, senders: set[str], names: dict[str, str]) -> str:
    """Determine the OCEL object type for a participant address.

    Object type = the participant's role in the choreography, resolved with a
    deterministic, log-wide priority:

        EOA                  the address sends a transaction anywhere in the log
        contractCalledName   named contract (log-wide map, _collect_contract_names)
        <address>            otherwise (identity as the finest assertible role)

    Unnamed contracts deliberately do NOT share a generic ``CA`` type: object
    types feed the discovered models' participant bands, and a generic type
    would collapse distinct contracts into one meaningless band (decision
    revising participant_aware_event_typing_outline.md; the trade-off —
    distinct unnamed contracts never pool into one role — is accepted in
    favour of faithful, readable bands).
    """
    if address in senders:
        return "EOA"
    return names.get(address, address)


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
    names = _collect_contract_names(traces)  # log-wide address → name map
    senders = _collect_senders(traces)        # log-wide sender (EOA) set

    for trace in traces:
        events, objects = _transform_single(trace, seen_participants, senders, names)
        all_events.extend(events)
        all_objects.extend(objects)

    return all_events, all_objects


def _transform_single(
    trace: Trace,
    seen_participants: dict[str, OcelObject],
    senders: set[str],
    names: dict[str, str],
) -> tuple[list[OcelEvent], list[OcelObject]]:
    """Transform a single transaction trace."""
    txid = _tx_hash_id(trace.transaction_hash)
    choreo_inst_id = f"choreographyInstance:{trace.transaction_hash}"

    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    scoping: dict[str, OcelObject] = {}

    if not trace.internal_txs:
        # Section 4.3: empty internalTxs → single choreography task
        e, objs = _create_root_task_simple(trace, txid, choreo_inst_id, seen_participants, senders, names)
        events.append(e)
        objects.extend(objs)
    else:
        # Section 4.3: non-empty internalTxs → request + subchoreography (no response, EOA)
        evts, objs, _ = _create_root_split(trace, txid, choreo_inst_id, seen_participants, scoping, senders, names)
        events.extend(evts)
        objects.extend(objs)

    # Add choreography instance object
    objects.append(OcelObject(id=choreo_inst_id, type="choreographyInstance"))

    return events, objects


def _create_root_task_simple(
    trace: Trace,
    txid: str,
    choreo_inst_id: str,
    seen: dict,
    senders: set[str],
    names: dict[str, str],
) -> tuple[OcelEvent, list[OcelObject]]:
    """Root with no internal calls → single choreography task event."""
    event_id = f"e:{txid}:root"
    req_msg_id = f"call:req:{txid}:root"

    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(trace.sender, "EOA", seen)
    if p:
        objects.append(p)
    # Root contract typed via the log-wide name map (its name may only surface
    # on internal frames calling back into it), else its address.
    p = _make_participant(
        trace.contract_address,
        _participant_type(trace.contract_address, senders, names),
        seen,
    )
    if p:
        objects.append(p)

    # Request message (no response for EOA root)
    objects.append(_make_message(
        req_msg_id, _request_message_type(trace.function_name),
        trace.sender, trace.contract_address,
        attributes=_input_attrs(trace.inputs),
    ))

    # Event
    root_disc = _participant_discriminator(names.get(trace.contract_address), trace.contract_address)
    event = OcelEvent(
        id=event_id,
        type=_event_type(trace.function_name, root_disc),
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
    senders: set[str],
    names: dict[str, str],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Root with internal calls → request event + scoping object, then recurse children."""
    req_event_id = f"e:{txid}:root:request"
    req_msg_id = f"call:req:{txid}:root"
    sub_obj_id = f"subchoreographyInstance:{txid}:root"

    trace_order = 0
    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(trace.sender, "EOA", seen)
    if p:
        objects.append(p)
    # Root contract typed via the log-wide name map (its name may only surface
    # on internal frames calling back into it), else its address.
    p = _make_participant(
        trace.contract_address,
        _participant_type(trace.contract_address, senders, names),
        seen,
    )
    if p:
        objects.append(p)

    # Request message (no response for EOA root)
    objects.append(_make_message(
        req_msg_id, _request_message_type(trace.function_name),
        trace.sender, trace.contract_address,
        attributes=_input_attrs(trace.inputs),
    ))

    # Scoping object — named with the call key (task-label style), so the
    # stored name IS the sub-choreography label downstream (scope-typing
    # rung 1) and matches the event-type discriminator by construction.
    root_disc = _participant_discriminator(names.get(trace.contract_address), trace.contract_address)
    sub_obj = OcelObject(
        id=sub_obj_id, type="subchoreographyInstance",
        attributes={"name": _call_key(trace.function_name, root_disc)},
    )
    objects.append(sub_obj)
    scoping[sub_obj_id] = sub_obj

    # Request event — contained in the root scope it opens (spec I3/A2:
    # the outermost bracket pair is contained in the instance's root scope).
    events.append(OcelEvent(
        id=req_event_id,
        type=_event_type(trace.function_name, root_disc, kind="request"),
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(req_event_id, trace.sender, CHOREO_INITIATOR),
            E2O(req_event_id, trace.contract_address, CHOREO_PARTICIPANT),
            E2O(req_event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(req_event_id, sub_obj_id, CHOREO_CONTAINED_BY),
            E2O(req_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    # Process children in callId order
    for child in trace.internal_txs:
        child_events, child_objects, trace_order = _process_call_frame(
            child, trace, txid, choreo_inst_id, sub_obj_id, seen, trace_order, scoping, senders, names,
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
    senders: set[str],
    names: dict[str, str],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Recursively process a call frame. Returns events, objects, updated trace_order."""
    if frame.calls:
        return _create_subchoreography(
            frame, trace, txid, choreo_inst_id, parent_sub_id, seen, trace_order, scoping, senders, names,
        )
    else:
        events, objects = _create_leaf_task(
            frame, trace, txid, choreo_inst_id, parent_sub_id, seen, trace_order, senders, names,
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
    senders: set[str],
    names: dict[str, str],
) -> tuple[list[OcelEvent], list[OcelObject]]:
    """Create OCEL events/objects for a leaf choreography task (section 4.4)."""
    event_id = f"e:{txid}:{frame.call_id}"
    req_msg_id = f"call:req:{txid}:{frame.call_id}"
    res_msg_id = f"call:res:{txid}:{frame.call_id}"

    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(frame.from_addr, _participant_type(frame.from_addr, senders, names), seen)
    if p:
        objects.append(p)

    p = _make_participant(frame.to_addr, _participant_type(frame.to_addr, senders, names), seen)
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
    disc = _participant_discriminator(names.get(frame.to_addr), frame.to_addr)
    event = OcelEvent(
        id=event_id,
        type=_event_type(frame.activity, disc),
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
    senders: set[str],
    names: dict[str, str],
) -> tuple[list[OcelEvent], list[OcelObject], int]:
    """Create request/response events for a non-leaf call with scoping object."""
    req_event_id = f"e:{txid}:{frame.call_id}:request"
    res_event_id = f"e:{txid}:{frame.call_id}:response"
    req_msg_id = f"call:req:{txid}:{frame.call_id}"
    res_msg_id = f"call:res:{txid}:{frame.call_id}"
    sub_obj_id = f"subchoreographyInstance:{txid}:{frame.call_id}"

    events: list[OcelEvent] = []
    objects: list[OcelObject] = []

    # Participants
    p = _make_participant(frame.from_addr, _participant_type(frame.from_addr, senders, names), seen)
    if p:
        objects.append(p)

    p = _make_participant(frame.to_addr, _participant_type(frame.to_addr, senders, names), seen)
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

    # Scoping object (C14: parent contains child) — named with the call key
    # (task-label style), matching the event-type discriminator by construction
    disc = _participant_discriminator(names.get(frame.to_addr), frame.to_addr)
    sub_obj = OcelObject(
        id=sub_obj_id, type="subchoreographyInstance",
        attributes={"name": _call_key(frame.activity, disc)},
    )
    objects.append(sub_obj)
    scoping[sub_obj_id] = sub_obj

    # Add choreo:contains O2O to the *parent* scoping object
    scoping[parent_sub_id].o2o.append(
        O2O(parent_sub_id, sub_obj_id, CHOREO_CONTAINS)
    )

    # Request event — contained in the scope it opens (spec I3/A2), not the parent
    events.append(OcelEvent(
        id=req_event_id,
        type=_event_type(frame.activity, disc, kind="request"),
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(req_event_id, frame.from_addr, CHOREO_INITIATOR),
            E2O(req_event_id, frame.to_addr, CHOREO_PARTICIPANT),
            E2O(req_event_id, req_msg_id, CHOREO_MESSAGE),
            E2O(req_event_id, sub_obj_id, CHOREO_CONTAINED_BY),
            E2O(req_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    # Recurse into children
    for child in frame.calls:
        child_events, child_objects, trace_order = _process_call_frame(
            child, trace, txid, choreo_inst_id, sub_obj_id, seen, trace_order, scoping, senders, names,
        )
        events.extend(child_events)
        objects.extend(child_objects)

    # Response event (after all children) — contained in the scope it closes (I3/A2)
    events.append(OcelEvent(
        id=res_event_id,
        type=_event_type(frame.activity, disc, kind="response"),
        time=_make_time(trace, trace_order),
        attributes={"trace_order": trace_order},
        e2o=[
            E2O(res_event_id, frame.to_addr, CHOREO_INITIATOR),
            E2O(res_event_id, frame.from_addr, CHOREO_PARTICIPANT),
            E2O(res_event_id, res_msg_id, CHOREO_MESSAGE),
            E2O(res_event_id, sub_obj_id, CHOREO_CONTAINED_BY),
            E2O(res_event_id, choreo_inst_id, CHOREO_INSTANCE),
        ],
    ))
    trace_order += 1

    return events, objects, trace_order
