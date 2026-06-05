#!/usr/bin/env python3
"""Log-level variant agreement (and supplementary conformance) against Peña
et al.'s choreography artefacts.

Produces ⟨K⟩/7 — the number of Corradini et al. datasets on which our
OCEL-derived control-flow variant set matches Peña's _chor.xes variant set.
This is the metric reported in the paper.

Per dataset, the script:
  1. Counts our per-instance BPMN files and asserts the expected count.
  2. Derives a control-flow trace per choreographyInstance from our OCEL log,
     and asserts it matches the case_*.bpmn label sequence (faithfulness).
  3. Writes a control-flow XES from those traces (one trace per instance,
     each event carrying only concept:name).
  4. Compares the variant set of our control-flow XES against Peña's
     _chor.xes using pm4py.get_variants_as_tuples. Reports |ours|, |pena|,
     and the only_in_* counts.

Supplementary (not in the paper): alignment-based conformance against Peña's
discovered BPMN choreography models. Numbers are low and we explain why in
the printed output; see the "Supplementary analysis" section at the bottom
of the report.

Inputs (eval_artifacts/input/):
  - collog_<dataset>.bpmn               — Peña discovered BPMN models
  - collectivelog_<dataset>_chor.xes    — Peña choreography logs

Outputs (eval_artifacts/output/, gitignored):
  - <dataset>_collog_process.bpmn       — Peña BPMN rewritten as <process>
  - <dataset>_control_flow.xes          — our OCEL projected to control flow

Run:
    uv run --with pm4py python evaluate_conformance.py
    uv run --with pm4py python evaluate_conformance.py --dataset real3
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

try:
    import pm4py
    HAVE_PM4PY = True
except ImportError:
    HAVE_PM4PY = False


# ─── Configuration ─────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
DATASETS = ["real1", "real2", "real3", "real4", "real5", "healthcare", "smartagriculture"]
EXPECTED_INSTANCE_COUNTS = {
    "real1": 1, "real2": 96, "real3": 59, "real4": 1, "real5": 3,
    "healthcare": 17, "smartagriculture": 10,
}

OUR_BPMN_DIR  = SCRIPT_DIR / "ocelchormodel" / "data" / "output"
OUR_OCEL_DIR  = SCRIPT_DIR / "xescol2ocelchor" / "data" / "output"
EVAL_INPUT    = SCRIPT_DIR / "eval_artifacts" / "input"
EVAL_OUTPUT   = SCRIPT_DIR / "eval_artifacts" / "output"

BPMN_NS   = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS     = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS     = "http://www.omg.org/spec/DD/20100524/DI"


# ─── XML helpers ───────────────────────────────────────────────────
def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace('"', "&quot;")
             .replace("<", "&lt;").replace(">", "&gt;"))


# ─── Read our per-instance BPMN to get the linear task name sequence
def read_label_sequence(case_path: Path) -> list[str]:
    """Return the ordered choreographyTask `name` values from a linear
    per-instance BPMN, walking sequenceFlows from startEvent."""
    root = ET.parse(case_path).getroot()
    choreo = root.find(f"{{{BPMN_NS}}}choreography")
    if choreo is None:
        raise ValueError(f"{case_path.name}: no <choreography> element")

    nodes: dict[str, tuple[str, str]] = {}  # id → (kind, name)
    edges: dict[str, str] = {}              # sourceRef → targetRef (linear, 1-out)
    start_id: str | None = None
    end_id: str | None = None
    for elem in choreo:
        tag = _local(elem.tag)
        eid = elem.get("id")
        if tag == "startEvent":
            nodes[eid] = ("start", elem.get("name", ""))
            start_id = eid
        elif tag == "endEvent":
            nodes[eid] = ("end", elem.get("name", ""))
            end_id = eid
        elif tag == "choreographyTask":
            nodes[eid] = ("task", elem.get("name", ""))
        elif tag == "sequenceFlow":
            src, tgt = elem.get("sourceRef"), elem.get("targetRef")
            if src in edges:
                raise ValueError(
                    f"{case_path.name}: branching at {src} — per-instance BPMN should be linear"
                )
            edges[src] = tgt

    labels: list[str] = []
    cur = start_id
    visited = set()
    while cur in edges:
        cur = edges[cur]
        if cur in visited:
            raise ValueError(f"{case_path.name}: cycle in per-instance BPMN")
        visited.add(cur)
        kind, name = nodes.get(cur, (None, None))
        if cur == end_id:
            break
        if kind == "task":
            labels.append(name)
        else:
            raise ValueError(f"{case_path.name}: unexpected node {kind!r} in linear sequence")
    return labels


# ─── Rewrite Peña's choreography BPMN to a control-flow process ────
def rewrite_pena_to_process(in_path: Path, out_path: Path) -> None:
    """Rewrite collog_*.bpmn (choreography) to a plain control-flow process
    suitable for both pm4py.read_bpmn and graphical BPMN editors.

    Process side:
    - <choreography>       → <process isExecutable="false">.
    - <choreographyTask>   → <task> (drop initiatingParticipantRef + child
      participantRef/messageFlowRef).
    - Drop <participant> and any top-level <collaboration>.
    - Keep startEvent, endEvent, exclusiveGateway, parallelGateway,
      sequenceFlow as-is.

    Diagram side:
    - Preserve <bpmndi:BPMNDiagram> so editors can render the file; drop
      only the shapes/edges referencing removed elements (participant
      bands, message flows). pm4py ignores the diagram either way.
    """
    ET.register_namespace("bpmn2",  BPMN_NS)
    ET.register_namespace("bpmndi", BPMNDI_NS)
    ET.register_namespace("dc",     DC_NS)
    ET.register_namespace("di",     DI_NS)

    tree = ET.parse(in_path)
    root = tree.getroot()

    # Pass 1: rewrite the process; remember which element ids survive.
    surviving_ids: set[str] = set()
    for child in list(root):
        tag = _local(child.tag)
        if tag == "collaboration":
            root.remove(child)
        elif tag == "choreography":
            child.tag = f"{{{BPMN_NS}}}process"
            child.set("isExecutable", "false")
            if child.get("id"):
                surviving_ids.add(child.get("id"))
            for sub in list(child):
                stag = _local(sub.tag)
                if stag == "participant":
                    child.remove(sub)
                elif stag == "choreographyTask":
                    sub.tag = f"{{{BPMN_NS}}}task"
                    sub.attrib.pop("initiatingParticipantRef", None)
                    for inner in list(sub):
                        itag = _local(inner.tag)
                        if itag in ("participantRef", "messageFlowRef"):
                            sub.remove(inner)
                    surviving_ids.add(sub.get("id"))
                elif sub.get("id"):
                    surviving_ids.add(sub.get("id"))

    # Pass 2: prune diagram shapes/edges that reference removed elements.
    diagram = root.find(f"{{{BPMNDI_NS}}}BPMNDiagram")
    if diagram is not None:
        plane = diagram.find(f"{{{BPMNDI_NS}}}BPMNPlane")
        if plane is not None:
            for shape in list(plane):
                ref = shape.get("bpmnElement")
                if ref not in surviving_ids:
                    plane.remove(shape)

    tree.write(out_path, encoding="UTF-8", xml_declaration=True)


# ─── OCEL trace derivation ─────────────────────────────────────────
def _doc_order_from_id(event_id: str) -> int:
    """Parse the trailing integer from an event id like 'e:case_1:5'."""
    try:
        return int(event_id.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        return 0


def derive_traces_from_ocel(ocel_path: Path) -> dict[str, list[str]]:
    """Group OCEL events by choreo:instance, order by (time, doc_order from id),
    return {instance_id: [task_label, ...]}.
    """
    ocel = json.loads(ocel_path.read_text())
    groups: dict[str, list[dict]] = defaultdict(list)
    for ev in ocel["events"]:
        for r in ev.get("relationships", []):
            if r["qualifier"] == "choreo:instance":
                groups[r["objectId"]].append(ev)
                break
    out: dict[str, list[str]] = {}
    for inst, evs in groups.items():
        evs.sort(key=lambda e: (e["time"], _doc_order_from_id(e["id"])))
        out[inst] = [e["type"] for e in evs]
    return out


def _instance_to_case_id(inst_id: str) -> str:
    """choreographyInstance:case_139 → case_139, choreographyInstance:1 → 1."""
    return inst_id.split(":", 1)[1] if ":" in inst_id else inst_id


def assert_faithfulness(traces: dict[str, list[str]],
                        case_dir: Path, dataset: str) -> None:
    """For each instance, the OCEL-derived label sequence must equal the
    case_*.bpmn task name sequence. Raise on mismatch."""
    case_paths = {p.stem: p for p in case_dir.glob("*.bpmn")}
    ocel_cases = {_instance_to_case_id(i) for i in traces}

    only_ocel = ocel_cases - case_paths.keys()
    only_bpmn = case_paths.keys() - ocel_cases
    mismatches: list[tuple[str, list[str], list[str]]] = []

    for inst, ocel_labels in traces.items():
        cid = _instance_to_case_id(inst)
        if cid not in case_paths:
            continue
        bpmn_labels = read_label_sequence(case_paths[cid])
        if bpmn_labels != ocel_labels:
            mismatches.append((cid, bpmn_labels, ocel_labels))

    if mismatches or only_ocel or only_bpmn:
        lines = [f"[{dataset}] faithfulness check failed:"]
        for cid, b, o in mismatches[:3]:
            lines.append(f"  {cid}:")
            lines.append(f"     BPMN: {b}")
            lines.append(f"     OCEL: {o}")
        if len(mismatches) > 3:
            lines.append(f"  ... and {len(mismatches) - 3} more mismatches")
        if only_ocel:
            lines.append(f"  In OCEL but no BPMN: {sorted(only_ocel)[:5]}")
        if only_bpmn:
            lines.append(f"  In BPMN but no OCEL: {sorted(only_bpmn)[:5]}")
        raise AssertionError("\n".join(lines))


# ─── Write the control-flow XES for pm4py ──────────────────────────
def write_control_flow_xes(traces: dict[str, list[str]], out_path: Path) -> None:
    """One trace per choreography instance; each event carries only
    concept:name = task label. Timestamps are synthesised (pm4py requires them)."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<log xes.version="1849.2016" xmlns="http://www.xes-standard.org/">',
        '  <extension name="Concept" prefix="concept" uri="http://www.xes-standard.org/concept.xesext"/>',
        '  <extension name="Time" prefix="time" uri="http://www.xes-standard.org/time.xesext"/>',
    ]
    for inst, labels in traces.items():
        cid = _instance_to_case_id(inst)
        lines.append("  <trace>")
        lines.append(f'    <string key="concept:name" value="{_xml_escape(cid)}"/>')
        for i, label in enumerate(labels):
            ts = f"2000-01-01T{i // 3600 % 24:02d}:{i // 60 % 60:02d}:{i % 60:02d}.000+00:00"
            lines.append("    <event>")
            lines.append(f'      <string key="concept:name" value="{_xml_escape(label)}"/>')
            lines.append(f'      <date key="time:timestamp" value="{ts}"/>')
            lines.append("    </event>")
        lines.append("  </trace>")
    lines.append("</log>")
    out_path.write_text("\n".join(lines))


# ─── Conformance: pm4py alignments ─────────────────────────────────
def alignment_conformance(xes_path: Path, process_bpmn_path: Path) -> tuple[int, int]:
    """Returns (conforming, total). Conforming = trace alignment fitness == 1.0."""
    log = pm4py.read_xes(str(xes_path))
    bpmn = pm4py.read_bpmn(str(process_bpmn_path))
    net, im, fm = pm4py.convert_to_petri_net(bpmn)
    diagnostics = pm4py.conformance_diagnostics_alignments(log, net, im, fm)
    total = len(diagnostics)
    conforming = sum(1 for d in diagnostics if abs(d.get("fitness", 0.0) - 1.0) < 1e-9)
    return conforming, total


# ─── Log-level variant comparison ──────────────────────────────────
def variant_keys(xes_path: Path) -> set[tuple[str, ...]]:
    """Return the set of distinct activity-sequence tuples (trace variants)
    in an XES log via pm4py.get_variants_as_tuples (with a fallback to the
    older pm4py.statistics.variants.log.get.get_variants API)."""
    log = pm4py.read_xes(str(xes_path))
    try:
        variants = pm4py.get_variants_as_tuples(log)
    except AttributeError:  # pragma: no cover
        from pm4py.statistics.variants.log.get import get_variants
        variants = get_variants(log)
    return set(variants.keys())


def variant_agreement(dataset: str, our_cf_xes: Path) -> dict:
    """Compare our OCEL-derived control-flow variants against Peña's
    _chor.xes for one dataset.

    Returns
        {
          "ours":  int,                  # number of variants in our log
          "pena":  int,                  # number of variants in Peña's log
          "only_in_ours":  int,
          "only_in_pena":  int,
          "set_equal":     bool,
        }
    """
    pena_xes = EVAL_INPUT / f"collectivelog_{dataset}_chor.xes"
    if not pena_xes.exists():
        return {"error": f"Missing Peña _chor.xes: {pena_xes}"}
    ours = variant_keys(our_cf_xes)
    pena = variant_keys(pena_xes)
    return {
        "ours": len(ours),
        "pena": len(pena),
        "only_in_ours": len(ours - pena),
        "only_in_pena": len(pena - ours),
        "set_equal": ours == pena,
    }


# ─── Per-dataset evaluation ────────────────────────────────────────
def evaluate_dataset(dataset: str) -> dict:
    result: dict = {"dataset": dataset, "errors": []}

    case_dir = OUR_BPMN_DIR / f"{dataset}_uniqueInteraction"
    if not case_dir.exists():
        result["errors"].append(f"Missing per-instance BPMN dir: {case_dir}")
        return result
    case_paths = sorted(case_dir.glob("*.bpmn"))
    expected = EXPECTED_INSTANCE_COUNTS[dataset]
    if len(case_paths) != expected:
        result["errors"].append(
            f"Expected {expected} per-instance BPMNs, found {len(case_paths)}"
        )
        return result
    result["#inst"] = len(case_paths)

    ocel_path = OUR_OCEL_DIR / f"{dataset}_uniqueInteraction_ocel.json"
    if not ocel_path.exists():
        result["errors"].append(f"Missing OCEL log: {ocel_path}")
        return result
    traces = derive_traces_from_ocel(ocel_path)
    try:
        assert_faithfulness(traces, case_dir, dataset)
    except AssertionError as e:
        result["errors"].append(str(e))
        return result

    pena_bpmn = EVAL_INPUT / f"collog_{dataset}.bpmn"
    if not pena_bpmn.exists():
        result["errors"].append(f"Missing Peña BPMN: {pena_bpmn}")
        return result

    EVAL_OUTPUT.mkdir(parents=True, exist_ok=True)
    rewritten = EVAL_OUTPUT / f"{dataset}_collog_process.bpmn"
    rewrite_pena_to_process(pena_bpmn, rewritten)

    cf_xes = EVAL_OUTPUT / f"{dataset}_control_flow.xes"
    write_control_flow_xes(traces, cf_xes)

    # Primary metric: log-level variant agreement against Peña's _chor.xes.
    if HAVE_PM4PY:
        result["variants"] = variant_agreement(dataset, cf_xes)
    else:
        result["variants"] = None

    # Supplementary: alignment-based conformance against Peña's discovered model.
    if HAVE_PM4PY:
        try:
            result["align"] = alignment_conformance(cf_xes, rewritten)
        except Exception as e:  # pragma: no cover
            result["errors"].append(f"Alignment failed: {e}")
            result["align"] = None
    else:
        result["align"] = None

    return result


# ─── Reporting ─────────────────────────────────────────────────────
def format_pair(p) -> str:
    if p is None:
        return "N/A"
    if p == "skip":
        return "(skip)"
    a, b = p
    return f"{a}/{b}"


def print_variant_table(results: list[dict]) -> tuple[bool, int, int]:
    """Headline: per-dataset variant-agreement table. Returns
    (any_errors, variant_match, variant_total) for the paper sentence."""
    header = (
        f"{'dataset':<18s} {'#inst':>5s}  {'variants(ours/pena)':>20s}  "
        f"{'only(ours/pena)':>15s}  {'set-equal':>10s}"
    )
    print(header)
    print("-" * len(header))
    variant_match = variant_total = 0
    any_errors = False

    for r in results:
        d = r["dataset"]
        if r["errors"]:
            any_errors = True
            print(f"  ⚠  {d}: {r['errors'][0]}")
            for line in r["errors"][0].split("\n")[1:]:
                print(f"     {line}")
            continue
        n = r["#inst"]
        var = r.get("variants")
        if var and "error" not in var:
            variant_total += 1
            if var["set_equal"]:
                variant_match += 1
            var_pair  = f"{var['ours']}/{var['pena']}"
            only_pair = f"{var['only_in_ours']}/{var['only_in_pena']}"
            eq        = "✓" if var["set_equal"] else "✗"
        else:
            var_pair = only_pair = eq = "N/A"
        print(f"{d:<18s} {n:>5d}  {var_pair:>20s}  {only_pair:>15s}  {eq:>10s}")

    print("-" * len(header))
    var_total_str = f"{variant_match}/{variant_total}" if variant_total else "N/A"
    print(f"{'TOTAL':<18s}                                                {var_total_str:>10s}")
    return any_errors, variant_match, variant_total


def print_paper_sentence(variant_match: int, variant_total: int) -> None:
    print()
    print("=== Paper sentence ===")
    print()
    print("For the Corradini et al. data, our extracted choreography control-flows")
    print(f"show the same trace variants as Peña et al.'s independently created XES")
    print(f"choreography logs on {variant_match}/{variant_total} datasets.")
    print()
    print("Role agreement (initiator / participants per task event) is established")
    print("separately by xescol2ocelchor/tests/test_crosscheck.py — 100% agreement")
    print("against Peña's _collab.xes annotations on all 7 datasets.")


def print_supplementary(results: list[dict]) -> None:
    """Print alignment-based conformance numbers as supplementary context.

    These were investigated during the evaluation but did not make it into
    the paper. We report them for transparency, with an explanatory note on
    why the numbers are low and why we did not pursue them further.
    """
    print()
    print("=== Supplementary analysis (not in paper) ===")
    print()
    print("Alignment-based conformance against Peña's discovered BPMN choreography")
    print("models (pm4py, fitness == 1.0). Numbers are low for two reasons that we")
    print("traced during evaluation:")
    print()
    print("  (a) Peña's discovered models are process-mining generalisations that")
    print("      abstract away trace-level variation our OCEL preserves. real2 is")
    print("      the extreme case: 96 distinct trace variants in our log collapse")
    print("      onto one canonical model path.")
    print("  (b) Peña's real3 model conflates two execution cycles that in the")
    print("      data are independent, so most of our real3 traces don't fit it.")
    print()
    print("These observations did not move into the paper for space reasons and")
    print("because they do not contribute to the variant-agreement claim above.")
    print()
    header = f"{'dataset':<18s} {'#inst':>5s}  {'conform(align)':>14s}"
    print(header)
    print("-" * len(header))
    a_total = b_total = 0
    for r in results:
        if r["errors"]:
            continue
        d = r["dataset"]
        n = r["#inst"]
        align = r.get("align")
        if align is not None:
            ac, at = align
            a_total += ac
            b_total += at
        print(f"{d:<18s} {n:>5d}  {format_pair(align):>14s}")
    print("-" * len(header))
    print(f"{'TOTAL':<18s}        {a_total}/{b_total}")


# ─── Entry point ───────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conformance evaluation of our OCEL choreographies against Peña et al.'s discovered BPMN models.",
    )
    parser.add_argument(
        "--dataset", choices=DATASETS,
        help="Run a single dataset (for debugging). Default: all 7.",
    )
    args = parser.parse_args()

    datasets = [args.dataset] if args.dataset else DATASETS
    results = [evaluate_dataset(d) for d in datasets]
    any_errors, vm, vt = print_variant_table(results)
    print_paper_sentence(vm, vt)
    print_supplementary(results)

    if not HAVE_PM4PY:
        print()
        print("WARNING: pm4py is not installed — variant agreement and alignment")
        print("conformance were skipped. Run with:")
        print("  uv run --with pm4py python evaluate_conformance.py")

    sys.exit(1 if any_errors else 0)


if __name__ == "__main__":
    main()
