# trace2choreo

**trace2choreo** converts pre-processed Ethereum mainnet transaction traces into
[OCEL 2.0](https://ocel-standard.org/) event logs that encode BPMN choreography
semantics. It is the reference implementation accompanying the paper

> *[Title]*. [Authors]. [Venue, Year].

The transformation maps each transaction's internal call tree to a choreography
instance, producing typed participant objects, typed message objects carrying
decoded call parameters, and qualified E2O/O2O relations (`choreo:initiator`,
`choreo:participant`, `choreo:message`, `choreo:source`, `choreo:target`,
`choreo:contained-by`, `choreo:contains`, `choreo:instance`).

---

## Requirements

- Python 3.10 or later
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
git clone <repository-url>
cd trace2ocelchor
uv sync
```

---

## Usage

```bash
uv run trace2choreo <input> [<input> ...] [options]
```

`<input>` may be one or more JSON files or a directory. Multiple inputs are
merged into a single event log with globally deduplicated participant objects.

### Options

| Flag | Description |
|------|-------------|
| `-o FILE` | Output path (default: `output.ocel.json`) |
| `--stats` | Print a summary of events and objects after conversion |
| `--verbose` | Enable debug logging |

### Example

```bash
uv run trace2choreo data/traces.json -o traces.ocel.json --stats
```

---

## Input format

Input files must be JSON arrays of transaction objects (or a single object).
Each transaction object requires at minimum:

| Field | Description |
|-------|-------------|
| `transactionHash` | Unique transaction identifier |
| `functionName` | Top-level function name (optional; defaults to `"undefined"` if null or absent) |
| `contractAddress` | Address of the called contract |
| `sender` | Externally owned account (EOA) address |
| `timestamp.$date` | ISO 8601 block timestamp |
| `inputs` | Decoded top-level function parameters |
| `internalTxs` | Recursive array of internal call frames |

Internal call frames follow the same recursive structure via a `calls` field and
carry `callId`, `from`, `to`, `type`, `activity`, `inputs`, and `output`.

---

## Output format

The output is a valid OCEL 2.0 JSON file. Object types produced:

| Type | Description |
|------|-------------|
| `EOA` | Externally owned account (transaction sender) |
| `CA` | Contract address without a known name |
| *contract name* | Named contract (from `contractCalledName` field) |
| `<function> call` | Request message object |
| `<function> call response` | Response message object |
| `subchoreographyInstance` | Scoping object grouping nested calls; carries a `name` attribute (e.g. `"subchoreography swap"`) |
| `choreographyInstance` | One instance per transaction |

---

## Project structure

```
src/trace2choreo/
    parser.py       — JSON ingestion and schema normalisation
    transformer.py  — trace-to-OCEL transformation (choreography mining)
    ocel.py         — OCEL 2.0 JSON serialisation
    models.py       — dataclasses and qualifier constants
    cli.py          — command-line interface
    stats.py        — summary statistics
tests/
    test_parser.py
    test_transformer.py
    test_ocel.py
    test_cli.py
    test_integration.py
    expected/       — human-readable expected-output specifications
    data/           — synthetic and ground-truth test fixtures
data/
    input/          — real-world transaction trace files (input)
    output/         — generated OCEL output files (gitignored)
```

---

## Testing

```bash
uv run pytest
```

Software quality was ensured through a test-driven development process applied
consistently across all layers of the implementation. A formal requirements
specification (with numbered sections) guided the transformation rules, and
human-readable expected-output documents served as "ground truth" from which a 
subset of the test cases were derived before any implementation was written. The test suite
comprises unit tests for parsing and transformation logic, schema-validity tests
against the official OCEL 2.0 JSON Schema (sourced from ocel-standard.org,
validated using the Python `jsonschema` library), CLI integration tests, and
integrity checks that assert the absence of duplicate IDs and the consistency of 
all E2O and O2O relations. Beyond synthetic fixtures, two real-world DApp transaction datasets (PancakeSwap MasterChef v3 and Tornado Cash Governance) are included as 
integration tests that verify the expected event, object, and relation counts of the produced logs.

---

## License

MIT — see [LICENSE](LICENSE).

---

## GenAI assistance disclosure
The implementation of this repository was developed in collaboration with
[Claude Code](https://claude.ai/code) (Anthropic).

