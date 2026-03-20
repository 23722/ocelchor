"""CLI entry point for ocelchormodel."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ocelchormodel.bpmn import generate_bpmn, write_bpmn
from ocelchormodel.extractor import extract_instance, list_instances
from ocelchormodel.layout import compute_layout
from ocelchormodel.reader import read_ocel

log = logging.getLogger(__name__)


def _stem(path: Path) -> str:
    """Derive the output subdirectory name from an input filename.

    Strips the ``_ocel.json`` suffix if present, otherwise uses the full stem.
    """
    name = path.name
    if name.endswith("_ocel.json"):
        return name[: -len("_ocel.json")]
    return path.stem


def _tx_hash(instance_id: str) -> str:
    """Extract the transaction hash from a choreography instance ID.

    ``choreographyInstance:0xabcd...`` → ``0xabcd...``
    """
    prefix = "choreographyInstance:"
    if instance_id.startswith(prefix):
        return instance_id[len(prefix):]
    return instance_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="ocelchormodel",
        description=(
            "Generate BPMN 2.0 choreography models from OCEL 2.0 event logs "
            "produced by trace2choreo."
        ),
    )
    parser.add_argument(
        "input",
        nargs="+",
        help="One or more OCEL 2.0 JSON files produced by trace2choreo",
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        default=False,
        help="Print all choreography instance IDs and exit",
    )
    parser.add_argument(
        "--order-by",
        choices=["timestamp", "trace_order"],
        default="timestamp",
        dest="order_by",
        help="Event ordering: timestamp (default) or trace_order",
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

    input_paths = [Path(p) for p in args.input]
    output_dir = Path(args.output)

    # Validate input files exist
    for p in input_paths:
        if not p.exists():
            print(f"Error: input file not found: {p}", file=sys.stderr)
            sys.exit(1)

    # --list mode: print instances grouped by file and exit
    if args.list:
        for input_path in input_paths:
            try:
                ocel = read_ocel(input_path)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            instances = list_instances(ocel)
            print(f"{input_path.name}: {len(instances)} instance(s)")
            for i, (oid, short) in enumerate(instances):
                print(f"  [{i}] {oid}  (short: {short})")
        sys.exit(0)

    # Batch processing
    total = 0
    failed = 0
    for input_path in input_paths:
        try:
            ocel = read_ocel(input_path)
        except ValueError as e:
            log.warning("Skipping %s: %s", input_path.name, e)
            failed += 1
            continue

        instances = list_instances(ocel)
        if not instances:
            log.warning("No instances in %s, skipping.", input_path.name)
            continue

        subdir = output_dir / _stem(input_path)
        subdir.mkdir(parents=True, exist_ok=True)

        for inst_id, short_id in instances:
            try:
                instance = extract_instance(ocel, inst_id, order_by=args.order_by)
                layout = compute_layout(instance)
                xml_str = generate_bpmn(instance, layout)

                bpmn_path = subdir / f"{_tx_hash(inst_id)}.bpmn"
                write_bpmn(xml_str, bpmn_path)
                total += 1
                print(f"  {bpmn_path}", file=sys.stderr)
            except Exception as e:
                log.warning("Failed instance %s in %s: %s", short_id, input_path.name, e)
                failed += 1

    print(f"Done: {total} BPMN files written, {failed} failed.", file=sys.stderr)
