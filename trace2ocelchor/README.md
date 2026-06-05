# trace2ocelchor

Converts pre-processed Ethereum mainnet transaction traces into
[OCEL 2.0](https://ocel-standard.org/) event logs encoding BPMN choreography
semantics. The output is consumable by the domain-independent
`ocelchorvalidator` (C0–C16 constraint validation) and `ocelchormodel`
(OCEL → BPMN choreography model) without modification.

For repository-wide context (pipeline diagram, evaluation results, unified
CLI), see the [root README](../README.md).

---

## Requirements + Installation

Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/). Install dev extras
(includes test dependencies):

```bash
cd trace2ocelchor
uv sync --extra dev
```

---

## Usage

```bash
uv run trace2ocelchor <input> [<input> ...] [options]
```

`<input>` may be one or more JSON files or a directory. Multiple inputs are
merged into a single event log with globally deduplicated participant
objects.

| Flag | Description |
|------|-------------|
| `-o FILE` | Output path (default: `output.ocel.json`) |
| `--stats` | Print a summary of events and objects after conversion |
| `--verbose` | Enable debug logging |

Example:

```bash
uv run trace2ocelchor data/traces.json -o traces.ocel.json --stats
```

---

## Input format

JSON arrays of transaction objects (or a single object). Each transaction
requires at minimum:

| Field | Description |
|-------|-------------|
| `transactionHash` | Unique transaction identifier |
| `functionName` | Top-level function name (optional; defaults to `"undefined"` if null or absent) |
| `contractAddress` | Address of the called contract |
| `sender` | Externally owned account (EOA) address |
| `timestamp.$date` | ISO 8601 block timestamp |
| `inputs` | Decoded top-level function parameters |
| `internalTxs` | Recursive array of internal call frames |

Internal call frames follow the same recursive structure via a `calls`
field and carry `callId`, `from`, `to`, `type`, `activity`, `inputs`, and
`output`.

---

## Output format

Valid OCEL 2.0 JSON file. Object types produced:

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

## Limitations

- **DELEGATECALL reattribution.** For `DELEGATECALL` internal calls, the
  extractor reattributes the issuer of nested sub-calls from caller to
  callee to align with BPMN choreography semantics. Other low-level call
  variants (STATICCALL, CALLCODE) are not specially handled.
- **Reverted calls.** By default, reverted/failed call frames are excluded;
  pass `--include-reverted` to include them.
- **Metadata.** Gas usage, value transferred, call id, depth, and block
  number are stored as event attributes only when `--include-metadata` is
  set; the default output keeps the OCEL minimal.

---

## Data attribution

The blockchain transaction-trace inputs in `data/input/` are from

> A. Marcelletti. *BlockchainDataset.*
> <https://github.com/AlessandroMarcellettiUnicam1/BlockchainDataset>

Cite the source when reusing the datasets.

---

## Package structure

```
src/trace2ocelchor/     parser, transformer, ocel serialisation, models, cli, stats
tests/                  unit + integration tests (incl. schema validation)
data/input/             real-world transaction trace files (tracked)
data/output/            generated OCEL files (gitignored)
```

---

## Testing

```bash
uv run pytest
```

Covers unit tests for parsing and transformation, OCEL 2.0 JSON-schema
validation (sourced from ocel-standard.org), CLI integration, and
integrity checks (duplicate IDs, E2O/O2O consistency). Beyond synthetic
fixtures, two real-world DApp datasets (PancakeSwap MasterChef v3 and
Tornado Cash Governance) are included as integration tests asserting the
expected event, object, and relation counts.
