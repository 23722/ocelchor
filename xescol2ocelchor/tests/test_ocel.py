"""Tests for OCEL 2.0 JSON assembly and schema validity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xescol2ocelchor.extractor import extract
from xescol2ocelchor.ocel import build_ocel, write_ocel
from xescol2ocelchor.reader import load_xes

FIXTURES = Path(__file__).parent / "data"
SCHEMA_PATH = Path(__file__).parent / "schemas" / "ocel20-schema.json"
REAL1 = Path(__file__).parent.parent / "data" / "input" / "collectivelog_real1.xes"


@pytest.fixture
def synthetic_ocel():
    traces = load_xes(FIXTURES / "synthetic_minimal.xes")
    events, objects, _ = extract(traces)
    return build_ocel(events, objects)


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


class TestStructure:

    def test_top_level_keys(self, synthetic_ocel):
        assert set(synthetic_ocel) == {"objectTypes", "eventTypes", "objects", "events"}

    def test_object_types_include_choreography_instance(self, synthetic_ocel):
        names = {t["name"] for t in synthetic_ocel["objectTypes"]}
        assert "choreographyInstance" in names
        assert "participant" in names
        assert "Greeting" in names

    def test_event_types_match_concept_names(self, synthetic_ocel):
        names = {t["name"] for t in synthetic_ocel["eventTypes"]}
        # The two sends in the synthetic fixture share concept:name "Alice_Greet"
        assert names == {"Alice_Greet"}

    def test_event_time_is_iso_z(self, synthetic_ocel):
        for ev in synthetic_ocel["events"]:
            assert ev["time"].endswith("Z")
            assert "T" in ev["time"]

    def test_object_attributes_carry_time_field(self, synthetic_ocel):
        for obj in synthetic_ocel["objects"]:
            for attr in obj.get("attributes", []):
                assert "time" in attr
                assert attr["time"] == "1970-01-01T00:00:00Z"


class TestSchemaValidation:

    def test_synthetic_validates_against_ocel20_schema(self, synthetic_ocel, schema):
        jsonschema = pytest.importorskip("jsonschema")
        jsonschema.validate(instance=synthetic_ocel, schema=schema)

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_validates_against_ocel20_schema(self, schema):
        jsonschema = pytest.importorskip("jsonschema")
        traces = load_xes(REAL1)
        events, objects, _ = extract(traces)
        ocel = build_ocel(events, objects)
        jsonschema.validate(instance=ocel, schema=schema)


class TestWriteOcel:

    def test_round_trip_via_disk(self, synthetic_ocel, tmp_path):
        out = tmp_path / "synthetic_ocel.json"
        write_ocel(synthetic_ocel, out)
        with open(out) as f:
            loaded = json.load(f)
        assert loaded == synthetic_ocel
