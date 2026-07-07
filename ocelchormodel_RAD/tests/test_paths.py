"""M1 — paths: ≻ ordering, one hierarchical trace per instance, D9 (spec §B2.4)."""

from __future__ import annotations

import pytest

from ocelchormodel_rad import reader
from ocelchormodel_rad.paths import all_traces, event_path, instance_order
from ocelchormodel_rad.reader import OrderingTie
from ocelchormodel_rad.typing import ScopeType, TaskType


def _render(path):
    """Render an EventPath to comparable tuples: scopes as ('S', ...), leaf as ('T', ...)."""
    out = []
    for node in path:
        if isinstance(node, ScopeType):
            o = node.opener
            out.append(("S", o.exec_type, o.init_role, o.noninit_role))
        else:
            assert isinstance(node, TaskType)
            out.append(("T", node.exec_type, node.init_role, node.noninit_role))
    return tuple(out)


def test_one_trace_per_instance(worked_example):
    tr = all_traces(worked_example)
    assert len(tr) == 2
    lengths = sorted(len(v) for v in tr.values())
    assert lengths == [5, 8]


def test_instance_order_is_by_timestamp(worked_example):
    ids = [e.id for e in instance_order(worked_example, "choreographyInstance:A")]
    assert ids == [
        "e:A:R:req", "e:A:t1:req", "e:A:t1:hook", "e:A:t1:res", "e:A:R:res",
    ]


def test_event_path_snapshot_instance_a(worked_example):
    m = worked_example
    S_UNLOCK = ("S", "Request unlock [Gov]", "Proxy", "Governance")
    S_TRANSFER = ("S", "Request transfer [TORN]", "Governance", "TORN")
    paths = [_render(event_path(m, e)) for e in instance_order(m, "choreographyInstance:A")]
    assert paths == [
        (S_UNLOCK, ("T", "Request unlock [Gov]", "Proxy", "Governance")),
        (S_UNLOCK, S_TRANSFER, ("T", "Request transfer [TORN]", "Governance", "TORN")),
        (S_UNLOCK, S_TRANSFER, ("T", "hook [Vault]", "TORN", "Vault")),
        (S_UNLOCK, S_TRANSFER, ("T", "Respond to transfer [TORN]", "TORN", "Governance")),
        (S_UNLOCK, ("T", "Respond to unlock [Gov]", "Governance", "Proxy")),
    ]


def test_flat_events_have_length_one_paths():
    """A flat log (no scopes) yields event paths of length 1 (just the leaf)."""
    ocel = {
        "objectTypes": [], "eventTypes": [],
        "objects": [
            {"id": "i", "type": "choreographyInstance", "relationships": []},
            {"id": "a", "type": "RoleA", "relationships": []},
            {"id": "b", "type": "RoleB", "relationships": []},
        ],
        "events": [{
            "id": "e1", "type": "greet", "time": "2020-01-01T00:00:00.000Z",
            "attributes": [],
            "relationships": [
                {"objectId": "a", "qualifier": "choreo:initiator"},
                {"objectId": "b", "qualifier": "choreo:participant"},
                {"objectId": "i", "qualifier": "choreo:instance"},
            ],
        }],
    }
    m = reader.build_model(ocel, run_validator=False)
    (path,) = [event_path(m, e) for e in instance_order(m, "i")]
    assert len(path) == 1
    assert path[0] == TaskType("greet", "RoleA", "RoleB")


def test_ordering_tie_is_hard_error():
    same = "2020-01-01T00:00:00.000Z"
    ocel = {
        "objectTypes": [], "eventTypes": [],
        "objects": [
            {"id": "i", "type": "choreographyInstance", "relationships": []},
            {"id": "a", "type": "RoleA", "relationships": []},
            {"id": "b", "type": "RoleB", "relationships": []},
        ],
        "events": [
            {"id": "e1", "type": "x", "time": same, "attributes": [], "relationships": [
                {"objectId": "a", "qualifier": "choreo:initiator"},
                {"objectId": "b", "qualifier": "choreo:participant"},
                {"objectId": "i", "qualifier": "choreo:instance"}]},
            {"id": "e2", "type": "y", "time": same, "attributes": [], "relationships": [
                {"objectId": "a", "qualifier": "choreo:initiator"},
                {"objectId": "b", "qualifier": "choreo:participant"},
                {"objectId": "i", "qualifier": "choreo:instance"}]},
        ],
    }
    m = reader.build_model(ocel, run_validator=False)
    with pytest.raises(OrderingTie):
        instance_order(m, "i")
