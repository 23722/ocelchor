"""Command-line interface for the ocelchormodel-rad miner (spec M4).

Validator-style: positional OCEL 2.0 inputs, one output folder per log. Per
input the miner loads (hard gates C0/C2/C3/C11/C12/C14 — a violating log is
reported and skipped, the remaining inputs still run; C3 is gated by shape:
missing receivers are tolerated with the reserved empty role, multicast
aborts), discovers, and writes

    <out-dir>/<stem>/discovered_model.bpmn   BPMN 2.0 choreography + DI
    <out-dir>/<stem>/process_tree.txt        choreography-tree s-expression
    <out-dir>/<stem>/diagnostics.json        D1-D13 (spec B8)
    <out-dir>/<stem>/WARNINGS.txt            only when C3 missing-receiver
                                             events were tolerated

A refused log leaves <out-dir>/<stem>/REFUSED.txt (and nothing else) naming
the violated gate, so the artifact explains its own gaps.

No tuning flags by design: discovery is deterministic and diagnostics never
change the model (run configuration, spec section B0).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ocelchormodel_rad import __version__, reader
from ocelchormodel_rad.diagnostics import compute_diagnostics
from ocelchormodel_rad.discover import discover
from ocelchormodel_rad.export_bpmn import to_bpmn, tree_sexpr
from ocelchormodel_rad.reader import ContractViolation


def _stem(path: Path) -> str:
    """`x_ocel.json` -> `x` (matching the established output layout)."""
    if path.name.endswith("_ocel.json"):
        return path.name[: -len("_ocel.json")]
    return path.stem


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ocelchormodel-rad",
        description=(
            "Discover a hierarchical BPMN choreography model from an "
            "OCEL 2.0 choreography log."
        ),
    )
    parser.add_argument("input", nargs="+", help="OCEL 2.0 JSON file(s)")
    parser.add_argument(
        "-o", "--out-dir", default="output",
        help="Output directory; one subfolder per input log (default: output)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    out_root = Path(args.out_dir)
    failed = False

    for file_path in args.input:
        path = Path(file_path)
        try:
            model = reader.load(path)
        except ContractViolation as exc:
            print(f"SKIP {path.name}: {exc}", file=sys.stderr)
            # The refused log leaves an output directory holding only a
            # refusal note, so the artifact explains its own gap.
            out = out_root / _stem(path)
            out.mkdir(parents=True, exist_ok=True)
            (out / "REFUSED.txt").write_text(
                f"{_stem(path)}: no model discovered.\n\n{exc}\n",
                encoding="utf-8")
            failed = True
            continue
        except (OSError, ValueError) as exc:
            print(f"ERROR {path.name}: {exc}", file=sys.stderr)
            failed = True
            continue

        d = discover(model)
        out = out_root / _stem(path)
        out.mkdir(parents=True, exist_ok=True)
        (out / "discovered_model.bpmn").write_text(
            to_bpmn(d.tree, d.side_index), encoding="utf-8")
        (out / "process_tree.txt").write_text(
            tree_sexpr(d.tree) + "\n", encoding="utf-8")
        diag = compute_diagnostics(model, d, _stem(path))
        (out / "diagnostics.json").write_text(
            json.dumps(diag, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        if model.missing_receiver_events:
            ids = "\n".join(f"  {eid}" for eid in model.missing_receiver_events)
            print(
                f"WARN {path.name}: {len(model.missing_receiver_events)} "
                "event(s) with unrecorded receiver (C3) — typed with the "
                "reserved empty role", file=sys.stderr)
            (out / "WARNINGS.txt").write_text(
                f"{_stem(path)}: model discovered despite C3 violations.\n\n"
                f"{len(model.missing_receiver_events)} event(s) have no "
                "recorded receiver (choreo:participant edge missing). Each is "
                "typed with the reserved empty participant role and appears "
                "as an empty band in the model — reported, not repaired; see "
                "the constraints section of diagnostics.json.\n\nEvents:\n"
                f"{ids}\n",
                encoding="utf-8")

        print(
            f"OK {path.name}: {len(model.events)} events, "
            f"{len(model.scopes)} scopes, "
            f"{len(d.recursion)} recursion finding(s), "
            f"{len(d.and_nodes)} parallel node(s) -> {out}"
        )

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
