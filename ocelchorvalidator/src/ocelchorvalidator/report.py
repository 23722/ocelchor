"""Output formatting — table, CSV, LaTeX, constraint details, violations."""

from __future__ import annotations

import csv
import io

from ocelchorvalidator.constraints import Violation
from ocelchorvalidator.stats import LogStats

_CONSTRAINT_IDS = [f"C{i}" for i in range(16)]


def format_table(stats_list: list[LogStats]) -> str:
    """Human-readable summary table."""
    if not stats_list:
        return "No datasets.\n"

    # Column widths
    name_w = max(len(s.file_name) for s in stats_list)
    name_w = max(name_w, 7)  # "Dataset"
    header = (
        f"{'Dataset':<{name_w}}  #vars  #e  #m  #parts  #scoping  #E2O  #O2O  #E2O[m]  #E2O[cb]  #O2O[c]  "
        + "  ".join(f"{cid:>3}" for cid in _CONSTRAINT_IDS)
    )
    sep = "-" * len(header)
    lines = [header, sep]
    for s in stats_list:
        cstatus = "  ".join(
            f"{s.constraint_results[cid].num_violations}/{s.constraint_results[cid].elements_checked}"
            for cid in _CONSTRAINT_IDS
            if cid in s.constraint_results
        )
        lines.append(
            f"{s.file_name:<{name_w}}  {s.num_vars:>5}  {s.num_events:>2}  "
            f"{s.num_messages:>2}  {s.num_participants:>6}  {s.num_scoping_objects:>8}  "
            f"{s.num_e2o:>4}  {s.num_o2o:>4}  {s.num_e2o_m:>7}  {s.num_e2o_cb:>8}  {s.num_o2o_c:>6}  "
            f"{cstatus}"
        )
    lines.append("")
    return "\n".join(lines)


def format_csv(stats_list: list[LogStats]) -> str:
    """CSV output."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = [
        "file_name", "num_vars", "num_events", "num_messages",
        "num_participants", "num_scoping_objects", "num_e2o", "num_o2o",
        "num_e2o_m", "num_e2o_cb", "num_o2o_c",
    ] + _CONSTRAINT_IDS
    writer.writerow(header)
    for s in stats_list:
        row = [
            s.file_name, s.num_vars, s.num_events, s.num_messages,
            s.num_participants, s.num_scoping_objects, s.num_e2o, s.num_o2o,
            s.num_e2o_m, s.num_e2o_cb, s.num_o2o_c,
        ]
        for cid in _CONSTRAINT_IDS:
            if cid in s.constraint_results:
                r = s.constraint_results[cid]
                row.append(f"{r.num_violations}/{r.elements_checked}")
            else:
                row.append("")
        writer.writerow(row)
    return buf.getvalue()


def format_latex(stats_list: list[LogStats]) -> str:
    """LaTeX tabular for paper inclusion (LNCS column width)."""
    ncols = 11 + len(_CONSTRAINT_IDS)  # Dataset + 10 stats + C0..C15
    col_spec = "l" + "r" * 10 + "r" * len(_CONSTRAINT_IDS)
    lines = [
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule",
        "Dataset & \\#vars & \\#e & \\#m & \\#parts & \\#scoping & \\#E2O & \\#O2O"
        " & \\#E2O[m] & \\#E2O[cb] & \\#O2O[c] & "
        + " & ".join(_CONSTRAINT_IDS) + " \\\\",
        "\\midrule",
    ]
    for s in stats_list:
        cells = [
            s.file_name.replace("_", "\\_"),
            str(s.num_vars),
            str(s.num_events),
            str(s.num_messages),
            str(s.num_participants),
            str(s.num_scoping_objects),
            str(s.num_e2o),
            str(s.num_o2o),
            str(s.num_e2o_m),
            str(s.num_e2o_cb),
            str(s.num_o2o_c),
        ]
        for cid in _CONSTRAINT_IDS:
            if cid in s.constraint_results:
                r = s.constraint_results[cid]
                cells.append(f"{r.num_violations}/{r.elements_checked}")
            else:
                cells.append("")
        lines.append(" & ".join(cells) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    return "\n".join(lines)


def format_constraint_details(stats_list: list[LogStats]) -> str:
    """Per-constraint element counts across all logs."""
    if not stats_list:
        return "No datasets.\n"

    lines: list[str] = []
    for cid in _CONSTRAINT_IDS:
        total_checked = 0
        total_violations = 0
        for s in stats_list:
            if cid in s.constraint_results:
                total_checked += s.constraint_results[cid].elements_checked
                total_violations += s.constraint_results[cid].num_violations
        status = "FAIL" if total_violations > 0 else "pass"
        lines.append(
            f"{cid}: {total_checked} elements checked, "
            f"{total_violations} violations ({status})"
        )
    return "\n".join(lines) + "\n"


def format_violations(violations: list[Violation]) -> str:
    """Verbose individual violation details."""
    if not violations:
        return ""
    lines: list[str] = []
    for v in violations:
        parts = [f"[{v.constraint}] {v.message}"]
        if v.event_id:
            parts.append(f"event={v.event_id}")
        if v.object_id:
            parts.append(f"object={v.object_id}")
        lines.append("  ".join(parts))
    return "\n".join(lines) + "\n"
