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
  → reader      (constraint validation; hard gates C0, C2, C3, C11, C12, C14)
  → typing      (taskType = ⟨event type, initiator role, receiver role⟩;
                 scopeType = taskType of a scope's opening bracket)
  → projection  (one subtrace per scope object, keyed by containment context)
  → discovery   (stock pm4py inductive miner per sublog; post-order
                 composition of named subtrees; recursion detection)
  → export      (BPMN 2.0 choreography XML + diagram interchange;
                 renderable in bpmn-js / chor-js)
```

Roles are the logs' **object types, consumed verbatim** — the miner performs
no role inference, no label shortening, no domain-specific handling.

## Outputs (per input log, in `data/output/<log>/`)

| File | Content |
|------|---------|
| `discovered_model.bpmn` | The generalised choreography model (semantics + layout) |
| `process_tree.txt` | The discovered process tree as an indented s-expression: operators `→ × ↻ ∧`, `τ` for silent steps, `∇_{scope}` for named subtrees; leaves show the full discovery alphabet symbol `'event type' ⟨initiator→receiver⟩` |

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

## Testing

```bash
uv run --project ocelchormodel_RAD python -m pytest ocelchormodel_RAD/tests
```

The suite covers typing and event paths, discovery (pooling, context
separation, recursion detection against the audited baseline), export
(per-instance structural round-trip against the `ocelchormodel` reference
models, message labels, process-tree snapshot), and layout invariants.
