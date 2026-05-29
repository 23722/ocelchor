"""XES 1.0 (IEEE 1849-2016) parser using the standard library only.

Reads collaborative event logs by Peña, Delgado, Calegari (open-coal /
bpmncollaborativepm). Returns a list of :class:`XesTrace`.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from xescol2ocelchor.models import XesEvent, XesTrace

logger = logging.getLogger(__name__)

# XES 1.0 namespace
_XES_NS = "http://www.xes-standard.org"

# Tokens treated as "absent" for optional string attributes (spec §8)
_ABSENT_TOKENS = {None, "", "None", "-"}


def load_xes(path: Path) -> list[XesTrace]:
    """Parse a XES file and return its traces."""
    tree = ET.parse(path)
    root = tree.getroot()
    return [_parse_trace(t) for t in _findall(root, "trace")]


def _findall(elem: ET.Element, local: str) -> list[ET.Element]:
    """Find direct children by local tag name (namespace-agnostic)."""
    return [e for e in elem if _local(e.tag) == local]


def _local(tag: str) -> str:
    """Strip the XML namespace from a tag, returning the local name."""
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _parse_trace(trace_elem: ET.Element) -> XesTrace:
    """Parse one ``<trace>`` element."""
    attrs = _parse_attributes(trace_elem)
    concept_name = attrs.pop("concept:name", "")
    if not concept_name:
        logger.warning("Trace without concept:name encountered; using empty string")

    events: list[XesEvent] = []
    for i, event_elem in enumerate(_findall(trace_elem, "event")):
        events.append(_parse_event(event_elem, doc_order=i))

    return XesTrace(concept_name=concept_name, events=events, attributes=attrs)


def _parse_event(event_elem: ET.Element, doc_order: int) -> XesEvent:
    """Parse one ``<event>`` element."""
    attrs = _parse_attributes(event_elem)

    concept_name = attrs.pop("concept:name", "")
    timestamp_raw = attrs.pop("time:timestamp", None)
    if not timestamp_raw:
        raise ValueError(
            f"Event {doc_order} missing time:timestamp (concept:name={concept_name!r})"
        )
    timestamp = _parse_iso_timestamp(timestamp_raw)
    org_group = attrs.pop("org:group", "")

    msg_type = _coalesce_absent(attrs.pop("msgType", None))
    msg_instance_id = _coalesce_absent(attrs.pop("msgInstanceId", None))
    msg_name = _coalesce_absent(attrs.pop("msgName", None))
    # msgFlow can also carry the message name; not currently surfaced (spec §8)
    msg_flow = _coalesce_absent(attrs.pop("msgFlow", None))
    if msg_name is None and msg_flow is not None:
        msg_name = msg_flow

    return XesEvent(
        concept_name=concept_name,
        timestamp=timestamp,
        org_group=org_group,
        doc_order=doc_order,
        msg_type=msg_type,
        msg_instance_id=msg_instance_id,
        msg_name=msg_name,
        attributes=attrs,
    )


def _parse_attributes(elem: ET.Element) -> dict[str, str]:
    """Collect XES attribute children of an element into a flat string dict.

    XES attribute element tags (``string``, ``date``, ``int``, ``float``,
    ``boolean``, ``id``) each carry ``key`` and ``value`` attributes. We
    preserve the raw value as a string; type coercion happens at the call
    site for the fields that need it (``time:timestamp`` only).

    Nested attributes (``<string><string ... /></string>``) are not produced
    by Fluxicon Disco for these datasets and are not handled.
    """
    out: dict[str, str] = {}
    for child in elem:
        tag = _local(child.tag)
        if tag in {"string", "date", "int", "float", "boolean", "id"}:
            key = child.get("key")
            value = child.get("value")
            if key is None:
                continue
            out[key] = value if value is not None else ""
    return out


def _coalesce_absent(value: str | None) -> str | None:
    """Map XES 'missing' sentinels (per spec §8) to None."""
    if value in _ABSENT_TOKENS:
        return None
    return value


def _parse_iso_timestamp(raw: str) -> datetime:
    """Parse an ISO 8601 timestamp, accepting both 'Z' and offset forms."""
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)
