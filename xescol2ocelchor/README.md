# xescol2ocelchor

Converts XES collaborative event logs into
[OCEL 2.0](https://ocel-standard.org/) event logs encoding BPMN choreography
semantics. For each `send` event in the input log the extractor emits one
one-way choreography task event; the receiver(s) are recovered from
`receive` events sharing the same `msgInstanceId` in the same trace. The
output is consumable by the domain-independent `ocelchorvalidator` (C0–C16
constraint validation) and `ocelchormodel` (OCEL → BPMN choreography
model) without modification.

For repository-wide context (pipeline diagram, evaluation results, unified
CLI), see the [root README](../README.md).

---

## Requirements + Installation

Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/). Install dev extras
(includes test dependencies):

```bash
cd xescol2ocelchor
uv sync --extra dev
```

---

## Usage

```bash
uv run xescol2ocelchor <input.xes> [<input.xes> ...] -o DIR [options]
```

For each XES input, one OCEL 2.0 JSON file is written into the output
directory. Output files are named `<dataset>_ocel.json` — the
`collectivelog_` prefix and `.xes` suffix are stripped, so e.g.
`collectivelog_real1.xes` becomes `real1_ocel.json`.

| Flag | Description |
|------|-------------|
| `-o DIR` | Output directory (created if missing). Required. |
| `--crosscheck` | After each conversion, compare the reconstruction with the sibling `<name>_collab.xes` and report agreement percentage. |
| `--keep-internal-events` | Experimental — not used for the paper's evaluation: keep internal (non-message) XES events as OCEL events outside `E_T` (no `choreo:*` qualifiers). |
| `--verbose` | Verbose logging. |

Example:

```bash
# Convert all seven datasets and run the cross-check
uv run xescol2ocelchor data/input/collectivelog_*.xes \
    -o data/output/ --crosscheck

# Then validate against C0–C16 using the unchanged validator
cd ../ocelchorvalidator
uv run ocelchorvalidator ../xescol2ocelchor/data/output/*.json
```

The paper's evaluation numbers derive from the deduplicated variants,
`data/input_unique/collectivelog_*_uniqueInteraction.xes`.

---

## Input format

XES 1.0 (IEEE 1849-2016). Each trace's `concept:name` is the choreography
instance identifier. Each event carries the standard `concept:name`,
`time:timestamp`, `org:group`, plus the domain-specific:

| Attribute | Role |
|-----------|------|
| `msgType` | `send` or `receive`. **Absent** on internal events. |
| `msgInstanceId` | Per-trace message identifier. Sender and receiver(s) of the same message share this value. |
| `msgName` (or `msgFlow`) | Message-flow name. Used as the OCEL message object type when present. |

Tokens `None`, `""`, `"None"`, and `"-"` are treated as "absent".

---

## Output format

Valid OCEL 2.0 JSON file (validated against the official schema in tests).
Choreography semantics are expressed through qualified E2O and O2O
relationships, without any extension to OCEL 2.0:

| Object type | Description |
|-------------|-------------|
| `choreographyInstance` | One per XES trace |
| *org:group value* | One participant object per distinct `org:group`, global across the log. Both id and **type** are the `org:group` value itself — the object type is the participant's role, consumed verbatim by downstream tools |
| *message type* | One per distinct `(trace, msgInstanceId)` — type derived from `msgName`, else the `msgInstanceId` with any trailing `_<digits>` stripped (e.g. `Offer_260` → `Offer`), else `message` |

| Qualifier (E2O on task event) | Target |
|-------------------------------|--------|
| `choreo:instance` | choreographyInstance |
| `choreo:initiator` | sending participant |
| `choreo:participant` | receiving participant (one per distinct receiver) |
| `choreo:message` | message object |

| Qualifier (O2O on message object) | Target |
|-----------------------------------|--------|
| `choreo:source` | sending participant |
| `choreo:target` | receiving participant (one per distinct receiver) |

Sub-choreography scoping is **not** produced (these logs are flat;
inferring nesting would be fabrication — see *Limitations*).

---

## Cross-check (`--crosscheck`)

For each plain `<name>.xes` input, the tool can verify its reconstruction
against the sibling `<name>_collab.xes` ground truth (Peña et al.'s
`collab:fromParticipant` / `collab:toParticipant` / `collab:participant`
attributes). Expected agreement is **100%** on every dataset; verified.

---

## Limitations

- **One-way tasks only.** These datasets have no marker pairing a request
  with a response; constructing two-way (request/response) tasks would be
  fabrication.
- **Internal (non-message) events are dropped by default.** Attaching them
  with `choreo:instance` would pull them into `E_T` and produce spurious
  C0/C2/C3 violations. The experimental `--keep-internal-events` flag emits
  them outside `E_T` instead (no `choreo:*` qualifiers, linked to a
  `collaborationInstance` object); not used for the paper's evaluation.
- **No sub-choreographies.** The XES logs are flat; inserting
  `subchoreographyInstance` objects without a containment signal would be
  fabrication.
- **Missing sender.** A `send` without `org:group` is emitted without its
  `choreo:initiator` / `choreo:source` relationships rather than skipped —
  the recording gap stays visible to the validator. (Does not occur in the
  Corradini corpus.)
- **Unmatched send.** A `send` whose `msgInstanceId` has no matching
  `receive` in its trace is emitted without `choreo:participant` /
  `choreo:target` relationships — the receiver is unrecorded.
- **Multi-cast over-connection (acceptable, intended).** When a multi-cast
  msgInstanceId repeats within a trace, every send is attributed to all
  receivers under that id (no occurrence matching). The validator surfaces
  these as C3/C6 events.

---

## Data attribution

The collaborative XES event logs in `data/input/` are from

> F. Corradini, S. Pettinari, B. Re, L. Rossi, F. Tiezzi. *A technique for
> discovering BPMN collaboration diagrams.* Software and Systems Modeling
> 23(6), 1323–1343 (2024).
> <https://bitbucket.org/proslabteam/colliery_validation/>

Cite the source when reusing the datasets.

The cross-check ground-truth files under `tests/data/`
(`collectivelog_*_collab.xes`) are derived artefacts published by Peña et al.
(*Inter-organizational collaborative BPMN 2.0 business process discovery*,
J. Intelligent Information Systems, 2024); verify their provenance
independently before redistributing. The conformance-evaluation script at
the repository root (`evaluate_conformance.py`) uses additional Peña-derived
files (`_chor.xes` choreography logs and `collog_*.bpmn` discovered models);
those live under `eval_artifacts/input/` with their own README.

---

## Package structure

```
src/xescol2ocelchor/    reader (XES), extractor (send → task), ocel writer, crosscheck, cli
tests/                  unit + integration tests; OCEL 2.0 schema validation
tests/data/             synthetic XES fixture + 7 _collab.xes ground-truth files
data/input/             Corradini collaborative event logs (tracked)
data/input_unique/      deduplicated counterparts (tracked)
data/output/            generated OCEL files (gitignored)
```

---

## Testing

```bash
uv run pytest
```

60+ tests, sub-second runtime. Covers reader / extractor / OCEL writer /
CLI / cross-check parametrised over all 7 datasets (asserting 100%
agreement) / integration against ground-truth event and object counts /
OCEL 2.0 JSON-schema validation on every dataset's output.
