# Expected Output: swap_root_only.json

Transaction: `approve()`, sender `0x111...` → contract `0xCCC...`, no internal calls.

Per section 4.3: empty `internalTxs` → only the root choreography task event (no subchoreography).
Per section 4.3: no response message (EOA cannot receive return value).

txHash (without 0x): `aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111`

## Events (1)

| # | Event ID | Event Type | time | trace_order | E2O relations |
|---|----------|-----------|------|-------------|---------------|
| 0 | `e:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root` | `approve` | 2024-01-01T00:00:00.000Z | 0 | choreo:initiator → `0x1111111111111111111111111111111111111111` |
| | | | | | choreo:participant → `0xcccccccccccccccccccccccccccccccccccccccc` |
| | | | | | choreo:message → `call:req:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root` |
| | | | | | choreo:instance → `choreoInst:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111` |

## Objects (4)

### Participants (2)

| Object ID | Object Type |
|-----------|-------------|
| `0x1111111111111111111111111111111111111111` | `EOA` |
| `0xcccccccccccccccccccccccccccccccccccccccc` | `CA` |

### Messages (1)

| Object ID | Object Type | Attributes | O2O relations |
|-----------|-------------|------------|---------------|
| `call:req:aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111:root` | `approve call` | spender: `0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`, amount: 99999 | choreo:source → `0x1111111111111111111111111111111111111111` |
| | | | choreo:target → `0xcccccccccccccccccccccccccccccccccccccccc` |

### Choreography Instance (1)

| Object ID | Object Type |
|-----------|-------------|
| `choreoInst:0xaaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111` | `ChoreographyInstance` |

## Summary Counts

- Events: 1 (1 choreography task)
- Objects: 4 (2 participants, 1 message, 1 choreography instance)
- E2O relations: 4
- O2O relations: 2
