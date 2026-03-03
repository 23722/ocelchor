"""Tests for OCEL 2.0 assembly and output."""

import json
from pathlib import Path

import pytest

from trace2choreo.ocel import build_ocel
from trace2choreo.transformer import transform_traces

SCHEMA_PATH = Path(__file__).parent / "schemas" / "ocel20-schema.json"


# ---------------------------------------------------------------------------
# TestOcelJsonSchema — validate serialized output against official OCEL 2.0
# JSON schema from https://www.ocel-standard.org/2.0/ocel20-schema-json.json
# ---------------------------------------------------------------------------

class TestOcelJsonSchema:

    @pytest.fixture(
        params=["swap_root_only_trace", "swap_1_trace", "swap_3_trace"],
    )
    def ocel_json(self, request):
        """Transform a trace and serialize to OCEL 2.0 JSON dict."""
        trace = request.getfixturevalue(request.param)
        events, objects = transform_traces([trace])
        return build_ocel(events, objects)

    def test_validates_against_ocel20_schema(self, ocel_json):
        import jsonschema

        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        jsonschema.validate(instance=ocel_json, schema=schema)

    def test_has_required_top_level_keys(self, ocel_json):
        assert "eventTypes" in ocel_json
        assert "objectTypes" in ocel_json
        assert "events" in ocel_json
        assert "objects" in ocel_json

    def test_events_have_required_fields(self, ocel_json):
        for event in ocel_json["events"]:
            assert "id" in event
            assert "type" in event
            assert "time" in event

    def test_objects_have_required_fields(self, ocel_json):
        for obj in ocel_json["objects"]:
            assert "id" in obj
            assert "type" in obj
