"""End-to-end integration tests for ocelchormodel.

Each test runs the full pipeline: read -> extract -> layout -> generate.
While unit tests verify individual modules, these tests confirm
the modules work together correctly.

Test data covers:
  - swap_1: simple swap (2 tasks, 1 sub)
  - swap_3: complex swap (8 tasks, 3 subs, 3 nesting levels)
  - swap_root_only: minimal (1 task, 0 subs)
  - swap_multi_tx: 2 independent instances
  - 0x55: 9 real PancakeSwap instances (up to 20 participants)

Why these tests matter:
  Integration tests catch bugs that only appear when modules
  interact, such as ID collisions or mismatched assumptions
  between the extractor and the BPMN generator.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ocelchormodel.bpmn import generate_bpmn
from ocelchormodel.extractor import extract_instance, list_instances
from ocelchormodel.layout import compute_layout
from ocelchormodel.reader import read_ocel

DATA_DIR = Path(__file__).parent / "data"

BPMN2 = "http://www.omg.org/spec/BPMN/20100524/MODEL"


def _b2(tag):
    return f"{{{BPMN2}}}{tag}"


def _parse_bpmn(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str.split("\n", 1)[-1])


def _count(root: ET.Element, tag: str) -> int:
    return len(root.findall(f".//{_b2(tag)}"))


def _run_pipeline(ocel_path: Path) -> tuple[ET.Element, str]:
    """Full pipeline: read -> list -> extract first instance -> layout -> bpmn."""
    ocel = read_ocel(ocel_path)
    instances = list_instances(ocel)
    assert instances, "No instances found"
    instance = extract_instance(ocel, instances[0][0])
    layout = compute_layout(instance)
    xml_str = generate_bpmn(instance, layout)
    return _parse_bpmn(xml_str), xml_str


def _flows_connected(root: ET.Element) -> bool:
    """Check that all sequenceFlow sourceRef/targetRef reference existing IDs."""
    all_ids = {el.get("id") for el in root.iter() if el.get("id")}
    for sf in root.findall(f".//{_b2('sequenceFlow')}"):
        if sf.get("sourceRef") not in all_ids or sf.get("targetRef") not in all_ids:
            return False
    return True


# ---------------------------------------------------------------------------
# swap_1: simple swap
# ---------------------------------------------------------------------------

class TestSwap1:
    """Full pipeline on swap_1 produces correct BPMN structure."""

    @pytest.fixture(autouse=True)
    def _run(self):
        self.root, _ = _run_pipeline(DATA_DIR / "swap_1_ocel.json")

    def test_valid_xml(self):
        assert self.root is not None

    def test_element_counts(self):
        assert _count(self.root, "choreographyTask") == 2
        assert _count(self.root, "subChoreography") == 1

    def test_flows_connected(self):
        assert _flows_connected(self.root)


# ---------------------------------------------------------------------------
# swap_3: complex multi-hop swap
# ---------------------------------------------------------------------------

class TestSwap3:
    @pytest.fixture(autouse=True)
    def _run(self):
        self.root, _ = _run_pipeline(DATA_DIR / "swap_3_ocel.json")

    def test_element_counts(self):
        assert _count(self.root, "choreographyTask") == 8
        assert _count(self.root, "subChoreography") == 3

    def test_all_participants_declared(self):
        """Every participantRef resolves to a declared participant."""
        choreo = self.root.find(_b2("choreography"))
        declared = {p.get("id") for p in choreo.findall(_b2("participant"))}
        for ref in self.root.findall(f".//{_b2('participantRef')}"):
            assert ref.text in declared


# ---------------------------------------------------------------------------
# Root-only: simplest choreography
# ---------------------------------------------------------------------------

class TestRootOnly:
    @pytest.fixture(autouse=True)
    def _run(self):
        self.root, _ = _run_pipeline(DATA_DIR / "swap_root_only_ocel.json")

    def test_one_task_zero_subs(self):
        assert _count(self.root, "choreographyTask") == 1
        assert _count(self.root, "subChoreography") == 0


# ---------------------------------------------------------------------------
# Multi-transaction: 2 instances produce different output
# ---------------------------------------------------------------------------

MULTI_TX_IDS = [
    "choreoInst:0xbbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
    "choreoInst:0xcccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333",
]


class TestMultiTx:
    def test_instances_produce_different_output(self):
        ocel = read_ocel(DATA_DIR / "swap_multi_tx_ocel.json")
        xmls = {}
        for inst_id in MULTI_TX_IDS:
            inst = extract_instance(ocel, inst_id)
            layout = compute_layout(inst)
            xmls[inst_id] = generate_bpmn(inst, layout)
        assert xmls[MULTI_TX_IDS[0]] != xmls[MULTI_TX_IDS[1]]


# ---------------------------------------------------------------------------
# Real-world: 0x55 PancakeSwap (9 instances)
# ---------------------------------------------------------------------------

class TestRealWorld:
    """End-to-end tests on real Ethereum transaction data."""

    @pytest.fixture(autouse=True)
    def _run(self):
        self.ocel = read_ocel(DATA_DIR / "0x55_truncated_ocel.json")
        self.instances = list_instances(self.ocel)

    def test_all_nine_produce_valid_xml(self):
        for inst_id, _ in self.instances:
            inst = extract_instance(self.ocel, inst_id)
            layout = compute_layout(inst)
            root = _parse_bpmn(generate_bpmn(inst, layout))
            assert root is not None, f"Instance {inst_id} invalid"

    def test_largest_passes_structural_validation(self):
        """The most complex instance passes all chor-js import rules."""
        from ocelchormodel.validate import validate_chorjs_compat

        best_id, best_count = None, 0
        for inst_id, _ in self.instances:
            inst = extract_instance(self.ocel, inst_id)
            if len(inst.elements) > best_count:
                best_id, best_count = inst_id, len(inst.elements)
        inst = extract_instance(self.ocel, best_id)
        layout = compute_layout(inst)
        xml_str = generate_bpmn(inst, layout)
        errors = validate_chorjs_compat(xml_str)
        assert errors == [], f"Validation errors: {errors}"

    def test_no_duplicate_ids(self):
        for inst_id, _ in self.instances:
            inst = extract_instance(self.ocel, inst_id)
            layout = compute_layout(inst)
            root = _parse_bpmn(generate_bpmn(inst, layout))
            ids = [el.get("id") for el in root.iter() if el.get("id")]
            assert len(ids) == len(set(ids)), f"Duplicate IDs in {inst_id}"

    def test_completes_under_one_second(self):
        """Performance guard: all 9 instances in < 1 second."""
        import time
        start = time.monotonic()
        for inst_id, _ in self.instances:
            inst = extract_instance(self.ocel, inst_id)
            layout = compute_layout(inst)
            generate_bpmn(inst, layout)
        assert time.monotonic() - start < 1.0
