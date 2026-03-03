"""Tests for ocelchorvalidator.cli."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocelchorvalidator.cli import main

DATA_DIR = Path(__file__).parent / "data"

ALL_FILES = [
    "swap_1_ocel.json",
    "swap_2_ocel.json",
    "swap_3_ocel.json",
    "swap_root_only_ocel.json",
    "swap_multi_tx_ocel.json",
    "0x5e_0xcd4_ocel.json",
]


# ---------------------------------------------------------------------------
# Argument parsing + exit codes
# ---------------------------------------------------------------------------


class TestExitCodes:

    def test_single_file_passes(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([str(DATA_DIR / "swap_1_ocel.json")])
        assert exc_info.value.code == 0

    def test_nonexistent_file(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([str(DATA_DIR / "nonexistent.json")])
        assert exc_info.value.code == 2

    def test_all_files_pass(self) -> None:
        args = [str(DATA_DIR / f) for f in ALL_FILES]
        with pytest.raises(SystemExit) as exc_info:
            main(args)
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Output format flags
# ---------------------------------------------------------------------------


class TestOutputFormats:

    def test_default_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main([str(DATA_DIR / "swap_1_ocel.json")])
        out = capsys.readouterr().out
        assert "Dataset" in out
        assert "swap_1_ocel.json" in out

    def test_csv_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["--csv", str(DATA_DIR / "swap_1_ocel.json")])
        out = capsys.readouterr().out
        assert "file_name" in out
        assert "swap_1_ocel.json" in out
        assert "0/" in out

    def test_latex_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["--latex", str(DATA_DIR / "swap_1_ocel.json")])
        out = capsys.readouterr().out
        assert "\\begin{tabular}" in out
        assert "0/" in out

    def test_verbose_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["--verbose", str(DATA_DIR / "swap_1_ocel.json")])
        out = capsys.readouterr().out
        assert "elements checked" in out

    def test_csv_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main(["--csv", "--verbose", str(DATA_DIR / "swap_1_ocel.json")])
        out = capsys.readouterr().out
        assert "file_name" in out
        assert "elements checked" in out


# ---------------------------------------------------------------------------
# Output to file
# ---------------------------------------------------------------------------


class TestOutputFile:

    def test_output_to_file(self, tmp_path: Path) -> None:
        out_file = tmp_path / "results.txt"
        with pytest.raises(SystemExit):
            main(["-o", str(out_file), str(DATA_DIR / "swap_1_ocel.json")])
        content = out_file.read_text()
        assert "Dataset" in content
        assert "swap_1_ocel.json" in content


# ---------------------------------------------------------------------------
# Constraint filtering
# ---------------------------------------------------------------------------


class TestConstraintFiltering:

    def test_subset_constraints(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit):
            main([
                "--constraints", "C0,C1,C2",
                "--verbose",
                str(DATA_DIR / "swap_1_ocel.json"),
            ])
        out = capsys.readouterr().out
        assert "C0:" in out
        assert "C1:" in out
        assert "C2:" in out


# ---------------------------------------------------------------------------
# End-to-end integration
# ---------------------------------------------------------------------------


class TestEndToEnd:

    @pytest.mark.parametrize("filename", ALL_FILES)
    def test_each_file_passes(self, filename: str) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main([str(DATA_DIR / filename)])
        assert exc_info.value.code == 0

    def test_all_files_csv(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = ["--csv"] + [str(DATA_DIR / f) for f in ALL_FILES]
        with pytest.raises(SystemExit):
            main(args)
        out = capsys.readouterr().out
        lines = out.strip().split("\n")
        assert len(lines) == 7  # header + 6 data rows

    def test_all_files_latex(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = ["--latex"] + [str(DATA_DIR / f) for f in ALL_FILES]
        with pytest.raises(SystemExit):
            main(args)
        out = capsys.readouterr().out
        assert "\\begin{tabular}" in out
        for f in ALL_FILES:
            # LaTeX escapes underscores
            assert f.replace("_", "\\_") in out

    def test_all_files_verbose(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = ["--verbose"] + [str(DATA_DIR / f) for f in ALL_FILES]
        with pytest.raises(SystemExit):
            main(args)
        out = capsys.readouterr().out
        assert "elements checked" in out
        for f in ALL_FILES:
            assert f in out
