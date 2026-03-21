# ocelchor

Reference implementation accompanying the paper:

> *[Title]*. [Authors]. [Venue, Year].

This repository provides a pipeline for:
- Representing BPMN 2.0 process choreographies from Ethereum transaction traces via OCEL 2.0 event logs
- Checking well-formedness of the representations based on 17 constraints
- Converting the event log representation of individual choreographies encoded in OCEL 2.0 as BPMN files

---

## Repository layout

```
ocelchor/
├── trace2ocelchor/    Convert Ethereum transaction traces → OCEL 2.0 event logs
├── ocelchormodel/     Create BPMN choreography models from OCEL 2.0 event logs
├── ocelchorvalidator/ Validate OCEL 2.0 logs against formal constraints C0–C15
├── generate_fig4.py   Standalone script for reproducing Figure 4 (requires pm4py)
└── src/ocelchor/      Unified CLI dispatcher
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

This installs the `ocelchor` unified CLI as well as the three individual tool CLIs.

---

## Pipeline

The three tools form a sequential pipeline:

```
Ethereum traces  →  OCEL 2.0 log  →  validation  →  BPMN choreography
```

### Step 1 — Convert traces to OCEL 2.0

Input traces are in `trace2ocelchor/data/input/`.
Pre-computed OCEL 2.0 logs are in `trace2ocelchor/data/output/`.

```bash
uv run ocelchor convert trace2ocelchor/data/input/ -o log.ocel.json
```

### Step 2 — Validate the log

```bash
uv run ocelchor validate log.ocel.json
```

### Step 3 — Create BPMN choreography models (one per choreograohy instance)

Pre-computed BPMN files are in `ocelchormodel/data/output/`.

```bash
uv run ocelchor mine log.ocel.json -o output/
```

BPMN files written to `output/` can be opened in
[chor-js](https://bpt-lab.org/chor-js-demo/).

---

## Individual CLIs

Each tool is also available as a standalone command:

| Command                    | Tool             |
|----------------------------|------------------|
| `uv run trace2ocelchor`    | trace2ocelchor   |
| `uv run ocelchormodel`     | ocelchormodel    |
| `uv run ocelchorvalidator` | ocelchorvalidator |

Run any command with `--help` for the full list of options.

---

## Running tests

Each tool has its own test suite. From the repository root:

```bash
cd trace2ocelchor    && uv run pytest && cd ..
cd ocelchormodel     && uv run pytest && cd ..
cd ocelchorvalidator && uv run pytest && cd ..
```

---

## Evaluation results

The table below shows the dataset characteristics and constraint validation results
for all 12 datasets used in the evaluation. Input files are in `ocelchorvalidator/data/input/`.
Column names follow the paper's notation.

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

Non-zero violation counts: C4 has 2 violations in CryptoKitties: Core and 10 in PancakeSwap: MasterChefV3;
C15 has 1 violation in Beanstalk Farms: Attack data. 
The violations can be traced back to blockchain implementation particularities, as described in detail in the paper accompanying this implementation.
All other constraints pass on all datasets.

---

## Reproducing Figure 4

Figure 4 is produced by the standalone script `generate_fig4.py`, which requires
[pm4py](https://pm4py.fit.fraunhofer.de/). Install it and run:

```bash
pip install pm4py
python generate_fig4.py
```

---

## License

MIT — see [LICENSE](LICENSE).


## GenAI assistance disclosure
The implementation of this repository was developed in collaboration with
[Claude Code](https://claude.ai/code) (Anthropic).

