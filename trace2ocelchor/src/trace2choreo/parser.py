"""JSON input loading and schema normalization."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from trace2choreo.models import CallFrame, CallType, InputParam, Trace

logger = logging.getLogger(__name__)

# Fields required at the transaction level
_REQUIRED_TX_FIELDS = {"transactionHash", "sender", "contractAddress", "functionName", "timestamp"}


def load_trace_file(path: Path) -> list[Trace]:
    """Load a JSON file and return a list of parsed Trace objects.

    Accepts a JSON array of transactions or a single transaction object.
    Skips transactions missing required fields with a warning.
    """
    with open(path) as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        raw = [raw]

    traces = []
    for i, tx in enumerate(raw):
        missing = _REQUIRED_TX_FIELDS - tx.keys()
        if missing:
            logger.warning(
                "Skipping transaction %d in %s: missing fields %s", i, path, missing
            )
            continue
        traces.append(_parse_transaction(tx))
    return traces


def load_trace_dir(path: Path) -> list[Trace]:
    """Load all .json files from a directory."""
    traces = []
    for json_file in sorted(path.glob("*.json")):
        traces.extend(load_trace_file(json_file))
    return traces


def _parse_transaction(raw: dict) -> Trace:
    """Parse a raw transaction dict into a Trace dataclass."""
    return Trace(
        transaction_hash=raw["transactionHash"],
        function_name=raw.get("functionName") or "undefined",
        contract_address=raw["contractAddress"].lower(),
        sender=raw["sender"].lower(),
        timestamp=parse_timestamp(raw["timestamp"]),
        block_number=raw.get("blockNumber"),
        gas_used=raw.get("gasUsed"),
        value=raw.get("value", 0),
        inputs=_parse_top_level_inputs(raw.get("inputs", [])),
        internal_txs=[
            normalize_call_frame(frame)
            for frame in raw.get("internalTxs", [])
        ],
    )


def parse_timestamp(ts_field: dict) -> datetime:
    """Parse a MongoDB-style timestamp {'$date': '...'} to a UTC datetime."""
    date_str = ts_field["$date"]
    # Handle both 'Z' suffix and '+00:00'
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)


def normalize_call_frame(
    raw: dict,
    parent_call_type: CallType | None = None,
    parent_to: str | None = None,
) -> CallFrame:
    """Normalize a raw call frame dict into a CallFrame dataclass.

    Handles field ordering variations, missing optional fields,
    and inputsCall as either hex string or array.

    DELEGATECALL rewrite: if the parent frame was a DELEGATECALL, the child's
    ``from`` address is rewritten to the parent's ``to`` address (the callee
    whose code is actually running).  This applies recursively.
    """
    # activity: default to "undefined" if missing
    activity = raw.get("activity") or "undefined"
    if activity == "undefined":
        logger.warning(
            "Call frame %s has undefined activity", raw.get("callId", "unknown")
        )

    # inputsCall: normalize to keep original form (string or list)
    inputs_call = raw.get("inputsCall")

    # inputs: may be absent (only raw calldata available)
    raw_inputs = raw.get("inputs", [])
    inputs = _parse_call_frame_inputs(raw_inputs) if raw_inputs else []

    from_addr = raw.get("from", "")
    to_addr = raw.get("to", "")
    call_type_str = raw.get("type", "CALL")
    if not from_addr:
        logger.warning("Call frame %s missing 'from' field", raw.get("callId", "unknown"))
    if not to_addr:
        logger.warning("Call frame %s missing 'to' field", raw.get("callId", "unknown"))

    # DELEGATECALL rewrite: parent was DELEGATECALL → child.from = parent.to
    if parent_call_type == CallType.DELEGATECALL and parent_to:
        from_addr = parent_to

    try:
        call_type = CallType(call_type_str)
    except ValueError:
        logger.warning(
            "Call frame %s has unknown call type %r, defaulting to CALL",
            raw.get("callId", "unknown"), call_type_str,
        )
        call_type = CallType.CALL

    # Recurse into nested calls, passing this frame's type and to_addr
    nested_calls = [
        normalize_call_frame(c, parent_call_type=call_type, parent_to=to_addr)
        for c in raw.get("calls", [])
    ]

    return CallFrame(
        call_id=raw.get("callId", "unknown"),
        from_addr=from_addr.lower(),
        to_addr=to_addr.lower(),
        call_type=call_type,
        depth=raw.get("depth", 0),
        activity=activity,
        output=raw.get("output"),
        inputs=inputs,
        inputs_call=inputs_call,
        contract_called_name=raw.get("contractCalledName"),
        gas=raw.get("gas"),
        gas_used=raw.get("gasUsed"),
        value=raw.get("value", 0),
        calls=nested_calls,
        error=raw.get("error"),
    )


def _parse_top_level_inputs(raw_inputs: list) -> list[InputParam]:
    """Parse top-level transaction inputs (inputName/inputValue keys).

    Skips entries that are not dicts or lack the required keys.
    """
    params = []
    for inp in raw_inputs:
        if not isinstance(inp, dict):
            continue
        if "inputName" not in inp or "inputValue" not in inp:
            continue
        params.append(InputParam(
            name=inp["inputName"],
            type=inp.get("type", "string"),
            value=inp["inputValue"],
        ))
    return params


def _parse_call_frame_inputs(raw_inputs: list) -> list[InputParam]:
    """Parse call frame inputs (name/value keys).

    Inputs may be a list of dicts (decoded params) or a list of raw hex
    strings (undecoded calldata).  Only decoded dicts are parsed; raw
    strings are skipped.
    """
    params = []
    for inp in raw_inputs:
        if not isinstance(inp, dict):
            continue
        name = inp["name"]
        if not isinstance(name, str):
            name = str(name)
        params.append(InputParam(
            name=name,
            type=inp["type"],
            value=inp["value"],
        ))
    return params
