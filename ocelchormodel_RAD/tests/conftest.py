"""Shared test fixtures for the ocelchormodel_rad miner."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchormodel_rad import reader

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def worked_example_path() -> Path:
    return FIXTURES / "worked_example.json"


@pytest.fixture
def worked_example(worked_example_path):
    return reader.load(worked_example_path)
