"""Tests for constraints C11–C14 (subchoreography / containment hierarchy)."""

from __future__ import annotations

from ocelchorvalidator.constraints import (
    check_c11,
    check_c12,
    check_c13,
    check_c14,
    validate_all,
)
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
# C11 — Containment uniqueness
# ---------------------------------------------------------------------------


class TestC11:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c11(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c11(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 8

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c11(build_index(swap_root_only_ocel))
        assert r.passed

    def test_two_contained_by(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("sub_a", "choreo:contained-by"),
                _rel("sub_b", "choreo:contained-by"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[
                _obj("sub_a", "Subchoreography"),
                _obj("sub_b", "Subchoreography"),
            ],
        )
        r = check_c11(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e1"

    def test_empty_log(self) -> None:
        r = check_c11(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C12 — Non-empty scope
# ---------------------------------------------------------------------------


class TestC12:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c12(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 1

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c12(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 3

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c12(build_index(swap_root_only_ocel))
        assert r.passed
        assert r.elements_checked == 0  # no scoping objects

    def test_empty_scope(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("sub_orphan", "Subchoreography")],
        )
        r = check_c12(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "sub_orphan"

    def test_empty_log(self) -> None:
        r = check_c12(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C13 — Instance consistency
# ---------------------------------------------------------------------------


class TestC13:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c13(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 1  # 1 scoping object with events

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c13(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 3

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c13(build_index(swap_root_only_ocel))
        assert r.passed
        assert r.elements_checked == 0

    def test_mixed_instances(self) -> None:
        ocel = _minimal_ocel(
            events=[
                _event("e1", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst2", "choreo:instance"),  # different instance
                ]),
            ],
            objects=[_obj("sub_a", "Subchoreography")],
        )
        r = check_c13(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "sub_a"

    def test_empty_log(self) -> None:
        r = check_c13(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C14 — Nesting structure
# ---------------------------------------------------------------------------


class TestC14:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c14(build_index(swap1_ocel))
        assert r.passed

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c14(build_index(swap3_ocel))
        assert r.passed
        assert r.elements_checked == 3  # 3 scoping objects checked

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c14(build_index(swap_root_only_ocel))
        assert r.passed
        assert r.elements_checked == 0

    def test_two_parents(self) -> None:
        """Scoping object with 2 incoming choreo:contains."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", [
                    _rel("sub_child", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[
                _obj("sub_parent1", "Subchoreography", [
                    _rel("sub_child", "choreo:contains"),
                ]),
                _obj("sub_parent2", "Subchoreography", [
                    _rel("sub_child", "choreo:contains"),
                ]),
                _obj("sub_child", "Subchoreography"),
            ],
        )
        r = check_c14(build_index(ocel))
        assert not r.passed
        has_parent_violation = any("parent" in v.message.lower() for v in r.violations)
        assert has_parent_violation

    def test_instance_mismatch_across_nesting(self) -> None:
        """Parent scope events link to inst1, child scope events link to inst2."""
        ocel = _minimal_ocel(
            events=[
                _event("e_parent", [
                    _rel("sub_parent", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e_child", [
                    _rel("sub_child", "choreo:contained-by"),
                    _rel("inst2", "choreo:instance"),
                ]),
            ],
            objects=[
                _obj("sub_parent", "Subchoreography", [
                    _rel("sub_child", "choreo:contains"),
                ]),
                _obj("sub_child", "Subchoreography"),
            ],
        )
        r = check_c14(build_index(ocel))
        assert not r.passed
        has_instance_violation = any("instance" in v.message.lower() for v in r.violations)
        assert has_instance_violation

    def test_cycle(self) -> None:
        """sub_a contains sub_b, sub_b contains sub_a → cycle."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", [
                    _rel("sub_b", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[
                _obj("sub_a", "Subchoreography", [
                    _rel("sub_b", "choreo:contains"),
                ]),
                _obj("sub_b", "Subchoreography", [
                    _rel("sub_a", "choreo:contains"),
                ]),
            ],
        )
        r = check_c14(build_index(ocel))
        assert not r.passed
        has_cycle_violation = any("cycle" in v.message.lower() for v in r.violations)
        assert has_cycle_violation

    def test_empty_log(self) -> None:
        r = check_c14(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# validate_all now includes C11–C14
# ---------------------------------------------------------------------------


class TestValidateAllIncludesC11C14:

    def test_all_keys(self, swap1_ocel: dict) -> None:
        results = validate_all(build_index(swap1_ocel))
        for cid in ["C11", "C12", "C13", "C14"]:
            assert cid in results
            assert results[cid].passed
