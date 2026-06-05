# ocelchor

Reference implementation accompanying the paper:

> Richard Hobeck, Alessandro Marcelletti, Andrea Morichetta, Ingo Weber.
> *Representing BPMN Choreographies in OCEL 2.0.*

This repository provides a pipeline for:
- Representing BPMN 2.0 process choreographies as OCEL 2.0 event logs from
  two source domains: Ethereum transaction traces and XES collaborative
  event logs (Corradini et al. 2024).
- Checking well-formedness of the representations based on 17 constraints (C0–C16).
- Converting the event log representation of individual choreographies
  encoded in OCEL 2.0 as BPMN files.

---

## Repository layout

```
ocelchor/
├── trace2ocelchor/        Convert Ethereum transaction traces → OCEL 2.0
├── xescol2ocelchor/       Convert XES collaborative event logs → OCEL 2.0
├── ocelchorvalidator/     Validate OCEL 2.0 logs against constraints C0–C16
├── ocelchormodel/         Create BPMN choreography models from OCEL 2.0 logs
├── generate_unique_xes.py Standalone script: deduplicate XES traces by
│                          choreography variant (requires pm4py)
├── generate_fig4.py       Standalone script for reproducing Figure 4
│                          (requires pm4py)
└── src/ocelchor/          Unified CLI dispatcher (blockchain workflow)
```

Each tool has its own `README.md`, `tests/`, and `data/` directory.

---

## Requirements

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/)

---

## Installation

Clone the repository and install all tools in one step:

```bash
git clone <repository-url>
cd ocelchor
uv sync
```

This installs the `ocelchor` unified CLI as well as the four individual tool CLIs.

---

## Pipeline

The tools form a pipeline with two source-domain entry points sharing the
downstream validator and converter:

```
                                                       Validator
                                                  ocelchorvalidator
                                                       ▲      │
                                                       │      ▼
Ethereum traces  ─→  Extractor trace2ocelchor   ─┐
                                                 ├─→  OCEL 2.0 log  ─→  Converter ocelchormodel  ─→  BPMN choreography model (per inst.)
XES collab. logs ─→  Extractor xescol2ocelchor  ─┘
```

### Step 1 — Convert source data to OCEL 2.0

**Blockchain side.** Input traces are in `trace2ocelchor/data/input/`;
pre-computed OCEL 2.0 logs are in `trace2ocelchor/data/output/`.

```bash
uv run ocelchor convert trace2ocelchor/data/input/ -o log.ocel.json
```

**XES side.** Original Corradini et al. logs are in
`xescol2ocelchor/data/input/`; deduplicated counterparts (one representative
trace per choreography variant) are in `xescol2ocelchor/data/input_unique/`;
the resulting OCEL 2.0 logs are in `xescol2ocelchor/data/output/`.

```bash
cd xescol2ocelchor
uv run xescol2ocelchor data/input_unique/collectivelog_*_uniqueInteraction.xes -o data/output/
```

See [Regenerating the deduplicated XES data](#regenerating-the-deduplicated-xes-data)
below for the pm4py-based dedup script that produces `data/input_unique/`.

### Step 2 — Validate the log

```bash
uv run ocelchor validate log.ocel.json
```

The `ocelchorvalidator/data/input/` directory mirrors both source domains'
OCEL outputs, so running

```bash
cd ocelchorvalidator && uv run ocelchorvalidator data/input/*.json
```

reproduces the constraint-validation results reported under
[Evaluation results](#evaluation-results).

### Step 3 — Create BPMN choreography models (one per choreography instance)

Pre-computed BPMN files are in `ocelchormodel/data/output/`.

```bash
uv run ocelchor mine log.ocel.json -o output/
```

BPMN files written to `output/` can be opened in
[chor-js](https://bpt-lab.org/chor-js-demo/).

---

## Individual CLIs

Each tool is also available as a standalone command:

| Command                    | Tool              |
|----------------------------|-------------------|
| `uv run trace2ocelchor`    | trace2ocelchor    |
| `uv run xescol2ocelchor`   | xescol2ocelchor   |
| `uv run ocelchorvalidator` | ocelchorvalidator |
| `uv run ocelchormodel`     | ocelchormodel     |

Run any command with `--help` for the full list of options. The unified
`ocelchor` dispatcher currently routes `convert` to `trace2ocelchor`; for
the XES side, invoke `xescol2ocelchor` directly.

---

## Running tests

Each tool has its own test suite. From the repository root:

```bash
cd trace2ocelchor    && uv run pytest && cd ..
cd xescol2ocelchor   && uv run pytest && cd ..
cd ocelchorvalidator && uv run pytest && cd ..
cd ocelchormodel     && uv run pytest && cd ..
```

---

## Evaluation results

The tables below show the dataset characteristics and constraint validation
results for the 19 datasets used in the evaluation:

- **12 blockchain logs** — Ethereum transaction traces processed by
  `trace2ocelchor`.
- **7 XES collaborative event logs** — from Corradini et al. (2024) [^1],
  processed by `xescol2ocelchor` (figures reported here come from the
  unique-trace deduplicated pipeline run).

Column names follow the paper's notation.

[^1]: Corradini, F., Pettinari, S., Re, B., Rossi, L., Tiezzi, F.
  *A technique for discovering BPMN collaboration diagrams.* Software and
  Systems Modeling 23(6), 1323–1343 (2024). Data:
  <https://bitbucket.org/proslabteam/colliery_validation/>.

**Dataset characteristics**

| Dataset | #vars | #e | #m | #parts | #scoping | #E2O | #O2O | #E2O[m] | #E2O[cb] | #O2O[c] |
|---------|------:|---:|---:|-------:|---------:|-----:|-----:|--------:|---------:|--------:|
| **Consensus Layer: DepositContract**<br>`0x00000000219ab540356cbb839cbe05303d7705fa` |  1 |   9 |  17 |  3 |   1 |    52 |    34 |  17 |   8 |   0 |
| **ENS: ENSGovernor**<br>`0x323a76393544d5ecca80cd6ef2a560c6a395b7e3` |  9 |  21 |  31 |  8 |   6 |   106 |    63 |  31 |  12 |   1 |
| **Tornado.Cash: GovernanceProposalStateUpgrade**<br>`0x5efda50f22d34f262c29268506c5fa42cb56a1ce` | 11 |  35 |  47 | 16 |  17 |   176 |   100 |  47 |  24 |   6 |
| **Tornado.Cash: TornadoRouter**<br>`0xd90e2f925da726b50c4ed8d0fb90ad053324f31b` |  2 |  85 | 146 | 22 |  13 |   484 |   303 | 146 |  83 |  11 |
| **PancakeSwap: MasterChefV3**<br>`0x556b9306565093c855aea9ae92a594704c2cd59e` | 13 | 241 | 361 | 45 |  64 |  1312 |   776 | 361 | 228 |  54 |
| **Uniswap: UniswapV2Pair (USDC-WETH)**<br>`0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc` |  6 |  61 |  88 | 16 |  17 |   326 |   190 |  88 |  55 |  14 |
| **SushiSwap: Router**<br>`0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f` | 19 | 267 | 415 | 55 |  67 |  1464 |   880 | 415 | 248 |  50 |
| **CryptoKitties: Core (KittyCore)**<br>`0x06012c8cf97bead5deae237070f9587f8e7a266d` | 22 | 204 | 302 | 78 |  59 |  1096 |   646 | 302 | 182 |  42 |
| **CryptoKitties: SaleClockAuction**<br>`0xb1690c08e213a35ed9bab7b318de14420fb57d8c` |  2 |   6 |  10 |  4 |   2 |    32 |    20 |  10 |   4 |   0 |
| **Yuga Labs: BoredApeYachtClub**<br>`0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d` |  9 |  18 |  21 | 13 |   5 |    84 |    45 |  21 |   9 |   3 |
| **Nouns DAO: NounsToken**<br>`0x9c8ff314c9bc7f6e59a9d9225fb22946427edc03` |  7 |  12 |  13 | 11 |   3 |    54 |    28 |  13 |   5 |   2 |
| **Beanstalk Farms: Attack data**<br>`beanstalk_attack_ocel.json` |  3 | 489 | 703 | 59 | 139 |  2656 |  1542 | 703 | 486 | 136 |
| **Real1: Two-robot search**<br>`collectivelog_real1_uniqueInteraction.xes` |  1 |   2 |   2 |  2 |   0 |     8 |     4 |   2 |   0 |   0 |
| **Real2: Travel booking**<br>`collectivelog_real2_uniqueInteraction.xes` | 96 | 842 | 480 |  2 |   0 |  3368 |   960 | 842 |   0 |   0 |
| **Real3: Smart thermostat**<br>`collectivelog_real3_uniqueInteraction.xes` | 59 | 472 | 321 |  3 |   0 |  1880 |   634 | 472 |   0 |   0 |
| **Real4: ZooClub registration**<br>`collectivelog_real4_uniqueInteraction.xes` |  1 |   4 |   4 |  3 |   0 |    16 |     8 |   4 |   0 |   0 |
| **Real5: Academic paper review**<br>`collectivelog_real5_uniqueInteraction.xes` |  3 |  15 |  15 |  3 |   0 |    60 |    30 |  15 |   0 |   0 |
| **Healthcare: Hospitalization**<br>`collectivelog_healthcare_uniqueInteraction.xes` | 17 | 116 | 116 |  4 |   0 |   455 |   223 | 116 |   0 |   0 |
| **Smart agriculture: Tractor coordination**<br>`collectivelog_smartagriculture_uniqueInteraction.xes` | 10 | 114 | 100 |  3 |   0 |   452 |   206 | 114 |   0 |   0 |

**Constraint validation results** (format: `violations / checked`)

| Dataset |   C0 |   C1 |   C2 |   C3 |     C4 |   C5 |   C6 |   C7 |   C8 |   C9 |  C10 |  C11 |  C12 |  C13 |  C14 |    C15 |   C16 |
|---------|-----:|-----:|-----:|-----:|-------:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-------:|------:|
| **Consensus Layer: DepositContract**<br>`0x00000000219ab540356cbb839cbe05303d7705fa` | 0/9  | 0/17 | 0/9  | 0/9  |   0/9  | 0/17 | 0/17 | 0/9  | 0/9  | 0/9  | 0/8  | 0/9  | 0/1  | 0/1  | 0/1  |   0/8  |  0/1  |
| **ENS: ENSGovernor**<br>`0x323a76393544d5ecca80cd6ef2a560c6a395b7e3` | 0/21 | 0/31 | 0/21 | 0/21 |   0/21 | 0/31 | 0/31 | 0/21 | 0/21 | 0/21 | 0/10 | 0/21 | 0/6  | 0/6  | 0/6  |  0/12  |  0/6  |
| **Tornado.Cash: GovernanceProposalStateUpgrade**<br>`0x5efda50f22d34f262c29268506c5fa42cb56a1ce` | 0/35 | 0/47 | 0/35 | 0/35 |   0/35 | 0/47 | 0/47 | 0/35 | 0/35 | 0/35 | 0/12 | 0/35 | 0/17 | 0/17 | 0/17 |  0/24  | 0/17  |
| **Tornado.Cash: TornadoRouter**<br>`0xd90e2f925da726b50c4ed8d0fb90ad053324f31b` | 0/85 | 0/146| 0/85 | 0/85 |   0/85 | 0/146| 0/146| 0/85 | 0/85 | 0/85 | 0/61 | 0/85 | 0/13 | 0/13 | 0/13 |  0/83  | 0/13  |
| **PancakeSwap: MasterChefV3**<br>`0x556b9306565093c855aea9ae92a594704c2cd59e` | 0/241| 0/361| 0/241| 0/241| 10/241 | 0/361| 0/361| 0/241| 0/241| 0/241| 0/130| 0/241| 0/64 | 0/64 | 0/64 |  0/228 | 0/64  |
| **Uniswap: UniswapV2Pair (USDC-WETH)**<br>`0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc` | 0/61 | 0/88 | 0/61 | 0/61 |   0/61 | 0/88 | 0/88 | 0/61 | 0/61 | 0/61 | 0/27 | 0/61 | 0/17 | 0/17 | 0/17 |  0/55  | 0/17  |
| **SushiSwap: Router**<br>`0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f` | 0/267| 0/415| 0/267| 0/267|  0/267 | 0/415| 0/415| 0/267| 0/267| 0/267| 0/148| 0/267| 0/67 | 0/67 | 0/67 |  0/248 | 0/67  |
| **CryptoKitties: Core (KittyCore)**<br>`0x06012c8cf97bead5deae237070f9587f8e7a266d` | 0/204| 0/302| 0/204| 0/204|  2/204 | 0/302| 0/302| 0/204| 0/204| 0/204| 0/100| 0/204| 0/59 | 0/59 | 0/59 |  0/182 | 0/59  |
| **CryptoKitties: SaleClockAuction**<br>`0xb1690c08e213a35ed9bab7b318de14420fb57d8c` | 0/6  | 0/10 | 0/6  | 0/6  |   0/6  | 0/10 | 0/10 | 0/6  | 0/6  | 0/6  | 0/4  | 0/6  | 0/2  | 0/2  | 0/2  |  0/4   |  0/2  |
| **Yuga Labs: BoredApeYachtClub**<br>`0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d` | 0/18 | 0/21 | 0/18 | 0/18 |   0/18 | 0/21 | 0/21 | 0/18 | 0/18 | 0/18 | 0/3  | 0/18 | 0/5  | 0/5  | 0/5  |  0/9   |  0/5  |
| **Nouns DAO: NounsToken**<br>`0x9c8ff314c9bc7f6e59a9d9225fb22946427edc03` | 0/12 | 0/13 | 0/12 | 0/12 |   0/12 | 0/13 | 0/13 | 0/12 | 0/12 | 0/12 | 0/1  | 0/12 | 0/3  | 0/3  | 0/3  |  0/5   |  0/3  |
| **Beanstalk Farms: Attack data**<br>`beanstalk_attack_ocel.json` | 0/489| 0/703| 0/489| 0/489|  0/489 | 0/703| 0/703| 0/489| 0/489| 0/489| 0/214| 0/489| 0/139| 0/139| 0/139|  1/486 | 0/139 |
| **Real1: Two-robot search**<br>`collectivelog_real1_uniqueInteraction.xes` |  0/2  |  0/2  |  0/2  |   0/2  |   0/2  |  0/2  |   0/2  |  0/2  |  0/2  |  0/2  | 0/0 |  0/2  | 0/0 | 0/0 | 0/0 |  0/1   | 0/0 |
| **Real2: Travel booking**<br>`collectivelog_real2_uniqueInteraction.xes` | 0/842 | 0/842 | 0/842 |  0/842 |  0/842 | 0/842 |  0/842 | 0/842 | 0/842 | 0/842 | 0/0 | 0/842 | 0/0 | 0/0 | 0/0 |  0/746 | 0/0 |
| **Real3: Smart thermostat**<br>`collectivelog_real3_uniqueInteraction.xes` | 0/472 | 0/472 | 0/472 |  **8**/472 |  0/472 | 0/472 |  **8**/472 | 0/472 | 0/472 | 0/464 | 0/0 | 0/472 | 0/0 | 0/0 | 0/0 | **99**/413 | 0/0 |
| **Real4: ZooClub registration**<br>`collectivelog_real4_uniqueInteraction.xes` |  0/4  |  0/4  |  0/4  |   0/4  |   0/4  |  0/4  |   0/4  |  0/4  |  0/4  |  0/4  | 0/0 |  0/4  | 0/0 | 0/0 | 0/0 |  0/3   | 0/0 |
| **Real5: Academic paper review**<br>`collectivelog_real5_uniqueInteraction.xes` |  0/15 |  0/15 |  0/15 |   0/15 |   0/15 |  0/15 |   0/15 |  0/15 |  0/15 |  0/15 | 0/0 |  0/15 | 0/0 | 0/0 | 0/0 |  0/12  | 0/0 |
| **Healthcare: Hospitalization**<br>`collectivelog_healthcare_uniqueInteraction.xes` | 0/116 | 0/116 | 0/116 |  **9**/116 |  0/116 | 0/116 |  **9**/116 | 0/116 | 0/116 | 0/107 | 0/0 | 0/116 | 0/0 | 0/0 | 0/0 |  **9**/99 | 0/0 |
| **Smart agriculture: Tractor coordination**<br>`collectivelog_smartagriculture_uniqueInteraction.xes` | 0/114 | 0/114 | 0/114 | **28**/114 |  0/114 | 0/114 | **28**/114 | 0/114 | 0/114 | 0/98  | 0/0 | 0/114 | 0/0 | 0/0 | 0/0 |  **9**/104 | 0/0 |

The violations have two distinct sources: blockchain implementation
particularities (for `trace2ocelchor`) and source-data fidelity choices in
the XES corpus (for `xescol2ocelchor`).

**Blockchain side.**

- **C4 has 2 violations in CryptoKitties: Core.** The violations of C4
  occurred due to the respective calls using a *multicall* pattern, which
  self-executes functions through explicit CALLs and DELEGATECALLs. Thus the
  self-execute functions were treated as internal transactions. This results
  in the caller being equal to the callee. This pattern is typically used to
  optimize execution costs and enable modular execution.
- **C4 has 10 violations in PancakeSwap: MasterChefV3.** Same root cause as
  above — multicall-style self-execution where a contract dispatches calls
  to itself.
- **C15 has 1 violation in Beanstalk Farms: Attack data.** The violation of
  C15 occurred when a contract was created and immediately after started to
  issue calls on its part. Since the address of the created contract was not
  known before its creation, it did not appear in the data.

**XES side.**

- **C3 / C6 have 45 violations each across three datasets.** These mark
  events whose receiver(s) cannot be uniquely recovered from the XES
  collaboration log, in two flavours:
  - *Unmatched sends* — a `send` event whose `msgInstanceId` has no matching
    `receive` in the same trace; 8 in Real3, 9 in Healthcare, 16 in Smart
    agriculture. The extractor keeps the event with initiator and message
    but emits it without `choreo:participant` / `choreo:target`, which is
    what C3 / C6 flag.
  - *Broadcast over-connection* — a `send` whose `msgInstanceId` is
    received by multiple participants; 12 occurrences in Smart agriculture
    (drone broadcasting `weed_position` to both tractors). The extractor
    attributes every send to the full broadcast group (the source data
    carries no marker pairing a specific send with a specific receiver),
    which the validator flags as 2 participants / 2 targets. This is the
    BPMN multi-instance participant pattern surfaced as a constraint
    violation (see paper §X.Y).
- **C15 has 117 violations across three datasets.** These mark
  initiator-discontinuity in multi-party processes — the initiator of an
  event was neither initiator nor participant of the immediately preceding
  event in the same instance. 99 in Real3 (Controller / User re-entering
  after Thermostat-mediated exchanges), 9 in Healthcare (Hospital
  re-entering after Patient / Laboratory exchanges), 9 in Smart agriculture
  (a tractor re-entering after exchanges that did not involve it).
  Identical figures appear in the Peña et al. reference choreography
  logs (`_chor.xes`), confirming the structural origin of these
  discontinuities in the source data rather than in our conversion.

---

## Reproducing Figure 4

Figure 4 is produced by the standalone script `generate_fig4.py`, which requires
[pm4py](https://pm4py.fit.fraunhofer.de/). Install it and run:

```bash
pip install pm4py
python generate_fig4.py
```

---

## Regenerating the deduplicated XES data

The seven deduplicated XES logs in `xescol2ocelchor/data/input_unique/` are
produced from the original Corradini et al. logs in
`xescol2ocelchor/data/input/` by the standalone script
`generate_unique_xes.py`, which requires
[pm4py](https://pm4py.fit.fraunhofer.de/):

```bash
uv run --with pm4py python generate_unique_xes.py
```

The deduplicated logs are then converted to OCEL via `xescol2ocelchor`:

```bash
cd xescol2ocelchor
uv run xescol2ocelchor data/input_unique/collectivelog_*_uniqueInteraction.xes -o data/output/
```

The resulting OCEL files in `xescol2ocelchor/data/output/` are the source of
truth for the XES OCEL files; the validator's and modeler's `data/input/`
directories hold copies.

---

## License

MIT — see [LICENSE](LICENSE).


## GenAI assistance disclosure
The implementation of this repository was developed in collaboration with
[Claude Code](https://claude.ai/code) (Anthropic).

