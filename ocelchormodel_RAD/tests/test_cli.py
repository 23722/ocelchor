"""M4 — CLI acceptance: per-log output triple, hard-gate failure path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocelchormodel_rad.cli import main

DATA = Path(__file__).resolve().parents[1] / "data" / "input"


def test_cli_fixture_three_files(worked_example_path, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(worked_example_path), "-o", str(tmp_path)])
    assert exc.value.code == 0

    out = tmp_path / "worked_example"
    bpmn = (out / "discovered_model.bpmn").read_text()
    assert bpmn.startswith("<?xml") and "choreography" in bpmn
    tree = (out / "process_tree.txt").read_text()
    assert tree.startswith("∇_{unlock [Gov]} ⟨Proxy→Governance⟩(")
    assert tree.endswith(")\n")
    diag = json.loads((out / "diagnostics.json").read_text())
    assert diag["log"] == "worked_example"
    assert diag["d02_scope_openers"]["non_request_openers"] == 0

    assert "OK worked_example.json" in capsys.readouterr().out


def test_cli_hard_gate_skip_continues(worked_example_path, tmp_path, capsys):
    """A C3-violating log is reported and skipped with nonzero exit; the
    remaining inputs are still processed."""
    bad = DATA / "healthcare_uniqueInteraction_ocel.json"
    if not bad.exists():
        pytest.skip(f"{bad} not present")
    with pytest.raises(SystemExit) as exc:
        main([str(bad), str(worked_example_path), "-o", str(tmp_path)])
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "SKIP healthcare_uniqueInteraction_ocel.json" in captured.err
    assert "C3" in captured.err
    assert not (tmp_path / "healthcare_uniqueInteraction").exists()
    # the good input still produced its triple
    assert (tmp_path / "worked_example" / "diagnostics.json").exists()
