# ocelchormodel_RAD

Discovers **one generalised BPMN 2.0 choreography model per OCEL 2.0
choreography log** — a RAD-inspired, hierarchy-aware adaptation of the
inductive-miner framework. Where the sibling `ocelchormodel` renders each
choreography *instance*, this miner pools all instances of a log into a
single model with roles as participant bands.

The miner is **domain-agnostic**: all domain knowledge arrives through the
log per the interface contract (event types, object types, choreography
relationships). Nothing blockchain-specific lives in this package; the same
code discovers models from blockchain-derived and XES-derived logs.

For repository-wide context see the [root README](../README.md); for how the
blockchain extractor types participants and events, see the
[trace2ocelchor README](../trace2ocelchor/README.md).

---

## Pipeline

```
OCEL 2.0 choreography log
  → reader      (constraint validation; hard gates C0, C2, C3, C11, C12, C14 —
                 C3 by shape: multicast aborts, an unrecorded receiver is
                 tolerated with the reserved empty role and a warning)
  → typing      (taskType = ⟨event type, initiator role, receiver role⟩;
                 scopeType = ⟨label, initiator role, receiver role⟩ — label
                 from the scoping object's name attribute, else derived from
                 the first task event; roles from that same first task event)
  → projection  (one subtrace per scope object, keyed by containment context)
  → discovery   (stock pm4py inductive miner per sublog; post-order
                 composition of named subtrees; recursion detection)
  → export      (BPMN 2.0 choreography XML + diagram interchange;
                 renderable in bpmn-js / chor-js)
```

Roles are the logs' **object types, consumed verbatim** — the miner performs
no role inference, no label shortening, no domain-specific handling.

## Usage

```bash
cd ocelchormodel_RAD
uv run ocelchormodel-rad <ocel.json> [<ocel.json> ...] [-o OUT_DIR]
```

One subfolder per input log is written under `OUT_DIR` (default `output`).
A log that violates a hard-gate constraint is reported on stderr and
skipped; its subfolder holds only a `REFUSED.txt` naming the violated
gate, the remaining inputs still run, and the exit code is nonzero.
C3 is gated by *shape*: an event with **more than one receiver**
(multicast) aborts the log — which role enters the task type is genuinely
undefined, and any choice would silently drop a receiver — while an event
with **no recorded receiver** is tolerated: it is typed with the reserved
empty participant role (rendered as an empty band), the C3 violation stays
visible in the `constraints` section of `diagnostics.json`, and a
`WARNINGS.txt` names the affected events. Reported, never repaired.
There are **no tuning flags by design** — discovery is deterministic and
diagnostics never change the model.

## Outputs (per input log, in `data/output/<log>/`)

| File | Content |
|------|---------|
| `discovered_model.bpmn` | The generalised choreography model (semantics + layout) |
| `process_tree.txt` | The discovered process tree as an indented s-expression: operators `→ × ↻ ∧`, `τ` for silent steps, `∇_{scope} ⟨initiator→receiver⟩` for named subtrees; leaves show `'event type' ⟨initiator→receiver⟩`. Every symbol prints its full type — the ∇ pair is the role pair of the scope's first task event, so scopes with the same label but different openers (an outer call vs. a re-entrant self-call) stay distinguishable on the ∇ line |
| `diagnostics.json` | Diagnostics D1–D13 (below) plus the non-blocking validator constraint summary |
| `WARNINGS.txt` | Only when C3 missing-receiver events were tolerated: names the events typed with the reserved empty role |

(A refused log's subfolder holds only `REFUSED.txt` with the violated gate.)

## Message labels

Choreography tasks carry message envelopes whose labels are **generalised
per task type and direction** over all pooled occurrences. The label is
resolved through a preference chain of plain OCEL-level data — no domain
knowledge:

1. **Payload schema** — the attribute *names* of the collected message
   objects, where all occurrences agree (e.g. `to, amount` for a token
   transfer). Empty attribute names (producers store unnamed source
   parameters verbatim) carry no display value and are dropped first.
2. **Message kind** — the message *object type*, where no payload schema
   exists but all occurrences share one kind (e.g. `Offer`, `Confirmation`).
3. **Generic** `input` / `output`.

Incompatible payload structures (or, lacking those, incompatible kinds)
within one task type yield the generic label and are flagged as a message
conflict (diagnostic D8); the task type is never split over message
differences.

The chain covers both current log families without configuration, because
the producers agree on where message information lives — payload fields in
message-object *attributes*, the message kind in the message-object *type*:

| | blockchain-derived logs | XES-derived logs |
|---|---|---|
| payload (attributes) | decoded call parameters → labels like `to, amount` | *(sources carry no message payload)* |
| kind (object type) | `<function> call` / `… call response` — used when all parameters are unnamed | `Offer`, `Confirmation`, … → the label |
| generic | undecodable / conflicting cases | messages without kind |

## Sub-choreography labels

A sub-choreography is typed like a task — label + participants. The label
resolves through a two-rung chain of plain OCEL-level data:

1. **Stored name** — the scoping object's `name` attribute, where present:
   an explicit sub-choreography label supplied at extraction.
2. **Derived** — the type of the scope's first task event, with the kind
   prefix (`Request `/`Respond to `) stripped.

Both roles always come from the scope's ≻-first *choreography task event*
(one carrying initiator and participant edges) — never from internal
non-choreography events, which cannot supply them. A scope containing no
task event at all is untypeable and aborts the log: reported, never
repaired. Diagnostic D2 certifies the derivation (first task event = the
request bracket); it applies on both rungs, since a stored name does not
exempt the roles.

Because the roles are part of the type, identical stored names never merge
scopes opened by different role pairs — Beanstalk's outer `exchange`
(attacker → pool) and its re-entrant `exchange` (pool → pool) stay separate
submodels even though both scoping objects carry the same name. The same
role component keys recursion detection (D12: ⟨label, receiver role⟩
recurring on its own containment path).

As with roles (the object type, consumed verbatim) and message labels
(chain above), the rungs advance on *absence*, not disagreement — each
lookup location has exactly one auditing diagnostic: D2 for scope labels,
D4 for the role slot, D8 for message content.

## Same-role interactions (doppelgänger participants)

A choreography task whose initiator and receiver map to the **same role**
(two contracts of one named type interacting, or a genuine self-call) cannot
reference one participant twice — BPMN participant bands must be distinct,
and renderers such as chor-js reject duplicate references. The exporter
therefore emits a second participant element with the **same display name**
(a *doppelgänger*, internal id suffix `_2`) rather than merging or renaming.
This is the conservative reading of BPMN's distinctness requirement: the
model shows exactly what the log asserts — the same role on both sides —
without inventing a new role. Genuine self-calls are independently flagged
by validator constraint **C4**, so a doppelgänger band in a model is
traceable to its cause via the `constraints` section of `diagnostics.json`.

## Diagnostics (D1–D13)

`diagnostics.json` reports thirteen diagnostics in four groups, following
the argument *trust the data → trust the typing → trust the control flow →
read the findings*. Diagnostics **never change the model**; they tell the
analyst how much to trust it and where to look.

**Group I — encoding & data trust** (does the log honour the interface
contract?)

| D | Diagnostic | What it means |
|---|-----------|----------------|
| D1 | Ordering determinism | Timestamps totally order every instance; any residual tie would make discovery non-deterministic. Expect `passed`. |
| D2 | Scope openers | Every scope's first task event is its request bracket, certifying the role/label derivation as branch-invariant (checked even when the label comes from a stored name). A scope with no task event at all is untypeable and aborts the log — reported, never repaired. Expect zero. |
| D3 | Bracket completeness | Scopes without their own response bracket, split into **expected** (the root-scope asymmetry: an outermost initiator that never receives a reply) and **unexpected** (interior scopes — an encoding defect). |
| D4 | Identity-as-label | Event types whose discriminator is a participant **object id** (an unnamed participant): the type is as fine-grained as the instance level, so pooling across such participants is impossible by construction. |

**Group II — typing & generalization** (what did the typing decisions cost
and buy?)

| D | Diagnostic | What it means |
|---|-----------|----------------|
| D5 | Event-type fan-out | One bare activity name split into several participant-discriminated event types (e.g. `balanceOf` per token). Measures what participant-aware typing separates. |
| D6 | Task-type fan-out | One event type used between several role pairs. Measures what role-banding separates on top of event types. |
| D7 | Scope pooling | Occurrences ÷ variants per scope type: how much repetition the hierarchy pools into one submodel. High ratios are where generalisation actually happens. |
| D8 | Message merging | Task types whose pooled message payloads/kinds disagree; the label falls back to generic and the conflict is listed. Measures what label generalisation glosses over. |

**Group III — control-flow trust** (audit of inductive-miner fallthroughs;
signature-based on the tree and its sublogs, no pm4py internals)

| D | Diagnostic | What it means |
|---|-----------|----------------|
| D9 | Parallelism witnesses | Per `∧` and branch pair: is the interleaving witnessed in **both** directions in the sublog? A zero-reversal pair *proves* the `∧` did not come from a parallel cut (which requires bidirectional evidence) but from a fallthrough — localized, explainable imprecision. |
| D10 | Unrestricted repetition | Loops with a silent body (`↻(τ, …)`, flower-shaped): the model permits arbitrary repetition the log never restricted — the strict-tau-loop/flower fallthrough signature. |
| D11 | Choice realizability | Interior choices whose branches start with different initiating roles: locally, each participant must know which branch was taken (realizability concern, reported not repaired). |

**Group IV — process findings** (what the models reveal)

| D | Diagnostic | What it means |
|---|-----------|----------------|
| D12 | Recursion / re-entrancy | Scope types recurring on their own containment path (direct or indirect), with depths — on the blockchain logs this includes the Beanstalk read-only-reentrancy pattern. |
| D13 | Cross-depth participants | The same concrete object appearing in ancestor **and** descendant scopes under different task types — hierarchical role reuse that flat models cannot show. |

## Testing

```bash
uv run --project ocelchormodel_RAD python -m pytest ocelchormodel_RAD/tests
```

The suite covers typing and event paths, discovery (pooling, context
separation, recursion detection against the audited baseline), export
(per-instance structural round-trip against the `ocelchormodel` reference
models, message labels, process-tree snapshot), layout invariants,
diagnostics (pinned acceptance values on the real logs plus synthetic
cases), and the CLI (output triple, hard-gate failure path).
