"""CLI integration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "data"
REAL1 = Path(__file__).parent.parent / "data" / "input" / "collectivelog_real1.xes"


def _run(args: list[str]):
    return subprocess.run(
        [sys.executable, "-m", "xescol2ocelchor", *args],
        capture_output=True, text=True,
    )


class TestCliBasic:

    def test_help_exits_zero(self):
        r = _run(["--help"])
        assert r.returncode == 0
        assert "xescol2ocelchor" in r.stdout

    def test_missing_input_errors(self, tmp_path):
        r = _run([str(tmp_path / "nope.xes"), "-o", str(tmp_path)])
        assert r.returncode == 2

    def test_synthetic_writes_output(self, tmp_path):
        r = _run([str(FIXTURES / "synthetic_minimal.xes"), "-o", str(tmp_path)])
        assert r.returncode == 0, r.stderr
        out = tmp_path / "synthetic_minimal_ocel.json"
        assert out.exists()
        with open(out) as f:
            ocel = json.load(f)
        assert set(ocel) == {"objectTypes", "eventTypes", "objects", "events"}


class TestCliReal1:

    @pytest.mark.skipif(not REAL1.exists(), reason="real1 dataset not present")
    def test_real1_round_trip(self, tmp_path):
        r = _run([str(REAL1), "-o", str(tmp_path)])
        assert r.returncode == 0, r.stderr
        out = tmp_path / "real1_ocel.json"
        assert out.exists()
        with open(out) as f:
            ocel = json.load(f)

        # Appendix A: 22 instances → 22 choreographyInstance objects
        inst = [o for o in ocel["objects"] if o["type"] == "choreographyInstance"]
        assert len(inst) == 22

        # Appendix A: 44 task events (one per send)
        assert len(ocel["events"]) == 44

        # Appendix A: 44 message objects
        msgs = [o for o in ocel["objects"]
                if not o["type"].startswith("choreography")
                and o["type"] != "participant"]
        assert len(msgs) == 44

        # Appendix A: 2 participants (Dingo, Rex)
        parts = [o for o in ocel["objects"] if o["type"] == "participant"]
        assert len(parts) == 2
        assert {p["id"] for p in parts} == {
            "participant:Dingo", "participant:Rex",
        }
