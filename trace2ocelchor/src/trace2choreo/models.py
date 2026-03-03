"""Data models and choreography qualifier constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Choreography qualifier constants (E2O and O2O)
# ---------------------------------------------------------------------------

CHOREO_INITIATOR = "choreo:initiator"
CHOREO_PARTICIPANT = "choreo:participant"
CHOREO_MESSAGE = "choreo:message"
CHOREO_INSTANCE = "choreo:instance"
CHOREO_SOURCE = "choreo:source"
CHOREO_TARGET = "choreo:target"
CHOREO_CONTAINED_BY = "choreo:contained-by"
CHOREO_CONTAINS = "choreo:contains"


# ---------------------------------------------------------------------------
# Call types
# ---------------------------------------------------------------------------

class CallType(Enum):
    CALL = "CALL"
    STATICCALL = "STATICCALL"
    DELEGATECALL = "DELEGATECALL"
    CREATE = "CREATE"


# ---------------------------------------------------------------------------
# Input models (parsed from JSON)
# ---------------------------------------------------------------------------

@dataclass
class InputParam:
    """A decoded function parameter (top-level or call frame)."""
    name: str
    type: str
    value: object


@dataclass
class CallFrame:
    """A single internal call frame (recursive via calls)."""
    call_id: str
    from_addr: str
    to_addr: str
    call_type: CallType
    depth: int
    activity: str
    output: str | None = None
    inputs: list[InputParam] = field(default_factory=list)
    inputs_call: str | list | None = None
    contract_called_name: str | None = None
    gas: int | None = None
    gas_used: int | None = None
    value: int | float = 0
    calls: list[CallFrame] = field(default_factory=list)
    error: str | None = None


@dataclass
class Trace:
    """A parsed Ethereum transaction trace."""
    transaction_hash: str
    function_name: str
    contract_address: str
    sender: str
    timestamp: datetime
    block_number: int | None = None
    gas_used: int | None = None
    value: int | float = 0
    inputs: list[InputParam] = field(default_factory=list)
    internal_txs: list[CallFrame] = field(default_factory=list)


# ---------------------------------------------------------------------------
# OCEL 2.0 output models
# ---------------------------------------------------------------------------

@dataclass
class E2O:
    """Event-to-object relation with qualifier."""
    event_id: str
    object_id: str
    qualifier: str


@dataclass
class O2O:
    """Object-to-object relation with qualifier."""
    source_id: str
    target_id: str
    qualifier: str


@dataclass
class OcelObject:
    """An OCEL 2.0 object instance."""
    id: str
    type: str
    attributes: dict = field(default_factory=dict)
    o2o: list[O2O] = field(default_factory=list)


@dataclass
class OcelEvent:
    """An OCEL 2.0 event instance."""
    id: str
    type: str
    time: datetime
    attributes: dict = field(default_factory=dict)
    e2o: list[E2O] = field(default_factory=list)
