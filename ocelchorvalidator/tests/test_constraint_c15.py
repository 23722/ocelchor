"""Tests for constraint C15 (initiator continuity)."""

from __future__ import annotations

from ocelchorvalidator.constraints import check_c15, validate_all
from ocelchorvalidator.index import build_index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_ocel(events: list[dict], objects: list[dict] | None = None) -> dict:
    return {
        "objectTypes": [],
        "eventTypes": [],
        "objects": objects or [],
        "events": events,
    }


def _event(eid: str, time: str, rels: list[dict]) -> dict:
    return {"id": eid, "type": "test", "time": time, "relationships": rels}


def _rel(oid: str, qualifier: str) -> dict:
    return {"objectId": oid, "qualifier": qualifier}


def _obj(oid: str, otype: str = "test", rels: list[dict] | None = None) -> dict:
    o: dict = {"id": oid, "type": otype}
    if rels:
        o["relationships"] = rels
    return o


# ---------------------------------------------------------------------------
# Positive cases against real fixtures
# ---------------------------------------------------------------------------


class TestC15Positive:

    def test_swap1(self, swap1_ocel: dict) -> None:
        r = check_c15(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 1  # 2 events → 1 pair

    def test_swap3(self, swap3_ocel: dict) -> None:
        r = check_c15(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 7  # 8 events → 7 pairs

    def test_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c15(build_index(swap_root_only_ocel))
        assert r.passed
        assert r.elements_checked == 0  # 1 event → 0 pairs

    def test_multi_tx(self, swap_multi_tx_ocel: dict) -> None:
        r = check_c15(build_index(swap_multi_tx_ocel))
        assert r.passed
        # Instance 1: 1 event → 0 pairs; Instance 2: 4 events → 3 pairs
        assert r.elements_checked == 3

    def test_real_world(self, real_world_ocel: dict) -> None:
        r = check_c15(build_index(real_world_ocel))
        assert r.passed


# ---------------------------------------------------------------------------
# Case 3 — Same scope / descending / both top-level
# ---------------------------------------------------------------------------


class TestC15Case3:

    def test_same_scope_pass(self) -> None:
        """Two events in same scope, e_2 initiator is participant of e_1."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("B", "choreo:initiator"),
                    _rel("C", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
        )
        r = check_c15(build_index(ocel))
        assert r.passed

    def test_same_scope_violation(self) -> None:
        """e_2 initiator is NOT initiator or participant of e_1."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("X", "choreo:initiator"),
                    _rel("Y", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
        )
        r = check_c15(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e2"

    def test_descending_violation(self) -> None:
        """e_1 is top-level, e_2 descends into a scope. e_2 initiator not in e_1 roles."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("X", "choreo:initiator"),
                    _rel("Y", "choreo:participant"),
                    _rel("sub1", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub1", "Subchoreography")],
        )
        r = check_c15(build_index(ocel))
        assert not r.passed

    def test_both_top_level_pass(self) -> None:
        """Two top-level events, e_2 initiator is e_1's participant."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("C", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
        )
        r = check_c15(build_index(ocel))
        assert r.passed


# ---------------------------------------------------------------------------
# Case 1 — Ascending into ancestor scope
# ---------------------------------------------------------------------------


class TestC15Case1:

    def test_ascending_pass(self) -> None:
        """e_1 in child scope, e_2 in parent scope. Initiator of e_2 is involved in parent's scope tree."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("B", "choreo:initiator"),
                    _rel("C", "choreo:participant"),
                    _rel("sub_child", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("B", "choreo:initiator"),
                    _rel("A", "choreo:participant"),
                    _rel("sub_parent", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[
                _obj("sub_parent", "Subchoreography", [
                    _rel("sub_child", "choreo:contains"),
                ]),
                _obj("sub_child", "Subchoreography"),
            ],
        )
        r = check_c15(build_index(ocel))
        assert r.passed

    def test_ascending_violation(self) -> None:
        """e_1 in child scope, e_2 in parent scope. Initiator of e_2 NOT involved
        in the child scope tree (o_sub-1(e_2))."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("B", "choreo:initiator"),
                    _rel("C", "choreo:participant"),
                    _rel("sub_child", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("X", "choreo:initiator"),  # X not in sub_child events
                    _rel("A", "choreo:participant"),
                    _rel("sub_parent", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[
                _obj("sub_parent", "Subchoreography", [
                    _rel("sub_child", "choreo:contains"),
                ]),
                _obj("sub_child", "Subchoreography"),
            ],
        )
        r = check_c15(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e2"


# ---------------------------------------------------------------------------
# Case 2 — Exiting to top level
# ---------------------------------------------------------------------------


class TestC15Case2:

    def test_exiting_pass(self) -> None:
        """e_1 in a scope, e_2 is top-level. Initiator of e_2 is involved in root scope tree."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("sub1", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("C", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                    # no choreo:contained-by → top-level
                ]),
            ],
            objects=[_obj("sub1", "Subchoreography")],
        )
        r = check_c15(build_index(ocel))
        assert r.passed

    def test_exiting_violation(self) -> None:
        """e_1 in a scope, e_2 is top-level. Initiator of e_2 NOT involved in root scope tree."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("sub1", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("X", "choreo:initiator"),  # X not in sub1 scope tree
                    _rel("Y", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub1", "Subchoreography")],
        )
        r = check_c15(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e2"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestC15EdgeCases:

    def test_empty_log(self) -> None:
        r = check_c15(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0

    def test_single_event(self) -> None:
        ocel = _minimal_ocel([
            _event("e1", "2024-01-01T00:00:00.000Z", [
                _rel("A", "choreo:initiator"),
                _rel("B", "choreo:participant"),
                _rel("inst1", "choreo:instance"),
            ]),
        ])
        r = check_c15(build_index(ocel))
        assert r.passed
        assert r.elements_checked == 0

    def test_different_instances_checked_separately(self) -> None:
        """Events in different instances are not checked against each other."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00.000Z", [
                    _rel("A", "choreo:initiator"),
                    _rel("B", "choreo:participant"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:00:00.001Z", [
                    _rel("X", "choreo:initiator"),  # different from A,B
                    _rel("Y", "choreo:participant"),
                    _rel("inst2", "choreo:instance"),  # different instance
                ]),
            ],
        )
        r = check_c15(build_index(ocel))
        assert r.passed  # no pairs within either instance
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# validate_all includes C15
# ---------------------------------------------------------------------------


class TestValidateAllIncludesC15:

    def test_all_17_constraints(self, swap1_ocel: dict) -> None:
        results = validate_all(build_index(swap1_ocel))
        expected = {f"C{i}" for i in range(17)}
        assert set(results.keys()) == expected
        assert all(r.passed for r in results.values())
