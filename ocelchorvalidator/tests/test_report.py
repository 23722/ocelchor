"""Tests for ocelchorvalidator.report."""

from __future__ import annotations

from ocelchorvalidator.constraints import ConstraintResult, Violation, validate_all
from ocelchorvalidator.index import build_index
from ocelchorvalidator.report import (
    format_constraint_details,
    format_csv,
    format_latex,
    format_table,
    format_violations,
)
from ocelchorvalidator.stats import LogStats, compute_stats


def _make_stats(swap1_ocel: dict) -> LogStats:
    idx = build_index(swap1_ocel)
    return compute_stats("swap_1_ocel.json", swap1_ocel, idx, validate_all(idx))


# ---------------------------------------------------------------------------
# format_table
# ---------------------------------------------------------------------------


class TestFormatTable:

    def test_contains_header(self, swap1_ocel: dict) -> None:
        out = format_table([_make_stats(swap1_ocel)])
        assert "Dataset" in out
        assert "#vars" in out
        assert "#E2O" in out
        assert "#O2O" in out
        assert "#E2O[m]" in out
        assert "#E2O[cb]" in out
        assert "#O2O[c]" in out
        assert "C0" in out
        assert "C15" in out

    def test_contains_data_row(self, swap1_ocel: dict) -> None:
        out = format_table([_make_stats(swap1_ocel)])
        assert "swap_1_ocel.json" in out

    def test_empty_list(self) -> None:
        assert "No datasets" in format_table([])

    def test_pass_status(self, swap1_ocel: dict) -> None:
        out = format_table([_make_stats(swap1_ocel)])
        assert "0/" in out
        assert "ok" not in out


# ---------------------------------------------------------------------------
# format_csv
# ---------------------------------------------------------------------------


class TestFormatCSV:

    def test_header_row(self, swap1_ocel: dict) -> None:
        out = format_csv([_make_stats(swap1_ocel)])
        lines = out.strip().split("\n")
        header = lines[0]
        assert "file_name" in header
        assert "num_vars" in header
        assert "num_e2o" in header
        assert "num_o2o" in header
        assert "num_e2o_m" in header
        assert "num_e2o_cb" in header
        assert "num_o2o_c" in header
        assert "C0" in header
        assert "C15" in header

    def test_data_row(self, swap1_ocel: dict) -> None:
        out = format_csv([_make_stats(swap1_ocel)])
        lines = out.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "swap_1_ocel.json" in lines[1]
        assert "0/" in lines[1]

    def test_multiple_rows(self, swap1_ocel: dict, swap_root_only_ocel: dict) -> None:
        idx1 = build_index(swap1_ocel)
        idx2 = build_index(swap_root_only_ocel)
        stats = [
            compute_stats("swap_1", swap1_ocel, idx1, validate_all(idx1)),
            compute_stats("root_only", swap_root_only_ocel, idx2, validate_all(idx2)),
        ]
        out = format_csv(stats)
        lines = out.strip().split("\n")
        assert len(lines) == 3


# ---------------------------------------------------------------------------
# format_latex
# ---------------------------------------------------------------------------


class TestFormatLatex:

    def test_tabular_environment(self, swap1_ocel: dict) -> None:
        out = format_latex([_make_stats(swap1_ocel)])
        assert "\\begin{tabular}" in out
        assert "\\end{tabular}" in out

    def test_checkmark_for_pass(self, swap1_ocel: dict) -> None:
        out = format_latex([_make_stats(swap1_ocel)])
        assert "0/" in out
        assert "\\checkmark" not in out

    def test_times_for_fail(self) -> None:
        results = {f"C{i}": ConstraintResult(f"C{i}", 1) for i in range(16)}
        results["C0"] = ConstraintResult("C0", 1, [Violation("C0", "bad", "e1")])
        stats = LogStats("test", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, results)
        out = format_latex([stats])
        assert "1/" in out   # C0 has 1 violation
        assert "0/" in out   # other constraints have 0 violations

    def test_toprule_midrule(self, swap1_ocel: dict) -> None:
        out = format_latex([_make_stats(swap1_ocel)])
        assert "\\toprule" in out
        assert "\\midrule" in out
        assert "\\bottomrule" in out

    def test_underscore_escaped(self, swap1_ocel: dict) -> None:
        out = format_latex([_make_stats(swap1_ocel)])
        assert "swap\\_1\\_ocel.json" in out


# ---------------------------------------------------------------------------
# format_constraint_details
# ---------------------------------------------------------------------------


class TestFormatConstraintDetails:

    def test_all_constraints_listed(self, swap1_ocel: dict) -> None:
        out = format_constraint_details([_make_stats(swap1_ocel)])
        for i in range(16):
            assert f"C{i}:" in out

    def test_shows_elements_checked(self, swap1_ocel: dict) -> None:
        out = format_constraint_details([_make_stats(swap1_ocel)])
        assert "elements checked" in out

    def test_shows_pass(self, swap1_ocel: dict) -> None:
        out = format_constraint_details([_make_stats(swap1_ocel)])
        assert "0 violations (pass)" in out

    def test_empty_list(self) -> None:
        assert "No datasets" in format_constraint_details([])


# ---------------------------------------------------------------------------
# format_violations
# ---------------------------------------------------------------------------


class TestFormatViolations:

    def test_empty(self) -> None:
        assert format_violations([]) == ""

    def test_single_violation(self) -> None:
        v = Violation("C0", "Event has 0 instances", "e1")
        out = format_violations([v])
        assert "[C0]" in out
        assert "event=e1" in out

    def test_with_object_id(self) -> None:
        v = Violation("C5", "No source", "e1", "msg1")
        out = format_violations([v])
        assert "object=msg1" in out

    def test_multiple_violations(self) -> None:
        vs = [
            Violation("C0", "bad1", "e1"),
            Violation("C2", "bad2", "e2"),
        ]
        out = format_violations(vs)
        assert "[C0]" in out
        assert "[C2]" in out
        lines = out.strip().split("\n")
        assert len(lines) == 2
