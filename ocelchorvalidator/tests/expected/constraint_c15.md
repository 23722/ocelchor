# Test Plan: Constraint C15 (Initiator Continuity)

"The Initiator of a Choreography Activity MUST have been involved (as Initiator or Receiver) in the previous Choreography Activity." [BPMN 2.0.2, p. 336]

Events are grouped by `choreo:instance` and ordered by time within each group. For each consecutive pair (e_1, e_2):

- **Case 1 — Ascending into ancestor scope (one level down)**: o_sub(e_2) is a proper ancestor of o_sub(e_1). Let o_sub-1(e_2) be the child scope of o_sub(e_2) on the path to o_sub(e_1). Initiator of e_2 must appear as initiator or participant in any event enclosed by o_sub-1(e_2) or its descendant scopes.
- **Case 2 — Exiting to top level**: o_sub(e_1) exists but o_sub(e_2) does not. Same check but against the root ancestor scope of o_sub(e_1).
- **Case 3 — Same scope / descending / both top-level**: Otherwise. Initiator of e_2 must be initiator or participant of e_1.

---

## Positive cases

### swap_1 (2 events, 1 pair)

- root:request (top-level) → 0_1 (sub:root): Case 3 (descending). Init of e_2 = 0xaaa, roles of e_1 = {0x111, 0xaaa}. ✓
- `elements_checked == 1`, 0 violations

### swap_3 (8 events, 7 pairs)

All 7 pairs pass C15:
1. root:request → 0_1:request: Case 3 (descending into sub:root)
2. 0_1:request → 0_1_1:request: Case 3 (descending into sub:0_1)
3. 0_1_1:request → 0_1_1_1: Case 3 (descending into sub:0_1_1)
4. 0_1_1_1 → 0_1_1:response: Case 1 (ascending from sub:0_1_1 to sub:0_1)
5. 0_1_1:response → 0_1_2: Case 3 (same scope sub:0_1)
6. 0_1_2 → 0_1:response: Case 1 (ascending from sub:0_1 to sub:root)
7. 0_1:response → 0_2: Case 3 (same scope sub:root)

- `elements_checked == 7`, 0 violations

### swap_root_only (1 event, 0 pairs)

- No consecutive pairs → `elements_checked == 0`, passes vacuously

### swap_multi_tx (5 events, 2 instances)

- Instance 1: 1 event → 0 pairs
- Instance 2: 4 events → 3 pairs, all pass
- `elements_checked == 3`, 0 violations

---

## Negative cases

### Case 3 violation — same scope

Two top-level events where e_2's initiator is not initiator or participant of e_1.

### Case 3 violation — descending

e_1 is top-level, e_2 is in a scope. e_2's initiator is not in e_1's roles.

### Case 1 violation — ascending

e_1 is in a nested scope, e_2 is in an ancestor scope. e_2's initiator is not in the involved set of the ancestor scope's events.

### Case 2 violation — exiting to top level

e_1 is in a scope, e_2 is top-level. e_2's initiator is not in the involved set of the root ancestor scope's events.

---

## Edge cases

- **Empty log**: `elements_checked == 0`, passes
- **Single event**: `elements_checked == 0`, passes
- **Events without initiator**: Skipped (handled by C2)
