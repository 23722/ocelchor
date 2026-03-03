"""Auto-layout computation for BPMN choreography diagrams.

chor-js requires explicit DI coordinates; there is no auto-layout.
This module computes a simple left-to-right sequential layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocelchormodel.model import ChoreoInstance, ChoreoTask, SubChoreo

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

TASK_W = 100       # choreography task width
TASK_H = 80        # choreography task height (including participant bands)
BAND_H = 20        # participant band height (top AND bottom)
EVENT_SIZE = 36    # start / end event diameter
H_GAP = 50         # horizontal gap between adjacent elements
SUB_PAD_X = 30     # horizontal inner padding in subchoreography box
SUB_PAD_Y = 40     # vertical inner padding (above/below inner flow)
FLOW_Y = 250       # y-centre of the top-level sequence flow
X_ORIGIN = 100     # left margin


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Bounds:
    x: int
    y: int
    width: int
    height: int

    @property
    def cx(self) -> int:
        """Horizontal centre."""
        return self.x + self.width // 2

    @property
    def cy(self) -> int:
        """Vertical centre."""
        return self.y + self.height // 2

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass
class SequenceFlow:
    sf_id: str
    source_id: str
    target_id: str
    waypoints: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class DiagramLayout:
    """Complete layout for a choreography diagram."""

    # bpmn_id → Bounds for every element (tasks, subchoreos, start/end events)
    bounds: dict[str, Bounds] = field(default_factory=dict)

    # All sequence flows at all levels
    sequence_flows: list[SequenceFlow] = field(default_factory=list)

    # IDs assigned to start/end events at each level
    # top-level: stored under key "" (empty string)
    # inner levels: stored under the SubChoreo bpmn_id
    start_ids: dict[str, str] = field(default_factory=dict)   # level_key → start_event_id
    end_ids: dict[str, str] = field(default_factory=dict)     # level_key → end_event_id


# ---------------------------------------------------------------------------
# Participant counting (for band layout)
# ---------------------------------------------------------------------------

def _count_unique_participants(elements: list[ChoreoTask | SubChoreo]) -> int:
    """Count unique participants across all tasks in a subtree."""
    seen: set[str] = set()

    def _collect(elems: list[ChoreoTask | SubChoreo]) -> None:
        for elem in elems:
            if isinstance(elem, ChoreoTask):
                seen.add(elem.initiator.bpmn_id)
                seen.add(elem.participant.bpmn_id)
            else:
                _collect(elem.children)

    _collect(elements)
    return max(len(seen), 2)  # BPMN requires at least 2


def _band_split(n_parts: int) -> tuple[int, int]:
    """Return (n_top_bands, n_bottom_bands) using alternation.

    Participants alternate top/bottom: initiating at top, first non-initiating
    at bottom, next at top, etc.  n_top = ceil(N/2), n_bottom = floor(N/2).
    """
    return (n_parts + 1) // 2, n_parts // 2


# ---------------------------------------------------------------------------
# Size computation (bottom-up pass)
# ---------------------------------------------------------------------------

def _element_height(element: ChoreoTask | SubChoreo) -> int:
    """Return the visual height of a layout element."""
    if isinstance(element, ChoreoTask):
        return TASK_H
    # SubChoreo: all participant bands + padding + max child height
    n_parts = _count_unique_participants(element.children)
    child_hs = [_element_height(c) for c in element.children]
    inner_h = max([TASK_H] + child_hs)
    return n_parts * BAND_H + 2 * SUB_PAD_Y + inner_h


def _element_width(element: ChoreoTask | SubChoreo) -> int:
    """Return the visual width of a layout element."""
    if isinstance(element, ChoreoTask):
        return TASK_W
    # SubChoreo: padding + start_event + gaps + children + end_event + padding
    child_ws = [_element_width(c) for c in element.children]
    n = len(element.children)
    return (
        2 * SUB_PAD_X
        + 2 * EVENT_SIZE
        + H_GAP * (n + 1)
        + sum(child_ws)
    )


# ---------------------------------------------------------------------------
# Layout computation (top-down pass)
# ---------------------------------------------------------------------------

_sf_counter = 0


def _next_sf_id() -> str:
    global _sf_counter
    _sf_counter += 1
    return f"SF_{_sf_counter}"


def compute_layout(instance: ChoreoInstance) -> DiagramLayout:
    """Compute the full diagram layout for a choreography instance."""
    global _sf_counter
    _sf_counter = 0  # reset for deterministic IDs per call

    layout = DiagramLayout()
    _layout_level(
        elements=instance.elements,
        center_y=FLOW_Y,
        x_cursor=X_ORIGIN,
        level_key="",
        instance_short=instance.short_id,
        layout=layout,
    )
    return layout


def _layout_level(
    elements: list[ChoreoTask | SubChoreo],
    center_y: int,
    x_cursor: int,
    level_key: str,
    instance_short: str,
    layout: DiagramLayout,
) -> int:
    """Lay out a sequence of elements on a horizontal flow line.

    Returns the x coordinate after the last element (before the end event).
    """
    # Assign start event
    start_id = f"Start_{instance_short}_{level_key}" if level_key else f"Start_{instance_short}"
    end_id   = f"End_{instance_short}_{level_key}"   if level_key else f"End_{instance_short}"
    layout.start_ids[level_key] = start_id
    layout.end_ids[level_key]   = end_id

    start_bounds = Bounds(
        x=x_cursor,
        y=center_y - EVENT_SIZE // 2,
        width=EVENT_SIZE,
        height=EVENT_SIZE,
    )
    layout.bounds[start_id] = start_bounds
    x_cursor += EVENT_SIZE + H_GAP

    # Track the ordered sequence of element IDs for flow connection
    ordered_ids: list[str] = [start_id]

    for element in elements:
        elem_h = _element_height(element)
        elem_w = _element_width(element)
        elem_y = center_y - elem_h // 2

        if isinstance(element, ChoreoTask):
            layout.bounds[element.bpmn_id] = Bounds(
                x=x_cursor, y=elem_y, width=elem_w, height=elem_h
            )
            ordered_ids.append(element.bpmn_id)
            x_cursor += elem_w + H_GAP

        else:  # SubChoreo
            sub_bounds = Bounds(
                x=x_cursor, y=elem_y, width=elem_w, height=elem_h
            )
            layout.bounds[element.bpmn_id] = sub_bounds
            ordered_ids.append(element.bpmn_id)

            # Account for asymmetric top/bottom bands
            n_parts = _count_unique_participants(element.children)
            n_top, n_bot = _band_split(n_parts)
            inner_top = elem_y + n_top * BAND_H + SUB_PAD_Y
            inner_bot = elem_y + elem_h - n_bot * BAND_H - SUB_PAD_Y
            inner_center_y = (inner_top + inner_bot) // 2
            # Inner flow starts after left padding
            inner_x_start = x_cursor + SUB_PAD_X

            _layout_level(
                elements=element.children,
                center_y=inner_center_y,
                x_cursor=inner_x_start,
                level_key=element.bpmn_id,
                instance_short=instance_short,
                layout=layout,
            )
            x_cursor += elem_w + H_GAP

    # Assign end event
    end_bounds = Bounds(
        x=x_cursor,
        y=center_y - EVENT_SIZE // 2,
        width=EVENT_SIZE,
        height=EVENT_SIZE,
    )
    layout.bounds[end_id] = end_bounds
    ordered_ids.append(end_id)

    # Build sequence flows between adjacent elements
    for i in range(len(ordered_ids) - 1):
        src_id = ordered_ids[i]
        tgt_id = ordered_ids[i + 1]
        src_b = layout.bounds[src_id]
        tgt_b = layout.bounds[tgt_id]
        sf = SequenceFlow(
            sf_id=_next_sf_id(),
            source_id=src_id,
            target_id=tgt_id,
            waypoints=[
                (src_b.right, center_y),
                (tgt_b.x, center_y),
            ],
        )
        layout.sequence_flows.append(sf)

    return x_cursor
