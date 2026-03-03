"""OCEL 2.0 index builder — pre-computes lookup structures for constraint checking."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OcelIndex:
    """Lookup indexes over raw OCEL 2.0 dict."""

    # Core lookups
    events: dict[str, dict]  # event_id → event dict
    objects: dict[str, dict]  # object_id → object dict

    # E2O relations: event_id → [(object_id, qualifier)]
    e2o: dict[str, list[tuple[str, str]]]

    # O2O relations: source_object_id → [(target_object_id, qualifier)]
    o2o: dict[str, list[tuple[str, str]]]

    # Derived indexes
    choreo_events: list[dict]  # events with E2O qualifier choreo:instance
    contained_events: list[dict]  # events with E2O qualifier choreo:contained-by
    scoping_objects: list[str]  # object IDs of type "Subchoreography"
    instance_objects: list[str]  # object IDs of type "ChoreographyInstance"


def build_index(ocel: dict) -> OcelIndex:
    """Build all lookup indexes from raw OCEL 2.0 dict."""
    # Core lookups
    events = {e["id"]: e for e in ocel["events"]}
    objects = {o["id"]: o for o in ocel["objects"]}

    # E2O relations from event relationships
    e2o: dict[str, list[tuple[str, str]]] = {}
    for e in ocel["events"]:
        rels = []
        for r in e.get("relationships", []):
            rels.append((r["objectId"], r["qualifier"]))
        e2o[e["id"]] = rels

    # O2O relations from object relationships
    o2o: dict[str, list[tuple[str, str]]] = {}
    for o in ocel["objects"]:
        rels = []
        for r in o.get("relationships", []):
            rels.append((r["objectId"], r["qualifier"]))
        if rels:
            o2o[o["id"]] = rels

    # Derived: choreo_events (events with choreo:instance)
    choreo_events = [
        e for e in ocel["events"]
        if any(r["qualifier"] == "choreo:instance" for r in e.get("relationships", []))
    ]

    # Derived: contained_events (events with choreo:contained-by)
    contained_events = [
        e for e in ocel["events"]
        if any(r["qualifier"] == "choreo:contained-by" for r in e.get("relationships", []))
    ]

    # Derived: scoping_objects (Subchoreography type)
    scoping_objects = [
        o["id"] for o in ocel["objects"]
        if o.get("type") == "Subchoreography"
    ]

    # Derived: instance_objects (ChoreographyInstance type)
    instance_objects = [
        o["id"] for o in ocel["objects"]
        if o.get("type") == "ChoreographyInstance"
    ]

    return OcelIndex(
        events=events,
        objects=objects,
        e2o=e2o,
        o2o=o2o,
        choreo_events=choreo_events,
        contained_events=contained_events,
        scoping_objects=scoping_objects,
        instance_objects=instance_objects,
    )
