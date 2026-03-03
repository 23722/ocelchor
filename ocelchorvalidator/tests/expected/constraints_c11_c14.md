# Test Plan: Constraints C11–C14 (Subchoreography / Containment Hierarchy)

## C11 — Containment uniqueness

Each event has at most one `choreo:contained-by` relation.

### Positive cases

- **swap_1**: Root event has 0, swap event has 1 → 0 violations, `elements_checked == 2`
- **swap_3**: 1 top-level event, 7 contained (each with exactly 1) → 0 violations
- **swap_root_only**: 1 event, 0 `choreo:contained-by` → 0 violations

### Negative cases

- **Two contained-by**: Event with 2 `choreo:contained-by` relations → violation with event ID

---

## C12 — Non-empty scope

Every scoping object (Subchoreography) has at least one event contained in it.

### Positive cases

- **swap_1**: 1 scoping object `sub:...:root`, 1 event contained → 0 violations, `elements_checked == 1`
- **swap_3**: 3 scoping objects, each has at least 1 event → 0 violations
- **swap_root_only**: 0 scoping objects → `elements_checked == 0`, passes vacuously

### Negative cases

- **Empty scope**: Scoping object with no events having `choreo:contained-by` pointing to it → violation with object ID

---

## C13 — Instance consistency

All events contained by the same scoping object must link to the same choreography instance.

### Positive cases

- **swap_1**: 1 event in `sub:...:root`, links to same instance → 0 violations
- **swap_3**: Multiple events per scope, all link to same instance → 0 violations
- **swap_root_only**: No scoping objects → passes vacuously

### Negative cases

- **Mixed instances**: Two events contained by same scoping object but linking to different `choreo:instance` objects → violation

---

## C14 — Nesting structure

Three sub-checks:
1. Each scoping object has at most one incoming `choreo:contains` relation
2. Events in nested scopes must share the same `choreo:instance` as events in the parent scope
3. The `choreo:contains` graph is acyclic

### Positive cases

- **swap_1**: 1 scoping object, no nesting → 0 violations
- **swap_3**: 3 scoping objects, chain `root → 0_1 → 0_1_1`, all events same instance → 0 violations
- **swap_root_only**: No scoping objects → passes vacuously

### Negative cases

- **Two parents**: Scoping object with 2 incoming `choreo:contains` → violation
- **Instance mismatch across nesting**: Parent scope events link to instance A, child scope events link to instance B → violation
- **Cycle**: `sub_a × choreo:contains × sub_b` and `sub_b × choreo:contains × sub_a` → violation

---

## Edge case: empty log

- All C11–C14 return `elements_checked == 0`, `passed == True`
