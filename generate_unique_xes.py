#!/usr/bin/env python3
"""
Deduplicate the Pena et al. XES collaborative event logs by choreography
behavior. Companion to xescol2ocelchor.

For each collectivelog_<name>.xes in xescol2ocelchor/data/input/, write a
deduplicated collectivelog_<name>.xes to xescol2ocelchor/data/input_unique/
containing exactly one representative trace per distinct choreography-relevant
variant.

Variant key: tuple of (concept:name) over message events only — i.e. events
whose msgType is "send" or "receive". Internal (non-message) events are
ignored when deciding equivalence: two traces with identical message
exchanges but different internal-event patterns are considered the same
choreography variant. Receives are kept in the key (not just sends) so that
two traces with the same send sequence but different recipients do not
collapse into one.

Each kept representative trace retains ALL its original events (sends,
receives, AND internal events) so xescol2ocelchor downstream can still match
sends to receives via msgInstanceId and can still emit kept internal events
when --keep-internal-events is active.

Traces with zero send events are dropped — they have no choreography
behavior to represent. Empty traces (zero events) are also dropped.

Run:
    uv run --with pm4py python generate_unique_xes.py
"""

import os
from collections import OrderedDict

import pm4py
from pm4py.objects.log.obj import EventLog

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR  = os.path.join(SCRIPT_DIR, 'xescol2ocelchor', 'data', 'input')
OUT_DIR    = os.path.join(SCRIPT_DIR, 'xescol2ocelchor', 'data', 'input_unique')

DATASETS = [
    'real1', 'real2', 'real3', 'real4', 'real5',
    'healthcare', 'smartagriculture',
]

os.makedirs(OUT_DIR, exist_ok=True)

# ─── Deduplicate ──────────────────────────────────────────────────────────────
print(f"{'dataset':<18s} {'traces':>7s} {'unique':>7s} {'no-send':>7s} {'empty':>7s}")
print('-' * 50)

for name in DATASETS:
    in_path  = os.path.join(INPUT_DIR, f'collectivelog_{name}.xes')
    out_path = os.path.join(OUT_DIR,   f'collectivelog_{name}.xes')

    log = pm4py.read_xes(in_path, return_legacy_log_object=True)

    seen: "OrderedDict[tuple, object]" = OrderedDict()
    empty = 0
    no_send = 0
    for trace in log:
        if len(trace) == 0:
            empty += 1
            continue
        if not any(ev.get('msgType') == 'send' for ev in trace):
            no_send += 1
            continue
        variant = tuple(ev['concept:name']
                        for ev in trace
                        if ev.get('msgType') in ('send', 'receive'))
        if variant not in seen:
            seen[variant] = trace

    unique = EventLog(
        list(seen.values()),
        attributes=log.attributes,
        extensions=log.extensions,
        classifiers=log.classifiers,
        omni_present=log.omni_present,
    )
    pm4py.write_xes(unique, out_path)

    print(f"{name:<18s} {len(log):>7d} {len(unique):>7d} {no_send:>7d} {empty:>7d}")

print()
print(f"Wrote deduplicated logs to: {OUT_DIR}")
