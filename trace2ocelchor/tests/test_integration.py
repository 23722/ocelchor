"""Integration tests against real (truncated) ground-truth transaction traces.

Expected counts were derived by running the pipeline on the truncated files and
verifying structural correctness. They act as regression anchors: if a refactor
changes the output, these tests catch it.

Structural invariants checked here correspond to constraints C0–C4 and C11–C14
from Section 5.4 of the paper, applied at the level that is observable from the
transformer output (i.e. without a full formal validator).
"""

from collections import Counter

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

def _e2o_qualifiers(event, qualifier):
    return [r.object_id for r in event.e2o if r.qualifier == qualifier]


def _qualifier_counts(events):
    return dict(Counter(r.qualifier for e in events for r in e.e2o))


# ---------------------------------------------------------------------------
# Shared structural invariant checker
# ---------------------------------------------------------------------------

def assert_structural_invariants(traces, events, objects):
    """Structural assertions that must hold for any valid choreography output.

    - All event and object IDs are unique.
    - Exactly one choreographyInstance object per trace (C0 — instance scope).
    - Every event has exactly one choreo:instance link (C0 — event side).
    - Every event has exactly one choreo:initiator (C2)
      and one choreo:participant (C3), and they differ (C4).
    - Every event has at most one choreo:contained-by link (C11).
    - Every message object has exactly one choreo:source and one choreo:target O2O
      relation (C5, C6).
    """
    # Unique IDs
    assert len({e.id for e in events}) == len(events), "Duplicate event IDs"
    assert len({o.id for o in objects}) == len(objects), "Duplicate object IDs"

    # One choreographyInstance per trace (C0)
    choreo_instances = [o for o in objects if o.type == "choreographyInstance"]
    assert len(choreo_instances) == len(traces)

    for event in events:
        # Every event has exactly one choreo:instance link (C0)
        instances = _e2o_qualifiers(event, CHOREO_INSTANCE)
        assert len(instances) == 1, (
            f"Event {event.id!r} has {len(instances)} choreo:instance links (expected 1)"
        )

        # Every event: exactly one initiator (C2) and one participant (C3)
        initiators = _e2o_qualifiers(event, CHOREO_INITIATOR)
        participants = _e2o_qualifiers(event, CHOREO_PARTICIPANT)
        assert len(initiators) == 1, (
            f"Event {event.id!r} has {len(initiators)} initiators (expected 1)"
        )
        assert len(participants) == 1, (
            f"Event {event.id!r} has {len(participants)} participants (expected 1)"
        )
        # Initiator and participant must differ (C4)
        assert initiators[0] != participants[0], (
            f"Event {event.id!r}: initiator == participant ({initiators[0]!r})"
        )

        # At most one choreo:contained-by (C11)
        contained = _e2o_qualifiers(event, CHOREO_CONTAINED_BY)
        assert len(contained) <= 1, (
            f"Event {event.id!r} has {len(contained)} choreo:contained-by links (expected ≤1)"
        )

    # Every message object has exactly one source and one target (C5, C6)
    for obj in objects:
        if obj.type.endswith(" call") or obj.type.endswith(" call response"):
            sources = [r for r in obj.o2o if r.qualifier == CHOREO_SOURCE]
            targets = [r for r in obj.o2o if r.qualifier == CHOREO_TARGET]
            assert len(sources) == 1, (
                f"Message {obj.id!r} has {len(sources)} choreo:source relations (expected 1)"
            )
            assert len(targets) == 1, (
                f"Message {obj.id!r} has {len(targets)} choreo:target relations (expected 1)"
            )


# ---------------------------------------------------------------------------
# Ground truth: PancakeSwap MasterChef v3 (0x55…), 9 transactions
# ---------------------------------------------------------------------------

class TestGroundTruth0x55:
    """9 real PancakeSwap MasterChef v3 transactions; 7 have internal calls."""

    @pytest.fixture(autouse=True)
    def _transform(self, gt_0x55_traces):
        self.traces = gt_0x55_traces
        self.events, self.objects = transform_traces(self.traces)

    def test_trace_count(self):
        assert len(self.traces) == 9
        assert sum(1 for t in self.traces if t.internal_txs) == 7
        assert sum(1 for t in self.traces if not t.internal_txs) == 2

    def test_event_and_object_counts(self):
        assert len(self.events) == 146
        assert len(self.objects) == 307

    def test_relation_counts(self):
        e2o = sum(len(e.e2o) for e in self.events)
        o2o = sum(len(o.o2o) for o in self.objects)
        assert e2o == 820
        assert o2o == 509

    def test_e2o_qualifier_distribution(self):
        counts = _qualifier_counts(self.events)
        assert counts[CHOREO_INITIATOR] == 146
        assert counts[CHOREO_PARTICIPANT] == 146
        assert counts[CHOREO_MESSAGE] == 245
        assert counts[CHOREO_INSTANCE] == 146
        assert counts[CHOREO_CONTAINED_BY] == 137

    def test_structural_invariants(self):
        assert_structural_invariants(self.traces, self.events, self.objects)


# ---------------------------------------------------------------------------
# Ground truth: Tornado Cash Governance (0x5e…), 5 transactions
# ---------------------------------------------------------------------------

class TestGroundTruth0x5e:
    """5 real Tornado Cash Governance transactions; all have internal calls."""

    @pytest.fixture(autouse=True)
    def _transform(self, gt_0x5e_traces):
        self.traces = gt_0x5e_traces
        self.events, self.objects = transform_traces(self.traces)

    def test_trace_count(self):
        assert len(self.traces) == 6
        assert all(t.internal_txs for t in self.traces)

    def test_event_and_object_counts(self):
        assert len(self.events) == 37
        assert len(self.objects) == 82

    def test_relation_counts(self):
        e2o = sum(len(e.e2o) for e in self.events)
        o2o = sum(len(o.o2o) for o in self.objects)
        assert e2o == 190
        assert o2o == 106

    def test_e2o_qualifier_distribution(self):
        counts = _qualifier_counts(self.events)
        assert counts[CHOREO_INITIATOR] == 37
        assert counts[CHOREO_PARTICIPANT] == 37
        assert counts[CHOREO_MESSAGE] == 48
        assert counts[CHOREO_INSTANCE] == 37
        assert counts[CHOREO_CONTAINED_BY] == 31

    def test_structural_invariants(self):
        assert_structural_invariants(self.traces, self.events, self.objects)

