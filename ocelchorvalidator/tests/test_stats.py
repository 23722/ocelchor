"""Tests for ocelchorvalidator.stats."""

from __future__ import annotations

from ocelchorvalidator.constraints import ConstraintResult, Violation, validate_all
from ocelchorvalidator.index import build_index
from ocelchorvalidator.stats import LogStats, compute_stats


class TestComputeStatsSwap1:

    def test_file_name(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1_ocel.json", swap1_ocel, idx, validate_all(idx))
        assert stats.file_name == "swap_1_ocel.json"

    def test_num_vars(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.num_vars == 1

    def test_num_events(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.num_events == 2

    def test_num_messages(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.num_messages == 3

    def test_num_scoping_objects(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.num_scoping_objects == 1

    def test_num_participants(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.num_participants == 3

    def test_num_e2o(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        expected = sum(len(rels) for rels in idx.e2o.values())
        assert stats.num_e2o == expected
        assert stats.num_e2o > 0

    def test_num_o2o(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        expected = sum(len(rels) for rels in idx.o2o.values())
        assert stats.num_o2o == expected
        assert stats.num_o2o > 0

    def test_num_e2o_m(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        expected = sum(1 for rels in idx.e2o.values() for _, q in rels if q == "choreo:message")
        assert stats.num_e2o_m == expected
        assert stats.num_e2o_m > 0

    def test_num_e2o_cb(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        expected = sum(1 for rels in idx.e2o.values() for _, q in rels if q == "choreo:contained-by")
        assert stats.num_e2o_cb == expected
        assert stats.num_e2o_cb > 0

    def test_num_o2o_c(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        expected = sum(1 for rels in idx.o2o.values() for _, q in rels if q == "choreo:contains")
        assert stats.num_o2o_c == expected


class TestComputeStatsRootOnly:

    def test_counts(self, swap_root_only_ocel: dict) -> None:
        idx = build_index(swap_root_only_ocel)
        stats = compute_stats("root_only", swap_root_only_ocel, idx, validate_all(idx))
        assert stats.num_vars == 1
        assert stats.num_events == 1
        assert stats.num_messages == 1
        assert stats.num_scoping_objects == 0
        assert stats.num_participants == 2


class TestComputeStatsEmpty:

    def test_all_zero(self) -> None:
        ocel = {"objectTypes": [], "eventTypes": [], "objects": [], "events": []}
        idx = build_index(ocel)
        stats = compute_stats("empty", ocel, idx, validate_all(idx))
        assert stats.num_vars == 0
        assert stats.num_events == 0
        assert stats.num_messages == 0
        assert stats.num_scoping_objects == 0
        assert stats.num_participants == 0
        assert stats.num_e2o == 0
        assert stats.num_o2o == 0
        assert stats.num_e2o_m == 0
        assert stats.num_e2o_cb == 0
        assert stats.num_o2o_c == 0


class TestLogStatsDerivedProperties:

    def test_all_passed(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        stats = compute_stats("swap_1", swap1_ocel, idx, validate_all(idx))
        assert stats.constraints_all_passed
        assert stats.violated_constraints == []

    def test_total_elements_checked(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        results = validate_all(idx)
        stats = compute_stats("swap_1", swap1_ocel, idx, results)
        expected = sum(r.elements_checked for r in results.values())
        assert stats.total_elements_checked == expected
        assert stats.total_elements_checked > 0

    def test_violated_constraints(self) -> None:
        results = {
            "C0": ConstraintResult("C0", 1, [Violation("C0", "bad", "e1")]),
            "C1": ConstraintResult("C1", 1),
        }
        stats = LogStats(
            file_name="test",
            num_vars=0,
            num_events=0,
            num_messages=0,
            num_scoping_objects=0,
            num_participants=0,
            num_e2o=0,
            num_o2o=0,
            num_e2o_m=0,
            num_e2o_cb=0,
            num_o2o_c=0,
            constraint_results=results,
        )
        assert not stats.constraints_all_passed
        assert stats.violated_constraints == ["C0"]
