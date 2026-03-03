"""CLI entry point for trace2choreo."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from trace2choreo.ocel import build_ocel, write_ocel
from trace2choreo.parser import load_trace_dir, load_trace_file
from trace2choreo.stats import collect_stats, print_stats
from trace2choreo.transformer import transform_traces


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="trace2ocelchor",
        description="Convert Ethereum transaction traces to OCEL 2.0 choreography event logs.",
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="Input JSON file(s) or directory",
    )
    parser.add_argument(
        "-o", "--output",
        default="output.ocel.json",
        help="Output OCEL 2.0 JSON file path (default: output.ocel.json)",
    )
    parser.add_argument(
        "--call-types",
        nargs="+",
        default=["CALL", "STATICCALL", "DELEGATECALL", "CREATE"],
        help="Call frame types to include (default: all)",
    )
    parser.add_argument(
        "--include-reverted",
        action="store_true",
        default=False,
        help="Include reverted/failed call frames",
    )
    parser.add_argument(
        "--include-metadata",
        action="store_true",
        default=False,
        help="Store gasUsed, value, callId, depth, blockNumber as event attributes",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Print summary statistics after conversion",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Main entry point."""
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Load traces from all inputs
    traces = []
    for input_path in args.input:
        p = Path(input_path)
        if not p.exists():
            logging.error("Input path does not exist: %s", p)
            sys.exit(1)
        if p.is_dir():
            traces.extend(load_trace_dir(p))
        else:
            traces.extend(load_trace_file(p))

    if not traces:
        logging.error("No traces loaded from input")
        sys.exit(1)

    logging.info("Loaded %d trace(s)", len(traces))

    # Transform
    events, objects = transform_traces(
        traces,
        call_types=set(args.call_types),
        include_reverted=args.include_reverted,
        include_metadata=args.include_metadata,
    )

    logging.info("Generated %d events, %d objects", len(events), len(objects))

    # Serialize and write
    ocel = build_ocel(events, objects)
    output_path = Path(args.output)
    write_ocel(ocel, output_path)

    print(f"Wrote {len(events)} events, {len(objects)} objects to {output_path}", file=sys.stderr)

    # Stats
    if args.stats:
        stats = collect_stats(traces, events, objects)
        print_stats(stats)
