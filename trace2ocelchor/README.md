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
| `EOA` | Externally owned account (user where identifiable as sender of a transaction) |
| *contract name* | Named contract (from `contractCalledName`, resolved log-wide) |
| *contract address* | Contract without a known name anywhere in the log |
| `<function> call` | Request message object |
| `<function> call response` | Response message object |
| `subchoreographyInstance` | Scoping object grouping nested calls; carries a `name` attribute in task-label style (e.g. `"swap [Router]"` — the function plus the same log-wide discriminator as event types), which downstream discovery consumes as the sub-choreography label |
| `choreographyInstance` | One instance per transaction |

### Participant typing and event types

Participant objects use the address as `id` and their **role** as `type`,
resolved with a deterministic, log-wide priority:

```
type = EOA                  the address sends a transaction anywhere in the log
       contractCalledName   named contract (address→name map over all traces)
       <address>            otherwise
```

The sender set and the address→name map are collected over the whole log
before typing, so an object's type never depends on the order in which the
address is first encountered (an EOA may, e.g., receive a payout in an
earlier transaction before sending its own). Unnamed contracts are
deliberately typed by their address rather than a generic class (such as
`CA`): object types are the roles that appear as participant bands in
choreography models discovered downstream, and a generic type would collapse
distinct contracts into one meaningless band — for an unverified contract,
the finest role that can be asserted is its identity. (Trade-off: distinct
unnamed contracts never pool into one role.)

Event types are participant-aware call keys,

```
[kind prefix +] <function> [<discriminator>]
```

with kind prefix `Request ` / `Respond to ` for the bracket events of
non-leaf calls (e.g. `transfer [TORN]`, `Request unlock [Governance]`). The
discriminator resolves through the **same** log-wide name map (name where
known anywhere in the log, else the called contract's address — never a
generic class), so event-type discriminators and participant roles agree by
construction.

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
- **Unrecorded endpoints.** An event whose endpoint address is missing from
  the source record (e.g. the empty `contractAddress` of a contract-creation
  transaction) is emitted **without** the corresponding
  `choreo:participant` / `choreo:target` (or, symmetrically,
  `choreo:initiator` / `choreo:source`) relationships; no empty-identifier
  participant object is materialised. The recording gap thus stays visible
  to the downstream validator rather than being masked by a degenerate
  object that formally satisfies the constraints.

---

## Data attribution

The blockchain transaction-trace inputs are from

> A. Marcelletti. *BlockchainDataset.*
> <https://github.com/AlessandroMarcellettiUnicam1/BlockchainDataset>

Two families are used: the deduplicated `data/input_unique/` traces
(committed here) and the full, non-deduplicated traces in
`data/input_full/` — the latter are **not committed** (≈3 GB; stored via
Git LFS in the upstream repository
<https://github.com/AlessandroMarcellettiUnicam1/BlockchainDataset>, which
remains the canonical source; download them there and place them in
`data/input_full/`).

Cite the source when reusing the datasets.

---

## Package structure

```
src/trace2ocelchor/     parser, transformer, ocel serialisation, models, cli, stats
tests/                  unit + integration tests (incl. schema validation)
data/input_unique/      deduplicated real-world transaction traces (tracked)
data/input_full/        full trace family (≈3 GB; not committed — see Data attribution)
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
