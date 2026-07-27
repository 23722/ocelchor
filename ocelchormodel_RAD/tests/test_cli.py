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
    """A multicast log (C3 shape |noninit| > 1) is refused with nonzero exit
    and leaves only a refusal note; the remaining inputs still run."""
    bad = DATA / "smartagriculture_uniqueInteraction_ocel.json"
    if not bad.exists():
        pytest.skip(f"{bad} not present")
    with pytest.raises(SystemExit) as exc:
        main([str(bad), str(worked_example_path), "-o", str(tmp_path)])
    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert "SKIP smartagriculture_uniqueInteraction_ocel.json" in captured.err
    assert "multicast" in captured.err
    refused_dir = tmp_path / "smartagriculture_uniqueInteraction"
    assert [p.name for p in refused_dir.iterdir()] == ["REFUSED.txt"]
    note = (refused_dir / "REFUSED.txt").read_text()
    assert "no model discovered" in note and "multicast" in note
    # the good input still produced its triple
    assert (tmp_path / "worked_example" / "diagnostics.json").exists()
    assert not (tmp_path / "worked_example" / "WARNINGS.txt").exists()


def test_cli_missing_receiver_warned_not_refused(tmp_path, capsys):
    """A missing-receiver log (C3 shape |noninit| = 0) is discovered with a
    warnings note naming the tolerated events; exit stays zero."""
    warned = DATA / "healthcare_uniqueInteraction_ocel.json"
    if not warned.exists():
        pytest.skip(f"{warned} not present")
    with pytest.raises(SystemExit) as exc:
        main([str(warned), "-o", str(tmp_path)])
    assert exc.value.code == 0

    captured = capsys.readouterr()
    assert "OK healthcare_uniqueInteraction_ocel.json" in captured.out
    assert "WARN healthcare_uniqueInteraction_ocel.json" in captured.err

    out = tmp_path / "healthcare_uniqueInteraction"
    assert (out / "discovered_model.bpmn").exists()
    note = (out / "WARNINGS.txt").read_text()
    assert "despite C3 violations" in note
    assert note.count("e:case_") == 9  # the nine tolerated events, by id

    diag = json.loads((out / "diagnostics.json").read_text())
    assert len(diag["hard_gates"]["tolerated_missing_receiver_events"]) == 9
    assert diag["constraints"]["C3"]["violations"] == 9
