"""Shared pytest fixtures for ocelchormodel tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchormodel.reader import read_ocel

DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def swap1_ocel() -> dict:
    return read_ocel(DATA_DIR / "swap_1_ocel.json")


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
    return read_ocel(DATA_DIR / "0x55_truncated_ocel.json")
