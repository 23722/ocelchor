# ocelchormodel

**ocelchormodel** reads [OCEL 2.0](https://ocel-standard.org/) choreography event logs
produced by **trace2choreo** and generates BPMN 2.0 choreography models from them.
It is the reference implementation of the mining step accompanying the paper

> *[Title]*. [Authors]. [Venue, Year].

For each choreography instance in the log, ocelchormodel reconstructs the
hierarchical choreography model encoded in the OCEL 2.0 relations and emits a
BPMN 2.0 XML file importable into [chor-js](https://bpt-lab.org/chor-js-demo/).
Because each instance corresponds to one blockchain transaction trace — a
deterministic, gateway-free execution sequence — no gateway discovery is
required; the output is a purely sequential choreography model with nested
subchoreographies.

---

## Requirements

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- OCEL 2.0 event log(s) produced by **trace2choreo**

## Installation

```bash
git clone <repository-url>
cd ocelchormodel
uv sync
```

---

## Usage

```bash
uv run ocelchormodel <input files...> [options]
```

The CLI accepts one or more OCEL 2.0 JSON files. For each input file, it
extracts all choreography instances and writes one BPMN file per instance
into a subdirectory of the output directory.

### Options

| Flag | Description |
|------|-------------|
| `-o DIR` | Output directory (default: current directory) |
| `--list` | Print all choreography instance IDs and exit |
| `--order-by MODE` | Event ordering: `timestamp` (default) or `trace_order` |
| `--verbose` | Enable debug logging |

### Examples

Batch-convert all input files, one BPMN per instance:

```bash
uv run ocelchormodel data/input/*.json -o data/output/
```

List all choreography instances across multiple files:

```bash
uv run ocelchormodel data/input/*.json --list
```

Convert a single file:

```bash
uv run ocelchormodel traces.ocel.json -o output/
```

### Output structure

```
data/output/
  0x556b9306..._uniqueFunction/
    0xabc123...def456.bpmn
    0x789abc...123456.bpmn
  beanstalk_attack/
    0x68cdec0a...4fa54c6f.bpmn
    0xcd314668...c5d33ad7.bpmn
```

- One subdirectory per input file, named by stripping `_ocel.json` from the filename
- One BPMN file per choreography instance, named by the full transaction hash

---

## Typical workflow

```
Ethereum traces
      │
      ▼  trace2choreo
OCEL 2.0 event log  (.ocel.json)
      │
      ▼  ocelchormodel
BPMN 2.0 choreography  (.bpmn)
      │
      ▼  chor-js demo
Visual choreography diagram
```

---

## Input format

The input must be a valid OCEL 2.0 JSON file produced by **trace2choreo**.
The tool reads the following OCEL 2.0 constructs:

### Event-to-object (E2O) qualifiers used

| Qualifier | Role |
|-----------|------|
| `choreo:instance` | Links a choreography event to its `ChoreographyInstance` object; only events carrying this qualifier are processed |
| `choreo:initiator` | The participant that initiates the message exchange |
| `choreo:participant` | The non-initiating participant |
| `choreo:message` | A request or response message object |
| `choreo:contained-by` | Links an event to the `Subchoreography` scope object it belongs to |

### Object-to-object (O2O) qualifiers used

| Qualifier | Role |
|-----------|------|
| `choreo:source` | The sending participant of a message |
| `choreo:target` | The receiving participant of a message |
| `choreo:contains` | Links a parent `Subchoreography` scope to a child scope (hierarchy) |

### Event ordering

Events within an instance are ordered by their OCEL `time` field (ISO 8601
timestamp) by default. The alternative `--order-by trace_order` uses the
`trace_order` attribute (an integer assigned by trace2choreo).

---

## Output format

The output is a BPMN 2.0 XML file conforming to the OMG BPMN 2.0.2
specification and importable into [chor-js](https://bpt-lab.org/chor-js-demo/).

### BPMN elements produced

| Element | Description |
|---------|-------------|
| `<choreographyTask>` | One per choreography task event; carries initiating and (if present) returning message flows |
| `<subChoreography>` | One per subchoreography scope; expanded, containing its own sequential flow |
| `<participant>` | One per unique participant address in the instance |
| `<message>` | One per unique message object (request or response) |
| `<messageFlow>` | Connects a message's source and target participants |
| `<startEvent>` / `<endEvent>` | Boundary events at every level of the hierarchy |
| `<sequenceFlow>` | Sequential connections between adjacent elements at each level |

### Diagram interchange (DI)

The BPMN XML includes full layout coordinates (`BPMNShape`, `BPMNEdge`,
`dc:Bounds`, `di:waypoint`) required by chor-js. Participant bands
(`participantBandKind`, `choreographyActivityShape`, `isMessageVisible`) are
generated for every choreography task and subchoreography.

Layout is computed automatically using a left-to-right sequential algorithm.
Subchoreography boxes are sized bottom-up to contain their inner elements at any
nesting depth.

---

## Project structure

```
src/ocelchormodel/
    reader.py      — OCEL 2.0 JSON loading and validation
    model.py       — domain dataclasses (Participant, Message, ChoreoTask,
                     SubChoreo, ChoreoInstance)
    extractor.py   — instance listing and recursive model extraction from OCEL
    layout.py      — auto-layout: bottom-up size computation, top-down
                     coordinate assignment
    bpmn.py        — BPMN 2.0 XML serialisation (xml.etree.ElementTree)
    validate.py    — structural validator for chor-js import compatibility
    cli.py         — command-line interface (batch conversion)
tests/
    test_reader.py
    test_extractor.py
    test_layout.py
    test_bpmn.py
    test_validate.py
    test_cli.py
    test_integration.py
    data/          — OCEL 2.0 test fixtures
```

---

## Testing

```bash
uv sync --extra dev
uv run python -m pytest
```

The test suite (94 tests) covers:

- **Reader**: valid and malformed inputs, missing keys, non-JSON files.
- **Extractor**: instance listing, task and subchoreography counts, message
  directionality, nesting depth (up to 3 levels), ordering, per-instance
  scope filtering, unknown-instance error handling.
- **Layout**: bounds arithmetic, band splitting, element sizing, full layout
  computation including subchoreography start/end events.
- **BPMN generator**: well-formedness, element counts, referential integrity
  (all `participantRef`, `messageFlowRef`, `messageRef`, and `bpmnElement`
  values reference declared IDs), waypoint presence, positive DI bounds,
  absence of duplicate IDs.
- **Validator**: structural rules for chor-js compatibility.
- **CLI**: `--list`, batch conversion, output directory structure, error handling.
- **Integration**: end-to-end pipeline for test fixtures, verifying
  element counts, sequence-flow connectivity, duplicate-ID absence, and
  referential integrity.

---

## Limitations

- Produces sequential models only (no gateway discovery); one instance
  corresponds to one transaction trace.
- Only request-response call frames are represented; log entries, storage
  operations, and static calls not modelled in trace2choreo are out of scope.
- Subchoreography participant bands show at most one non-initiating participant
  on the outer container box. The contained tasks carry the full participant
  detail.

---

## License

MIT — see [LICENSE](../trace2ocelchor/LICENSE).

---

## GenAI assistance disclosure

The implementation of this repository was developed in collaboration with
[Claude Code](https://claude.ai/code) (Anthropic).
