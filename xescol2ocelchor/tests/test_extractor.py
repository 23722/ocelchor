"""Tests for the §4 extraction algorithm."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from xescol2ocelchor.extractor import extract
from xescol2ocelchor.models import (
    CHOREO_INITIATOR,
    CHOREO_INSTANCE,
    CHOREO_MESSAGE,
    CHOREO_PARTICIPANT,
    CHOREO_SOURCE,
    CHOREO_TARGET,
    COLLAB_INSTANCE,
    XesEvent,
    XesTrace,
)
from xescol2ocelchor.reader import load_xes

FIXTURES = Path(__file__).parent / "data"
REAL1 = Path(__file__).parent.parent / "data" / "input" / "collectivelog_real1.xes"


def _ev(
    name: str, group: str, t: int, doc_order: int,
    msg_type: str | None = None,
    msg_instance_id: str | None = None,
    msg_name: str | None = None,
) -> XesEvent:
    return XesEvent(
        concept_name=name,
        timestamp=datetime(2024, 1, 1, 0, 0, t, tzinfo=timezone.utc),
        org_group=group,
        doc_order=doc_order,
        msg_type=msg_type,
        msg_instance_id=msg_instance_id,
        msg_name=msg_name,
    )


def _qualifiers(rels):
    return {(r.object_id if hasattr(r, "object_id") else r.target_id, r.qualifier)
            for r in rels}


class TestMinimalSynthetic:

    @pytest.fixture
    def result(self):
        traces = load_xes(FIXTURES / "synthetic_minimal.xes")
        return extract(traces)

    def test_emits_one_event_per_send(self, result):
        events, _, stats = result
        # case_1 has one send; case_2 has one send → 2 events
        assert stats.task_events == 2
        assert len(events) == 2

    def test_drops_internal_events(self, result):
        _, _, stats = result
        assert stats.internal_events_dropped == 1

    def test_global_participant_dedup(self, result):
        events, objects, stats = result
        # Alice (sender) + Bob (receiver) = 2 distinct participant objects
        assert stats.participant_objects == 2
        assert set(stats.participants_by_name) == {"Alice", "Bob"}

    def test_choreography_instance_per_trace(self, result):
        _, objects, _ = result
        inst_objs = [o for o in objects if o.type == "choreographyInstance"]
        assert len(inst_objs) == 2
        assert {o.id for o in inst_objs} == {
            "choreographyInstance:case_1", "choreographyInstance:case_2",
        }

    def test_send_event_has_full_qualifier_set(self, result):
        events, _, _ = result
        case1 = next(e for e in events if e.id == "e:case_1:1")
        quals = _qualifiers(case1.e2o)
        assert ("choreographyInstance:case_1", CHOREO_INSTANCE) in quals
        assert ("Alice", CHOREO_INITIATOR) in quals
        assert ("Bob", CHOREO_PARTICIPANT) in quals
        assert ("message:case_1:Greeting_1", CHOREO_MESSAGE) in quals

    def test_message_object_o2o(self, result):
        _, objects, _ = result
        msg = next(o for o in objects if o.id == "message:case_1:Greeting_1")
        quals = _qualifiers(msg.o2o)
        assert ("Alice", CHOREO_SOURCE) in quals
        assert ("Bob", CHOREO_TARGET) in quals

    def test_message_object_type_uses_msg_name(self, result):
        _, objects, _ = result
        msg = next(o for o in objects if o.id == "message:case_1:Greeting_1")
        assert msg.type == "Greeting"

    def test_unmatched_send_flagged(self, result):
        _, _, stats = result
        # case_2's Greeting_1 send has no matching receive
        assert stats.unmatched_send_events == 1
        assert stats.unmatched_msg_ids == 1

    def test_unmatched_send_has_no_participant_or_target(self, result):
        events, objects, _ = result
        case2 = next(e for e in events if e.id == "e:case_2:0")
        quals = _qualifiers(case2.e2o)
        assert not any(q == CHOREO_PARTICIPANT for _, q in quals)
        msg = next(o for o in objects if o.id == "message:case_2:Greeting_1")
        assert not any(q == CHOREO_TARGET for _, q in _qualifiers(msg.o2o))


class TestMessageTypeFallbacks:

    def test_strips_trailing_numeric_suffix(self):
        send = _ev("X", "Alice", 1, 0,
                   msg_type="send", msg_instance_id="Offer_260", msg_name=None)
        trace = XesTrace(concept_name="t", events=[send])
        _, objects, _ = extract([trace])
        msg = next(o for o in objects if o.id == "message:t:Offer_260")
        assert msg.type == "Offer"

    def test_falls_back_to_message_when_nothing_useful(self):
        send = _ev("X", "Alice", 1, 0, msg_type="send", msg_instance_id="raw")
        trace = XesTrace(concept_name="t", events=[send])
        _, objects, _ = extract([trace])
        msg = next(o for o in objects if o.id == "message:t:raw")
        assert msg.type == "raw"


class TestBroadcast:

    def test_multi_receiver_yields_multiple_participants_and_targets(self):
        send = _ev("bcast", "drone", 1, 0,
                   msg_type="send", msg_instance_id="ping_1", msg_name="ping")
        rcv1 = _ev("rx", "tractor_1", 1, 1,
                   msg_type="receive", msg_instance_id="ping_1", msg_name="ping")
        rcv2 = _ev("rx", "tractor_2", 1, 2,
                   msg_type="receive", msg_instance_id="ping_1", msg_name="ping")
        trace = XesTrace(concept_name="t", events=[send, rcv1, rcv2])
        events, objects, stats = extract([trace])
        assert stats.broadcast_send_events == 1
        assert stats.broadcast_msg_ids == 1

        ev = next(e for e in events if e.id == "e:t:0")
        participants = [r.object_id for r in ev.e2o if r.qualifier == CHOREO_PARTICIPANT]
        assert set(participants) == {"tractor_1", "tractor_2"}

        msg = next(o for o in objects if o.id == "message:t:ping_1")
        targets = [r.target_id for r in msg.o2o if r.qualifier == CHOREO_TARGET]
        assert set(targets) == {"tractor_1", "tractor_2"}


class TestMessageObjectDedup:
    """Same (trace, msgInstanceId) reused across sends → one message object."""

    def test_repeat_msg_id_within_trace_is_single_object(self):
        send1 = _ev("Offer", "Customer", 1, 0,
                    msg_type="send", msg_instance_id="Offer_1", msg_name="Offer")
        rcv1 = _ev("Offer", "Agency", 1, 1,
                   msg_type="receive", msg_instance_id="Offer_1", msg_name="Offer")
        send2 = _ev("Offer", "Customer", 2, 2,
                    msg_type="send", msg_instance_id="Offer_1", msg_name="Offer")
        rcv2 = _ev("Offer", "Agency", 2, 3,
                   msg_type="receive", msg_instance_id="Offer_1", msg_name="Offer")
        trace = XesTrace(concept_name="t", events=[send1, rcv1, send2, rcv2])
        events, objects, stats = extract([trace])

        # Two task events but only one message object (shared id).
        assert stats.task_events == 2
        assert stats.message_objects == 1

        # Object ids globally unique.
        ids = [o.id for o in objects]
        assert len(ids) == len(set(ids))


class TestRealReal1:
    """Spot-check the extractor's output against Appendix A ground truth."""

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_appendix_a_counts(self):
        traces = load_xes(REAL1)
        events, objects, stats = extract(traces)

        # Appendix A: 22 traces, 44 sends → 44 task events,
        # 44 message instances, 66 internal events dropped, 2 participants.
        assert stats.traces == 22
        assert stats.task_events == 44
        assert stats.message_objects == 44
        assert stats.internal_events_dropped == 66
        assert stats.participant_objects == 2
        assert set(stats.participants_by_name) == {"Dingo", "Rex"}

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_no_unmatched_or_broadcast(self):
        traces = load_xes(REAL1)
        _, _, stats = extract(traces)
        # §5 expected profile: real1 has 0 unmatched sends, 0 broadcast ids
        assert stats.unmatched_send_events == 0
        assert stats.broadcast_send_events == 0
        assert stats.unmatched_msg_ids == 0
        assert stats.broadcast_msg_ids == 0


class TestKeepInternalEvents:
    """--keep-internal-events: emit internal events outside E_T."""

    @pytest.fixture
    def result(self):
        traces = load_xes(FIXTURES / "synthetic_minimal.xes")
        return extract(traces, keep_internal_events=True)

    def test_stats_count_kept_not_dropped(self, result):
        _, _, stats = result
        # Synthetic has one internal event (Alice_Internal in case_1).
        assert stats.internal_events_kept == 1
        assert stats.internal_events_dropped == 0

    def test_collaboration_instance_per_trace(self, result):
        _, objects, _ = result
        collab_objs = [o for o in objects if o.type == "collaborationInstance"]
        assert {o.id for o in collab_objs} == {
            "collaborationInstance:case_1",
            "collaborationInstance:case_2",
        }

    def test_task_event_has_collab_instance(self, result):
        events, _, _ = result
        case1 = next(e for e in events if e.id == "e:case_1:1")
        quals = _qualifiers(case1.e2o)
        assert ("collaborationInstance:case_1", COLLAB_INSTANCE) in quals
        # And the existing choreo:* edges are still present.
        assert ("choreographyInstance:case_1", CHOREO_INSTANCE) in quals

    def test_kept_event_has_collab_instance_only(self, result):
        events, _, _ = result
        # Alice_Internal has doc_order 0 in case_1.
        internal = next(e for e in events if e.id == "e:case_1:0")
        assert internal.type == "Alice_Internal"
        assert len(internal.e2o) == 1
        rel = internal.e2o[0]
        assert rel.object_id == "collaborationInstance:case_1"
        assert rel.qualifier == COLLAB_INSTANCE

    def test_kept_event_has_no_choreo_qualifiers(self, result):
        events, _, _ = result
        internal = next(e for e in events if e.id == "e:case_1:0")
        assert not any(q.startswith("choreo:") for _, q in _qualifiers(internal.e2o))


class TestMissingSender:
    """A send without org:group is emitted WITHOUT initiator/source edges,
    not skipped — the extraction-side twin of the missing-receiver strategy
    (event stays, gap visible, validator flags C2/C5/C7)."""

    @pytest.fixture
    def result(self):
        send = _ev("X", "", 1, 0, msg_type="send", msg_instance_id="m1")
        rcv = _ev("X", "Bob", 2, 1, msg_type="receive", msg_instance_id="m1")
        trace = XesTrace(concept_name="t", events=[send, rcv])
        return extract([trace])

    def test_event_emitted(self, result):
        events, _, stats = result
        assert stats.task_events == 1
        assert len(events) == 1

    def test_no_initiator_edge_and_no_empty_object(self, result):
        events, objects, _ = result
        quals = {q for _, q in _qualifiers(events[0].e2o)}
        assert CHOREO_INITIATOR not in quals
        assert CHOREO_PARTICIPANT in quals  # receiver edge intact
        assert all(o.id != "" for o in objects)

    def test_message_has_no_source_relation(self, result):
        _, objects, _ = result
        msg = next(o for o in objects if o.id == "message:t:m1")
        quals = {q for _, q in _qualifiers(msg.o2o)}
        assert CHOREO_SOURCE not in quals
        assert CHOREO_TARGET in quals
