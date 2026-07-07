"""M1 — reader: load, hard gates, kind parsing (spec §B8/§B10)."""

from __future__ import annotations

import pytest

from ocelchormodel_rad import reader
from ocelchormodel_rad.reader import ContractViolation


def test_loads_two_instances(worked_example):
    assert len(worked_example.instances) == 2
    assert len(worked_example.scopes) == 5  # A: root+t1 ; B: root+t1+t2


def test_kind_parsed_from_prefix_only(worked_example):
    m = worked_example
    kinds = {e.type: m.kind(e) for e in m.events.values()}
    assert kinds["Request unlock [Gov]"] == "request"
    assert kinds["Respond to unlock [Gov]"] == "response"
    assert kinds["hook [Vault]"] == "atomic"


def test_scope_hierarchy_recorded(worked_example):
    m = worked_example
    # Instance B root contains two transfer scopes.
    root_b = "sub:B:root"
    assert set(m.scope_contains[root_b]) == {"sub:B:t1", "sub:B:t2"}
    assert m.scope_parent["sub:B:t1"] == root_b


def test_all_events_transitive(worked_example):
    m = worked_example
    # Root scope of A transitively contains the transfer frame's events.
    all_ids = {e.id for e in m.all_events("sub:A:root")}
    assert "e:A:t1:hook" in all_ids  # a descendant-scope event
    assert "e:A:R:req" in all_ids  # a direct event


def test_hard_gate_aborts_on_missing_initiator(worked_example_path):
    import json

    ocel = json.loads(worked_example_path.read_text())
    # Strip the initiator from one event → C2 violation (a hard gate).
    for e in ocel["events"]:
        e["relationships"] = [r for r in e["relationships"] if r["qualifier"] != "choreo:initiator"]
        break
    with pytest.raises(ContractViolation):
        reader.build_model(ocel)


def test_run_validator_false_skips_gates(worked_example_path):
    import json

    ocel = json.loads(worked_example_path.read_text())
    for e in ocel["events"]:
        e["relationships"] = [r for r in e["relationships"] if r["qualifier"] != "choreo:initiator"]
        break
    # With the validator off, no gate is asserted (used only for controlled tests).
    m = reader.build_model(ocel, run_validator=False)
    assert m.constraints == {}
