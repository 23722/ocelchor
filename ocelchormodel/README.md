# ocelchormodel

Reads OCEL 2.0 choreography event logs and emits one BPMN 2.0 choreography
diagram per choreography instance, importable into
[chor-js](https://github.com/bptlab/chor-js-demo). Domain-independent:
consumes the OCEL output of either `trace2ocelchor` (blockchain) or
`xescol2ocelchor` (XES) without modification.

Because each instance corresponds to one observed execution, no gateway
discovery is performed — output is a purely sequential choreography model
with nested sub-choreographies. Start and end events are added for visual
guidance but have no explicit entries in the event log.

## Degenerate-data policy

One rule: **the converter renders what is recorded, makes recording gaps
visible, and refuses what bilateral choreography tasks cannot express.**

- **Unrecorded endpoint** (an event without a receiver — missing
  `choreo:participant` / `choreo:target` edges, the validator's C3/C6
  finding): an *incompleteness* of the record, rendered honestly as an
  **empty phantom participant band**. One phantom per event (a shared
  phantom would assert all unrecorded receivers are the same participant),
  in a reserved id namespace (`P__unknown_<eventId>`), on **both layers** —
  the participant band *and* the message flow's endpoint. The phantom is
  presentational only: an element of the generated `.bpmn`, never of any
  OCEL file — the log keeps recording nothing, the validator keeps
  flagging it. The instance converts, a `<instance>.warnings.txt` names
  the affected events, and the CLI warns on stderr.
- **Multi-cast** (an event with more than one receiver) and **participant
  self-identity** (initiator = receiver, the validator's C4): *positive
  assertions* the bilateral choreography-task construct cannot express —
  rendering them would require inventing or dropping information. The
  instance is **refused**: a stderr line and a `<instance>.refused.txt`
  name the shape and the validator constraint, the log's remaining
  instances still convert, and the exit code is nonzero.

`validate.py` enforces the both-layers consistency machine-side: each
task's two bands must be distinct, and each of its message flows must
connect exactly those two bands (which also rejects self-sends).

For repository-wide context (pipeline diagram, evaluation results, unified
CLI), see the [root README](../README.md).

---

## Requirements + Installation

Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/). Install dev extras
(includes test dependencies):

```bash
cd ocelchormodel
uv sync --extra dev
```

---

## Usage

```bash
uv run ocelchormodel <input files...> [options]
```

For each input OCEL file, the tool extracts all choreography instances and
writes one BPMN file per instance into a subdirectory of the output
directory.

| Flag | Description |
|------|-------------|
| `-o DIR` | Output directory (default: current directory) |
| `--list` | Print all choreography instance IDs and exit |
| `--order-by MODE` | Event ordering: `timestamp` (default) or `trace_order` |
| `--verbose` | Enable debug logging |

Examples:

```bash
# Batch-convert all input files, one BPMN per instance
uv run ocelchormodel data/input/*.json -o data/output/

# List all choreography instance IDs
uv run ocelchormodel data/input/*.json --list

# Convert a single file
uv run ocelchormodel traces.ocel.json -o output/
```

### Output directory structure

```
data/output/
  0x556b9306..._uniqueFunction/
    0xabc123...def456.bpmn                 the converted model
    0xabc123...def456.chorjs.report.json   chor-js render evidence
    0x789abc...123456.refused.txt          instance refused (see policy above)
    0x456def...789abc.warnings.txt         converted with phantom bands
  beanstalk_attack/
    0x68cdec0a...4fa54c6f.bpmn
    ...
```

One subdirectory per input file (input filename with `_ocel.json` stripped);
one BPMN file per converted choreography instance (named by the instance
id), each with its chor-js render report (produced by the headless harness
in `../ocelchormodel_RAD/tools/chorjs-render/`; see its README).
Refused instances leave a
`.refused.txt` note instead of a model; instances converted with phantom
bands additionally leave a `.warnings.txt` note (degenerate-data policy
above).

---

## Input format

Valid OCEL 2.0 JSON file produced by `trace2ocelchor` or `xescol2ocelchor`.
The tool reads the following qualified relationships:

### Event-to-object (E2O)

| Qualifier | Role |
|-----------|------|
| `choreo:instance` | Links a choreography event to its `choreographyInstance` object; only events with this qualifier are processed |
| `choreo:initiator` | The participant that initiates the message exchange |
| `choreo:participant` | The non-initiating participant |
| `choreo:message` | A request or response message object |
| `choreo:contained-by` | Links an event to the `subchoreographyInstance` scope object it belongs to |

### Object-to-object (O2O)

| Qualifier | Role |
|-----------|------|
| `choreo:source` | The sending participant of a message |
| `choreo:target` | The receiving participant of a message |
| `choreo:contains` | Links a parent `subchoreographyInstance` scope to a child scope (hierarchy) |

Events within an instance are ordered by their OCEL `time` field (ISO 8601
timestamp) by default; `--order-by trace_order` switches to the
`trace_order` event attribute when present.

---

## Output format

BPMN 2.0 XML conforming to the OMG BPMN 2.0.2 specification.

| Element | Description |
|---------|-------------|
| `<choreographyTask>` | One per choreography task event; carries initiating and (if present) returning message flows |
| `<subChoreography>` | One per sub-choreography scope; expanded, containing its own sequential flow |
| `<participant>` | One per unique participant in the instance |
| `<message>` | One per unique message object |
| `<messageFlow>` | One per choreography task, connecting source and target participants and referencing the message |
| `<startEvent>` / `<endEvent>` | Boundary events at every level of the hierarchy |
| `<sequenceFlow>` | Sequential connections between adjacent elements at each level |

The BPMN XML includes full diagram interchange (`BPMNShape`, `BPMNEdge`,
`dc:Bounds`, `di:waypoint`) so the file renders directly in chor-js.
Participant bands are generated for every choreography task and
sub-choreography. Layout is computed by a left-to-right sequential
algorithm; sub-choreography boxes are sized bottom-up to contain their
inner elements at any nesting depth.

---

## Limitations

- **Sequential models only** — no gateway discovery; one instance
  corresponds to one observed execution.
- **One messageFlow per task** — each choreography task gets its own
  `<bpmn2:messageFlow>` element (even if multiple tasks reference the
  same logical message object). This is the BPMN-correct mapping; see
  paper §4.1 for the rationale.
- **Sub-choreography participant bands** show at most one non-initiating
  participant on the outer container box; the contained tasks carry the
  full participant detail.

---

## Package structure

```
src/ocelchormodel/      reader, model (dataclasses), extractor, layout, bpmn writer, validator, cli
tests/                  unit + integration tests against OCEL fixtures
data/input/             mirror of upstream OCEL outputs (12 blockchain
                        + 1 running example + 7 XES; tracked)
data/output/            converted models — tracked regression baseline
                        (BPMN, chor-js render reports, refusal/warning
                        notes; only rendered SVGs are gitignored)
```

---

## Testing

```bash
uv run pytest
```

Covers reader / instance extraction (incl. sub-choreography nesting up to
3 levels) / layout arithmetic / BPMN well-formedness (element counts,
referential integrity, waypoint presence, no duplicate ids) / chor-js
import compatibility / CLI / end-to-end integration on real fixtures.
