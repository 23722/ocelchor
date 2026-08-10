# ocelchorvalidator

Validates OCEL 2.0 choreography logs against the 17 formal constraints
(C0–C16) defined in *Representing BPMN Choreographies in OCEL 2.0*
(Section 4.3). Domain-independent: consumes the OCEL output of either
`trace2ocelchor` (blockchain) or `xescol2ocelchor` (XES) without
modification.

Produces a per-dataset characterisation table and per-constraint
`violations / checked` counts, with CSV and LaTeX output modes for
paper inclusion.

For repository-wide context (pipeline diagram, evaluation results, unified
CLI), see the [root README](../README.md).

---

## Requirements + Installation

Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/). Zero production
dependencies; dev extras pull in the test toolchain:

```bash
cd ocelchorvalidator
uv sync --extra dev
```

---

## Usage

```bash
# Validate one or more OCEL 2.0 JSON files (human-readable table)
uv run ocelchorvalidator data/input/mylog.ocel.json
uv run ocelchorvalidator data/input/*.json

# With individual violation details
uv run ocelchorvalidator data/input/*.json --verbose

# CSV for spreadsheet / pandas analysis
uv run ocelchorvalidator data/input/*.json --csv -o results.csv

# LaTeX tabular for paper inclusion
uv run ocelchorvalidator data/input/*.json --latex -o table.tex

# Check a subset of constraints only
uv run ocelchorvalidator data/input/mylog.ocel.json --constraints C0,C1,C4
```

Exit codes: **0** all constraints pass; **1** at least one violation;
**2** input error (file not found, invalid JSON, missing OCEL keys).

---

## Input format

OCEL 2.0 JSON files conforming to the official schema, encoding
choreography semantics via qualified relationships
(`choreo:instance`, `choreo:initiator`, `choreo:participant`,
`choreo:message`, `choreo:source`, `choreo:target`, `choreo:contained-by`,
`choreo:contains`). See either upstream extractor's README for how those
qualifiers are produced.

---

## Output format

Per-dataset characterisation columns:

| Column | Description |
|--------|-------------|
| `#vars` | Distinct choreography instances (`choreo:instance` values) |
| `#e` | Total events |
| `#m` | Distinct message objects (`choreo:message`) |
| `#parts` | Distinct participant objects (`choreo:initiator` or `choreo:participant`) |
| `#scoping` | Distinct sub-choreography scoping objects |
| `#E2O` | Total event-to-object relations |
| `#O2O` | Total object-to-object relations |
| `#E2O[m]` | E2O relations with qualifier `choreo:message` (1–2 per event) |
| `#E2O[cb]` | E2O relations with qualifier `choreo:contained-by` |
| `#O2O[c]` | O2O relations with qualifier `choreo:contains` (nesting) |
| `C0`–`C16` | Per-constraint result: `violations / checked` |

`checked` is the population the constraint quantifies over: events for the
per-event constraints (C0, C2–C4, C7, C8, C11), event–message pairs for the
message constraints (C1, C5, C6, C9, C10), consecutive event pairs for C15,
and scoping objects for C12–C14, C16. Vacuously satisfied cases count as
checked, and an event violating several constraints is reported by each of
them.

---

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

### Sub-choreography constraints (C11–C16)

| ID | Name | Checks |
|----|------|--------|
| C11 | Containment uniqueness | Each event is contained in at most one scoping object |
| C12 | Non-empty scope | Each scoping object contains at least one event |
| C13 | Instance consistency | All events transitively enclosed by a scope link to the same choreography instance |
| C14 | Nesting structure | Scoping hierarchy has unique parents and is acyclic (DAG) |
| C15 | Initiator continuity | The initiator of each task was involved (as initiator or participant) in the previous task within the same instance |
| C16 | Scope re-entry | Once an instance's sequence flow has left a sub-choreography scope, it cannot re-enter that scope |

---

## Package structure

```
src/ocelchorvalidator/  reader, index, constraint checks, stats, report, cli
tests/                  unit tests per constraint + integration on real OCEL files
data/input/             mirror of upstream OCEL outputs (12 blockchain + 7 XES; tracked)
```

---

## Testing

```bash
uv run pytest
```
