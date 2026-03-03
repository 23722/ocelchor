# Test Plan: Constraints C5–C10 (Message Constraints)

## C5 — Message source uniqueness

Each message object linked to an event has exactly one `choreo:source`.

### Positive cases

- **swap_1**: All 3 messages have exactly 1 `choreo:source` → 0 violations
- **swap_3**: All messages have exactly 1 source → 0 violations

### Negative cases

- **No source**: Message with 0 `choreo:source` → violation with event ID and message object ID
- **Two sources**: Message with 2 `choreo:source` → violation

---

## C6 — Message target uniqueness

Each message object linked to an event has exactly one `choreo:target`.

### Positive cases

- **swap_1**: All 3 messages have exactly 1 `choreo:target` → 0 violations

### Negative cases

- **No target**: Message with 0 `choreo:target` → violation
- **Two targets**: Message with 2 `choreo:target` → violation

---

## C7 — Initiating message

Each event has exactly one message whose source is the event's initiator.

### Positive cases

- **swap_1**: Root event: `call:req:...:root` has source 0x111 = initiator. Swap event: `call:req:...:0_1` has source 0xaaa = initiator. Each has exactly one such message. → 0 violations
- **swap_root_only**: 1 event with 1 message sourced by initiator → 0 violations

### Negative cases

- **No initiating message**: Event with messages but none sourced by the initiator → violation
- **Two initiating messages**: Event with 2 messages both sourced by the initiator → violation

---

## C8 — At most one return message

Each event has at most one message whose source is the participant (non-initiator).

### Positive cases

- **swap_1**: Root event has 0 return messages (only initiating). Swap event has 1 return message (`call:res:...:0_1` sourced by 0xbbb = participant). → 0 violations
- **swap_root_only**: 0 return messages → 0 violations

### Negative cases

- **Two return messages**: Event with 2 messages both sourced by the participant → violation

---

## C9 — Initiating message target

The initiating message (source = initiator) must target the participant.

### Positive cases

- **swap_1**: Root: `call:req:...:root` source=0x111 (initiator), target=0xaaa (participant) ✓. Swap: `call:req:...:0_1` source=0xaaa (initiator), target=0xbbb (participant) ✓.

### Negative cases

- **Wrong target**: Initiating message targets an object other than the participant → violation

---

## C10 — Return message target

The return message (source = participant) must target the initiator.

### Positive cases

- **swap_1**: Swap event: `call:res:...:0_1` source=0xbbb (participant), target=0xaaa (initiator) ✓.

### Negative cases

- **Wrong target**: Return message targets an object other than the initiator → violation

### Edge case

- **No return message**: Event with only an initiating message → C10 passes (nothing to check for that event)

---

## Edge case: empty log

- All C5–C10 return `elements_checked == 0`, `passed == True`
