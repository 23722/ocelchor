"""Tests for constraints C5–C10 (message constraints)."""

from __future__ import annotations

from ocelchorvalidator.constraints import (
    check_c5,
    check_c6,
    check_c7,
    check_c8,
    check_c9,
    check_c10,
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


def _valid_event_and_objects():
    """A valid event with initiator, participant, initiating message, and return message."""
    return (
        _event("e1", [
            _rel("o_i", "choreo:initiator"),
            _rel("o_p", "choreo:participant"),
            _rel("msg_init", "choreo:message"),
            _rel("msg_ret", "choreo:message"),
            _rel("inst1", "choreo:instance"),
        ]),
        [
            _obj("msg_init", "call", [
                _rel("o_i", "choreo:source"),
                _rel("o_p", "choreo:target"),
            ]),
            _obj("msg_ret", "call response", [
                _rel("o_p", "choreo:source"),
                _rel("o_i", "choreo:target"),
            ]),
        ],
    )


# ---------------------------------------------------------------------------
# C5 — Message source uniqueness
# ---------------------------------------------------------------------------


class TestC5:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c5(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 3  # 1 + 2 messages

    def test_positive_swap3(self, swap3_ocel: dict) -> None:
        r = check_c5(build_index(swap3_ocel))
        assert r.passed

    def test_no_source(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call")],  # no relationships → no source
        )
        r = check_c5(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "msg1"

    def test_two_sources(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
                _rel("o_x", "choreo:source"),
            ])],
        )
        r = check_c5(build_index(ocel))
        assert not r.passed

    def test_empty_log(self) -> None:
        r = check_c5(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C6 — Message target uniqueness
# ---------------------------------------------------------------------------


class TestC6:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c6(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 3

    def test_no_target(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
            ])],  # source but no target
        )
        r = check_c6(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "msg1"

    def test_two_targets(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
                _rel("o_p", "choreo:target"),
                _rel("o_x", "choreo:target"),
            ])],
        )
        r = check_c6(build_index(ocel))
        assert not r.passed

    def test_empty_log(self) -> None:
        r = check_c6(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C7 — Initiating message
# ---------------------------------------------------------------------------


class TestC7:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c7(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2

    def test_positive_root_only(self, swap_root_only_ocel: dict) -> None:
        r = check_c7(build_index(swap_root_only_ocel))
        assert r.passed

    def test_no_initiating_message(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_p", "choreo:source"),  # source is participant, not initiator
                _rel("o_i", "choreo:target"),
            ])],
        )
        r = check_c7(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e1"

    def test_two_initiating_messages(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("msg2", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[
                _obj("msg1", "call", [
                    _rel("o_i", "choreo:source"),
                    _rel("o_p", "choreo:target"),
                ]),
                _obj("msg2", "call", [
                    _rel("o_i", "choreo:source"),
                    _rel("o_p", "choreo:target"),
                ]),
            ],
        )
        r = check_c7(build_index(ocel))
        assert not r.passed

    def test_empty_log(self) -> None:
        r = check_c7(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C8 — At most one return message
# ---------------------------------------------------------------------------


class TestC8:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c8(build_index(swap1_ocel))
        assert r.passed

    def test_positive_root_only_no_return(self, swap_root_only_ocel: dict) -> None:
        r = check_c8(build_index(swap_root_only_ocel))
        assert r.passed

    def test_two_return_messages(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg_init", "choreo:message"),
                _rel("msg_ret1", "choreo:message"),
                _rel("msg_ret2", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[
                _obj("msg_init", "call", [
                    _rel("o_i", "choreo:source"),
                    _rel("o_p", "choreo:target"),
                ]),
                _obj("msg_ret1", "resp1", [
                    _rel("o_p", "choreo:source"),
                    _rel("o_i", "choreo:target"),
                ]),
                _obj("msg_ret2", "resp2", [
                    _rel("o_p", "choreo:source"),
                    _rel("o_i", "choreo:target"),
                ]),
            ],
        )
        r = check_c8(build_index(ocel))
        assert not r.passed
        assert r.violations[0].event_id == "e1"

    def test_empty_log(self) -> None:
        r = check_c8(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C9 — Initiating message target
# ---------------------------------------------------------------------------


class TestC9:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c9(build_index(swap1_ocel))
        assert r.passed
        assert r.elements_checked == 2  # 2 events, each with 1 initiating message

    def test_wrong_target(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
                _rel("outsider", "choreo:target"),  # not the participant
            ])],
        )
        r = check_c9(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "msg1"

    def test_empty_log(self) -> None:
        r = check_c9(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# C10 — Return message target
# ---------------------------------------------------------------------------


class TestC10:

    def test_positive_swap1(self, swap1_ocel: dict) -> None:
        r = check_c10(build_index(swap1_ocel))
        assert r.passed
        # swap_1: only swap event has a return message → 1 checked
        assert r.elements_checked == 1

    def test_wrong_target(self) -> None:
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg_init", "choreo:message"),
                _rel("msg_ret", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[
                _obj("msg_init", "call", [
                    _rel("o_i", "choreo:source"),
                    _rel("o_p", "choreo:target"),
                ]),
                _obj("msg_ret", "call response", [
                    _rel("o_p", "choreo:source"),
                    _rel("outsider", "choreo:target"),  # not the initiator
                ]),
            ],
        )
        r = check_c10(build_index(ocel))
        assert not r.passed
        assert r.violations[0].object_id == "msg_ret"

    def test_no_return_message_passes(self) -> None:
        """Event with only an initiating message → C10 passes (nothing to check)."""
        ocel = _minimal_ocel(
            events=[_event("e1", [
                _rel("o_i", "choreo:initiator"),
                _rel("o_p", "choreo:participant"),
                _rel("msg1", "choreo:message"),
                _rel("inst1", "choreo:instance"),
            ])],
            objects=[_obj("msg1", "call", [
                _rel("o_i", "choreo:source"),
                _rel("o_p", "choreo:target"),
            ])],
        )
        r = check_c10(build_index(ocel))
        assert r.passed
        assert r.elements_checked == 0

    def test_empty_log(self) -> None:
        r = check_c10(build_index(_minimal_ocel([])))
        assert r.passed
        assert r.elements_checked == 0


# ---------------------------------------------------------------------------
# validate_all now includes C5–C10
# ---------------------------------------------------------------------------


class TestValidateAllIncludesC5C10:

    def test_all_keys(self, swap1_ocel: dict) -> None:
        results = validate_all(build_index(swap1_ocel))
        for cid in ["C5", "C6", "C7", "C8", "C9", "C10"]:
            assert cid in results
            assert results[cid].passed
