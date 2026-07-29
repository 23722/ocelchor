#!/usr/bin/env python3
"""
Fig. 4 generation for:
  "Representing BPMN Choreographies in OCEL 2.0"

Discovers an Object-Centric Directly-Follows Graph (OC-DFG) from the
Tornado.Cash governance OCEL 2.0 log and saves publication-ready figures.
All events of the choreography instance are included (incl. the root-level
"Request unlock [Proxy]").

pm4py's color assignment is hash-order-dependent; SEED pins it so the script
reproduces the chosen figure deterministically.
"""

import os
import random
import sys

# ─── Color seed ───────────────────────────────────────────────────────────────
# PYTHONHASHSEED only takes effect at interpreter start, so re-exec once.
SEED = 5
if os.environ.get('PYTHONHASHSEED') != str(SEED):
    os.execvpe(sys.executable, [sys.executable] + sys.argv,
               {**os.environ, 'PYTHONHASHSEED': str(SEED)})
random.seed(SEED)

import pm4py

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH   = os.path.join(SCRIPT_DIR, 'trace2ocelchor', 'data', 'output',
                          '0x5e_cd49912_ocel.json')
OUT_PDF    = os.path.join(SCRIPT_DIR, 'fig4_ocdfg.pdf')
OUT_SVG    = os.path.join(SCRIPT_DIR, 'fig4_ocdfg.svg')

# ─── 1. Load OCEL 2.0 log ─────────────────────────────────────────────────────
ocel = pm4py.read_ocel2_json(LOG_PATH)

print("=== Loaded log ===")
print(f"  Events   : {len(ocel.events)}")
print(f"  Objects  : {len(ocel.objects)}")
print(f"  Relations: {len(ocel.relations)}")
print()

# ─── 2. Filter: drop the root scope object ────────────────────────────────────
# Under request/response-inside-scope bracketing the root request event is
# contained in the root scope it opens.  The running-example figures omit that
# root scoping object; only the inner sub-choreography scope is shown.
OID_COL, OID2_COL, TYPE_COL = 'ocel:oid', 'ocel:oid_2', 'ocel:type'

root_scopes = set(ocel.objects[
    (ocel.objects[TYPE_COL] == 'subchoreographyInstance')
    & (ocel.objects[OID_COL].str.endswith(':root'))
][OID_COL])

ocel.objects   = (ocel.objects  [~ocel.objects  [OID_COL].isin(root_scopes)]
                  .reset_index(drop=True))
ocel.relations = (ocel.relations[~ocel.relations[OID_COL].isin(root_scopes)]
                  .reset_index(drop=True))
ocel.o2o       = (ocel.o2o[~(ocel.o2o[OID_COL].isin(root_scopes)
                             | ocel.o2o[OID2_COL].isin(root_scopes))]
                  .reset_index(drop=True))

# ─── 3. Discover OC-DFG ───────────────────────────────────────────────────────
ocdfg = pm4py.discover_ocdfg(ocel)

# ─── 3. Save ──────────────────────────────────────────────────────────────────
pm4py.save_vis_ocdfg(ocdfg, OUT_PDF)
print(f"Saved: {OUT_PDF}")

pm4py.save_vis_ocdfg(ocdfg, OUT_SVG)
print(f"Saved: {OUT_SVG}")
