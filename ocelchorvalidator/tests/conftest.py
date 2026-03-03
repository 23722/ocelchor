"""Shared pytest fixtures for ocelchorvalidator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchorvalidator.reader import read_ocel

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def swap1_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_1_ocel.json")


@pytest.fixture
def swap2_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_2_ocel.json")


@pytest.fixture
def swap3_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_3_ocel.json")


@pytest.fixture
def swap_root_only_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_root_only_ocel.json")


@pytest.fixture
def swap_multi_tx_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_multi_tx_ocel.json")


@pytest.fixture
def real_world_ocel() -> dict:
    return read_ocel(DATA_DIR / "0x5e_0xcd4_ocel.json")
