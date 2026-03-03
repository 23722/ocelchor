"""BPMN 2.0 XML generator for choreography models.

Produces standard BPMN 2.0 XML importable by chor-js
(https://bpt-lab.org/chor-js-demo/).
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from ocelchormodel.layout import Bounds, DiagramLayout, SequenceFlow
from ocelchormodel.model import (
    ChoreoInstance,
    ChoreoTask,
    Message,
    Participant,
    SubChoreo,
)

# ---------------------------------------------------------------------------
# XML namespaces
# ---------------------------------------------------------------------------

BPMN2 = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI = "http://www.omg.org/spec/BPMN/20100524/DI"
DC = "http://www.omg.org/spec/DD/20100524/DC"
DI = "http://www.omg.org/spec/DD/20100524/DI"
TARGET_NS = "http://bpmn.io/schema/bpmn2"

# Register namespace prefixes (must happen before any element is created)
ET.register_namespace("bpmn2", BPMN2)
ET.register_namespace("bpmndi", BPMNDI)
ET.register_namespace("dc", DC)
ET.register_namespace("di", DI)

# Shorthand helpers
def _b2(tag: str) -> str:
    return f"{{{BPMN2}}}{tag}"

def _di(tag: str) -> str:
    return f"{{{BPMNDI}}}{tag}"

def _dc(tag: str) -> str:
    return f"{{{DC}}}{tag}"

def _ddi(tag: str) -> str:
    return f"{{{DI}}}{tag}"


# ---------------------------------------------------------------------------
# Helpers: collect all participants / messages from a subtree
# ---------------------------------------------------------------------------

def _collect_participants(
    elements: list[ChoreoTask | SubChoreo],
) -> dict[str, Participant]:
    """Return {bpmn_id: Participant} for all participants in the subtree."""
    result: dict[str, Participant] = {}
    for elem in elements:
        if isinstance(elem, ChoreoTask):
            for p in (elem.initiator, elem.participant):
                result[p.bpmn_id] = p
        else:
            result.update(_collect_participants(elem.children))
    return result


def _collect_messages(
    elements: list[ChoreoTask | SubChoreo],
) -> dict[str, Message]:
    """Return {bpmn_id: Message} for all messages in the subtree."""
    result: dict[str, Message] = {}
    for elem in elements:
        if isinstance(elem, ChoreoTask):
            for msg in (elem.initiating_msg, elem.returning_msg):
                if msg is not None:
                    result[msg.bpmn_id] = msg
        else:
            result.update(_collect_messages(elem.children))
    return result


def _first_initiator(elements: list[ChoreoTask | SubChoreo]) -> Participant | None:
    """Return the initiating participant of the first task in a subtree."""
    for elem in elements:
        if isinstance(elem, ChoreoTask):
            return elem.initiator
        result = _first_initiator(elem.children)
        if result:
            return result
    return None


def _sub_participants(sub: SubChoreo) -> list[Participant]:
    """Return deduplicated participants for a subchoreography (recursive)."""
    seen: dict[str, Participant] = {}
    for p in _collect_participants(sub.children).values():
        seen[p.bpmn_id] = p
    return list(seen.values())


# ---------------------------------------------------------------------------
# DI shape builder helpers
# ---------------------------------------------------------------------------

def _bounds_el(bounds: Bounds) -> ET.Element:
    el = ET.Element(_dc("Bounds"), {
        "x": str(bounds.x),
        "y": str(bounds.y),
        "width": str(bounds.width),
        "height": str(bounds.height),
    })
    return el


def _add_shape(
    plane: ET.Element,
    shape_id: str,
    bpmn_element: str,
    bounds: Bounds,
    **extra_attrs: str,
) -> ET.Element:
    shape = ET.SubElement(plane, _di("BPMNShape"), {
        "id": shape_id,
        "bpmnElement": bpmn_element,
        **extra_attrs,
    })
    shape.append(_bounds_el(bounds))
    return shape


def _add_edge(
    plane: ET.Element,
    sf: SequenceFlow,
) -> None:
    edge = ET.SubElement(plane, _di("BPMNEdge"), {
        "id": f"{sf.sf_id}_di",
        "bpmnElement": sf.sf_id,
    })
    for x, y in sf.waypoints:
        wp = ET.SubElement(edge, _ddi("waypoint"), {"x": str(x), "y": str(y)})
        _ = wp  # suppress unused warning


def _add_task_bands(
    plane: ET.Element,
    task_shape_id: str,
    task_bounds: Bounds,
    task: ChoreoTask,
) -> None:
    """Add initiating and non-initiating participant band shapes for a task."""
    from ocelchormodel.layout import BAND_H

    # Top band — initiating participant
    top_bounds = Bounds(
        x=task_bounds.x,
        y=task_bounds.y,
        width=task_bounds.width,
        height=BAND_H,
    )
    _add_shape(
        plane,
        shape_id=f"{task_shape_id}_top",
        bpmn_element=task.initiator.bpmn_id,
        bounds=top_bounds,
        participantBandKind="top_initiating",
        isMessageVisible="true" if task.initiating_msg is not None else "false",
        choreographyActivityShape=task_shape_id,
    )

    # Bottom band — non-initiating participant
    bot_bounds = Bounds(
        x=task_bounds.x,
        y=task_bounds.y + task_bounds.height - BAND_H,
        width=task_bounds.width,
        height=BAND_H,
    )
    _add_shape(
        plane,
        shape_id=f"{task_shape_id}_bot",
        bpmn_element=task.participant.bpmn_id,
        bounds=bot_bounds,
        participantBandKind="bottom_non_initiating",
        isMessageVisible="true" if task.returning_msg is not None else "false",
        choreographyActivityShape=task_shape_id,
    )


def _add_sub_bands(
    plane: ET.Element,
    sub_shape_id: str,
    sub_bounds: Bounds,
    sub: SubChoreo,
) -> None:
    """Add participant band shapes for a subchoreography container.

    Bands alternate between the upper and lower sections of the sub per the
    BPMN 2.0.2 spec (Section 11.5.2, p.331): initiating at top, first
    non-initiating at bottom, next at top, etc.
    """
    from ocelchormodel.layout import BAND_H

    initiator = _first_initiator(sub.children)
    all_parts = _sub_participants(sub)

    if initiator is None or not all_parts:
        return

    non_init = [p for p in all_parts if p.bpmn_id != initiator.bpmn_id]
    ordered = [initiator] + non_init
    n = len(ordered)

    # Split into top and bottom groups via alternation
    top_parts = [ordered[i] for i in range(0, n, 2)]   # indices 0, 2, 4, ...
    bot_parts = [ordered[i] for i in range(1, n, 2)]    # indices 1, 3, 5, ...

    # Top bands: stack downward from sub top
    for i, p in enumerate(top_parts):
        if i == 0:
            kind = "top_initiating"
        else:
            kind = "middle_non_initiating"
        _add_shape(
            plane,
            shape_id=f"{sub_shape_id}_band_t{i}",
            bpmn_element=p.bpmn_id,
            bounds=Bounds(
                x=sub_bounds.x,
                y=sub_bounds.y + i * BAND_H,
                width=sub_bounds.width,
                height=BAND_H,
            ),
            participantBandKind=kind,
            isMessageVisible="false",
            choreographyActivityShape=sub_shape_id,
        )

    # Bottom bands: stack upward from sub bottom
    # First bot_part (index 1 overall = first non-initiating) goes to very bottom
    n_bot = len(bot_parts)
    for j, p in enumerate(bot_parts):
        if j == 0:
            kind = "bottom_non_initiating"
        else:
            kind = "middle_non_initiating"
        _add_shape(
            plane,
            shape_id=f"{sub_shape_id}_band_b{j}",
            bpmn_element=p.bpmn_id,
            bounds=Bounds(
                x=sub_bounds.x,
                y=sub_bounds.y + sub_bounds.height - (j + 1) * BAND_H,
                width=sub_bounds.width,
                height=BAND_H,
            ),
            participantBandKind=kind,
            isMessageVisible="false",
            choreographyActivityShape=sub_shape_id,
        )


# ---------------------------------------------------------------------------
# Semantic section builders
# ---------------------------------------------------------------------------

def _level_sf_maps(
    level_el_ids: list[str],
    layout: DiagramLayout,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (sf_by_source, sf_by_target) for consecutive pairs at this level."""
    sf_by_source: dict[str, str] = {}
    sf_by_target: dict[str, str] = {}
    for sf in layout.sequence_flows:
        if sf.source_id in level_el_ids and sf.target_id in level_el_ids:
            src_idx = level_el_ids.index(sf.source_id)
            tgt_idx = level_el_ids.index(sf.target_id)
            if tgt_idx == src_idx + 1:
                sf_by_source[sf.source_id] = sf.sf_id
                sf_by_target[sf.target_id] = sf.sf_id
    return sf_by_source, sf_by_target


def _build_flow_elements(
    parent: ET.Element,
    elements: list[ChoreoTask | SubChoreo],
    layout: DiagramLayout,
    level_key: str,
    instance_short: str,
) -> None:
    """Append start event, elements, end event, and sequence flows to parent."""
    start_id = layout.start_ids[level_key]
    end_id = layout.end_ids[level_key]

    level_el_ids = [start_id] + [e.bpmn_id for e in elements] + [end_id]
    sf_by_source, sf_by_target = _level_sf_maps(level_el_ids, layout)

    # Start event — outgoing only
    start_el = ET.SubElement(parent, _b2("startEvent"), {"id": start_id})
    if start_id in sf_by_source:
        ET.SubElement(start_el, _b2("outgoing")).text = sf_by_source[start_id]

    # Elements in order, passing their incoming/outgoing SF ids up-front
    for elem in elements:
        inc = sf_by_target.get(elem.bpmn_id)
        out = sf_by_source.get(elem.bpmn_id)
        if isinstance(elem, ChoreoTask):
            _build_choreo_task(parent, elem, layout, incoming=inc, outgoing=out)
        else:
            _build_sub_choreo(parent, elem, layout, instance_short, incoming=inc, outgoing=out)

    # End event — incoming only
    end_el = ET.SubElement(parent, _b2("endEvent"), {"id": end_id})
    if end_id in sf_by_target:
        ET.SubElement(end_el, _b2("incoming")).text = sf_by_target[end_id]

    # Sequence flow declarations
    for sf in layout.sequence_flows:
        if sf.source_id in level_el_ids and sf.target_id in level_el_ids:
            src_idx = level_el_ids.index(sf.source_id)
            tgt_idx = level_el_ids.index(sf.target_id)
            if tgt_idx == src_idx + 1:
                ET.SubElement(parent, _b2("sequenceFlow"), {
                    "id": sf.sf_id,
                    "sourceRef": sf.source_id,
                    "targetRef": sf.target_id,
                })


def _build_choreo_task(
    parent: ET.Element,
    task: ChoreoTask,
    layout: DiagramLayout,
    incoming: str | None = None,
    outgoing: str | None = None,
) -> None:
    """Append a <bpmn2:choreographyTask> element."""
    attrs: dict[str, str] = {
        "id": task.bpmn_id,
        "name": task.name,
        "initiatingParticipantRef": task.initiator.bpmn_id,
    }
    task_el = ET.SubElement(parent, _b2("choreographyTask"), attrs)

    # incoming/outgoing MUST precede participantRef (BPMN 2.0 schema order)
    if incoming:
        ET.SubElement(task_el, _b2("incoming")).text = incoming
    if outgoing:
        ET.SubElement(task_el, _b2("outgoing")).text = outgoing

    ET.SubElement(task_el, _b2("participantRef")).text = task.initiator.bpmn_id
    ET.SubElement(task_el, _b2("participantRef")).text = task.participant.bpmn_id

    for msg in (task.initiating_msg, task.returning_msg):
        if msg is not None:
            ET.SubElement(task_el, _b2("messageFlowRef")).text = msg.mf_id


def _build_sub_choreo(
    parent: ET.Element,
    sub: SubChoreo,
    layout: DiagramLayout,
    instance_short: str,
    incoming: str | None = None,
    outgoing: str | None = None,
) -> None:
    """Append a <bpmn2:subChoreography> element with its inner flow."""
    initiator = _first_initiator(sub.children)
    all_parts = _sub_participants(sub)

    attrs: dict[str, str] = {
        "id": sub.bpmn_id,
        "name": sub.name,
    }
    if initiator:
        attrs["initiatingParticipantRef"] = initiator.bpmn_id

    sub_el = ET.SubElement(parent, _b2("subChoreography"), attrs)

    # incoming/outgoing MUST precede participantRef (BPMN 2.0 schema order)
    if incoming:
        ET.SubElement(sub_el, _b2("incoming")).text = incoming
    if outgoing:
        ET.SubElement(sub_el, _b2("outgoing")).text = outgoing

    # participantRefs — initiating first, then non-initiating (matches band order)
    non_init = [p for p in all_parts if p.bpmn_id != initiator.bpmn_id]
    for p in [initiator] + non_init:
        ET.SubElement(sub_el, _b2("participantRef")).text = p.bpmn_id

    # Inner flow
    _build_flow_elements(
        parent=sub_el,
        elements=sub.children,
        layout=layout,
        level_key=sub.bpmn_id,
        instance_short=instance_short,
    )


# ---------------------------------------------------------------------------
# DI section builder
# ---------------------------------------------------------------------------

def _build_di(
    plane: ET.Element,
    instance: ChoreoInstance,
    layout: DiagramLayout,
) -> None:
    """Append all BPMNShape and BPMNEdge elements to the plane."""

    def _add_level(elements: list[ChoreoTask | SubChoreo], level_key: str) -> None:
        start_id = layout.start_ids[level_key]
        end_id = layout.end_ids[level_key]

        # Start event shape
        _add_shape(plane, f"{start_id}_di", start_id, layout.bounds[start_id])

        for elem in elements:
            if isinstance(elem, ChoreoTask):
                task_shape_id = f"{elem.bpmn_id}_di"
                _add_shape(plane, task_shape_id, elem.bpmn_id, layout.bounds[elem.bpmn_id])
                _add_task_bands(plane, task_shape_id, layout.bounds[elem.bpmn_id], elem)
            else:
                sub_shape_id = f"{elem.bpmn_id}_di"
                _add_shape(
                    plane, sub_shape_id, elem.bpmn_id, layout.bounds[elem.bpmn_id],
                    isExpanded="true",
                )
                _add_sub_bands(plane, sub_shape_id, layout.bounds[elem.bpmn_id], elem)
                _add_level(elem.children, elem.bpmn_id)

        # End event shape
        _add_shape(plane, f"{end_id}_di", end_id, layout.bounds[end_id])

    _add_level(instance.elements, "")

    # All sequence flow edges
    for sf in layout.sequence_flows:
        _add_edge(plane, sf)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_bpmn(instance: ChoreoInstance, layout: DiagramLayout) -> str:
    """Generate a BPMN 2.0 XML string for the given instance and layout."""
    # --- Collect all participants and messages globally ---
    all_participants = _collect_participants(instance.elements)
    all_messages = _collect_messages(instance.elements)

    # --- Root <bpmn2:definitions> ---
    defs = ET.Element(_b2("definitions"), {
        "targetNamespace": TARGET_NS,
        "id": f"Definitions_{instance.short_id}",
    })

    # --- Global message definitions ---
    for msg in all_messages.values():
        ET.SubElement(defs, _b2("message"), {
            "id": msg.bpmn_id,
            "name": msg.name,
        })

    # --- <bpmn2:choreography> ---
    choreo_id = f"Choreography_{instance.short_id}"
    choreo = ET.SubElement(defs, _b2("choreography"), {
        "id": choreo_id,
        "name": instance.short_id,
    })

    # Declare all participants
    for part in all_participants.values():
        ET.SubElement(choreo, _b2("participant"), {
            "id": part.bpmn_id,
            "name": part.display_name,
        })

    # Declare all message flows
    for msg in all_messages.values():
        ET.SubElement(choreo, _b2("messageFlow"), {
            "id": msg.mf_id,
            "sourceRef": msg.source.bpmn_id,
            "targetRef": msg.target.bpmn_id,
            "messageRef": msg.bpmn_id,
        })

    # Build top-level flow elements
    _build_flow_elements(
        parent=choreo,
        elements=instance.elements,
        layout=layout,
        level_key="",
        instance_short=instance.short_id,
    )

    # --- <bpmndi:BPMNDiagram> ---
    diagram = ET.SubElement(defs, _di("BPMNDiagram"), {
        "id": f"BPMNDiagram_{instance.short_id}",
    })
    plane = ET.SubElement(diagram, _di("BPMNPlane"), {
        "id": f"BPMNPlane_{instance.short_id}",
        "bpmnElement": choreo_id,
    })

    _build_di(plane, instance, layout)

    # --- Serialise with indentation ---
    ET.indent(defs, space="  ")
    xml_str = ET.tostring(defs, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}\n'


def write_bpmn(xml_str: str, path: Path) -> None:
    """Write the BPMN XML string to a file (UTF-8)."""
    path.write_text(xml_str, encoding="utf-8")
