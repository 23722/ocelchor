"""OCEL 2.0 JSON assembly and output.

Mirrors ``trace2choreo/ocel.py``: ``objectTypes`` and ``eventTypes`` are
auto-derived from instances; values are serialised as strings.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from xescol2ocelchor.models import OcelEvent, OcelObject

# Sentinel "time" attached to static object attributes (the value never changes).
_STATIC_ATTR_TIME = "1970-01-01T00:00:00Z"


def build_ocel(events: list[OcelEvent], objects: list[OcelObject]) -> dict:
    """Assemble an OCEL 2.0 JSON dict from events and objects."""
    return {
        "objectTypes": _build_object_types(objects),
        "eventTypes": _build_event_types(events),
        "objects": [_serialize_object(o) for o in objects],
        "events": [_serialize_event(e) for e in events],
    }


def write_ocel(ocel: dict, path: Path) -> None:
    """Write an OCEL 2.0 dict to a JSON file (indented for diffability)."""
    with open(path, "w") as f:
        json.dump(ocel, f, indent=2)


def _build_object_types(objects: list[OcelObject]) -> list[dict]:
    seen: dict[str, set[str]] = {}
    seen_values: dict[tuple[str, str], object] = {}
    for obj in objects:
        seen.setdefault(obj.type, set())
        for k, v in obj.attributes.items():
            seen[obj.type].add(k)
            seen_values.setdefault((obj.type, k), v)
    return [
        {
            "name": type_name,
            "attributes": [
                {"name": a, "type": _attr_type(seen_values.get((type_name, a)))}
                for a in sorted(attr_names)
            ],
        }
        for type_name, attr_names in sorted(seen.items())
    ]


def _build_event_types(events: list[OcelEvent]) -> list[dict]:
    seen: dict[str, set[str]] = {}
    seen_values: dict[tuple[str, str], object] = {}
    for event in events:
        seen.setdefault(event.type, set())
        for k, v in event.attributes.items():
            seen[event.type].add(k)
            seen_values.setdefault((event.type, k), v)
    return [
        {
            "name": type_name,
            "attributes": [
                {"name": a, "type": _attr_type(seen_values.get((type_name, a)))}
                for a in sorted(attr_names)
            ],
        }
        for type_name, attr_names in sorted(seen.items())
    ]


def _attr_type(val: object) -> str:
    """Infer the OCEL attribute primitive type from a sample value."""
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "float"
    return "string"


def _serialize_event(event: OcelEvent) -> dict:
    result: dict = {
        "id": event.id,
        "type": event.type,
        "time": _format_time(event.time),
    }
    if event.attributes:
        result["attributes"] = [
            {"name": k, "value": str(v)} for k, v in event.attributes.items()
        ]
    if event.e2o:
        result["relationships"] = [
            {"objectId": rel.object_id, "qualifier": rel.qualifier}
            for rel in event.e2o
        ]
    return result


def _serialize_object(obj: OcelObject) -> dict:
    result: dict = {
        "id": obj.id,
        "type": obj.type,
    }
    if obj.attributes:
        result["attributes"] = [
            {"name": k, "value": str(v), "time": _STATIC_ATTR_TIME}
            for k, v in obj.attributes.items()
        ]
    if obj.o2o:
        result["relationships"] = [
            {"objectId": rel.target_id, "qualifier": rel.qualifier}
            for rel in obj.o2o
        ]
    return result


def _format_time(dt: datetime) -> str:
    """Render an aware datetime in UTC with millisecond precision and 'Z' suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
