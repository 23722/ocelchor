"""Unified CLI dispatcher for the ocelchor pipeline.

Subcommands
-----------
  convert   Convert Ethereum transaction traces to OCEL 2.0 (trace2ocelchor)
  validate  Validate an OCEL 2.0 log against constraints C0-C15 (ocelchorvalidator)
  mine      Mine BPMN choreography models from an OCEL 2.0 log (ocelchormodel)
"""

from __future__ import annotations

import sys


USAGE = """\
usage: ocelchor <command> [options]

Commands:
  convert   Convert Ethereum transaction traces to OCEL 2.0
  validate  Validate an OCEL 2.0 log against constraints C0-C15
  mine      Mine BPMN choreography models from an OCEL 2.0 log

Run 'ocelchor <command> --help' for command-specific options.
"""

COMMANDS = ("convert", "validate", "mine")


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(USAGE, end="")
        sys.exit(0)

    command, rest = args[0], args[1:]

    if command == "convert":
        from trace2choreo.cli import main as _main
        _main(rest)

    elif command == "validate":
        from ocelchorvalidator.cli import main as _main
        _main(rest)

    elif command == "mine":
        from ocelchormodel.cli import main as _main
        _main(rest)

    else:
        print(f"ocelchor: unknown command '{command}'\n", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        sys.exit(1)
