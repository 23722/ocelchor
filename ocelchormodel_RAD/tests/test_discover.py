"""M2 — discovery acceptance (spec build-order M2 / §B4).

Mandatory: frame-exact splitting, context separation, fixture pooling, and
recursion detection (D12) on Beanstalk with the refreshed-audit behaviour on
the other logs.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from ocelchormodel_rad import reader
from ocelchormodel_rad.discover import discover, project
from ocelchormodel_rad.typing import ScopeType, TaskType

FIXTURES = Path(__file__).parent / "fixtures"
BLOCKCHAIN = Path(__file__).resolve().parents[2] / "ocelchormodel" / "data" / "input"

# Load the fixture builder module so tests can synthesise small logs.
_spec = importlib.util.spec_from_file_location("_wex", FIXTURES / "build_worked_example.py")
_wex = importlib.util.module_from_spec(_spec)
sys.modules["_wex"] = _wex
_spec.loader.exec_module(_wex)


def render(n) -> str:
    """Render a TreeNode to a compact s-expression over exec types."""
    if n.op == "NS":
        return f"NS[{n.label.opener.exec_type}]({render(n.children[0])})"
    if n.op is None:
        if n.label is None:
            return "tau"
        if isinstance(n.label, TaskType):
            return f"'{n.label.exec_type}'"
        return f"REF[{n.label.opener.exec_type}]"
    return f"{n.op}(" + ", ".join(render(c) for c in n.children) + ")"


# --- fixture pooling + frame-exact splitting ------------------------------

def test_fixture_frame_exact_and_pooling(worked_example):
    d = discover(worked_example)
    assert render(d.tree) == (
        "NS[Request unlock [Gov]]("
        "→("
        "'Request unlock [Gov]', "
        "↻(NS[Request transfer [TORN]]("
        "→('Request transfer [TORN]', 'hook [Vault]', 'Respond to transfer [TORN]')"
        "), tau), "
        "'Respond to unlock [Gov]'"
        "))"
    )
    # Three transfer frames pooled into ONE submodel; repetition lifted to a loop.
    assert d.recursion == []


def test_single_instance_reproduces_structure():
    b = _wex.Builder()
    _wex._instance(b, "A", transfer_frames=1)
    m = reader.build_model(b.build())
    d = discover(m)
    # One frame → no loop; the transfer frame stays a single named subtree.
    assert render(d.tree) == (
        "NS[Request unlock [Gov]]("
        "→("
        "'Request unlock [Gov]', "
        "NS[Request transfer [TORN]]("
        "→('Request transfer [TORN]', 'hook [Vault]', 'Respond to transfer [TORN]')"
        "), "
        "'Respond to unlock [Gov]'"
        "))"
    )


# --- context separation ----------------------------------------------------

def test_context_separation_distinct_buckets():
    """`transfer` under two different parents must land in different buckets."""
    b = _wex.Builder()
    inst = b.obj("choreographyInstance:C", "choreographyInstance")
    gov = b.obj("GovC", "Governance"); torn = b.obj("TORNC", "TORN")
    router = b.obj("RouterC", "Router"); vault = b.obj("VaultC", "Vault")
    proxy = b.obj("ProxyC", "Proxy")

    # unlock scope containing a transfer frame
    root = b.scope("sub:C:unlock", "subchoreography unlock")
    tr_u = b.scope("sub:C:unlock:t", "subchoreography transfer")
    b.contains(root, tr_u)
    # swap scope containing a transfer frame
    swap = b.scope("sub:C:swap", "subchoreography swap")
    tr_s = b.scope("sub:C:swap:t", "subchoreography transfer")
    b.contains(swap, tr_s)

    ms = 0
    b.event("e:C:u:req", "Request unlock [Gov]", ms, proxy, gov, root, inst, []); ms += 1
    b.event("e:C:ut:req", "Request transfer [TORN]", ms, gov, torn, tr_u, inst, []); ms += 1
    b.event("e:C:ut:res", "Respond to transfer [TORN]", ms, torn, gov, tr_u, inst, []); ms += 1
    b.event("e:C:u:res", "Respond to unlock [Gov]", ms, gov, proxy, root, inst, []); ms += 1
    b.event("e:C:s:req", "Request swap [Router]", ms, proxy, router, swap, inst, []); ms += 1
    b.event("e:C:st:req", "Request transfer [TORN]", ms, router, torn, tr_s, inst, []); ms += 1
    b.event("e:C:st:res", "Respond to transfer [TORN]", ms, torn, router, tr_s, inst, []); ms += 1
    b.event("e:C:s:res", "Respond to swap [Router]", ms, router, proxy, swap, inst, []); ms += 1

    m = reader.build_model(b.build(), run_validator=False)
    buckets, _ = project(m)
    # Both transfer frames share the scopeType symbol, but their context paths differ.
    keys = [k for k in buckets if k and k[-1].opener.exec_type == "Request transfer [TORN]"]
    parents = {k[-2].opener.exec_type for k in keys}
    assert parents == {"Request unlock [Gov]", "Request swap [Router]"}
    assert len(keys) == 2  # never pooled across parents


# --- recursion (D12) -------------------------------------------------------

def _load_blockchain(name):
    path = BLOCKCHAIN / f"{name}_ocel.json"
    if not path.exists():
        pytest.skip(f"{path} not present")
    return reader.load(path)


def test_recursion_beanstalk():
    m = _load_blockchain("beanstalk_attack")
    d = discover(m)
    execs = {f.exec_type for f in d.recursion}
    # The Curve reentrancy / read-only-reentrancy pattern (spec settled facts).
    for fn in ("exchange", "add_liquidity", "get_virtual_price", "remove_liquidity_one_coin"):
        assert any(fn in e for e in execs), f"missing recursive execType for {fn!r}: {execs}"
    # get_virtual_price recurs both directly and indirectly.
    gvp = [f for f in d.recursion if "get_virtual_price" in f.exec_type]
    assert any(f.direct for f in gvp) and any(not f.direct for f in gvp)


def _leaf_task_types(node):
    out = set()
    if node.op is None and isinstance(node.label, TaskType):
        out.add(node.label)
    for c in node.children:
        out |= _leaf_task_types(c)
    return out


@pytest.mark.parametrize("dataset", [
    "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc_uniqueFunction",  # loop with non-tau redo
    "0x5efda50f22d34f262c29268506c5fa42cb56a1ce_uniqueFunction",
    "0x06012c8cf97bead5deae237070f9587f8e7a266d_uniqueFunction",
    "beanstalk_attack",
])
def test_no_activity_dropped(dataset):
    """Every task type in the log appears as a discovered leaf (IM preserves the
    alphabet). Guards against dropping a loop's non-tau redo path (§B4/§B5)."""
    from ocelchormodel_rad.typing import task_type
    m = _load_blockchain(dataset)
    d = discover(m)
    model_tts = {task_type(m, e) for e in m.events.values()}
    assert _leaf_task_types(d.tree) == model_tts


def test_recursion_silent_on_non_recursive_log():
    # Beacon deposit: depth 1, no recursion.
    m = _load_blockchain("0x00000000219ab540356cbb839cbe05303d7705fa_uniqueFunction")
    d = discover(m)
    assert d.recursion == []


def test_and_nodes_collected_not_raised():
    """Fallthrough-∧ stays in the model (diagnostics never change the model)
    and the nodes are recorded for D9 (spec B4 correction):
    pm4py's ActivityOncePerTrace emits ∧ even on a single totally ordered
    subtrace with non-adjacent repeats — e.g. d9e1ce's
    swapExactTokensForTokensSupportingFeeOnTransferTokens frame."""
    m = _load_blockchain("0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f_uniqueFunction")
    d = discover(m)  # must not raise
    assert len(d.and_nodes) >= 1


def test_d12_matches_refreshed_audit():
    """D12 recursive execType set == refreshed recursion_report.json, all datasets."""
    audit_path = Path(__file__).resolve().parents[2] / "recursion_report.json"
    if not audit_path.exists():
        pytest.skip("recursion_report.json not present")
    audit = {r["dataset"]: r for r in json.loads(audit_path.read_text())}
    checked = 0
    for path in sorted(BLOCKCHAIN.glob("*_ocel.json")):
        name = path.name.replace(".json", "")  # e.g. beanstalk_attack_ocel
        if name not in audit:
            continue
        checked += 1
        d = discover(reader.load(path))
        d12 = {f.exec_type for f in d.recursion}
        expected = {t["exec_type"] for t in audit[name]["type_level"]["recurring_types"]}
        assert d12 == expected, f"{name}: D12={d12} audit={expected}"
    assert checked >= 12
