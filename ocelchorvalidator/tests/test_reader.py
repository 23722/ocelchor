"""Tests for ocelchorvalidator.reader — OCEL 2.0 JSON loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchorvalidator.reader import read_ocel

DATA_DIR = Path(__file__).parent / "data"


# --- Positive cases ---


def test_load_swap_1(swap1_ocel: dict) -> None:
    assert "objectTypes" in swap1_ocel
    assert "eventTypes" in swap1_ocel
    assert "objects" in swap1_ocel
    assert "events" in swap1_ocel
    assert len(swap1_ocel["events"]) == 2
    assert len(swap1_ocel["objects"]) == 8


def test_load_swap_3(swap3_ocel: dict) -> None:
    assert len(swap3_ocel["events"]) == 8


def test_load_real_world(real_world_ocel: dict) -> None:
    assert "events" in real_world_ocel
    assert len(real_world_ocel["events"]) > 0


# --- Negative cases ---


def test_nonexistent_file() -> None:
    with pytest.raises(ValueError, match="Cannot read"):
        read_ocel(Path("nonexistent.json"))


def test_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{broken")
    with pytest.raises(ValueError, match="Invalid JSON"):
        read_ocel(bad)


def test_not_a_json_object(tmp_path: Path) -> None:
    arr = tmp_path / "array.json"
    arr.write_text("[1, 2, 3]")
    with pytest.raises(ValueError, match="Expected a JSON object"):
        read_ocel(arr)


def test_missing_required_keys(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text('{"objectTypes": []}')
    with pytest.raises(ValueError, match="Missing required OCEL 2.0 keys"):
        read_ocel(incomplete)
