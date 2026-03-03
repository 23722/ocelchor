"""OCEL 2.0 JSON assembly and output."""

from __future__ import annotations

import json
from pathlib import Path

from trace2choreo.models import OcelEvent, OcelObject


def build_ocel(events: list[OcelEvent], objects: list[OcelObject]) -> dict:
    """Assemble OCEL 2.0 JSON structure from events and objects.

    Returns the top-level dict with objectTypes, eventTypes, objects, events.
    """
    return {
        "objectTypes": _build_object_types(objects),
        "eventTypes": _build_event_types(events),
        "objects": [_serialize_object(o) for o in objects],
        "events": [_serialize_event(e) for e in events],
    }


def write_ocel(ocel: dict, path: Path) -> None:
    """Write OCEL 2.0 dict to a JSON file."""
    with open(path, "w") as f:
        json.dump(ocel, f, indent=2)


def _build_object_types(objects: list[OcelObject]) -> list[dict]:
    """Derive objectTypes declarations from object instances."""
    seen: dict[str, set[str]] = {}
    for obj in objects:
        if obj.type not in seen:
            seen[obj.type] = set()
        for attr_name in obj.attributes:
            seen[obj.type].add(attr_name)

    return [
        {
            "name": type_name,
            "attributes": [
                {"name": a, "type": "string"} for a in sorted(attr_names)
            ],
        }
        for type_name, attr_names in sorted(seen.items())
    ]


def _build_event_types(events: list[OcelEvent]) -> list[dict]:
    """Derive eventTypes declarations from event instances."""
    seen: dict[str, set[str]] = {}
    for event in events:
        if event.type not in seen:
            seen[event.type] = set()
        for attr_name in event.attributes:
            seen[event.type].add(attr_name)

    return [
        {
            "name": type_name,
            "attributes": [
                {"name": a, "type": _infer_attr_type(type_name, a, events)}
                for a in sorted(attr_names)
            ],
        }
        for type_name, attr_names in sorted(seen.items())
    ]


def _infer_attr_type(event_type: str, attr_name: str, events: list[OcelEvent]) -> str:
    """Infer the OCEL attribute type from actual values."""
    for event in events:
        if event.type == event_type and attr_name in event.attributes:
            val = event.attributes[attr_name]
            if isinstance(val, int):
                return "integer"
            if isinstance(val, float):
                return "float"
            if isinstance(val, bool):
                return "boolean"
            return "string"
    return "string"


def _serialize_event(event: OcelEvent) -> dict:
    """Serialize an OcelEvent to OCEL 2.0 JSON format."""
    result: dict = {
        "id": event.id,
        "type": event.type,
        "time": event.time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
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
    """Serialize an OcelObject to OCEL 2.0 JSON format."""
    result: dict = {
        "id": obj.id,
        "type": obj.type,
    }
    if obj.attributes:
        result["attributes"] = [
            {"name": k, "value": str(v), "time": "1970-01-01T00:00:00Z"}
            for k, v in obj.attributes.items()
        ]
    if obj.o2o:
        result["relationships"] = [
            {"objectId": rel.target_id, "qualifier": rel.qualifier}
            for rel in obj.o2o
        ]
    return result
