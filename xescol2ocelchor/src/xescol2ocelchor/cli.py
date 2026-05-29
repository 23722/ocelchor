"""CLI entry point for xescol2ocelchor.

Usage::

    uv run xescol2ocelchor <input.xes> [<input.xes> ...] -o DIR [options]

For each input XES file, writes one OCEL 2.0 JSON file named
``<dataset>_ocel.json`` into the output directory (the ``collectivelog_``
prefix and ``.xes`` suffix are stripped from the dataset name).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from xescol2ocelchor.crosscheck import crosscheck, discover_collab_pair
from xescol2ocelchor.extractor import ExtractionStats, extract
from xescol2ocelchor.ocel import build_ocel, write_ocel
from xescol2ocelchor.reader import load_xes


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xescol2ocelchor",
        description=(
            "Convert XES collaborative event logs to OCEL 2.0 choreography "
            "event logs (Peña et al. → OCEL 2.0 per the BPM 2026 paper mapping)."
        ),
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="XES input file(s)",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Output directory for generated OCEL 2.0 JSON files",
    )
    parser.add_argument(
        "--keep-internal-events",
        action="store_true",
        help="Keep internal (non-message) XES events (default: drop)",
    )
    parser.add_argument(
        "--crosscheck",
        action="store_true",
        help=(
            "After conversion, compare reconstruction with the sibling "
            "<name>_collab.xes file (per spec §6). Reports agreement percentage."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    for input_path in args.input:
        in_path = Path(input_path)
        if not in_path.exists():
            print(f"Error: input not found: {in_path}", file=sys.stderr)
            sys.exit(2)
        if not in_path.is_file():
            print(f"Error: not a file: {in_path}", file=sys.stderr)
            sys.exit(2)

        dataset = _dataset_name(in_path)
        out_path = output_dir / f"{dataset}_ocel.json"

        traces = load_xes(in_path)
        events, objects, stats = extract(
            traces, keep_internal_events=args.keep_internal_events,
        )
        ocel = build_ocel(events, objects)
        write_ocel(ocel, out_path)
        _print_summary(in_path, out_path, stats)

        if args.crosscheck:
            _run_crosscheck(in_path)


def _run_crosscheck(plain_path: Path) -> None:
    collab = discover_collab_pair(plain_path)
    out = sys.stderr
    if collab is None:
        out.write(f"  crosscheck: no {plain_path.stem}_collab.xes found, skipping\n")
        return
    result = crosscheck(plain_path, collab)
    out.write(
        f"  crosscheck vs {collab.name}: {result.agreement_pct:.1f}% "
        f"({result.messages_agreeing}/{result.messages_compared})"
    )
    if result.only_in_plain or result.only_in_collab:
        out.write(
            f", only-in-plain={len(result.only_in_plain)}, "
            f"only-in-collab={len(result.only_in_collab)}"
        )
    out.write("\n")


def _dataset_name(path: Path) -> str:
    """Derive the dataset name from a ``collectivelog_<name>.xes`` filename."""
    name = path.stem
    if name.startswith("collectivelog_"):
        name = name[len("collectivelog_"):]
    return name


def _print_summary(in_path: Path, out_path: Path, stats: ExtractionStats) -> None:
    out = sys.stderr
    out.write(f"{in_path.name} → {out_path}\n")
    internal = f"{stats.internal_events_dropped} internal dropped"
    if stats.internal_events_kept:
        internal += f", {stats.internal_events_kept} internal kept"
    out.write(
        f"  {stats.traces} traces, {stats.task_events} tasks, "
        f"{stats.message_objects} messages, "
        f"{stats.participant_objects} participants, "
        f"{internal}\n"
    )
    if stats.unmatched_msg_ids or stats.broadcast_msg_ids:
        out.write(
            f"  flags (msg-id level): {stats.unmatched_msg_ids} unmatched, "
            f"{stats.broadcast_msg_ids} broadcast\n"
        )
