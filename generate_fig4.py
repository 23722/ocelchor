#!/usr/bin/env python3
"""
Fig. 4 generation for:
  "Representing BPMN Choreographies in OCEL 2.0"

Discovers an Object-Centric Directly-Follows Graph (OC-DFG) from the
Tornado.Cash governance OCEL 2.0 log and saves publication-ready figures.

Filtering: the root-level "Request unlock" (EOA → Proxy, trace_order=0) is
excluded so the scope matches Fig. 3b (internal subchoreography calls only).
"""

import os
import pm4py

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH   = os.path.join(SCRIPT_DIR, 'data', '0x5e_0xcd4_ocel.json')
OUT_DIR    = os.path.join(SCRIPT_DIR, 'output')
OUT_PDF    = os.path.join(OUT_DIR, 'fig4_ocdfg.pdf')
OUT_SVG    = os.path.join(OUT_DIR, 'fig4_ocdfg.svg')

os.makedirs(OUT_DIR, exist_ok=True)

# ─── 1. Load OCEL 2.0 log ─────────────────────────────────────────────────────
ocel = pm4py.read_ocel2_json(LOG_PATH)

print("=== Loaded log ===")
print(f"  Events   : {len(ocel.events)}")
print(f"  Objects  : {len(ocel.objects)}")
print(f"  Relations: {len(ocel.relations)}")
print()

# ─── 2. Filter: remove root-level EOA-initiated event ─────────────────────────
# Event e:...:root:request is the outermost EOA→Proxy call.  It lies outside
# the subchoreography scope and is not shown in Fig. 3b.
EID_COL = 'ocel:eid'
OID_COL = 'ocel:oid'

ROOT_EID = (
    'e:cd49912d9a4783abc4aa1ca545091dccb4aa4899d191ed62a1fd610b89af1af9'
    ':root:request'
)

ocel.events    = (ocel.events   [ocel.events   [EID_COL] != ROOT_EID]
                  .reset_index(drop=True))
ocel.relations = (ocel.relations[ocel.relations[EID_COL] != ROOT_EID]
                  .reset_index(drop=True))

active_oids = set(ocel.relations[OID_COL])
ocel.objects = (ocel.objects[ocel.objects[OID_COL].isin(active_oids)]
                .reset_index(drop=True))

print("=== After filtering ===")
print(f"  Events   : {len(ocel.events)}")
print(f"  Objects  : {len(ocel.objects)}")
print()

# ─── 3. Discover OC-DFG ───────────────────────────────────────────────────────
ocdfg = pm4py.discover_ocdfg(ocel)

# ─── 4. Save ──────────────────────────────────────────────────────────────────
pm4py.save_vis_ocdfg(ocdfg, OUT_PDF)
print(f"Saved: {OUT_PDF}")

pm4py.save_vis_ocdfg(ocdfg, OUT_SVG)
print(f"Saved: {OUT_SVG}")
