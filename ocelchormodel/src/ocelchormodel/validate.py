"""Structural validator for BPMN 2.0 choreography XML.

Checks the 10 structural rules that chor-js enforces on import.
Returns a list of error strings; an empty list means the BPMN is valid.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

BPMN2 = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"

_VALID_BAND_KINDS = {"top_initiating", "bottom_non_initiating", "middle_non_initiating"}


def _b2(tag: str) -> str:
    return f"{{{BPMN2}}}{tag}"


def _di(tag: str) -> str:
    return f"{{{BPMNDI}}}{tag}"


def _collect_all_ids(root: ET.Element) -> set[str]:
    """Collect every 'id' attribute in the document."""
    ids: set[str] = set()
    for el in root.iter():
        eid = el.get("id")
        if eid:
            ids.add(eid)
    return ids


def validate_chorjs_compat(xml_str: str) -> list[str]:
    """Validate BPMN XML against chor-js structural import rules.

    Returns a list of human-readable error strings.
    An empty list means the BPMN passes all checks.
    """
    errors: list[str] = []

    # Parse — strip XML declaration if present
    if xml_str.startswith("<?xml"):
        xml_str = xml_str.split("\n", 1)[1]
    root = ET.fromstring(xml_str)

    all_ids = _collect_all_ids(root)

    # --- Rule 9: No duplicate IDs ---
    seen_ids: set[str] = set()
    for el in root.iter():
        eid = el.get("id")
        if eid:
            if eid in seen_ids:
                errors.append(f"duplicate id: '{eid}'")
            seen_ids.add(eid)

    # Collect declared participants, messages, message flows
    choreo = root.find(_b2("choreography"))
    if choreo is None:
        errors.append("missing <choreography> element")
        return errors

    declared_participants = {
        p.get("id") for p in choreo.findall(_b2("participant"))
    }
    declared_message_flows = {
        mf.get("id") for mf in choreo.findall(_b2("messageFlow"))
    }
    declared_messages = {
        m.get("id") for m in root.findall(_b2("message"))
    }

    # --- Rule 10: All participantRef values resolve to declared participants ---
    for pref in root.iter(_b2("participantRef")):
        if pref.text not in declared_participants:
            errors.append(
                f"participantRef '{pref.text}' not in declared participants"
            )

    # --- Rule 7: All messageFlowRef, messageRef, initiatingParticipantRef resolve ---
    for mfref in root.iter(_b2("messageFlowRef")):
        if mfref.text not in declared_message_flows:
            errors.append(
                f"messageFlowRef '{mfref.text}' not in declared messageFlows"
            )

    for mf in choreo.findall(_b2("messageFlow")):
        mref = mf.get("messageRef")
        if mref and mref not in declared_messages:
            errors.append(
                f"messageRef '{mref}' not in declared messages"
            )

    for activity_tag in ("choreographyTask", "subChoreography"):
        for act in root.iter(_b2(activity_tag)):
            ipr = act.get("initiatingParticipantRef")
            if ipr and ipr not in declared_participants:
                errors.append(
                    f"initiatingParticipantRef '{ipr}' on {activity_tag} "
                    f"'{act.get('id')}' not in declared participants"
                )

    # --- Rule 8: sequenceFlow sourceRef/targetRef resolve ---
    for sf in root.iter(_b2("sequenceFlow")):
        src = sf.get("sourceRef")
        tgt = sf.get("targetRef")
        if src not in all_ids:
            errors.append(
                f"sequenceFlow '{sf.get('id')}' sourceRef '{src}' not found"
            )
        if tgt not in all_ids:
            errors.append(
                f"sequenceFlow '{sf.get('id')}' targetRef '{tgt}' not found"
            )

    # --- DI section checks ---
    plane = root.find(f".//{_di('BPMNPlane')}")
    if plane is None:
        errors.append("missing <BPMNPlane> element")
        return errors

    # Collect all DI shape IDs for cross-reference
    di_shape_ids = {
        s.get("id") for s in plane.findall(_di("BPMNShape"))
    }

    # --- Rule 1: All bpmnElement refs resolve ---
    for shape in plane.findall(_di("BPMNShape")):
        be = shape.get("bpmnElement")
        if be and be not in all_ids:
            errors.append(
                f"BPMNShape '{shape.get('id')}' bpmnElement '{be}' not found"
            )
    for edge in plane.findall(_di("BPMNEdge")):
        be = edge.get("bpmnElement")
        if be and be not in all_ids:
            errors.append(
                f"BPMNEdge '{edge.get('id')}' bpmnElement '{be}' not found"
            )

    # Identify band shapes (those with choreographyActivityShape attribute)
    band_shapes = [
        s for s in plane.findall(_di("BPMNShape"))
        if s.get("choreographyActivityShape") is not None
    ]

    # --- Rule 2: participantBandKind values ---
    for bs in band_shapes:
        kind = bs.get("participantBandKind")
        if kind not in _VALID_BAND_KINDS:
            errors.append(
                f"BPMNShape '{bs.get('id')}' has invalid "
                f"participantBandKind '{kind}'"
            )

    # --- Rule 3: choreographyActivityShape refs resolve to shape IDs ---
    for bs in band_shapes:
        cas = bs.get("choreographyActivityShape")
        if cas and cas not in di_shape_ids:
            errors.append(
                f"BPMNShape '{bs.get('id')}' choreographyActivityShape "
                f"'{cas}' not found in DI shapes"
            )

    # --- Rule 4: isMessageVisible present on every band ---
    for bs in band_shapes:
        if bs.get("isMessageVisible") is None:
            errors.append(
                f"BPMNShape '{bs.get('id')}' missing isMessageVisible attribute"
            )

    # --- Rules 5 & 6: participantRef count matches band count per activity ---
    for activity_tag in ("choreographyTask", "subChoreography"):
        for act in root.iter(_b2(activity_tag)):
            act_id = act.get("id")
            act_shape_id = f"{act_id}_di"

            # Count participantRef children
            prefs = act.findall(_b2("participantRef"))
            n_prefs = len(prefs)

            # Rule 5: at least 2 participantRefs
            if n_prefs < 2:
                errors.append(
                    f"{activity_tag} '{act_id}' has {n_prefs} participantRef "
                    f"(minimum 2 required)"
                )

            # Count DI band shapes referencing this activity
            n_bands = sum(
                1 for bs in band_shapes
                if bs.get("choreographyActivityShape") == act_shape_id
            )

            # Rule 6: counts must match
            if n_prefs != n_bands:
                errors.append(
                    f"{activity_tag} '{act_id}' has {n_prefs} participantRef(s) "
                    f"but {n_bands} DI band shape(s) — mismatch"
                )

    return errors
