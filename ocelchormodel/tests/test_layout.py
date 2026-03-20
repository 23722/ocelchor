"""Tests for ocelchormodel.layout.

Verifies the geometry engine that positions BPMN elements for
diagram interchange (DI) output. This includes:
  - Bounds arithmetic (center, right, bottom)
  - Band splitting (how participants are distributed top/bottom)
  - Element sizing (tasks vs. subchoreographies)
  - Full layout computation (start/end events, sequence flows)

Why these tests matter:
  Incorrect geometry produces BPMN that parses but renders
  incorrectly in chor-js. These tests pin down the mathematical
  properties that the renderer depends on.
"""

from __future__ import annotations

from ocelchormodel.layout import (
    BAND_H,
    SUB_PAD_Y,
    TASK_H,
    TASK_W,
    Bounds,
    _band_split,
    _count_unique_participants,
    _element_height,
    compute_layout,
)
from ocelchormodel.model import (
    ChoreoInstance,
    ChoreoTask,
    Participant,
    SubChoreo,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _part(suffix: str) -> Participant:
    return Participant(
        ocel_id=f"0x{suffix}",
        ocel_type="CA",
        display_name=f"CA_{suffix}",
        bpmn_id=f"P_{suffix}",
    )

def _task(name: str, init_suf: str = "aa", part_suf: str = "bb", order: int = 0) -> ChoreoTask:
    return ChoreoTask(
        bpmn_id=f"Task_{name}",
        name=name,
        initiator=_part(init_suf),
        participant=_part(part_suf),
        initiating_msg=None,
        returning_msg=None,
        trace_order=order,
    )


# ---------------------------------------------------------------------------
# Bounds: derived coordinate properties
# ---------------------------------------------------------------------------

class TestBounds:
    """Bounds stores (x, y, width, height) and derives center/right/bottom."""

    def test_center_x(self):
        b = Bounds(x=100, y=50, width=200, height=80)
        assert b.cx == 200  # x + width/2

    def test_center_y(self):
        b = Bounds(x=100, y=50, width=200, height=80)
        assert b.cy == 90  # y + height/2


# ---------------------------------------------------------------------------
# _band_split: distributes participants across top/bottom bands
# ---------------------------------------------------------------------------

class TestBandSplit:
    """Band split decides how many participant bands go on top vs. bottom
    of a choreography activity. The BPMN 2.0.2 spec (Section 11.5.2)
    requires the initiator on top; remaining bands alternate."""

    def test_two_participants(self):
        """Standard case: 1 top (initiator), 1 bottom."""
        assert _band_split(2) == (1, 1)

    def test_odd_count(self):
        """Odd counts put the extra band on top."""
        assert _band_split(5) == (3, 2)

    def test_invariant_sum_equals_n(self):
        """For any participant count, top + bottom = n."""
        for n in range(1, 21):
            n_top, n_bot = _band_split(n)
            assert n_top + n_bot == n, f"Failed for n={n}"


# ---------------------------------------------------------------------------
# _count_unique_participants: counts distinct actors in an element tree
# ---------------------------------------------------------------------------

class TestCountUniqueParticipants:
    """Used to determine how many bands a subchoreography needs."""

    def test_single_task_has_two(self):
        assert _count_unique_participants([_task("t1")]) == 2

    def test_nested_subchoreo(self):
        """SubChoreo with tasks involving 3 distinct participants."""
        t1 = _task("t1", "aa", "bb")
        t2 = _task("t2", "aa", "cc")
        sub = SubChoreo(bpmn_id="Sub_1", name="s", scope_ocel_id="sub:test:1", children=[t1, t2])
        assert _count_unique_participants([sub]) == 3


# ---------------------------------------------------------------------------
# _element_height: vertical size of a BPMN element
# ---------------------------------------------------------------------------

class TestElementSize:
    """Tasks have fixed height; subchoreographies grow with band count."""

    def test_task_height(self):
        assert _element_height(_task("t")) == TASK_H

    def test_subchoreo_height(self):
        """SubChoreo with 2 participants: 2*BAND_H + 2*SUB_PAD_Y + TASK_H."""
        sub = SubChoreo(
            bpmn_id="Sub_h", name="s", scope_ocel_id="sub:test:h",
            children=[_task("inner")],
        )
        expected = 2 * BAND_H + 2 * SUB_PAD_Y + TASK_H
        assert _element_height(sub) == expected


# ---------------------------------------------------------------------------
# compute_layout: full layout computation
# ---------------------------------------------------------------------------

class TestComputeLayout:
    """The layout engine places start events, elements, end events,
    and computes sequence flows connecting them."""

    def test_single_task_has_start_task_end(self):
        """A single-task instance produces bounds for start, task, and end."""
        inst = ChoreoInstance(
            ocel_id="choreographyInstance:0xabc",
            short_id="abcdef12",
            elements=[_task("t1")],
        )
        layout = compute_layout(inst)
        assert "Task_t1" in layout.bounds
        assert layout.start_ids[""] in layout.bounds
        assert layout.end_ids[""] in layout.bounds

    def test_single_task_has_two_sequence_flows(self):
        """start -> task -> end = 2 sequence flows."""
        inst = ChoreoInstance(
            ocel_id="choreographyInstance:0xabc", short_id="abcdef12",
            elements=[_task("t1")],
        )
        layout = compute_layout(inst)
        assert len(layout.sequence_flows) == 2

    def test_subchoreo_gets_own_start_and_end(self):
        """A subchoreography has its own start/end events (keyed by bpmn_id)."""
        inner = _task("inner")
        sub = SubChoreo(bpmn_id="Sub_x", name="s", scope_ocel_id="sub:test:x", children=[inner])
        inst = ChoreoInstance(
            ocel_id="choreographyInstance:0xabc", short_id="abcdef12",
            elements=[sub],
        )
        layout = compute_layout(inst)
        assert "Sub_x" in layout.start_ids
        assert "Sub_x" in layout.end_ids

    def test_deterministic_ids(self):
        """Two calls produce identical sequence flow IDs (no global state leak)."""
        inst = ChoreoInstance(
            ocel_id="choreographyInstance:0xabc", short_id="abcdef12",
            elements=[_task("t1"), _task("t2", order=1)],
        )
        layout1 = compute_layout(inst)
        layout2 = compute_layout(inst)
        ids1 = [sf.sf_id for sf in layout1.sequence_flows]
        ids2 = [sf.sf_id for sf in layout2.sequence_flows]
        assert ids1 == ids2
