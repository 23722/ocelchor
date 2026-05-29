"""Tests for the XES reader."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from xescol2ocelchor.reader import load_xes

FIXTURES = Path(__file__).parent / "data"


@pytest.fixture
def minimal_traces():
    return load_xes(FIXTURES / "synthetic_minimal.xes")


class TestTraceParsing:

    def test_returns_all_traces(self, minimal_traces):
        assert len(minimal_traces) == 2

    def test_trace_concept_names(self, minimal_traces):
        assert [t.concept_name for t in minimal_traces] == ["case_1", "case_2"]

    def test_trace_events_count(self, minimal_traces):
        assert len(minimal_traces[0].events) == 3
        assert len(minimal_traces[1].events) == 1


class TestEventParsing:

    def test_internal_event_has_no_msg_type(self, minimal_traces):
        ev = minimal_traces[0].events[0]
        assert ev.msg_type is None
        assert ev.msg_instance_id is None

    def test_send_event_fields(self, minimal_traces):
        ev = minimal_traces[0].events[1]
        assert ev.concept_name == "Alice_Greet"
        assert ev.org_group == "Alice"
        assert ev.msg_type == "send"
        assert ev.msg_instance_id == "Greeting_1"
        assert ev.msg_name == "Greeting"

    def test_receive_event_fields(self, minimal_traces):
        ev = minimal_traces[0].events[2]
        assert ev.msg_type == "receive"
        assert ev.org_group == "Bob"

    def test_timestamp_parsed_to_utc_aware(self, minimal_traces):
        ev = minimal_traces[0].events[0]
        assert ev.timestamp == datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_doc_order_assigned(self, minimal_traces):
        for i, ev in enumerate(minimal_traces[0].events):
            assert ev.doc_order == i


class TestReadingRealFile:
    """Spot-check that the reader handles the actual real1 dataset."""

    REAL1 = (
        Path(__file__).parent.parent / "data" / "input" / "collectivelog_real1.xes"
    )

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_trace_count(self):
        traces = load_xes(self.REAL1)
        # Appendix A ground truth: 22 traces
        assert len(traces) == 22

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_event_total(self):
        traces = load_xes(self.REAL1)
        total = sum(len(t.events) for t in traces)
        # Appendix A: 88 message events + 66 internal = 154
        assert total == 88 + 66

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_send_event_count(self):
        traces = load_xes(self.REAL1)
        sends = sum(
            1 for t in traces for e in t.events if e.msg_type == "send"
        )
        # Half of 88 message events are sends, half are receives
        assert sends == 44
