"""Tests for ocelchormodel.extractor.

Verifies that choreography instances are correctly extracted from
OCEL 2.0 event logs. The extractor is the core business logic:
it reads the flat OCEL event list and builds the hierarchical
structure of ChoreoTasks and SubChoreographies.

Test fixtures cover increasing complexity:
  - swap_1: 1 instance, 2 top-level elements, 1 nesting level
  - swap_3: 1 instance, 3 nesting levels, 8 tasks
  - swap_root_only: 1 instance, 1 task, 0 subchoreographies
  - swap_multi_tx: 2 instances in one file
  - 0x55 (real-world): 9 instances, up to 20 participants

Why these tests matter:
  If the extractor produces the wrong tree structure, the BPMN
  generator will output incorrect choreography models.
"""

from __future__ import annotations

import pytest

from ocelchormodel.extractor import extract_instance, list_instances
from ocelchormodel.model import ChoreoTask, SubChoreo

SWAP1_INSTANCE = "choreographyInstance:0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"
SWAP3_INSTANCE = "choreographyInstance:0xfed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"


# ---------------------------------------------------------------------------
# Listing instances
# ---------------------------------------------------------------------------

class TestListInstances:
    """list_instances returns (full_id, short_id) pairs for each
    choreographyInstance object found in the OCEL data."""

    def test_swap1_has_one_instance(self, swap1_ocel):
        assert len(list_instances(swap1_ocel)) == 1

    def test_short_id_is_non_empty(self, swap1_ocel):
        _, short = list_instances(swap1_ocel)[0]
        assert len(short) > 0


# ---------------------------------------------------------------------------
# Extracting swap_1 (2 elements, 1 nesting level)
# ---------------------------------------------------------------------------

class TestExtractSwap1:
    """swap_1 is a single token swap transaction. The extractor should
    produce 2 top-level elements: a ChoreoTask (the root call) and
    a SubChoreo (the internal swap logic with 1 child task)."""

    @pytest.fixture(autouse=True)
    def _extract(self, swap1_ocel):
        self.instance = extract_instance(swap1_ocel, SWAP1_INSTANCE)

    def test_two_top_level_elements(self):
        assert len(self.instance.elements) == 2

    def test_first_is_task_second_is_sub(self):
        assert isinstance(self.instance.elements[0], ChoreoTask)
        assert isinstance(self.instance.elements[1], SubChoreo)

    def test_elements_ordered_by_timestamp(self):
        """Top-level elements are sorted: task first, then subchoreo."""
        assert isinstance(self.instance.elements[0], ChoreoTask)
        assert isinstance(self.instance.elements[1], SubChoreo)

    def test_sub_choreo_has_one_child(self):
        sub = self.instance.elements[1]
        assert len(sub.children) == 1

    def test_root_task_is_request_only(self):
        """The root call has an initiating message but no return."""
        task = self.instance.elements[0]
        assert task.initiating_msg is not None
        assert task.returning_msg is None

    def test_bpmn_ids_are_valid_xml_names(self):
        """BPMN IDs must not contain ':' (XML NCName constraint)."""
        for elem in self.instance.elements:
            assert ":" not in elem.bpmn_id
            if isinstance(elem, SubChoreo):
                for child in elem.children:
                    assert ":" not in child.bpmn_id

    def test_unknown_instance_raises(self, swap1_ocel):
        with pytest.raises(ValueError, match="not found"):
            extract_instance(swap1_ocel, "choreographyInstance:0xdeadbeef")


# ---------------------------------------------------------------------------
# Extracting swap_3 (3 nesting levels, 8 tasks)
# ---------------------------------------------------------------------------

class TestExtractSwap3:
    """swap_3 is a multi-hop swap involving 3 nesting levels.
    Tests that deep nesting is handled correctly."""

    @pytest.fixture(autouse=True)
    def _extract(self, swap3_ocel):
        self.instance = extract_instance(swap3_ocel, SWAP3_INSTANCE)

    def _count_tasks(self, elements) -> int:
        count = 0
        for e in elements:
            if isinstance(e, ChoreoTask):
                count += 1
            else:
                count += self._count_tasks(e.children)
        return count

    def test_eight_total_tasks(self):
        assert self._count_tasks(self.instance.elements) == 8

    def test_three_nesting_levels(self):
        """root -> sub -> inner_sub -> innermost_sub (3 levels deep)."""
        root_sub = self.instance.elements[1]
        assert isinstance(root_sub, SubChoreo)
        inner_sub = next(c for c in root_sub.children if isinstance(c, SubChoreo))
        innermost = next(c for c in inner_sub.children if isinstance(c, SubChoreo))
        assert len(innermost.children) == 1
        assert isinstance(innermost.children[0], ChoreoTask)


# ---------------------------------------------------------------------------
# Extracting root-only (simplest: 1 task, 0 subs)
# ---------------------------------------------------------------------------

class TestExtractRootOnly:
    """The simplest possible choreography: one task, no subchoreographies."""

    @pytest.fixture(autouse=True)
    def _extract(self, swap_root_only_ocel):
        ROOT_ONLY = "choreographyInstance:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111"
        self.instance = extract_instance(swap_root_only_ocel, ROOT_ONLY)

    def test_single_task(self):
        assert len(self.instance.elements) == 1
        assert isinstance(self.instance.elements[0], ChoreoTask)


# ---------------------------------------------------------------------------
# Extracting multi-tx (2 instances in one file)
# ---------------------------------------------------------------------------

MULTI_TX_IDS = [
    "choreographyInstance:0xbbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222bbbb2222",
    "choreographyInstance:0xcccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333cccc3333",
]


class TestExtractMultiTx:
    """Two choreography instances from different transactions in one OCEL file.
    Tests that instances are isolated from each other."""

    def test_two_instances_found(self, swap_multi_tx_ocel):
        assert len(list_instances(swap_multi_tx_ocel)) == 2

    def test_independent_elements(self, swap_multi_tx_ocel):
        """The two instances have disjoint BPMN IDs."""
        inst0 = extract_instance(swap_multi_tx_ocel, MULTI_TX_IDS[0])
        inst1 = extract_instance(swap_multi_tx_ocel, MULTI_TX_IDS[1])
        ids0 = {e.bpmn_id for e in inst0.elements}
        ids1 = {e.bpmn_id for e in inst1.elements}
        assert ids0.isdisjoint(ids1)


# ---------------------------------------------------------------------------
# Real-world data (0x55 PancakeSwap, 9 instances, up to 20 participants)
# ---------------------------------------------------------------------------

class TestExtractRealWorld:
    """Real Ethereum transaction data from PancakeSwap MasterChef v3.
    Tests that the extractor handles real-world complexity."""

    def test_nine_instances(self, real_world_ocel):
        assert len(list_instances(real_world_ocel)) == 9

    def test_all_instances_extract_successfully(self, real_world_ocel):
        for inst_id, _ in list_instances(real_world_ocel):
            inst = extract_instance(real_world_ocel, inst_id)
            assert inst.ocel_id == inst_id

    def test_high_participant_count(self, real_world_ocel):
        """At least one instance has >= 10 unique participants."""
        max_parts = 0
        for inst_id, _ in list_instances(real_world_ocel):
            inst = extract_instance(real_world_ocel, inst_id)
            parts = set()
            def _collect(elements):
                for e in elements:
                    if isinstance(e, ChoreoTask):
                        parts.add(e.initiator.bpmn_id)
                        parts.add(e.participant.bpmn_id)
                    else:
                        _collect(e.children)
            _collect(inst.elements)
            max_parts = max(max_parts, len(parts))
        assert max_parts >= 10

    def test_all_bpmn_ids_valid(self, real_world_ocel):
        """All BPMN IDs are valid XML NCNames (no ':')."""
        for inst_id, _ in list_instances(real_world_ocel):
            inst = extract_instance(real_world_ocel, inst_id)
            def _check(elements):
                for e in elements:
                    assert ":" not in e.bpmn_id, f"Invalid NCName: {e.bpmn_id}"
                    if isinstance(e, SubChoreo):
                        _check(e.children)
            _check(inst.elements)
