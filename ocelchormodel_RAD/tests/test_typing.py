"""M1 — typing: taskType / scopeType and the pooling equalities (spec §B2)."""

from __future__ import annotations

import pytest

from ocelchormodel_rad.reader import UntypeableScope
from ocelchormodel_rad.typing import ScopeType, TaskType, scope_certified, scope_type, task_type


def _event(model, eid):
    return model.events[eid]


def test_task_type_carries_exec_and_roles(worked_example):
    m = worked_example
    tt = task_type(m, _event(m, "e:A:R:req"))
    assert tt == TaskType("Request unlock [Gov]", "Proxy", "Governance")


def test_response_reverses_roles(worked_example):
    m = worked_example
    tt = task_type(m, _event(m, "e:A:R:res"))
    # Response event: initiator is the callee (Governance), participant the caller (Proxy).
    assert tt == TaskType("Respond to unlock [Gov]", "Governance", "Proxy")


def test_scope_typed_by_name_and_first_task_roles(worked_example):
    """Rung 1: stored name; roles from the first task event (spec §B2.3)."""
    m = worked_example
    st = scope_type(m, "sub:A:root")
    assert st == ScopeType("unlock [Gov]", "Proxy", "Governance")
    assert scope_certified(m, "sub:A:root") is True


def test_scope_label_rung2_derivation(worked_example):
    """Without a stored name, the label derives from the first task event's
    type with the kind prefix stripped — identical result on this fixture."""
    m = worked_example
    del m.scope_names["sub:A:root"]
    st = scope_type(m, "sub:A:root")
    assert st == ScopeType("unlock [Gov]", "Proxy", "Governance")


def test_untypeable_scope_reported_not_repaired():
    """A scope with no task event raises; no fallback type is invented."""
    ocel = {
        "objectTypes": [], "eventTypes": [],
        "objects": [
            {"id": "i", "type": "choreographyInstance", "relationships": []},
            {"id": "s", "type": "subchoreographyInstance",
             "attributes": [{"name": "name", "value": "ghost [X]"}],
             "relationships": []},
        ],
        "events": [{
            # internal event: no initiator/participant edges -> not in E_T
            "id": "e1", "type": "internal log write",
            "time": "2020-01-01T00:00:00.000Z", "attributes": [],
            "relationships": [
                {"objectId": "s", "qualifier": "choreo:contained-by"},
                {"objectId": "i", "qualifier": "choreo:instance"},
            ],
        }],
    }
    from ocelchormodel_rad import reader
    m = reader.build_model(ocel, run_validator=False)
    assert m.non_task_events == 1
    with pytest.raises(UntypeableScope):
        scope_type(m, "s")


def test_transfer_frames_pool_to_one_scope_type(worked_example):
    """scopeType(T1)==scopeType(T1')==scopeType(T2') — the equality that drives pooling."""
    m = worked_example
    st_a = scope_type(m, "sub:A:t1")
    st_b1 = scope_type(m, "sub:B:t1")
    st_b2 = scope_type(m, "sub:B:t2")
    assert st_a == st_b1 == st_b2
    assert st_a == ScopeType("transfer [TORN]", "Governance", "TORN")


def test_task_and_scope_types_are_hashable(worked_example):
    m = worked_example
    s = {scope_type(m, sid) for sid in m.scopes}
    t = {task_type(m, e) for e in m.events.values()}
    # Two distinct scope types (unlock, transfer); several task types.
    assert len(s) == 2
    assert TaskType("hook [Vault]", "TORN", "Vault") in t


def test_missing_receiver_routed_into_typing_with_reserved_empty_role():
    """C3 shape |noninit| = 0: the event is typed with the reserved empty
    participant role — NOT filtered into the non-task count. Filtering it
    would silently shift the enclosing scope's first_task_in onto the next
    event (here the nested call's bracket) and corrupt the scope's roles."""
    ocel = {
        "objectTypes": [], "eventTypes": [],
        "objects": [
            {"id": "i", "type": "choreographyInstance", "relationships": []},
            {"id": "eoa", "type": "EOA", "relationships": []},
            {"id": "0xfeed", "type": "Vault", "relationships": []},
            {"id": "s", "type": "subchoreographyInstance",
             "attributes": [{"name": "name", "value": "0x60806040 []"}],
             "relationships": []},
        ],
        "events": [
            {
                # scope opener: receiver unrecorded (no participant edge)
                "id": "e:root:req", "type": "Request 0x60806040 []",
                "time": "2020-01-01T00:00:00.000Z", "attributes": [],
                "relationships": [
                    {"objectId": "eoa", "qualifier": "choreo:initiator"},
                    {"objectId": "s", "qualifier": "choreo:contained-by"},
                    {"objectId": "i", "qualifier": "choreo:instance"},
                ],
            },
            {
                # nested call with full role edges, one tick later
                "id": "e:0_1", "type": "init [Vault]",
                "time": "2020-01-01T00:00:00.001Z", "attributes": [],
                "relationships": [
                    {"objectId": "0xfeed", "qualifier": "choreo:initiator"},
                    {"objectId": "eoa", "qualifier": "choreo:participant"},
                    {"objectId": "s", "qualifier": "choreo:contained-by"},
                    {"objectId": "i", "qualifier": "choreo:instance"},
                ],
            },
        ],
    }
    from ocelchormodel_rad import reader
    m = reader.build_model(ocel, run_validator=False)
    assert m.non_task_events == 0
    assert m.missing_receiver_events == ["e:root:req"]
    assert m.events["e:root:req"].participant == ""

    tt = task_type(m, m.events["e:root:req"])
    assert tt == TaskType("Request 0x60806040 []", "EOA", "")

    # The scope is typed by its true opener: ⟨EOA, ""⟩ — not by the nested
    # call's ⟨Vault, EOA⟩, and the opener still certifies (D2).
    st = scope_type(m, "s")
    assert st == ScopeType("0x60806040 []", "EOA", "")
    assert scope_certified(m, "s") is True


def test_multicast_receiver_aborts():
    """C3 shape |noninit| > 1: the taskType tuple is undefined — the miner
    aborts rather than silently dropping a receiver."""
    from ocelchormodel_rad import reader
    ocel = {
        "objectTypes": [], "eventTypes": [],
        "objects": [
            {"id": "i", "type": "choreographyInstance", "relationships": []},
            {"id": "a", "type": "drone", "relationships": []},
            {"id": "b", "type": "tractor_1", "relationships": []},
            {"id": "c", "type": "tractor_2", "relationships": []},
        ],
        "events": [{
            "id": "e1", "type": "broadcast",
            "time": "2020-01-01T00:00:00.000Z", "attributes": [],
            "relationships": [
                {"objectId": "a", "qualifier": "choreo:initiator"},
                {"objectId": "b", "qualifier": "choreo:participant"},
                {"objectId": "c", "qualifier": "choreo:participant"},
                {"objectId": "i", "qualifier": "choreo:instance"},
            ],
        }],
    }
    with pytest.raises(reader.ContractViolation, match="multicast"):
        reader.build_model(ocel, run_validator=False)
