# Expected Output: swap_1.json

Transaction: `swapAssets()`, sender `0x111...` → contract `0xAAA...`.
Internal calls: `0_1` (leaf) — `0xAAA` calls `swap()` on `0xBBB` (SwapPool).

Per section 4.3: `internalTxs` is non-empty → root gets split into **request event** +
**scoping object** (no response, since EOA cannot receive return value).
Per section 4.4: `0_1` is a leaf → single choreography task event with request + response messages.
Per paper: child event `0_1` linked to the root's scoping object via `choreo:contained-by`.

txHash (without 0x): `abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca`

## Events (2)

| # | Event ID | Event Type | time | trace_order | E2O relations |
|---|----------|-----------|------|-------------|---------------|
| 0 | `e:abcabc...:root:request` | `Request swapAssets` | 2024-01-01T00:00:00.000Z | 0 | choreo:initiator → `0x1111111111111111111111111111111111111111` |
| | | | | | choreo:participant → `0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |
| | | | | | choreo:message → `call:req:abcabc...:root` |
| | | | | | choreo:instance → `choreographyInstance:0xabcabc...` |
| 1 | `e:abcabc...:0_1` | `swap` | 2024-01-01T00:00:00.001Z | 1 | choreo:initiator → `0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` |
| | | | | | choreo:participant → `0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` |
| | | | | | choreo:message → `call:req:abcabc...:0_1` |
| | | | | | choreo:message → `call:res:abcabc...:0_1` |
| | | | | | choreo:contained-by → `subchoreographyInstance:abcabc...:root` |
| | | | | | choreo:instance → `choreographyInstance:0xabcabc...` |

Event ordering: Request → [child: swap] (no Response since root is EOA-initiated).

## Objects (8)

### Participants (3)

| Object ID | Object Type | Notes |
|-----------|-------------|-------|
| `0x1111111111111111111111111111111111111111` | `EOA` | sender |
| `0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | `CA` | contractAddress (no contractCalledName available at top level) |
| `0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb` | `SwapPool` | contractCalledName from call frame 0_1 |

### Messages (3)

| Object ID | Object Type | Attributes | O2O relations |
|-----------|-------------|------------|---------------|
| `call:req:abcabc...:root` | `swapAssets call` | amountIn: 1000 | choreo:source → `0x111...` |
| | | | choreo:target → `0xAAA...` |
| `call:req:abcabc...:0_1` | `swap call` | amountIn: 1000 | choreo:source → `0xAAA...` |
| | | | choreo:target → `0xBBB...` |
| `call:res:abcabc...:0_1` | `swap call response` | output: `0x00...000003e3` | choreo:source → `0xBBB...` |
| | | | choreo:target → `0xAAA...` |

### Scoping Objects (1)

| Object ID | Object Type |
|-----------|-------------|
| `subchoreographyInstance:abcabc...:root` | `subchoreographyInstance` |

### Choreography Instance (1)

| Object ID | Object Type |
|-----------|-------------|
| `choreographyInstance:0xabcabc...` | `choreographyInstance` |

## Summary Counts

- Events: 2 (1 request, 1 choreography task)
- Objects: 8 (3 participants, 3 messages, 1 scoping, 1 choreography instance)
- E2O relations: 10
- O2O relations: 6
