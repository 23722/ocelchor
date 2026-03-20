"""Tests for trace-to-OCEL transformation logic.

Tests are derived from the expected output specifications in tests/expected/.
The transformer is not yet implemented (stubs raise NotImplementedError),
so these tests define the red phase of TDD.
"""

import pytest

from trace2choreo.models import (
    CHOREO_CONTAINED_BY,
    CHOREO_CONTAINS,
    CHOREO_INITIATOR,
    CHOREO_INSTANCE,
    CHOREO_MESSAGE,
    CHOREO_PARTICIPANT,
    CHOREO_SOURCE,
    CHOREO_TARGET,
)
from trace2choreo.transformer import transform_traces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _e2o_targets(event, qualifier):
    """Return list of object IDs linked to *event* by *qualifier*."""
    return [r.object_id for r in event.e2o if r.qualifier == qualifier]


def _e2o_target(event, qualifier):
    """Return the single object ID linked by *qualifier*, or None."""
    targets = _e2o_targets(event, qualifier)
    return targets[0] if targets else None


def _obj_by_id(objects, obj_id):
    """Find an object by ID in a list."""
    for o in objects:
        if o.id == obj_id:
            return o
    return None


def _o2o_targets(obj, qualifier):
    """Return list of target IDs linked from *obj* by *qualifier*."""
    return [r.target_id for r in obj.o2o if r.qualifier == qualifier]


def _objs_of_type(objects, obj_type):
    """Return objects whose type matches *obj_type*."""
    return [o for o in objects if o.type == obj_type]


# ---------------------------------------------------------------------------
# TestTransformTraces — basic API contract
# ---------------------------------------------------------------------------

class TestTransformTraces:

    def test_empty_list(self):
        events, objects = transform_traces([])
        assert events == []
        assert objects == []

    def test_returns_tuple(self, swap_root_only_trace):
        result = transform_traces([swap_root_only_trace])
        assert isinstance(result, tuple)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestSwapRootOnly — from tests/expected/swap_root_only.md
# No internal calls → single choreography task event, no subchoreography.
# Expected: 1 event, 4 objects (2 participants, 1 message, 1 choreo instance)
# ---------------------------------------------------------------------------

class TestSwapRootOnly:

    @pytest.fixture(autouse=True)
    def _transform(self, swap_root_only_trace):
        self.events, self.objects = transform_traces([swap_root_only_trace])

    # -- events --

    def test_event_count(self):
        assert len(self.events) == 1

    def test_event_id_and_type(self):
        e = self.events[0]
        assert e.id == "e:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root"
        assert e.type == "approve"

    def test_event_trace_order(self):
        assert self.events[0].attributes["trace_order"] == 0

    def test_event_e2o_count(self):
        assert len(self.events[0].e2o) == 4

    def test_event_initiator(self):
        assert _e2o_target(self.events[0], CHOREO_INITIATOR) == \
            "0x1111111111111111111111111111111111111111"

    def test_event_participant(self):
        assert _e2o_target(self.events[0], CHOREO_PARTICIPANT) == \
            "0xcccccccccccccccccccccccccccccccccccccccc"

    def test_event_message(self):
        assert _e2o_target(self.events[0], CHOREO_MESSAGE) == \
            "call:req:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root"

    def test_event_choreo_instance(self):
        inst = _e2o_target(self.events[0], CHOREO_INSTANCE)
        assert inst == "choreographyInstance:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"

    # -- objects --

    def test_object_count(self):
        assert len(self.objects) == 4

    def test_participant_eoa(self):
        eoa = _obj_by_id(self.objects, "0x1111111111111111111111111111111111111111")
        assert eoa is not None
        assert eoa.type == "EOA"

    def test_participant_ca(self):
        ca = _obj_by_id(self.objects, "0xcccccccccccccccccccccccccccccccccccccccc")
        assert ca is not None
        assert ca.type == "CA"

    def test_message_object(self):
        msg = _obj_by_id(self.objects, "call:req:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root")
        assert msg is not None
        assert msg.type == "approve call"

    def test_message_o2o(self):
        msg = _obj_by_id(self.objects, "call:req:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root")
        assert _o2o_targets(msg, CHOREO_SOURCE) == \
            ["0x1111111111111111111111111111111111111111"]
        assert _o2o_targets(msg, CHOREO_TARGET) == \
            ["0xcccccccccccccccccccccccccccccccccccccccc"]

    def test_no_response_message(self):
        assert _obj_by_id(self.objects, "call:res:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root") is None

    def test_choreography_instance(self):
        ci = _obj_by_id(
            self.objects,
            "choreographyInstance:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111",
        )
        assert ci is not None
        assert ci.type == "choreographyInstance"

    def test_no_scoping_object(self):
        scoping = _objs_of_type(self.objects, "subchoreographyInstance")
        assert len(scoping) == 0


# ---------------------------------------------------------------------------
# TestSwap1 — from tests/expected/swap_1.md
# One leaf internal call → root splits into request + subchoreography.
# Expected: 3 events, 8 objects
# ---------------------------------------------------------------------------

class TestSwap1:

    @pytest.fixture(autouse=True)
    def _transform(self, swap_1_trace):
        self.events, self.objects = transform_traces([swap_1_trace])

    # -- event counts and ordering --

    def test_event_count(self):
        assert len(self.events) == 2

    def test_event_ids_in_order(self):
        ids = [e.id for e in self.events]
        assert ids == [
            "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root:request",
            "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1",
        ]

    def test_event_types(self):
        types = [e.type for e in self.events]
        assert types == [
            "Request swapAssets",
            "swap",
        ]

    def test_trace_order_values(self):
        orders = [e.attributes["trace_order"] for e in self.events]
        assert orders == [0, 1]

    def test_no_subchoreography_events(self):
        assert not any(e.id.endswith(":sub") for e in self.events)
        assert not any("subchoreography" in e.type for e in self.events)

    def test_timestamps_increasing(self):
        times = [e.time for e in self.events]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

    # -- root request E2O --

    def test_root_request_initiator(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_INITIATOR) == \
            "0x1111111111111111111111111111111111111111"

    def test_root_request_participant(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_PARTICIPANT) == \
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_root_request_message(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_MESSAGE) == "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root"

    def test_root_request_instance(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_INSTANCE) is not None

    def test_root_request_no_contained_by(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) is None

    def test_root_request_e2o_count(self):
        assert len(self.events[0].e2o) == 4

    # -- leaf event (0_1) E2O --

    def test_leaf_initiator(self):
        e = self.events[1]
        assert _e2o_target(e, CHOREO_INITIATOR) == \
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_leaf_participant(self):
        e = self.events[1]
        assert _e2o_target(e, CHOREO_PARTICIPANT) == \
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    def test_leaf_messages(self):
        e = self.events[1]
        msgs = _e2o_targets(e, CHOREO_MESSAGE)
        assert "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1" in msgs
        assert "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1" in msgs

    def test_leaf_contained_by(self):
        e = self.events[1]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root"

    def test_leaf_e2o_count(self):
        assert len(self.events[1].e2o) == 6

    def test_scoping_root_has_no_contains(self):
        sub = _obj_by_id(self.objects, "subchoreographyInstance:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root")
        assert _o2o_targets(sub, CHOREO_CONTAINS) == []

    # -- objects --

    def test_object_count(self):
        assert len(self.objects) == 8

    def test_participant_count(self):
        participants = [o for o in self.objects if o.type in ("EOA", "CA", "SwapPool")]
        assert len(participants) == 3

    def test_participant_types(self):
        eoa = _obj_by_id(self.objects, "0x1111111111111111111111111111111111111111")
        assert eoa.type == "EOA"
        ca = _obj_by_id(self.objects, "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        assert ca.type == "CA"
        pool = _obj_by_id(self.objects, "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        assert pool.type == "SwapPool"

    def test_message_count(self):
        # root req + 0_1 req + 0_1 res = 3
        msg_ids = [
            "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root",
            "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1",
            "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1",
        ]
        for mid in msg_ids:
            assert _obj_by_id(self.objects, mid) is not None

    def test_message_types(self):
        root_msg = _obj_by_id(self.objects, "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root")
        assert root_msg.type == "swapAssets call"
        req_msg = _obj_by_id(self.objects, "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1")
        assert req_msg.type == "swap call"
        res_msg = _obj_by_id(self.objects, "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1")
        assert res_msg.type == "swap call response"

    def test_message_o2o_source_target(self):
        req = _obj_by_id(self.objects, "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1")
        assert _o2o_targets(req, CHOREO_SOURCE) == \
            ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
        assert _o2o_targets(req, CHOREO_TARGET) == \
            ["0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]
        res = _obj_by_id(self.objects, "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1")
        assert _o2o_targets(res, CHOREO_SOURCE) == \
            ["0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]
        assert _o2o_targets(res, CHOREO_TARGET) == \
            ["0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]

    def test_scoping_object(self):
        sub = _obj_by_id(self.objects, "subchoreographyInstance:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root")
        assert sub is not None
        assert sub.type == "subchoreographyInstance"

    def test_no_root_response_event(self):
        ids = [e.id for e in self.events]
        assert "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root:response" not in ids

    def test_no_root_response_message(self):
        assert _obj_by_id(self.objects, "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root") is None


# ---------------------------------------------------------------------------
# TestSwap3 — from tests/expected/swap_3.md
# Deep nesting: 0_1→(0_1_1→0_1_1_1, 0_1_2), 0_2
# Expected: 11 events, 22 objects, 50 E2O, 22 O2O
# ---------------------------------------------------------------------------

class TestSwap3:

    @pytest.fixture(autouse=True)
    def _transform(self, swap_3_trace):
        self.events, self.objects = transform_traces([swap_3_trace])

    # -- event counts and ordering --

    def test_event_count(self):
        assert len(self.events) == 8

    def test_event_ids_in_order(self):
        ids = [e.id for e in self.events]
        assert ids == [
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root:request",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1:request",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1:request",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1_1",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1:response",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_2",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1:response",
            "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_2",
        ]

    def test_trace_order_sequential(self):
        orders = [e.attributes["trace_order"] for e in self.events]
        assert orders == list(range(8))

    def test_timestamps_strictly_increasing(self):
        times = [e.time for e in self.events]
        for i in range(1, len(times)):
            assert times[i] > times[i - 1]

    # -- event types --

    def test_event_types(self):
        types = [e.type for e in self.events]
        assert types == [
            "Request swap",
            "Request swap",
            "Request transfer",
            "balanceOf",
            "Respond to transfer",
            "updateReserves",
            "Respond to swap",
            "logSwap",
        ]

    def test_no_subchoreography_events(self):
        assert not any(e.id.endswith(":sub") for e in self.events)
        assert not any("subchoreography" in e.type for e in self.events)

    # -- object counts --

    def test_object_count(self):
        assert len(self.objects) == 22

    def test_participant_count(self):
        participant_types = {"EOA", "CA", "SwapRouter", "TokenContract",
                             "BalanceOracle", "LiquidityPool", "SwapLogger"}
        participants = [o for o in self.objects if o.type in participant_types]
        assert len(participants) == 7

    def test_message_count(self):
        # Messages have IDs starting with "call:"
        messages = [o for o in self.objects if o.id.startswith("call:")]
        assert len(messages) == 11

    def test_scoping_count(self):
        scoping = _objs_of_type(self.objects, "subchoreographyInstance")
        assert len(scoping) == 3

    def test_scoping_ids(self):
        scoping = _objs_of_type(self.objects, "subchoreographyInstance")
        scoping_ids = sorted(o.id for o in scoping)
        assert scoping_ids == sorted([
            "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root",
            "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1",
            "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1",
        ])

    def test_choreography_instance(self):
        ci = _obj_by_id(
            self.objects,
            "choreographyInstance:0xfed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2",
        )
        assert ci is not None
        assert ci.type == "choreographyInstance"

    # -- aggregate relation counts --

    def test_total_e2o_count(self):
        total = sum(len(e.e2o) for e in self.events)
        # root:req(4) + 0_1:req(5) + 0_1_1:req(5) + 0_1_1_1(6) + 0_1_1:res(5)
        # + 0_1_2(6) + 0_1:res(5) + 0_2(6) = 42
        assert total == 42

    def test_total_o2o_count(self):
        total = sum(len(o.o2o) for o in self.objects)
        # 11 messages × 2 (source+target) = 22
        # + 2 choreo:contains O2O (root→0_1, 0_1→0_1_1) = 2
        assert total == 24

    # -- choreo:contained-by links to immediate parent --

    def test_contained_by_0_1_request(self):
        """0_1:request is contained by root subchoreography."""
        e = self.events[1]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root"

    def test_contained_by_0_1_1_request(self):
        """0_1_1:request is contained by 0_1 subchoreography."""
        e = self.events[2]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1"

    def test_contained_by_0_1_1_1(self):
        """Leaf 0_1_1_1 is contained by 0_1_1 subchoreography."""
        e = self.events[3]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1"

    def test_contained_by_0_1_1_response(self):
        """0_1_1:response is contained by 0_1 subchoreography."""
        e = self.events[4]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1"

    def test_contained_by_0_1_2(self):
        """Leaf 0_1_2 is contained by 0_1 subchoreography."""
        e = self.events[5]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1"

    def test_contained_by_0_1_response(self):
        """0_1:response is contained by root subchoreography."""
        e = self.events[6]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root"

    def test_contained_by_0_2(self):
        """Leaf 0_2 is contained by root subchoreography."""
        e = self.events[7]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) == "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root"

    # -- choreo:contains O2O on scoping objects --

    def test_scoping_root_contains_0_1(self):
        sub = _obj_by_id(self.objects, "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root")
        targets = _o2o_targets(sub, CHOREO_CONTAINS)
        assert "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1" in targets

    def test_scoping_0_1_contains_0_1_1(self):
        sub = _obj_by_id(self.objects, "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1")
        targets = _o2o_targets(sub, CHOREO_CONTAINS)
        assert "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1" in targets

    def test_scoping_leaf_has_no_contains(self):
        sub = _obj_by_id(self.objects, "subchoreographyInstance:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1")
        assert _o2o_targets(sub, CHOREO_CONTAINS) == []

    # -- leaf events have both request and response messages --

    def test_leaf_0_1_1_1_messages(self):
        e = self.events[3]  # balanceOf
        msgs = _e2o_targets(e, CHOREO_MESSAGE)
        assert "call:req:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1_1" in msgs
        assert "call:res:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1_1" in msgs

    def test_leaf_0_1_2_messages(self):
        e = self.events[5]  # updateReserves
        msgs = _e2o_targets(e, CHOREO_MESSAGE)
        assert "call:req:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_2" in msgs
        assert "call:res:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_2" in msgs

    def test_leaf_0_2_messages(self):
        e = self.events[7]  # logSwap
        msgs = _e2o_targets(e, CHOREO_MESSAGE)
        assert "call:req:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_2" in msgs
        assert "call:res:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_2" in msgs

    # -- non-leaf frames produce request + response (no sub) --

    def test_0_1_produces_two_events(self):
        """Non-leaf 0_1 produces request and response events (no sub)."""
        ids = [e.id for e in self.events]
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1:request" in ids
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1:response" in ids
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1:sub" not in ids

    def test_0_1_1_produces_two_events(self):
        """Non-leaf 0_1_1 produces request and response events (no sub)."""
        ids = [e.id for e in self.events]
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1:request" in ids
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1:response" in ids
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:0_1_1:sub" not in ids

    # -- response events reverse initiator/participant --

    def test_response_0_1_1_reverses_roles(self):
        """0_1_1:response has initiator=0xCCC (callee), participant=0xBBB (caller)."""
        e = self.events[4]
        assert _e2o_target(e, CHOREO_INITIATOR) == \
            "0xcccccccccccccccccccccccccccccccccccccccc"
        assert _e2o_target(e, CHOREO_PARTICIPANT) == \
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    def test_response_0_1_reverses_roles(self):
        """0_1:response has initiator=0xBBB (callee), participant=0xAAA (caller)."""
        e = self.events[6]
        assert _e2o_target(e, CHOREO_INITIATOR) == \
            "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        assert _e2o_target(e, CHOREO_PARTICIPANT) == \
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    # -- root has no response (EOA) --

    def test_no_root_response_event(self):
        ids = [e.id for e in self.events]
        assert "e:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root:response" not in ids

    def test_no_root_response_message(self):
        assert _obj_by_id(self.objects, "call:res:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root") is None

    # -- root request E2O --

    def test_root_request_e2o(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_INITIATOR) == \
            "0x1111111111111111111111111111111111111111"
        assert _e2o_target(e, CHOREO_PARTICIPANT) == \
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert _e2o_target(e, CHOREO_MESSAGE) == "call:req:fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2:root"

    def test_root_request_no_contained_by(self):
        e = self.events[0]
        assert _e2o_target(e, CHOREO_CONTAINED_BY) is None


# ---------------------------------------------------------------------------
# TestSwapMultiTx — global participant deduplication across two traces
# Two transactions sharing sender (0x111) and a contract (0xCCC).
# Trace 1: approve on 0xCCC (root-only, no internal calls)
# Trace 2: swap on 0xAAA → internal 0_1 swap on 0xBBB (SwapRouter)
#           → internal 0_1_1 transfer on 0xCCC (TokenContract, leaf)
# ---------------------------------------------------------------------------

_BBBB = "bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222"
_CCCC = "cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333"


class TestSwapMultiTx:

    @pytest.fixture(autouse=True)
    def _transform(self, data_dir):
        from trace2choreo.parser import load_trace_file
        traces = load_trace_file(data_dir / "swap_multi_tx.json")
        self.traces = traces
        self.events, self.objects = transform_traces(traces)

    # -- counts --

    def test_trace_count(self):
        assert len(self.traces) == 2

    def test_event_count(self):
        # trace 1 (root-only): 1 event
        # trace 2 (root with 0_1 subchoreography containing leaf 0_1_1):
        #   root:request, 0_1:request, 0_1_1, 0_1:response = 4
        assert len(self.events) == 5

    def test_object_count(self):
        # participants: EOA(0x111), CA(0xAAA), CA(0xCCC), SwapRouter(0xBBB) = 4 unique
        # messages: approve:req, swap:req(root), swap:req(0_1), swap:res(0_1),
        #           transfer:req, transfer:res = 6
        # scoping: sub(root), sub(0_1) = 2
        # choreo instances: 2
        assert len(self.objects) == 14

    # -- global participant deduplication --

    def test_shared_eoa_deduplicated(self):
        """0x111 (sender in both traces) appears as exactly one EOA object."""
        eoa_objs = [
            o for o in self.objects
            if o.id == "0x1111111111111111111111111111111111111111"
        ]
        assert len(eoa_objs) == 1
        assert eoa_objs[0].type == "EOA"

    def test_shared_contract_deduplicated(self):
        """0xCCC (appears in both traces as CA/TokenContract) appears exactly once."""
        ccc_objs = [
            o for o in self.objects
            if o.id == "0xcccccccccccccccccccccccccccccccccccccccc"
        ]
        assert len(ccc_objs) == 1

    def test_two_choreography_instances(self):
        """Each trace produces its own ChoreographyInstance."""
        instances = [o for o in self.objects if o.type == "choreographyInstance"]
        assert len(instances) == 2
        ids = {o.id for o in instances}
        assert f"choreographyInstance:0x{_BBBB}" in ids
        assert f"choreographyInstance:0x{_CCCC}" in ids

    # -- per-trace event structure --

    def test_trace1_produces_single_root_event(self):
        """approve (root-only) → one choreography task event."""
        assert self.events[0].id == f"e:{_BBBB}:root"
        assert self.events[0].type == "approve"

    def test_trace2_event_ids_in_order(self):
        ids = [e.id for e in self.events[1:]]
        assert ids == [
            f"e:{_CCCC}:root:request",
            f"e:{_CCCC}:0_1:request",
            f"e:{_CCCC}:0_1_1",
            f"e:{_CCCC}:0_1:response",
        ]

    # -- relation counts --

    def test_e2o_qualifier_distribution(self):
        from collections import Counter
        counts = Counter(r.qualifier for e in self.events for r in e.e2o)
        assert counts[CHOREO_INITIATOR] == 5
        assert counts[CHOREO_PARTICIPANT] == 5
        assert counts[CHOREO_MESSAGE] == 6
        assert counts[CHOREO_INSTANCE] == 5
        assert counts[CHOREO_CONTAINED_BY] == 3


# ---------------------------------------------------------------------------
# TestOcelReferentialIntegrity — structural invariants for any transformation
# Parametrized across all three scenarios.
# ---------------------------------------------------------------------------

class TestOcelReferentialIntegrity:

    @pytest.fixture(
        params=["swap_root_only_trace", "swap_1_trace", "swap_3_trace"],
    )
    def transformed(self, request):
        trace = request.getfixturevalue(request.param)
        events, objects = transform_traces([trace])
        return events, objects

    def test_no_duplicate_event_ids(self, transformed):
        events, _ = transformed
        ids = [e.id for e in events]
        assert len(ids) == len(set(ids)), f"Duplicate event IDs: {ids}"

    def test_no_duplicate_object_ids(self, transformed):
        _, objects = transformed
        ids = [o.id for o in objects]
        assert len(ids) == len(set(ids)), f"Duplicate object IDs: {ids}"

    def test_e2o_references_existing_objects(self, transformed):
        events, objects = transformed
        obj_ids = {o.id for o in objects}
        for event in events:
            for rel in event.e2o:
                assert rel.object_id in obj_ids, (
                    f"Event {event.id} E2O references non-existent object "
                    f"{rel.object_id!r} (qualifier={rel.qualifier!r})"
                )

    def test_o2o_references_existing_objects(self, transformed):
        _, objects = transformed
        obj_ids = {o.id for o in objects}
        for obj in objects:
            for rel in obj.o2o:
                assert rel.target_id in obj_ids, (
                    f"Object {obj.id} O2O references non-existent target "
                    f"{rel.target_id!r} (qualifier={rel.qualifier!r})"
                )

    def test_every_event_has_time(self, transformed):
        events, _ = transformed
        for event in events:
            assert event.time is not None, f"Event {event.id} has no time"

    def test_every_event_has_type(self, transformed):
        events, _ = transformed
        for event in events:
            assert event.type, f"Event {event.id} has empty type"

    def test_every_object_has_type(self, transformed):
        _, objects = transformed
        for obj in objects:
            assert obj.type, f"Object {obj.id} has empty type"


# ---------------------------------------------------------------------------
# TestMessageAttributes — decoded input params and output on message objects
#
# Request messages carry one attribute per decoded input param (name → value).
# Response messages carry a single attribute "output" with the raw hex string.
# Root-level inputs (inputName/inputValue) are normalised by the parser to the
# same InputParam dataclass as frame-level inputs (name/value), so the
# assertion shape is identical in both cases.
# ---------------------------------------------------------------------------

_AAAA1111 = "aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"
_ABCABC   = "abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"
_FED2FED2 = "fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"


class TestMessageAttributes_SwapRootOnly:
    """approve with no internal calls — only a root request message, no response."""

    @pytest.fixture(autouse=True)
    def _transform(self, swap_root_only_trace):
        _, self.objects = transform_traces([swap_root_only_trace])

    def test_root_request_has_decoded_inputs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_AAAA1111}:root")
        assert msg is not None
        assert msg.attributes.get("spender") == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert msg.attributes.get("amount") == 99999

    def test_root_request_no_extra_attributes(self):
        """Only the two decoded params — nothing else."""
        msg = _obj_by_id(self.objects, f"call:req:{_AAAA1111}:root")
        assert set(msg.attributes.keys()) == {"spender", "amount"}


class TestMessageAttributes_Swap1:
    """swapAssets root (no response) + 0_1 leaf (request + response)."""

    @pytest.fixture(autouse=True)
    def _transform(self, swap_1_trace):
        _, self.objects = transform_traces([swap_1_trace])

    def test_root_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_ABCABC}:root")
        assert msg.attributes == {"amountIn": 1000}

    def test_frame_0_1_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_ABCABC}:0_1")
        assert msg.attributes == {"amountIn": 1000}

    def test_frame_0_1_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_ABCABC}:0_1")
        assert msg.attributes == {
            "output": "0x00000000000000000000000000000000000000000000000000000000000003e3"
        }


class TestMessageAttributes_Swap3:
    """swap with three-level call tree — all request/response message attributes."""

    @pytest.fixture(autouse=True)
    def _transform(self, swap_3_trace):
        _, self.objects = transform_traces([swap_3_trace])

    def test_root_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:root")
        assert msg.attributes == {"amountIn": 1000}

    def test_0_1_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:0_1")
        assert msg.attributes == {"amountIn": 1000}

    def test_0_1_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_FED2FED2}:0_1")
        assert msg.attributes == {
            "output": "0x00000000000000000000000000000000000000000000000000000000000003e3"
        }

    def test_0_1_1_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:0_1_1")
        assert msg.attributes == {
            "to": "0x1111111111111111111111111111111111111111",
            "amount": 995,
        }

    def test_0_1_1_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_FED2FED2}:0_1_1")
        assert msg.attributes == {
            "output": "0x0000000000000000000000000000000000000000000000000000000000000001"
        }

    def test_0_1_1_1_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:0_1_1_1")
        assert msg.attributes == {
            "account": "0x1111111111111111111111111111111111111111"
        }

    def test_0_1_1_1_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_FED2FED2}:0_1_1_1")
        assert msg.attributes == {
            "output": "0x00000000000000000000000000000000000000000000000000000000000f4240"
        }

    def test_0_1_2_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:0_1_2")
        assert msg.attributes == {
            "token": "0xcccccccccccccccccccccccccccccccccccccccc",
            "amountOut": 995,
        }

    def test_0_1_2_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_FED2FED2}:0_1_2")
        assert msg.attributes == {
            "output": "0x0000000000000000000000000000000000000000000000000000000000000001"
        }

    def test_0_2_request_attrs(self):
        msg = _obj_by_id(self.objects, f"call:req:{_FED2FED2}:0_2")
        assert msg.attributes == {
            "user": "0x1111111111111111111111111111111111111111",
            "amount": 995,
        }

    def test_0_2_response_output(self):
        msg = _obj_by_id(self.objects, f"call:res:{_FED2FED2}:0_2")
        assert msg.attributes == {
            "output": "0x0000000000000000000000000000000000000000000000000000000000000001"
        }


# ---------------------------------------------------------------------------
# Response message type tests
# ---------------------------------------------------------------------------

_DDDD4444 = "dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444dddd4444"


class TestResponseMessageType:
    """Response messages use '<activity> call response' type, distinct from request."""

    @pytest.fixture(autouse=True)
    def _transform(self, swap_1_trace):
        _, self.objects = transform_traces([swap_1_trace])

    def test_request_message_type(self):
        msg = _obj_by_id(self.objects, f"call:req:{_ABCABC}:0_1")
        assert msg.type == "swap call"

    def test_response_message_type(self):
        msg = _obj_by_id(self.objects, f"call:res:{_ABCABC}:0_1")
        assert msg.type == "swap call response"

    def test_root_request_message_type(self):
        msg = _obj_by_id(self.objects, f"call:req:{_ABCABC}:root")
        assert msg.type == "swapAssets call"


# ---------------------------------------------------------------------------
# inputsCall fallback tests
# ---------------------------------------------------------------------------


class TestInputsCallFallback:
    """When decoded inputs are missing, request message falls back to inputsCall."""

    @pytest.fixture(autouse=True)
    def _transform(self, swap_undefined_activity_trace):
        _, self.objects = transform_traces([swap_undefined_activity_trace])

    def test_decoded_inputs_used_when_available(self):
        """Frame 0_1 has decoded inputs — should use those, not inputsCall."""
        msg = _obj_by_id(self.objects, f"call:req:{_DDDD4444}:0_1")
        assert msg.attributes == {"amountIn": 2000}

    def test_fallback_to_inputs_call(self):
        """Frame 0_1_1 has no decoded inputs — should fall back to inputsCall hex."""
        msg = _obj_by_id(self.objects, f"call:req:{_DDDD4444}:0_1_1")
        assert msg.attributes == {"inputsCall": "0xa9059cbb"}

    def test_response_unaffected_by_fallback(self):
        """Response messages always use output, regardless of input fallback."""
        msg = _obj_by_id(self.objects, f"call:res:{_DDDD4444}:0_1_1")
        assert msg.attributes == {
            "output": "0x0000000000000000000000000000000000000000000000000000000000000001"
        }

    def test_response_type_for_undefined(self):
        """Even undefined activities get the response type suffix."""
        msg = _obj_by_id(self.objects, f"call:res:{_DDDD4444}:0_1_1")
        assert msg.type == "undefined call response"


# ---------------------------------------------------------------------------
# DELEGATECALL integration — correct participants in OCEL output
# ---------------------------------------------------------------------------

class TestDelegatecallIntegration:
    """T9: DELEGATECALL from rewrite produces correct OCEL participants.

    Uses 0x5e_truncated.json, tx 0xcd4991... (unlock). The DELEGATECALL frame
    0_1 (Proxy→Governance) has a child 0_1_1 (transfer to TORN). After the from
    rewrite, Governance should appear as the initiator of the transfer event.
    """

    GOVERNANCE = "0xffbac21a641dcfe4552920138d90f3638b3c9fba"
    PROXY = "0x5efda50f22d34f262c29268506c5fa42cb56a1ce"

    @pytest.fixture(autouse=True)
    def _transform(self, gt_0x5e_traces):
        # Find the unlock tx (0xcd4991...)
        unlock = [t for t in gt_0x5e_traces if t.function_name == "unlock"][0]
        self.events, self.objects = transform_traces([unlock])

    def test_governance_is_participant_object(self):
        obj = _obj_by_id(self.objects, self.GOVERNANCE)
        assert obj is not None, "Governance should be a participant object"

    def test_governance_is_initiator_of_transfer(self):
        # The transfer event (leaf 0_1_1) should have Governance as initiator
        transfer_events = [e for e in self.events if e.type == "transfer"]
        assert len(transfer_events) == 1
        initiator = _e2o_target(transfer_events[0], CHOREO_INITIATOR)
        assert initiator == self.GOVERNANCE

    def test_proxy_not_initiator_of_transfer(self):
        transfer_events = [e for e in self.events if e.type == "transfer"]
        initiator = _e2o_target(transfer_events[0], CHOREO_INITIATOR)
        assert initiator != self.PROXY
