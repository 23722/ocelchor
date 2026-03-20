"""Tests for ocelchormodel.validate — chor-js structural validator."""

from __future__ import annotations

import re

import pytest

from ocelchormodel.bpmn import generate_bpmn
from ocelchormodel.extractor import extract_instance, list_instances
from ocelchormodel.layout import compute_layout
from ocelchormodel.validate import validate_chorjs_compat


# ---------------------------------------------------------------------------
# Helper: generate BPMN for a fixture + instance id
# ---------------------------------------------------------------------------

def _generate(ocel: dict, instance_id: str) -> str:
    inst = extract_instance(ocel, instance_id)
    layout = compute_layout(inst)
    return generate_bpmn(inst, layout)


SWAP1_ID = "choreographyInstance:0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"
SWAP3_ID = "choreographyInstance:0xfed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"


# ---------------------------------------------------------------------------
# Positive tests: valid BPMN passes
# ---------------------------------------------------------------------------

class TestValidBpmn:
    def test_swap1_passes(self, swap1_ocel):
        xml = _generate(swap1_ocel, SWAP1_ID)
        assert validate_chorjs_compat(xml) == []

    def test_swap3_passes(self, swap3_ocel):
        xml = _generate(swap3_ocel, SWAP3_ID)
        assert validate_chorjs_compat(xml) == []

    def test_root_only_passes(self, swap_root_only_ocel):
        instances = list_instances(swap_root_only_ocel)
        xml = _generate(swap_root_only_ocel, instances[0][0])
        assert validate_chorjs_compat(xml) == []

    def test_real_world_all_instances_pass(self, real_world_ocel):
        for inst_id, _ in list_instances(real_world_ocel):
            xml = _generate(real_world_ocel, inst_id)
            errors = validate_chorjs_compat(xml)
            assert errors == [], f"Instance {inst_id}: {errors}"

    def test_empty_errors_means_valid(self, swap1_ocel):
        xml = _generate(swap1_ocel, SWAP1_ID)
        result = validate_chorjs_compat(xml)
        assert isinstance(result, list)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Negative tests: injected defects are caught
# ---------------------------------------------------------------------------

class TestDetectsDefects:
    @pytest.fixture
    def valid_xml(self, swap1_ocel) -> str:
        return _generate(swap1_ocel, SWAP1_ID)

    def test_detects_missing_bpmn_element_ref(self, valid_xml):
        # Replace bpmnElement on a BPMNShape (not BPMNPlane) with non-existent ID
        broken = re.sub(
            r'(<bpmndi:BPMNShape[^>]*bpmnElement=")([^"]+)(")',
            r'\1NONEXISTENT\3',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("bpmnElement" in e or "NONEXISTENT" in e for e in errors)

    def test_detects_invalid_band_kind(self, valid_xml):
        broken = valid_xml.replace(
            'participantBandKind="top_initiating"',
            'participantBandKind="invalid_kind"',
            1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("participantBandKind" in e for e in errors)

    def test_detects_missing_is_message_visible(self, valid_xml):
        # Remove the first isMessageVisible attribute
        broken = re.sub(
            r' isMessageVisible="[^"]*"',
            '',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("isMessageVisible" in e for e in errors)

    def test_detects_orphan_choreography_activity_shape(self, valid_xml):
        broken = re.sub(
            r'choreographyActivityShape="([^"]+)"',
            'choreographyActivityShape="ORPHAN_SHAPE"',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("choreographyActivityShape" in e or "ORPHAN_SHAPE" in e for e in errors)

    def test_detects_fewer_than_two_participant_refs(self, valid_xml):
        # Remove one <bpmn2:participantRef> from the first choreographyTask
        # Find the first participantRef and remove it
        ns = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        tag = f"<bpmn2:participantRef xmlns:bpmn2=\"{ns}\">"
        # Simpler: just remove one participantRef line
        lines = valid_xml.split("\n")
        found = False
        new_lines = []
        for line in lines:
            if not found and "<bpmn2:participantRef>" in line:
                found = True
                continue  # skip this line
            new_lines.append(line)
        broken = "\n".join(new_lines)
        errors = validate_chorjs_compat(broken)
        assert any("participantRef" in e or "mismatch" in e for e in errors)

    def test_detects_band_count_mismatch(self, valid_xml):
        # Remove one BPMNShape that has choreographyActivityShape (a band shape)
        lines = valid_xml.split("\n")
        new_lines = []
        skip_until_close = False
        removed = False
        for line in lines:
            if not removed and "choreographyActivityShape=" in line and "<bpmndi:BPMNShape" in line:
                skip_until_close = True
                removed = True
                continue
            if skip_until_close:
                if "</bpmndi:BPMNShape>" in line:
                    skip_until_close = False
                continue
            new_lines.append(line)
        broken = "\n".join(new_lines)
        errors = validate_chorjs_compat(broken)
        assert any("mismatch" in e for e in errors)

    def test_detects_unresolved_message_flow_ref(self, valid_xml):
        broken = re.sub(
            r'(<bpmn2:messageFlowRef>)([^<]+)(</bpmn2:messageFlowRef>)',
            r'\1NONEXISTENT_MF\3',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("messageFlowRef" in e for e in errors)

    def test_detects_unresolved_message_ref(self, valid_xml):
        broken = re.sub(
            r'messageRef="([^"]+)"',
            'messageRef="NONEXISTENT_MSG"',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("messageRef" in e or "NONEXISTENT_MSG" in e for e in errors)

    def test_detects_unresolved_initiating_participant_ref(self, valid_xml):
        broken = re.sub(
            r'initiatingParticipantRef="([^"]+)"',
            'initiatingParticipantRef="NONEXISTENT_PART"',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("initiatingParticipantRef" in e for e in errors)

    def test_detects_duplicate_ids(self, valid_xml):
        # Duplicate the first id by inserting a second element with same id
        match = re.search(r'id="([^"]+)"', valid_xml)
        assert match
        first_id = match.group(1)
        # Insert a dummy element with the same id right before closing </bpmn2:choreography>
        broken = valid_xml.replace(
            "</bpmn2:choreography>",
            f'<bpmn2:participant id="{first_id}" name="dup" />\n</bpmn2:choreography>',
            1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("duplicate" in e for e in errors)

    def test_detects_broken_sequence_flow_refs(self, valid_xml):
        # Target a sequenceFlow element specifically (not messageFlow)
        broken = re.sub(
            r'(<bpmn2:sequenceFlow[^>]*sourceRef=")([^"]+)(")',
            r'\1NONEXISTENT_SRC\3',
            valid_xml,
            count=1,
        )
        errors = validate_chorjs_compat(broken)
        assert any("sourceRef" in e or "NONEXISTENT_SRC" in e for e in errors)
