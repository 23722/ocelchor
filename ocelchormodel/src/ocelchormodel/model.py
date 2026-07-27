"""Choreography domain model dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Participant:
    """A choreography participant (EOA or contract address)."""

    ocel_id: str       # OCEL object ID (Ethereum address)
    ocel_type: str     # OCEL object type ("EOA", "CA", "SwapPool", …)
    display_name: str  # Human-readable name for BPMN rendering
    bpmn_id: str       # Valid XML NCName derived from ocel_id


@dataclass
class Message:
    """A choreography message type (request or response call object).

    Maps to a single ``bpmn2:message`` element. The corresponding
    ``bpmn2:messageFlow`` elements are emitted per-choreography-task, not
    per-message, so that the same message object referenced by N events
    yields N distinct message flows (each carrying the same ``messageRef``).
    """

    ocel_id: str        # OCEL object ID (e.g. "call:req:abcabcab:root")
    name: str           # OCEL object type (e.g. "swap call")
    is_initiating: bool # True = request from initiator; False = response
    source: Participant
    target: Participant
    bpmn_id: str        # Valid XML NCName for the message definition


@dataclass
class ChoreoTask:
    """An atomic choreography task (maps to a single OCEL event)."""

    bpmn_id: str
    name: str
    initiator: Participant
    participant: Participant
    initiating_msg: Message | None
    returning_msg: Message | None
    trace_order: int


@dataclass
class SubChoreo:
    """A subchoreography scope (maps to a subchoreographyInstance scoping object)."""

    bpmn_id: str
    name: str
    scope_ocel_id: str  # OCEL object ID of the subchoreographyInstance scope object
    children: list[ChoreoTask | SubChoreo] = field(default_factory=list)


@dataclass
class ChoreoInstance:
    """A single choreography instance extracted from an OCEL log."""

    ocel_id: str   # "choreographyInstance:0x…"
    short_id: str  # last 8 hex chars of the tx hash, for display
    elements: list[ChoreoTask | SubChoreo] = field(default_factory=list)
    # Events whose unrecorded endpoint is rendered as an empty phantom band
    # (reported by the CLI in a per-instance warnings note; the validator
    # flags the underlying gap as C2/C3 + C5/C6).
    phantom_events: list[str] = field(default_factory=list)
