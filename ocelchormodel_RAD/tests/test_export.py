"""M3 — export: BPMN 2.0 choreography XML + per-instance round-trip (spec §B5)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ocelchormodel_rad import reader
from ocelchormodel_rad.discover import TreeNode, discover
from ocelchormodel_rad.export_bpmn import (
    BPMN,
    collapse_loops,
    structural_signature,
    structural_signature_xml,
    to_bpmn,
)
from ocelchormodel_rad.typing import ScopeType, TaskType
from conftest import single_instance_ocel

INPUT = Path(__file__).resolve().parents[2] / "ocelchormodel" / "data" / "input"
OUTPUT = Path(__file__).resolve().parents[2] / "ocelchormodel" / "data" / "output"

# Datasets whose every instance is IM-reproducible (no non-adjacent within-instance
# type recurrence): the discovered-from-one-instance model reproduces the reference.
CURATED = [
    "0x00000000219ab540356cbb839cbe05303d7705fa_uniqueFunction",
    "0x5e_cd49912",
    "0x5efda50f22d34f262c29268506c5fa42cb56a1ce_uniqueFunction",
    "0xb1690c08e213a35ed9bab7b318de14420fb57d8c_uniqueFunction",
    "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d_uniqueFunction",
    "0x323a76393544d5ecca80cd6ef2a560c6a395b7e3_uniqueFunction",
]


def _b(t):
    return f"{{{BPMN}}}{t}"


# --- valid XML + I5 conventions -------------------------------------------

def test_export_is_well_formed_choreography(worked_example):
    xml = to_bpmn(*_discover_tuple(worked_example))
    root = ET.fromstring(xml)  # well-formed
    assert root.tag == _b("definitions")
    assert root.find(_b("choreography")) is not None


def test_brackets_inside_with_caller_band(worked_example):
    xml = to_bpmn(*_discover_tuple(worked_example))
    root = ET.fromstring(xml)
    # The transfer subChoreography renders its Request bracket inside, first.
    subs = [e for e in root.iter(_b("subChoreography")) if e.get("name") == "transfer [TORN]"]
    assert subs
    tasks = [c.get("name") for c in subs[0] if c.tag == _b("choreographyTask")]
    assert tasks[0] == "Request transfer [TORN]"
    assert tasks[-1] == "Respond to transfer [TORN]"
    # Caller band (Governance) present on the container.
    bands = {c.text for c in subs[0] if c.tag == _b("participantRef")}
    parts = {p.get("id"): p.get("name") for p in root.iter(_b("participant"))}
    assert "Governance" in {parts[b] for b in bands}


def test_loop_marker_on_single_element_body(worked_example):
    """Repeated transfer frame → loopType="Standard" on that subChoreography
    (the choreography-activity loop marker, BPMN 11.5.3)."""
    xml = to_bpmn(*_discover_tuple(worked_example))
    root = ET.fromstring(xml)
    sub = next(e for e in root.iter(_b("subChoreography")) if e.get("name") == "transfer [TORN]")
    assert sub.get("loopType") == "Standard"


def test_root_xor_renders_multiple_start_events():
    """Root-level × → N unlabeled start events (one per branch)."""
    a = TreeNode(None, TaskType("a", "R1", "R2"))
    b = TreeNode(None, TaskType("b", "R1", "R2"))
    tree = TreeNode("×", None, [a, b])
    from ocelchormodel_rad.discover import SideIndex
    root = ET.fromstring(to_bpmn(tree, SideIndex()))
    choreo = root.find(_b("choreography"))
    starts = [e for e in choreo if e.tag == _b("startEvent")]
    assert len(starts) == 2
    assert all(not s.get("name") for s in starts)  # unlabeled


# --- per-instance round-trip ----------------------------------------------

@pytest.mark.parametrize("dataset", CURATED)
def test_per_instance_round_trip(dataset):
    ocel_path = INPUT / f"{dataset}_ocel.json"
    out_dir = OUTPUT / dataset
    if not ocel_path.exists() or not out_dir.exists():
        pytest.skip(f"{dataset} data not present")
    ocel = json.loads(ocel_path.read_text())
    checked = 0
    for bpmn in sorted(out_dir.glob("*.bpmn")):
        inst = "choreographyInstance:" + bpmn.stem
        sub = single_instance_ocel(ocel, inst)
        if not sub["events"]:
            continue
        checked += 1
        m = reader.build_model(sub, run_validator=False)
        d = discover(m, allow_and=False)
        disc = collapse_loops(structural_signature_xml(to_bpmn(d.tree, d.side_index)))
        ref = collapse_loops(structural_signature(ET.parse(bpmn).getroot()))
        assert disc == ref, f"{dataset} / {bpmn.stem}: round-trip structural mismatch"
    assert checked >= 1


def _discover_tuple(model):
    d = discover(model, allow_and=True)
    return d.tree, d.side_index
