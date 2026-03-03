"""Tests for CLI argument parsing and end-to-end execution."""

import json
from pathlib import Path

import pytest

from trace2choreo.cli import main, parse_args

DATA_DIR = Path(__file__).parent / "data"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

class TestParseArgs:

    def test_defaults(self):
        args = parse_args(["input.json"])
        assert args.input == ["input.json"]
        assert args.output == "output.ocel.json"
        assert args.call_types == ["CALL", "STATICCALL", "DELEGATECALL", "CREATE"]
        assert args.include_reverted is False
        assert args.include_metadata is False
        assert args.stats is False
        assert args.verbose is False

    def test_output_flag(self):
        args = parse_args(["input.json", "-o", "my_output.json"])
        assert args.output == "my_output.json"

    def test_multiple_inputs(self):
        args = parse_args(["a.json", "b.json", "c.json"])
        assert args.input == ["a.json", "b.json", "c.json"]

    def test_call_types_flag(self):
        args = parse_args(["input.json", "--call-types", "CALL", "STATICCALL"])
        assert args.call_types == ["CALL", "STATICCALL"]

    def test_all_flags(self):
        args = parse_args([
            "input.json",
            "-o", "out.json",
            "--include-reverted",
            "--include-metadata",
            "--stats",
            "--verbose",
        ])
        assert args.include_reverted is True
        assert args.include_metadata is True
        assert args.stats is True
        assert args.verbose is True


# ---------------------------------------------------------------------------
# End-to-end CLI execution
# ---------------------------------------------------------------------------

class TestMainExecution:

    def test_single_file(self, tmp_path):
        out = tmp_path / "result.json"
        main([str(DATA_DIR / "swap_1.json"), "-o", str(out)])

        assert out.exists()
        ocel = json.loads(out.read_text())
        assert "events" in ocel
        assert "objects" in ocel
        assert len(ocel["events"]) == 2
        assert len(ocel["objects"]) == 8

    def test_multiple_files(self, tmp_path):
        out = tmp_path / "result.json"
        main([
            str(DATA_DIR / "swap_1.json"),
            str(DATA_DIR / "swap_root_only.json"),
            "-o", str(out),
        ])

        ocel = json.loads(out.read_text())
        # swap_1: 2 events + swap_root_only: 1 event = 3
        assert len(ocel["events"]) == 3

    def test_directory_input(self, tmp_path):
        """Loading a directory processes all JSON files in it."""
        # Create a temp dir with a single test file
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        import shutil
        shutil.copy(DATA_DIR / "swap_root_only.json", input_dir / "swap_root_only.json")

        out = tmp_path / "result.json"
        main([str(input_dir), "-o", str(out)])

        ocel = json.loads(out.read_text())
        assert len(ocel["events"]) == 1

    def test_output_is_valid_ocel(self, tmp_path):
        """Output validates against the OCEL 2.0 JSON schema."""
        import jsonschema

        schema_path = Path(__file__).parent / "schemas" / "ocel20-schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        out = tmp_path / "result.json"
        main([str(DATA_DIR / "swap_3.json"), "-o", str(out)])

        ocel = json.loads(out.read_text())
        jsonschema.validate(instance=ocel, schema=schema)

    def test_verbose_flag(self, tmp_path):
        out = tmp_path / "result.json"
        # Should not raise
        main([str(DATA_DIR / "swap_1.json"), "-o", str(out), "--verbose"])
        assert out.exists()

    def test_stats_flag(self, tmp_path, capsys):
        out = tmp_path / "result.json"
        main([str(DATA_DIR / "swap_1.json"), "-o", str(out), "--stats"])

        captured = capsys.readouterr()
        assert "Statistics" in captured.err
        assert "Events generated" in captured.err

    def test_missing_input_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent_file.json"])
        assert exc_info.value.code == 1

    def test_swap_3_event_count(self, tmp_path):
        out = tmp_path / "result.json"
        main([str(DATA_DIR / "swap_3.json"), "-o", str(out)])

        ocel = json.loads(out.read_text())
        assert len(ocel["events"]) == 8
        assert len(ocel["objects"]) == 22
