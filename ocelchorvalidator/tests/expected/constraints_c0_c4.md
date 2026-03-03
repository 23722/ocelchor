# Test Plan: Constraints C0–C4 (Task Structure)

## Data classes

- `Violation(constraint, message, event_id, object_id)` — immutable record of a single violation
- `ConstraintResult(constraint_id, elements_checked, violations)` — result with `.passed` and `.num_violations` properties
- `validate_all(idx)` returns `dict[str, ConstraintResult]` for all 16 constraints
- `validate(idx, constraint_ids)` returns results for specified constraints only

---

## C0 — Instance linking

Every choreography event has exactly one `choreo:instance` relation.

### Positive cases

- **swap_1**: 2 events, each with exactly 1 `choreo:instance` → 0 violations, `elements_checked == 2`
- **swap_3**: 8 events → 0 violations, `elements_checked == 8`
- **swap_root_only**: 1 event → 0 violations, `elements_checked == 1`

### Negative cases

- **No instance**: Event with 0 `choreo:instance` relations → violation with event ID
- **Two instances**: Event with 2 `choreo:instance` relations → violation with event ID

---

## C1 — Message participation

For every event and message: message source/target must be the event's initiator or participant.

### Positive cases

- **swap_1**: Root event has 1 message (source=EOA=initiator, target=CA=participant). Swap event has 2 messages (req source=CA=initiator, req target=SwapPool=participant; res source=SwapPool=participant, res target=CA=initiator). 0 violations.
- **swap_3**: All message source/target objects match initiator/participant of their event. 0 violations.

### Negative cases

- **Message source not in event roles**: Message with `choreo:source` pointing to an object that is neither `choreo:initiator` nor `choreo:participant` of the event → violation mentioning event ID and message object ID.
- **Message target not in event roles**: Message with `choreo:target` pointing to an object that is neither role → violation.

---

## C2 — Single initiator

Each choreography event has exactly one `choreo:initiator` relation.

### Positive cases

- **swap_1**: 2 events, each with exactly 1 `choreo:initiator` → 0 violations
- **swap_root_only**: 1 event → 0 violations

### Negative cases

- **No initiator**: Event with 0 `choreo:initiator` → violation
- **Two initiators**: Event with 2 `choreo:initiator` → violation

---

## C3 — Single participant

Each choreography event has exactly one `choreo:participant` relation.

### Positive cases

- **swap_1**: 2 events, each with exactly 1 `choreo:participant` → 0 violations

### Negative cases

- **No participant**: Event with 0 `choreo:participant` → violation
- **Two participants**: Event with 2 `choreo:participant` → violation

---

## C4 — Role exclusivity

For each event, the `choreo:initiator` and `choreo:participant` must be different objects.

### Positive cases

- **swap_1**: Initiators and participants are always different addresses → 0 violations

### Negative cases

- **Same object as initiator and participant**: Event with `choreo:initiator → 0xAAA` and `choreo:participant → 0xAAA` → violation with event ID and object ID

---

## Edge case: empty log

- All constraints return `elements_checked == 0`, `violations == []`, `passed == True`
