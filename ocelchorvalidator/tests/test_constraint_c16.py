"""Tests for constraint C16 — scope re-entry."""

from __future__ import annotations

from ocelchorvalidator.constraints import check_c16, validate_all
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
# Positive cases (real logs)
# ---------------------------------------------------------------------------


class TestC16Positive:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c16(build_index(swap1_ocel))
        assert r.passed

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c16(build_index(swap3_ocel))
        assert r.passed

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c16(build_index(swap_root_only_ocel))
        assert r.passed

    def test_empty_log(self) -> None:
        r = check_c16(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# Minimal: no re-entry (stays inside scope)
# ---------------------------------------------------------------------------


class TestC16NoReentry:

    def test_always_inside(self) -> None:
        """All events of the instance are inside the scope — no violation."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert r.passed

    def test_always_outside(self) -> None:
        """Instance never enters the scope — no violation."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert r.passed

    def test_inside_then_outside_no_reentry(self) -> None:
        """e1 inside, e2 outside — exits cleanly, no re-entry."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("inst1", "choreo:instance"),  # outside scope
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert r.passed


# ---------------------------------------------------------------------------
# Negative: re-entry violation
# ---------------------------------------------------------------------------


class TestC16Violation:

    def test_reentry_violation(self) -> None:
        """e1 inside, e2 outside (exit), e3 inside again → violation on e3."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("inst1", "choreo:instance"),  # outside
                ]),
                _event("e3", "2024-01-01T00:02:00Z", [
                    _rel("sub_a", "choreo:contained-by"),  # re-enters
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 1
        assert r.violations[0].event_id == "e3"
        assert r.violations[0].object_id == "sub_a"

    def test_multiple_reentries(self) -> None:
        """e1 in, e2 out, e3 in, e4 out, e5 in → two re-entry violations."""
        ocel = _minimal_ocel(
            events=[
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e3", "2024-01-01T00:02:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e4", "2024-01-01T00:03:00Z", [
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e5", "2024-01-01T00:04:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 2
        violation_eids = {v.event_id for v in r.violations}
        assert "e3" in violation_eids
        assert "e5" in violation_eids

    def test_different_instances_independent(self) -> None:
        """inst1 exits and re-enters; inst2 stays inside — only inst1 violates."""
        ocel = _minimal_ocel(
            events=[
                # inst1: in, out, in (violation)
                _event("e1", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e2", "2024-01-01T00:01:00Z", [
                    _rel("inst1", "choreo:instance"),
                ]),
                _event("e3", "2024-01-01T00:02:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst1", "choreo:instance"),
                ]),
                # inst2: in, in (no violation)
                _event("e4", "2024-01-01T00:00:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst2", "choreo:instance"),
                ]),
                _event("e5", "2024-01-01T00:01:00Z", [
                    _rel("sub_a", "choreo:contained-by"),
                    _rel("inst2", "choreo:instance"),
                ]),
            ],
            objects=[_obj("sub_a", "subchoreographyInstance")],
        )
        r = check_c16(build_index(ocel))
        assert not r.passed
        assert r.num_violations == 1
        assert r.violations[0].event_id == "e3"


# ---------------------------------------------------------------------------
# validate_all includes C16
# ---------------------------------------------------------------------------


class TestValidateAllIncludesC16:

    def test_c16_key_present(self, swap1_ocel: dict) -> None:
        results = validate_all(build_index(swap1_ocel))
        assert "C16" in results
        assert results["C16"].passed
