"""M4 — diagnostics acceptance (spec B8, D1–D13 regrouped 2026-07-10).

Pinned cases per the M4 acceptance block:
  D9  real2 (partially witnessed, singleton pairs flagged, MTO witnessed) and
      0xd9e1ce (fallthrough-∧: exactly the once-per-trace-peeled pair flagged);
      ∧-free logs emit no D9 entries.
  D4  0x5e root identity-label flagged; fixture zero.
  D8  fixture clean; synthetic payload conflict flagged with structures.
  D2  zero on every input log.  D3  0x5e root expected-only.
  D5  0xb4e16d bare `balanceOf` fans out.  D6  synthetic role fan-out.
  D10 synthetic τ-body loop flagged.
  D12 audit equality lives in test_discover.py (test_d12_matches_refreshed_audit).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from ocelchormodel_rad import reader
from ocelchormodel_rad.diagnostics import compute_diagnostics, _d08_message_merging
from ocelchormodel_rad.discover import TreeNode, discover
from ocelchormodel_rad.typing import TaskType

FIXTURES = Path(__file__).parent / "fixtures"
DATA = Path(__file__).resolve().parents[1] / "data" / "input"

_spec = importlib.util.spec_from_file_location("_wexd", FIXTURES / "build_worked_example.py")
_wex = importlib.util.module_from_spec(_spec)
sys.modules["_wexd"] = _wex
_spec.loader.exec_module(_wex)


@lru_cache(maxsize=None)
def _diag(name: str) -> dict:
    path = DATA / f"{name}_ocel.json"
    if not path.exists():
        pytest.skip(f"{path} not present")
    m = reader.load(path)
    return compute_diagnostics(m, discover(m), name)


# --- Group I — encoding & data trust ---------------------------------------

def test_d1_ordering_passes(worked_example):
    d = compute_diagnostics(worked_example, discover(worked_example))
    assert d["d01_ordering_determinism"] == {
        "residual_ties": 0, "examples": [], "passed": True}


@pytest.mark.parametrize("path", sorted(DATA.glob("*_ocel.json")),
                         ids=lambda p: p.name[:24])
def test_d2_zero_everywhere(path):
    """Every scope's ≻-first event is its request bracket, on all input logs
    that pass the hard gates (C3-violating XES logs never reach diagnostics —
    they are the CLI failure-path material). Load-only — D2 needs no discovery."""
    try:
        m = reader.load(path)
    except reader.ContractViolation as exc:
        pytest.skip(f"hard gate: {exc}")
    from ocelchormodel_rad.diagnostics import _d02_scope_openers
    assert _d02_scope_openers(m)["non_request_openers"] == 0


def test_d3_root_asymmetry_expected_only():
    """0x5e: the EOA-rooted transaction has no top-level response bracket —
    counted as EXPECTED; every interior scope closes properly. The scope's own
    bracket is directly contained (I3), so descendants must not mask it."""
    d3 = _diag("0x5e_cd49912")["d03_bracket_completeness"]
    assert d3["expected_missing_response"] == 1
    assert d3["unexpected_missing_response"] == 0


def test_d3_fixture_clean(worked_example):
    d = compute_diagnostics(worked_example, discover(worked_example))
    assert d["d03_bracket_completeness"] == {
        "expected_missing_response": 0,
        "unexpected_missing_response": 0,
        "unexpected_examples": []}


def test_d4_identity_label_0x5e():
    """Unverified root contract: discriminator == participant object id."""
    d4 = _diag("0x5e_cd49912")["d04_identity_labels"]
    assert d4["exec_types"] == 1 and d4["occurrences"] == 1
    assert d4["examples"] == [
        "Request unlock [0x5efda50f22d34f262c29268506c5fa42cb56a1ce]"]


def test_d4_fixture_zero(worked_example):
    d = compute_diagnostics(worked_example, discover(worked_example))
    assert d["d04_identity_labels"]["exec_types"] == 0


# --- Group II — typing & generalization ------------------------------------

def test_d5_balanceof_fanout():
    """0xb4e16d: one bare activity name discriminated into several execTypes."""
    d5 = _diag("0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc_uniqueFunction")[
        "d05_event_type_fanout"]
    by_name = {e["name"]: e for e in d5}
    assert "balanceOf" in by_name
    assert by_name["balanceOf"]["exec_types"] >= 2


def _two_role_hook_model():
    """Same execType `hook [Vault]` issued by two different roles, under an
    IDENTICAL root scopeType (so both instances pool into one bucket and the
    role variation surfaces as an interior ×)."""
    b = _wex.Builder()
    for tag, issuer_t in (("A", "Governance"), ("B", "Router")):
        inst = b.obj(f"choreographyInstance:{tag}", "choreographyInstance")
        proxy = b.obj(f"Proxy{tag}", "Proxy")
        gov = b.obj(f"Gov{tag}", "Governance")
        issuer = gov if issuer_t == "Governance" else b.obj(f"Issuer{tag}", issuer_t)
        vault = b.obj(f"Vault{tag}", "Vault")
        root = b.scope(f"sub:{tag}:unlock", "subchoreography unlock")
        ms = 0
        b.event(f"e:{tag}:req", "Request unlock [Gov]", ms, proxy, gov, root, inst, []); ms += 1
        b.event(f"e:{tag}:hook", "hook [Vault]", ms, issuer, vault, root, inst, []); ms += 1
        b.event(f"e:{tag}:res", "Respond to unlock [Gov]", ms, gov, proxy, root, inst, []); ms += 1
    return reader.build_model(b.build(), run_validator=False)


def test_d6_role_fanout_synthetic():
    m = _two_role_hook_model()
    d = compute_diagnostics(m, discover(m))
    d6 = {e["exec_type"]: e for e in d["d06_task_type_fanout"]}
    assert "hook [Vault]" in d6
    assert sorted(map(tuple, d6["hook [Vault]"]["role_pairs"])) == [
        ("Governance", "Vault"), ("Router", "Vault")]


def test_d7_fixture_pooling(worked_example):
    """Three identical transfer frames pool into one bucket variant (M2)."""
    d7 = compute_diagnostics(worked_example, discover(worked_example))[
        "d07_scope_pooling"]
    transfer = [e for e in d7["top"]
                if e["context"][-1] == "Request transfer [TORN]"]
    assert transfer and transfer[0]["occurrences"] == 3
    assert transfer[0]["variants"] == 1
    assert transfer[0]["pooling_ratio"] == 3.0


def test_d8_fixture_clean(worked_example):
    d = compute_diagnostics(worked_example, discover(worked_example))
    assert d["d08_message_merging"] == []


def test_d8_synthetic_payload_conflict():
    """Two occurrences of one taskType with different request-payload keysets
    → merged label, conflict reported with both structures."""
    b = _wex.Builder()
    inst = b.obj("choreographyInstance:M", "choreographyInstance")
    proxy = b.obj("ProxyM", "Proxy")
    gov = b.obj("GovM", "Governance")
    vault = b.obj("VaultM", "Vault")
    root = b.scope("sub:M:unlock", "subchoreography unlock")
    m1 = b.msg("m:1", "GovM", "VaultM", {"amount": "1"})
    m2 = b.msg("m:2", "GovM", "VaultM", {"recipient": "0xabc"})
    ms = 0
    b.event("e:M:req", "Request unlock [Gov]", ms, proxy, gov, root, inst, []); ms += 1
    b.event("e:M:h1", "hook [Vault]", ms, gov, vault, root, inst, [m1]); ms += 1
    b.event("e:M:h2", "hook [Vault]", ms, gov, vault, root, inst, [m2]); ms += 1
    b.event("e:M:res", "Respond to unlock [Gov]", ms, gov, proxy, root, inst, []); ms += 1
    m = reader.build_model(b.build(), run_validator=False)
    conflicts = _d08_message_merging(discover(m))
    hook = [c for c in conflicts if c["exec_type"] == "hook [Vault]"]
    assert len(hook) == 1
    assert hook[0]["cause"] == "payload-structures"
    assert sorted(map(tuple, hook[0]["structures"])) == [
        ("amount",), ("recipient",)]


# --- Group III — control-flow trust (IM fallthrough audit) ------------------

REAL2_SINGLETONS = {"Order Ticket", "Pay Travel", "Confirm Booking", "Book Travel"}


def test_d9_real2_partially_witnessed():
    """real2 ∧: the four once-per-trace activities never interleave — all six
    pairs among them flagged with a zero-reversal proof; every pair involving
    the repeating `Make Travel Offer` is witnessed in both directions."""
    d9 = _diag("real2_uniqueInteraction")["d09_parallelism_witnesses"]
    assert len(d9) == 1
    entry = d9[0]
    assert entry["verdict"] == "partially_witnessed"
    assert entry["flagged_pairs"] == 6
    assert entry["subtraces"] == 96
    for p in entry["pairs"]:
        singletons = set(p["a"]) | set(p["b"]) <= REAL2_SINGLETONS
        assert p["flagged"] == singletons, p
        if p["flagged"]:
            assert p["a_before_b"] == 0 or p["b_before_a"] == 0, p


def test_d9_d9e1ce_fallthrough_localized():
    """0xd9e1ce: pm4py's ActivityOncePerTrace fallthrough emitted ∧ on a
    single-subtrace bucket. D9 localizes it: exactly the pair of peeled
    once-per-trace activities is flagged; the loop branch's repeats genuinely
    interleave with everything and stay unflagged."""
    d9 = _diag("0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f_uniqueFunction")[
        "d09_parallelism_witnesses"]
    assert len(d9) == 1
    entry = d9[0]
    assert entry["subtraces"] == 1
    assert entry["verdict"] == "partially_witnessed"
    assert entry["flagged_pairs"] == 1
    flagged = [p for p in entry["pairs"] if p["flagged"]]
    assert {tuple(flagged[0]["a"]), tuple(flagged[0]["b"])} == {
        ("balanceOf [TetherToken]",), ("balanceOf [WETH9]",)}


def test_d9_silent_without_and():
    assert _diag("0x5e_cd49912")["d09_parallelism_witnesses"] == []


def test_d10_tau_body_loop_flagged():
    """Synthetic flower-shaped ↻(τ, a, b): unrestricted repetition flagged
    with the redo alphabet listed."""
    from ocelchormodel_rad.diagnostics import _d10_unrestricted_repetition
    ta = TaskType("a [X]", "R1", "R2")
    tb = TaskType("b [Y]", "R1", "R3")
    tree = TreeNode("↻", None, [
        TreeNode(None, None),          # τ body
        TreeNode(None, ta), TreeNode(None, tb)])
    out = _d10_unrestricted_repetition(tree)
    assert len(out) == 1
    assert out[0]["redo_alphabet"] == ["a [X]", "b [Y]"]


def test_d10_fixture_loop_not_flagged(worked_example):
    """The fixture's ↻ has a non-τ body (the transfer frame) — no flag."""
    d = compute_diagnostics(worked_example, discover(worked_example))
    assert d["d10_unrestricted_repetition"] == []


def test_d11_synthetic_two_initiators():
    """Interior × whose branches start with different initiating roles."""
    m = _two_role_hook_model()
    d = compute_diagnostics(m, discover(m))
    d11 = d["d11_choice_realizability"]
    assert any(set(e["branch_initiating_roles"]) == {"Governance", "Router"}
               for e in d11)


# --- Group IV — process findings --------------------------------------------

def test_d12_beanstalk_summary():
    """Recursion summary mirrors Discovery.recursion (audit equality is pinned
    in test_discover.py::test_d12_matches_refreshed_audit)."""
    d12 = _diag("beanstalk_attack")["d12_recursion"]
    assert d12["direct"] >= 1 and d12["indirect"] >= 1
    assert d12["max_depth_delta"] >= 1
    execs = {f["exec_type"] for f in d12["findings"]}
    assert any("get_virtual_price" in e for e in execs)


def test_d13_cross_depth_0x5e():
    """The unverified root contract reappears one level down as the typed
    Governance participant — 1 ancestor/descendant pair."""
    d13 = _diag("0x5e_cd49912")["d13_cross_depth_participants"]
    assert d13["pairs"] == 1
    ex = d13["examples"][0]
    assert ex["object"] == "0x5efda50f22d34f262c29268506c5fa42cb56a1ce"
    assert ex["ancestor_task_types"] == [
        "Request unlock [0x5efda50f22d34f262c29268506c5fa42cb56a1ce]"]


# --- schema ------------------------------------------------------------------

def test_output_json_serializable_and_ordered(worked_example):
    d = compute_diagnostics(worked_example, discover(worked_example), "fixture")
    s = json.dumps(d)  # must not raise
    keys = [k for k in d if k.startswith("d")]
    assert keys == sorted(keys)  # zero-padded keys keep JSON ordering
    assert d["log"] == "fixture"
    assert "constraints" in d and d["hard_gates"]["passed"] is True
