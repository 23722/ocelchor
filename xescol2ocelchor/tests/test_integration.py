"""End-to-end integration tests against the spec ground-truth (Appendix A + §5).

These tests are the "Table 2 analogue" verification (per decision D3): instead
of writing a Table 2 report at runtime, the per-dataset counts are asserted
here against the values published in the implementation spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from xescol2ocelchor.extractor import extract
from xescol2ocelchor.reader import load_xes

DATA = Path(__file__).parent.parent / "data" / "input"


# Spec Appendix A (plain-log ground truth) + §5 expected flag profile.
# (traces, internal_events_dropped, participants_set, unmatched_sends, broadcast_msg_ids)
GROUND_TRUTH = {
    "real1": (22, 66, {"Rex", "Dingo"}, 0, 0),
    "real2": (100, 0, {"Customer", "TravelAgency"}, 0, 0),
    "real3": (100, 568, {"User", "Thermostat", "Controller"}, 13, 0),
    "real4": (100, 1000, {"Visitor", "Zoo", "Bank"}, 0, 0),
    "real5": (100, 599, {"Contact_Author", "PC_Chair", "Reviewer"}, 0, 0),
    "healthcare": (
        100, 376, {"Patient", "Gynecologist", "Hospital", "Laboratory"}, 26, 0,
    ),
    "smartagriculture": (
        10, 213, {"drone", "tractor_1", "tractor_2"}, 4, 10,
    ),
}


@pytest.mark.parametrize("dataset", list(GROUND_TRUTH))
def test_dataset_matches_spec_ground_truth(dataset):
    plain = DATA / f"collectivelog_{dataset}.xes"
    if not plain.exists():
        pytest.skip(f"{dataset} dataset not present")

    expected_traces, expected_internal, expected_parts, expected_unmatched, expected_bcast = (
        GROUND_TRUTH[dataset]
    )

    traces = load_xes(plain)
    events, objects, stats = extract(traces)

    assert stats.traces == expected_traces, (
        f"{dataset}: expected {expected_traces} traces, got {stats.traces}"
    )
    assert stats.internal_events_dropped == expected_internal, (
        f"{dataset}: expected {expected_internal} internal events dropped, "
        f"got {stats.internal_events_dropped}"
    )
    assert set(stats.participants_by_name) == expected_parts, (
        f"{dataset}: expected participants {expected_parts}, "
        f"got {set(stats.participants_by_name)}"
    )
    assert stats.unmatched_msg_ids == expected_unmatched, (
        f"{dataset}: expected {expected_unmatched} unmatched msg ids, "
        f"got {stats.unmatched_msg_ids}"
    )
    assert stats.broadcast_msg_ids == expected_bcast, (
        f"{dataset}: expected {expected_bcast} broadcast msg ids, "
        f"got {stats.broadcast_msg_ids}"
    )

    # Each task event is one send; sends + receives = total message events.
    # The number of task events equals the number of sends.
    sends = sum(1 for tr in traces for e in tr.events if e.msg_type == "send")
    assert stats.task_events == sends


@pytest.mark.parametrize("dataset", list(GROUND_TRUTH))
def test_ocel_passes_schema_for_all_datasets(dataset):
    """Every dataset's OCEL output must validate against the official schema."""
    jsonschema = pytest.importorskip("jsonschema")
    import json

    plain = DATA / f"collectivelog_{dataset}.xes"
    if not plain.exists():
        pytest.skip(f"{dataset} dataset not present")

    from xescol2ocelchor.ocel import build_ocel

    traces = load_xes(plain)
    events, objects, _ = extract(traces)
    ocel = build_ocel(events, objects)

    schema_path = Path(__file__).parent / "schemas" / "ocel20-schema.json"
    with open(schema_path) as f:
        schema = json.load(f)
    jsonschema.validate(instance=ocel, schema=schema)
