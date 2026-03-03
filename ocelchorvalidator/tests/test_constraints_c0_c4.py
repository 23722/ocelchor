"""Tests for constraints C0–C4 (task structure)."""

from __future__ import annotations

from ocelchorvalidator.constraints import (
    ConstraintResult,
    Violation,
    check_c0,
    check_c1,
    check_c2,
    check_c3,
    check_c4,
    validate,
    validate_all,
)
from ocelchorvalidator.index import build_index


# ---------------------------------------------------------------------------
# Helpers to build minimal OCEL dicts for negative tests
# ---------------------------------------------------------------------------

def _minimal_ocel(events: list[dict], objects: list[dict] | None = None) -> dict:
    return {
        "objectTypes": [],
        "eventTypes": [],
        "objects": objects or [],
        "events": events,
    }


def _event(eid: str, rels: list[dict]) -> dict:
    return {"id": eid, "type": "test", "time": "2024-01-01T00:00:00Z", "relationships": rels}


def _rel(oid: str, qualifier: str) -> dict:
    return {"objectId": oid, "qualifier": qualifier}


def _obj(oid: str, otype: str = "test", rels: list[dict] | None = None) -> dict:
    o: dict = {"id": oid, "type": otype}
    if rels:
        o["relationships"] = rels
    return o


# ---------------------------------------------------------------------------
# C0 — Instance linking
# ---------------------------------------------------------------------------


class TestC0:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c0(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c0(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 8

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c0(build_index(swap_root_only_ocel))
        assert r.passed
        assert r.elements_checked == 1

    def test_no_instance(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("o_i", "choreo:initiator"),
            _rel("o_p", "choreo:participant"),
        ])])
        r = check_c0(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 1
        assert r.violations[0].event_id == "e1"

    def test_two_instances(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("inst1", "choreo:instance"),
            _rel("inst2", "choreo:instance"),
        ])])
        r = check_c0(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e1"

    def test_empty_log(self) -> None:
        ocel = _minimal_ocel([])
        r = check_c0(build_index(ocel))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C1 — Message participation
# ---------------------------------------------------------------------------


class TestC1:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c1(build_index(swap1_ocel))
        assert r.passed
        # swap_1: root event has 1 message, swap event has 2 messages → 3 checked
        assert r.elements_checked == 3

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c1(build_index(swap3_ocel))
        assert r.passed

    def test_source_not_in_roles(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("outsider", "choreo:source"),
                _rel("o_p", "choreo:target"),
            ])],
        )
        r = check_c1(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 1
        assert "source" in r.violations[0].message.lower()

    def test_target_not_in_roles(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
                _rel("outsider", "choreo:target"),
            ])],
        )
        r = check_c1(build_index(ocel))
        assert not r.passed
        assert "target" in r.violations[0].message.lower()

    def test_empty_log(self) -> None:
        r = check_c1(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C2 — Single initiator
# ---------------------------------------------------------------------------


class TestC2:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c2(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c2(build_index(swap_root_only_ocel))
        assert r.passed

    def test_no_initiator(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("o_p", "choreo:participant"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c2(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e1"

    def test_two_initiators(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("o_i1", "choreo:initiator"),
            _rel("o_i2", "choreo:initiator"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c2(build_index(ocel))
        assert not r.passed


# ---------------------------------------------------------------------------
# C3 — Single participant
# ---------------------------------------------------------------------------


class TestC3:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c3(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_no_participant(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("o_i", "choreo:initiator"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c3(build_index(ocel))
        assert not r.passed

    def test_two_participants(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("o_p1", "choreo:participant"),
            _rel("o_p2", "choreo:participant"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c3(build_index(ocel))
        assert not r.passed


# ---------------------------------------------------------------------------
# C4 — Role exclusivity
# ---------------------------------------------------------------------------


class TestC4:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c4(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_same_object_both_roles(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("0xAAA", "choreo:initiator"),
            _rel("0xAAA", "choreo:participant"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c4(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 1
        assert r.violations[0].event_id == "e1"
        assert r.violations[0].object_id == "0xAAA"

    def test_different_objects_ok(self) -> None:
        ocel = _minimal_ocel([_event("e1", [
            _rel("0xAAA", "choreo:initiator"),
            _rel("0xBBB", "choreo:participant"),
            _rel("inst1", "choreo:instance"),
        ])])
        r = check_c4(build_index(ocel))
        assert r.passed


# ---------------------------------------------------------------------------
# validate / validate_all API
# ---------------------------------------------------------------------------


class TestValidateAPI:

    def test_validate_all_returns_all_constraints(self, swap1_ocel: dict) -> None:
        results = validate_all(build_index(swap1_ocel))
        assert {"C0", "C1", "C2", "C3", "C4"} <= set(results.keys())
        assert all(r.passed for r in results.values())

    def test_validate_subset(self, swap1_ocel: dict) -> None:
        results = validate(build_index(swap1_ocel), ["C0", "C2"])
        assert set(results.keys()) == {"C0", "C2"}

    def test_validate_none_means_all(self, swap1_ocel: dict) -> None:
        results = validate(build_index(swap1_ocel))
        assert {"C0", "C1", "C2", "C3", "C4"} <= set(results.keys())

    def test_validate_unknown_id_skipped(self, swap1_ocel: dict) -> None:
        results = validate(build_index(swap1_ocel), ["C0", "C99"])
        assert set(results.keys()) == {"C0"}


class TestDataclasses:

    def test_violation_fields(self) -> None:
        v = Violation("C0", "test msg", "e1", "o1")
        assert v.constraint == "C0"
        assert v.message == "test msg"
        assert v.event_id == "e1"
        assert v.object_id == "o1"

    def test_constraint_result_properties(self) -> None:
        r = ConstraintResult("C0", 5, [Violation("C0", "bad", "e1")])
        assert not r.passed
        assert r.num_violations == 1

    def test_constraint_result_passed(self) -> None:
        r = ConstraintResult("C0", 5)
        assert r.passed
        assert r.num_violations == 0
