"""M1 — typing: taskType / scopeType and the pooling equalities (spec §B2)."""

from __future__ import annotations

from ocelchormodel_rad.typing import ScopeType, TaskType, scope_type, task_type


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


def test_scope_typed_by_request_bracket(worked_example):
    m = worked_example
    st = scope_type(m, "sub:A:root")
    assert st.opener_is_request is True
    assert st.opener == TaskType("Request unlock [Gov]", "Proxy", "Governance")


def test_transfer_frames_pool_to_one_scope_type(worked_example):
    """scopeType(T1)==scopeType(T1')==scopeType(T2') — the equality that drives pooling."""
    m = worked_example
    st_a = scope_type(m, "sub:A:t1")
    st_b1 = scope_type(m, "sub:B:t1")
    st_b2 = scope_type(m, "sub:B:t2")
    assert st_a == st_b1 == st_b2
    assert st_a == ScopeType(TaskType("Request transfer [TORN]", "Governance", "TORN"), True)


def test_task_and_scope_types_are_hashable(worked_example):
    m = worked_example
    s = {scope_type(m, sid) for sid in m.scopes}
    t = {task_type(m, e) for e in m.events.values()}
    # Two distinct scope types (unlock, transfer); several task types.
    assert len(s) == 2
    assert TaskType("hook [Vault]", "TORN", "Vault") in t
