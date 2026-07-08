"""Shared test fixtures for the ocelchormodel_rad miner."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchormodel_rad import reader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def worked_example_path() -> Path:
    return FIXTURES / "worked_example.json"


@pytest.fixture
def worked_example(worked_example_path):
    return reader.load(worked_example_path)


def single_instance_ocel(ocel: dict, instance_id: str) -> dict:
    """Project an OCEL log to a single choreography instance (events + reachable
    objects), for per-instance round-trip tests (spec §B5/§B7)."""
    events = [
        e for e in ocel["events"]
        if any(r["qualifier"] == "choreo:instance" and r["objectId"] == instance_id
               for r in e.get("relationships", []))
    ]
    keep = {instance_id}
    for e in events:
        for r in e.get("relationships", []):
            keep.add(r["objectId"])
    by_id = {o["id"]: o for o in ocel["objects"]}
    for oid in list(keep):
        for r in by_id.get(oid, {}).get("relationships", []):
            keep.add(r["objectId"])
    return {
        "objectTypes": ocel.get("objectTypes", []),
        "eventTypes": ocel.get("eventTypes", []),
        "objects": [o for o in ocel["objects"] if o["id"] in keep],
        "events": events,
    }
