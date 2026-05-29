"""Data models and choreography qualifier constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# Choreography qualifier constants (E2O and O2O)
# ---------------------------------------------------------------------------

CHOREO_INITIATOR = "choreo:initiator"
CHOREO_PARTICIPANT = "choreo:participant"
CHOREO_MESSAGE = "choreo:message"
CHOREO_INSTANCE = "choreo:instance"
CHOREO_SOURCE = "choreo:source"
CHOREO_TARGET = "choreo:target"


# ---------------------------------------------------------------------------
# XES input models
# ---------------------------------------------------------------------------

@dataclass
class XesEvent:
    """A single XES event with the choreography-relevant fields surfaced.

    Standard XES fields are extracted into named attributes; everything else
    (e.g. ``lifecycle:transition``, ``act``, ``msgProtocol``) is kept in
    ``attributes`` for verbatim preservation on the resulting OCEL event.
    """
    concept_name: str
    timestamp: datetime
    org_group: str
    doc_order: int  # tiebreaker per spec §4.7
    msg_type: str | None = None  # "send" / "receive" / None (internal)
    msg_instance_id: str | None = None
    msg_name: str | None = None
    attributes: dict = field(default_factory=dict)


@dataclass
class XesTrace:
    """A single XES trace, i.e. one choreography instance."""
    concept_name: str
    events: list[XesEvent] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)


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
