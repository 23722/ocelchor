"""Tests for ocelchormodel.cli.

Verifies the command-line interface: listing instances, batch
conversion, output directory structure, and error handling.

Why these tests matter:
  The CLI is the user-facing interface. These tests confirm that
  all documented usage patterns work correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchormodel.cli import _stem, _tx_hash, main

DATA_DIR = Path(__file__).parent / "data"
SWAP1 = str(DATA_DIR / "swap_1_ocel.json")
MULTI_TX = str(DATA_DIR / "swap_multi_tx_ocel.json")


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------

class TestStem:
    """_stem strips _ocel.json when present."""

    def test_strips_ocel_suffix(self):
        assert _stem(Path("0x55_truncated_ocel.json")) == "0x55_truncated"

    def test_no_ocel_suffix(self):
        assert _stem(Path("myfile.json")) == "myfile"

    def test_beanstalk(self):
        assert _stem(Path("beanstalk_attack_ocel.json")) == "beanstalk_attack"


class TestTxHash:
    """_tx_hash extracts the hash from a choreographyInstance: ID."""

    def test_strips_prefix(self):
        assert _tx_hash("choreographyInstance:0xabc") == "0xabc"

    def test_no_prefix(self):
        assert _tx_hash("0xabc") == "0xabc"


# ---------------------------------------------------------------------------
# --list flag
# ---------------------------------------------------------------------------

class TestListFlag:
    """'ocelchormodel input.json --list' prints instance IDs and exits."""

    def test_prints_instance_ids(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([SWAP1, "--list"])
        assert exc.value.code == 0
        assert "choreographyInstance:" in capsys.readouterr().out

    def test_shows_count_for_multi_instance(self, capsys):
        with pytest.raises(SystemExit):
            main([MULTI_TX, "--list"])
        assert "2" in capsys.readouterr().out

    def test_list_multiple_files(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([SWAP1, MULTI_TX, "--list"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "swap_1_ocel.json" in out
        assert "swap_multi_tx_ocel.json" in out


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------

class TestBatchConversion:
    """Batch mode: all instances from each input file are converted."""

    def test_single_file_creates_subdir(self, tmp_path):
        main([SWAP1, "-o", str(tmp_path)])
        subdir = tmp_path / "swap_1"
        assert subdir.is_dir()
        bpmn_files = list(subdir.glob("*.bpmn"))
        assert len(bpmn_files) == 1
        assert bpmn_files[0].read_text().startswith("<?xml")

    def test_multi_instance_file(self, tmp_path):
        main([MULTI_TX, "-o", str(tmp_path)])
        subdir = tmp_path / "swap_multi_tx"
        assert subdir.is_dir()
        bpmn_files = list(subdir.glob("*.bpmn"))
        assert len(bpmn_files) == 2

    def test_multiple_input_files(self, tmp_path):
        main([SWAP1, MULTI_TX, "-o", str(tmp_path)])
        assert (tmp_path / "swap_1").is_dir()
        assert (tmp_path / "swap_multi_tx").is_dir()

    def test_bpmn_named_by_tx_hash(self, tmp_path):
        main([SWAP1, "-o", str(tmp_path)])
        subdir = tmp_path / "swap_1"
        bpmn_files = list(subdir.glob("*.bpmn"))
        # Filename should be the full tx hash (0x...) not a short id
        assert bpmn_files[0].stem.startswith("0x")
        assert len(bpmn_files[0].stem) > 10


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrors:
    """Invalid input should exit with a non-zero status code."""

    def test_missing_file(self):
        with pytest.raises(SystemExit) as exc:
            main(["/nonexistent/path.ocel.json", "--list"])
        assert exc.value.code != 0

    def test_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("NOT JSON AT ALL")
        with pytest.raises(SystemExit) as exc:
            main([str(bad), "--list"])
        assert exc.value.code != 0


# ---------------------------------------------------------------------------
# Hardening: refusal and warnings notes
# ---------------------------------------------------------------------------

class TestHardeningNotes:

    def _write_log(self, tmp_path, event_rels, msg_rels):
        import json
        ocel = {
            "objectTypes": [], "eventTypes": [],
            "objects": [
                {"id": "choreographyInstance:0xt1", "type": "choreographyInstance"},
                {"id": "0xaaa", "type": "EOA"},
                {"id": "0xbbb", "type": "Vault"},
                {"id": "0xccc", "type": "Pool"},
                {"id": "msg1", "type": "deposit call", "relationships": msg_rels},
            ],
            "events": [{
                "id": "e:t1:root", "type": "deposit [Vault]",
                "time": "2024-01-01T00:00:00.000Z",
                "attributes": [{"name": "trace_order", "value": 0}],
                "relationships": event_rels + [
                    {"objectId": "msg1", "qualifier": "choreo:message"},
                    {"objectId": "choreographyInstance:0xt1", "qualifier": "choreo:instance"},
                ],
            }],
        }
        p = tmp_path / "synthetic_ocel.json"
        p.write_text(json.dumps(ocel))
        return p

    def test_multicast_instance_refused_with_note(self, tmp_path, capsys):
        log = self._write_log(
            tmp_path,
            [{"objectId": "0xaaa", "qualifier": "choreo:initiator"},
             {"objectId": "0xbbb", "qualifier": "choreo:participant"},
             {"objectId": "0xccc", "qualifier": "choreo:participant"}],
            [{"objectId": "0xaaa", "qualifier": "choreo:source"},
             {"objectId": "0xbbb", "qualifier": "choreo:target"},
             {"objectId": "0xccc", "qualifier": "choreo:target"}],
        )
        out = tmp_path / "out"
        with pytest.raises(SystemExit) as exc:
            main([str(log), "-o", str(out)])
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "REFUSE" in err and "multicast" in err
        subdir = out / "synthetic"
        assert list(subdir.glob("*.bpmn")) == []
        note = (subdir / "0xt1.refused.txt").read_text()
        assert "no model converted" in note and "C3" in note

    def test_missing_receiver_converted_with_warning_note(self, tmp_path, capsys):
        log = self._write_log(
            tmp_path,
            [{"objectId": "0xaaa", "qualifier": "choreo:initiator"}],
            [{"objectId": "0xaaa", "qualifier": "choreo:source"}],
        )
        out = tmp_path / "out"
        main([str(log), "-o", str(out)])  # exits normally (no SystemExit)
        err = capsys.readouterr().err
        assert "WARN" in err and "phantom" in err
        subdir = out / "synthetic"
        assert len(list(subdir.glob("*.bpmn"))) == 1
        note = (subdir / "0xt1.warnings.txt").read_text()
        assert "unrecorded endpoints" in note and "e:t1:root" in note
