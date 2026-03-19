# ocelchorvalidator

Validates OCEL 2.0 choreography logs against the 17 formal constraints (C0–C16) defined in:

> "Representing BPMN Choreographies in OCEL 2.0" (Section 4.3)

The validator checks structural and syntactical correctness of choreography logs and produces evaluation statistics — including dataset characterization metrics and per-constraint non-vacuity counts — suitable for inclusion in the paper's evaluation section.

## Requirements

- Python ≥ 3.10
- [uv](https://github.com/astral-sh/uv)
- Zero production dependencies

## Installation

```bash
uv sync --extra dev
```

## Usage

```bash
# Validate one or more OCEL 2.0 JSON files (human-readable table)
uv run ocelchorvalidator data/input/mylog.ocel.json

# Multiple files
uv run ocelchorvalidator data/input/*.json

# With individual violation details
uv run ocelchorvalidator data/input/*.json --verbose

# CSV output (for spreadsheet / pandas analysis)
uv run ocelchorvalidator data/input/*.json --csv -o results.csv

# LaTeX tabular (for paper inclusion)
uv run ocelchorvalidator data/input/*.json --latex -o table.tex

# Check a subset of constraints only
uv run ocelchorvalidator data/input/mylog.ocel.json --constraints C0,C1,C4
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All constraints pass |
| 1 | At least one violation found |
| 2 | Input error (file not found, invalid JSON, missing OCEL keys) |

## Output table columns

| Column | Description |
|--------|-------------|
| `#vars` | Distinct choreography instances (`choreo:instance` values) |
| `#e` | Total events |
| `#m` | Distinct message objects (`choreo:message`) |
| `#parts` | Distinct participant objects (`choreo:initiator` or `choreo:participant`) |
| `#scoping` | Distinct Subchoreography scoping objects |
| `#E2O` | Total event-to-object relations |
| `#O2O` | Total object-to-object relations |
| `#E2O[m]` | E2O relations with qualifier `choreo:message` (1–2 per event) |
| `#E2O[cb]` | E2O relations with qualifier `choreo:contained-by` |
| `#O2O[c]` | O2O relations with qualifier `choreo:contains` (nesting) |
| `C0`–`C16` | Per-constraint result: `violations/checked` |

## Constraints

### Content constraints (C0–C10)

| ID | Name | Checks |
|----|------|--------|
| C0 | Instance linking | Each event links to exactly one choreography instance |
| C1 | Message participation | Message source/target are participants of the same event |
| C2 | Single initiator | Each event has exactly one `choreo:initiator` |
| C3 | Single participant | Each event has exactly one `choreo:participant` |
| C4 | Role exclusivity | No object is both initiator and participant of the same event |
| C5 | Message source uniqueness | Each message object has exactly one `choreo:source` |
| C6 | Message target uniqueness | Each message object has exactly one `choreo:target` |
| C7 | Initiating message | Each event has exactly one message sent by the initiator |
| C8 | At most one return message | Each event has at most one message sent by the participant |
| C9 | Initiating message target | The initiating message is received by the participant |
| C10 | Return message target | The return message is received by the initiator |

### Subchoreography constraints (C11–C16)

| ID | Name | Checks |
|----|------|--------|
| C11 | Containment uniqueness | Each event is contained in at most one scoping object |
| C12 | Non-empty scope | Each scoping object contains at least one event |
| C13 | Instance consistency | All events transitively enclosed by a scope (`allevents`) link to the same choreography instance |
| C14 | Nesting structure | Scoping hierarchy has unique parents and is acyclic (DAG) |
| C15 | Initiator continuity | The initiator of each choreography task was involved (as initiator or participant) in the previous task within the same instance |
| C16 | Scope re-entry | Once an instance's sequence flow has left a sub-choreography scope, it cannot re-enter that scope |

## Package structure

```
src/ocelchorvalidator/
├── reader.py       # OCEL 2.0 JSON loader with validation
├── index.py        # Pre-computed lookup indexes (events, objects, E2O, O2O)
├── constraints.py  # C0–C16 constraint checks
├── stats.py        # Dataset characterization + constraint result aggregation
├── report.py       # Output formatting (table, CSV, LaTeX)
└── cli.py          # argparse CLI entry point
```

## Running tests

```bash
uv run python -m pytest
```

---

## GenAI assistance disclosure

The implementation of this repository was developed in collaboration with
[Claude Code](https://claude.ai/code) (Anthropic).
