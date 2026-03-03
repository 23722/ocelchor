# Test Plan: Stats + Report

## stats.py — LogStats + compute_stats

### LogStats fields (swap_1)

| Field | Expected |
|-------|----------|
| file_name | "swap_1_ocel.json" |
| num_vars | 1 |
| num_events | 2 |
| num_messages | 3 |
| num_scoping_objects | 1 |
| num_participants | 3 |

### Derived properties

- `constraints_all_passed`: True when all constraint results pass
- `violated_constraints`: List of constraint IDs that failed
- `total_elements_checked`: Sum of `elements_checked` across all constraints

### swap_root_only verification

- num_vars=1, num_events=1, num_messages=1, num_scoping_objects=0, num_participants=2

### Edge case: empty log

- All counts are 0

---

## report.py — Output Formatting

### format_table

- Returns a human-readable table string
- Contains header row and one data row per LogStats
- Contains column headers: Dataset, #vars, #e, #m, #scoping, #parts, Checked, C0–C15

### format_csv

- Valid CSV with header row
- Columns: file_name, num_vars, num_events, num_messages, num_scoping_objects, num_participants, total_checked, C0–C15 (pass/fail)

### format_latex

- Produces LaTeX tabular environment
- Contains `\begin{tabular}` and `\end{tabular}`
- Uses `\checkmark` for pass and `$\times$` for fail
- One row per dataset

### format_constraint_details

- Per-constraint summary across all logs
- Shows constraint ID, total elements checked, total violations

### format_violations

- Shows individual violation details
- Includes constraint ID, message, event/object IDs
- Returns empty string when no violations
