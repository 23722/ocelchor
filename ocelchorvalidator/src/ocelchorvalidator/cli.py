"""Command-line interface for ocelchorvalidator."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ocelchorvalidator.constraints import validate, validate_all
from ocelchorvalidator.index import build_index
from ocelchorvalidator.reader import read_ocel
from ocelchorvalidator.report import (
    format_constraint_details,
    format_csv,
    format_latex,
    format_table,
    format_violations,
)
from ocelchorvalidator.stats import compute_stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocelchorvalidator",
        description="Validate OCEL 2.0 choreography logs against constraints C0\u2013C15.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="OCEL 2.0 JSON file(s)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Write output to file (default: stdout)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output in CSV format",
    )
    parser.add_argument(
        "--latex",
        action="store_true",
        help="Output in LaTeX tabular format",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show individual violation details",
    )
    parser.add_argument(
        "--constraints",
        help="Comma-separated constraint IDs to check (default: all)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Parse constraint filter
    constraint_ids: list[str] | None = None
    if args.constraints:
        constraint_ids = [c.strip() for c in args.constraints.split(",")]

    # Process each input file
    all_stats = []
    all_violations = []
    for file_path in args.input:
        path = Path(file_path)
        try:
            ocel = read_ocel(path)
        except ValueError as exc:
            print(f"Error: {path}: {exc}", file=sys.stderr)
            sys.exit(2)

        idx = build_index(ocel)
        if constraint_ids:
            results = validate(idx, constraint_ids)
        else:
            results = validate_all(idx)

        stats = compute_stats(path.name, ocel, idx, results)
        all_stats.append(stats)

        for r in results.values():
            all_violations.extend(r.violations)

    # Format output
    if args.csv:
        output = format_csv(all_stats)
    elif args.latex:
        output = format_latex(all_stats)
    else:
        output = format_table(all_stats)

    if args.verbose:
        output += "\n" + format_constraint_details(all_stats)
        violation_text = format_violations(all_violations)
        if violation_text:
            output += "\n" + violation_text

    # Write output
    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output, end="")

    # Exit code
    sys.exit(1 if all_violations else 0)
