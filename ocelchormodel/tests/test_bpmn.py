"""Tests for ocelchormodel.bpmn.

Verifies that the BPMN XML generator produces correct choreography
models. Tests check:
  - Correct element types and counts (tasks, subchoreographies)
  - All cross-references resolve (participants, messages, flows)
  - DI shapes reference valid BPMN elements
  - Band count matches participant count (the bug class we already hit)

Why these tests matter:
  The BPMN generator is the final output stage. If its XML is
  malformed or has broken references, chor-js will fail to import
  the choreography model.

Note: Structural validation rules are tested separately in
test_validate.py. This file focuses on element counts and
specific BPMN semantics.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from ocelchormodel.bpmn import generate_bpmn
from ocelchormodel.extractor import extract_instance, list_instances
from ocelchormodel.layout import compute_layout

SWAP1_INSTANCE = "choreoInst:0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"
SWAP3_INSTANCE = "choreoInst:0xfed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"

BPMN2 = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"


def _b2(tag):
    return f"{{{BPMN2}}}{tag}"


def _di(tag):
    return f"{{{BPMNDI}}}{tag}"


def _parse(xml_str: str) -> ET.Element:
    return ET.fromstring(xml_str.split("\n", 1)[-1])  # strip xml declaration


# ---------------------------------------------------------------------------
# swap_1: 2 tasks, 1 subchoreography
# ---------------------------------------------------------------------------

class TestBpmnSwap1:
    """Tests the BPMN output for a simple 1-hop token swap."""

    @pytest.fixture(autouse=True)
    def _build(self, swap1_ocel):
        instance = extract_instance(swap1_ocel, SWAP1_INSTANCE)
        layout = compute_layout(instance)
        self.xml_str = generate_bpmn(instance, layout)
        self.root = _parse(self.xml_str)

    def test_parses_as_valid_xml(self):
        assert self.root is not None

    def test_has_choreography_element(self):
        """The root must contain a <choreography> element."""
        assert self.root.find(_b2("choreography")) is not None

    def test_two_choreo_tasks(self):
        tasks = self.root.findall(f".//{_b2('choreographyTask')}")
        assert len(tasks) == 2

    def test_one_sub_choreography(self):
        subs = self.root.findall(f".//{_b2('subChoreography')}")
        assert len(subs) == 1

    def test_all_participants_declared(self):
        """Every participantRef in the document points to a declared participant."""
        choreo = self.root.find(_b2("choreography"))
        declared = {p.get("id") for p in choreo.findall(_b2("participant"))}
        for ref in self.root.findall(f".//{_b2('participantRef')}"):
            assert ref.text in declared, f"Undeclared participant: {ref.text}"

    def test_di_shapes_reference_existing_ids(self):
        """Every BPMNShape's bpmnElement attribute points to a real element."""
        all_ids: set[str] = set()
        for el in self.root.iter():
            eid = el.get("id")
            if eid:
                all_ids.add(eid)
        plane = self.root.find(f".//{_di('BPMNPlane')}")
        for shape in plane.findall(_di("BPMNShape")):
            assert shape.get("bpmnElement") in all_ids

    def test_sequence_flows_have_waypoints(self):
        """Every DI edge has at least 2 waypoints for rendering."""
        DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
        plane = self.root.find(f".//{_di('BPMNPlane')}")
        for edge in plane.findall(_di("BPMNEdge")):
            waypoints = edge.findall(f"{{{DI_NS}}}waypoint")
            assert len(waypoints) >= 2


# ---------------------------------------------------------------------------
# swap_3: 8 tasks, 3 subchoreographies
# ---------------------------------------------------------------------------

class TestBpmnSwap3:
    """Tests the BPMN output for a 3-hop multi-nesting swap."""

    @pytest.fixture(autouse=True)
    def _build(self, swap3_ocel):
        instance = extract_instance(swap3_ocel, SWAP3_INSTANCE)
        layout = compute_layout(instance)
        self.root = _parse(generate_bpmn(instance, layout))

    def test_eight_choreo_tasks(self):
        assert len(self.root.findall(f".//{_b2('choreographyTask')}")) == 8

    def test_all_participants_declared(self):
        choreo = self.root.find(_b2("choreography"))
        declared = {p.get("id") for p in choreo.findall(_b2("participant"))}
        for ref in self.root.findall(f".//{_b2('participantRef')}"):
            assert ref.text in declared


# ---------------------------------------------------------------------------
# Root-only: 1 task, 0 subchoreographies (simplest case)
# ---------------------------------------------------------------------------

ROOT_ONLY_INSTANCE = "choreoInst:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"


class TestBpmnRootOnly:
    """The simplest possible output: one task with two participant bands."""

    @pytest.fixture(autouse=True)
    def _build(self, swap_root_only_ocel):
        instance = extract_instance(swap_root_only_ocel, ROOT_ONLY_INSTANCE)
        layout = compute_layout(instance)
        self.root = _parse(generate_bpmn(instance, layout))

    def test_one_task_no_subs(self):
        assert len(self.root.findall(f".//{_b2('choreographyTask')}")) == 1
        assert len(self.root.findall(f".//{_b2('subChoreography')}")) == 0

    def test_two_participant_bands(self):
        """A 2-participant task must have exactly 2 DI band shapes."""
        plane = self.root.find(f".//{_di('BPMNPlane')}")
        bands = [s for s in plane.findall(_di("BPMNShape"))
                 if s.get("participantBandKind")]
        assert len(bands) == 2


# ---------------------------------------------------------------------------
# Multi-transaction: 2 instances generate independently
# ---------------------------------------------------------------------------

MULTI_TX_IDS = [
    "choreoInst:0xbbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
    "choreoInst:0xcccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333",
]


class TestBpmnMultiTx:
    def test_each_instance_generates_valid_xml(self, swap_multi_tx_ocel):
        for inst_id in MULTI_TX_IDS:
            instance = extract_instance(swap_multi_tx_ocel, inst_id)
            layout = compute_layout(instance)
            root = _parse(generate_bpmn(instance, layout))
            assert root is not None


# ---------------------------------------------------------------------------
# Real-world: largest 0x55 PancakeSwap instance (up to 20 participants)
# ---------------------------------------------------------------------------

REAL_WORLD_LARGEST = "choreoInst:0x493292e3d18dd7db7dffc4fd7d6badef2b89c956f310ba555b7977aae0ae233b"


class TestBpmnRealWorld:
    """Tests the most complex real-world instance. This is where the
    original participantRef/band-count mismatch bug manifested."""

    @pytest.fixture(autouse=True)
    def _build(self, real_world_ocel):
        instance = extract_instance(real_world_ocel, REAL_WORLD_LARGEST)
        layout = compute_layout(instance)
        self.root = _parse(generate_bpmn(instance, layout))

    def test_band_count_matches_participant_refs(self):
        """THE critical test: for every choreography activity, the number
        of participantRef children must equal the number of DI band shapes.
        This is the exact bug class we already hit and fixed."""
        plane = self.root.find(f".//{_di('BPMNPlane')}")
        for act_tag in ("choreographyTask", "subChoreography"):
            for act in self.root.findall(f".//{_b2(act_tag)}"):
                n_refs = len(act.findall(_b2("participantRef")))
                shape_id = f"{act.get('id')}_di"
                n_bands = sum(
                    1 for s in plane.findall(_di("BPMNShape"))
                    if s.get("choreographyActivityShape") == shape_id
                )
                assert n_refs == n_bands, (
                    f"{act.get('id')}: {n_refs} refs != {n_bands} bands"
                )

    def test_no_duplicate_ids(self):
        ids = [el.get("id") for el in self.root.iter() if el.get("id")]
        assert len(ids) == len(set(ids))

    def test_sequence_flows_connected(self):
        """All sequenceFlow sourceRef/targetRef point to existing elements."""
        all_ids = {el.get("id") for el in self.root.iter() if el.get("id")}
        for sf in self.root.findall(f".//{_b2('sequenceFlow')}"):
            assert sf.get("sourceRef") in all_ids
            assert sf.get("targetRef") in all_ids


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestBpmnHelpers:
    def test_collect_participants_empty(self):
        from ocelchormodel.bpmn import _collect_participants
        assert _collect_participants([]) == {}

    def test_collect_messages_empty(self):
        from ocelchormodel.bpmn import _collect_messages
        assert _collect_messages([]) == {}
