"""Shared pytest fixtures for loading test data."""

import json
from pathlib import Path

import pytest

from trace2choreo.parser import load_trace_file


DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def data_dir():
    return DATA_DIR


@pytest.fixture
def swap_1_raw(data_dir):
    with open(data_dir / "swap_1.json") as f:
        return json.load(f)


@pytest.fixture
def swap_2_raw(data_dir):
    with open(data_dir / "swap_2.json") as f:
        return json.load(f)


@pytest.fixture
def swap_3_raw(data_dir):
    with open(data_dir / "swap_3.json") as f:
        return json.load(f)


@pytest.fixture
def swap_3_inconsistent_raw(data_dir):
    with open(data_dir / "swap_3_inconsistent.json") as f:
        return json.load(f)


@pytest.fixture
def swap_root_only_raw(data_dir):
    with open(data_dir / "swap_root_only.json") as f:
        return json.load(f)


@pytest.fixture
def swap_multi_tx_raw(data_dir):
    with open(data_dir / "swap_multi_tx.json") as f:
        return json.load(f)


@pytest.fixture
def swap_undefined_activity_raw(data_dir):
    with open(data_dir / "swap_undefined_activity.json") as f:
        return json.load(f)


@pytest.fixture
def swap_special_calls_raw(data_dir):
    with open(data_dir / "swap_special_calls.json") as f:
        return json.load(f)


@pytest.fixture
def swap_reverted_raw(data_dir):
    with open(data_dir / "swap_reverted.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parsed Trace fixtures (for transformer tests)
# ---------------------------------------------------------------------------

@pytest.fixture
def swap_root_only_trace(data_dir):
    traces = load_trace_file(data_dir / "swap_root_only.json")
    return traces[0]


@pytest.fixture
def swap_1_trace(data_dir):
    traces = load_trace_file(data_dir / "swap_1.json")
    return traces[0]


@pytest.fixture
def swap_3_trace(data_dir):
    traces = load_trace_file(data_dir / "swap_3.json")
    return traces[0]


@pytest.fixture
def swap_undefined_activity_trace(data_dir):
    traces = load_trace_file(data_dir / "swap_undefined_activity.json")
    return traces[0]


# ---------------------------------------------------------------------------
# Ground-truth fixtures (real PancakeSwap / other DApp traces, truncated)
# ---------------------------------------------------------------------------

@pytest.fixture
def gt_0x55_traces(data_dir):
    return load_trace_file(data_dir / "0x55_truncated.json")


@pytest.fixture
def gt_0x5e_traces(data_dir):
    return load_trace_file(data_dir / "0x5e_truncated.json")


