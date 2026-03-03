# Test Plan: CLI + Integration

## cli.py — Command-Line Interface

### Argument parsing

- **Single file**: `ocelchorvalidator swap_1_ocel.json` → processes 1 file
- **Multiple files**: `ocelchorvalidator swap_1_ocel.json swap_3_ocel.json` → processes 2 files
- **No files**: exits with code 2 (argparse error)
- **Non-existent file**: exits with code 2 and error message on stderr

### Output format flags (mutually exclusive with default)

- **Default (no flag)**: human-readable table via `format_table`
- **`--csv`**: CSV output via `format_csv`
- **`--latex`**: LaTeX tabular via `format_latex`
- **`--verbose`**: includes constraint details + individual violations after the table

### Output destination

- **Default**: prints to stdout
- **`-o results.txt`**: writes output to file instead of stdout

### Constraint filtering

- **`--constraints C0,C1,C2`**: only check specified constraints
- **Default (no flag)**: check all C0–C15

### Exit codes

- **0**: all constraints pass across all input files
- **1**: at least one violation found
- **2**: input error (bad file, missing file, invalid JSON)

### Verbose mode details

- Shows per-file constraint details via `format_constraint_details`
- Shows individual violations via `format_violations`

---

## End-to-end integration

### All test data files pass

Run CLI on each of the 6 test data files:
- `swap_1_ocel.json` → exit 0
- `swap_2_ocel.json` → exit 0
- `swap_3_ocel.json` → exit 0
- `swap_root_only_ocel.json` → exit 0
- `swap_multi_tx_ocel.json` → exit 0
- `0x5e_0xcd4_ocel.json` → exit 0

### All files at once

- `ocelchorvalidator swap_1_ocel.json swap_2_ocel.json ... 0x5e_0xcd4_ocel.json` → exit 0, output contains all file names

### CSV format end-to-end

- Run with `--csv` on all files → valid CSV with header + 6 data rows

### LaTeX format end-to-end

- Run with `--latex` on all files → contains `\begin{tabular}` and all 6 dataset names

### Verbose end-to-end

- Run with `--verbose` on valid files → includes "elements checked" in output
