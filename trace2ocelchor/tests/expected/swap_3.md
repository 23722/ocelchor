# Expected Output: swap_3.json

Transaction: `swap()`, sender `0x111...` → contract `0xAAA...`.

Call tree:
```
EOA 0x111... → 0xAAA... (swap, top-level)
├── 0_1: 0xAAA → 0xBBB (swap, SwapRouter) — has calls → subchoreography
│   ├── 0_1_1: 0xBBB → 0xCCC (transfer, TokenContract) — has calls → subchoreography
│   │   └── 0_1_1_1: 0xCCC → 0xDDD (balanceOf, BalanceOracle, STATICCALL) — leaf
│   └── 0_1_2: 0xBBB → 0xEEE (updateReserves, LiquidityPool) — leaf
└── 0_2: 0xAAA → 0xFFF (logSwap, SwapLogger) — leaf
```

Transformation rules applied:
- Root (non-empty internalTxs) → section 4.3: request + scoping object (no response, EOA)
- 0_1 (non-empty calls) → section 4.5: request + response, scoping object with choreo:contains
- 0_1_1 (non-empty calls) → section 4.5: request + response, scoping object with choreo:contains
- 0_1_1_1, 0_1_2, 0_2 (leaf) → section 4.4: single choreography task
- All contained events have choreo:contained-by E2O to their parent scoping object

txHash (without 0x): `fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2`

## Events (8)

Ordering follows section 4.5: Request → [children in callId order] → Response.
choreo:contained-by links connect each event to its **immediate** parent subchoreography scoping object.

| # | Event ID | Event Type | time | trace_order |
|---|----------|-----------|------|-------------|
| 0 | `e:fed2...:root:request` | `Request swap` | 2024-01-01T00:10:00.000Z | 0 |
| 1 | `e:fed2...:0_1:request` | `Request swap` | 2024-01-01T00:10:00.001Z | 1 |
| 2 | `e:fed2...:0_1_1:request` | `Request transfer` | 2024-01-01T00:10:00.002Z | 2 |
| 3 | `e:fed2...:0_1_1_1` | `balanceOf` | 2024-01-01T00:10:00.003Z | 3 |
| 4 | `e:fed2...:0_1_1:response` | `Respond to transfer` | 2024-01-01T00:10:00.004Z | 4 |
| 5 | `e:fed2...:0_1_2` | `updateReserves` | 2024-01-01T00:10:00.005Z | 5 |
| 6 | `e:fed2...:0_1:response` | `Respond to swap` | 2024-01-01T00:10:00.006Z | 6 |
| 7 | `e:fed2...:0_2` | `logSwap` | 2024-01-01T00:10:00.007Z | 7 |

### E2O Relations per Event

**e:fed2...:root:request** (Request swap):
- choreo:initiator → `0x111...` (EOA)
- choreo:participant → `0xAAA...` (CA)
- choreo:message → `call:req:fed2...:root`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1:request** (Request swap):
- choreo:initiator → `0xAAA...`
- choreo:participant → `0xBBB...` (SwapRouter)
- choreo:message → `call:req:fed2...:0_1`
- choreo:contained-by → `sub:fed2...:root`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1_1:request** (Request transfer):
- choreo:initiator → `0xBBB...`
- choreo:participant → `0xCCC...` (TokenContract)
- choreo:message → `call:req:fed2...:0_1_1`
- choreo:contained-by → `sub:fed2...:0_1`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1_1_1** (balanceOf):
- choreo:initiator → `0xCCC...`
- choreo:participant → `0xDDD...` (BalanceOracle)
- choreo:message → `call:req:fed2...:0_1_1_1`
- choreo:message → `call:res:fed2...:0_1_1_1`
- choreo:contained-by → `sub:fed2...:0_1_1`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1_1:response** (Respond to transfer):
- choreo:initiator → `0xCCC...` (reversed)
- choreo:participant → `0xBBB...` (reversed)
- choreo:message → `call:res:fed2...:0_1_1`
- choreo:contained-by → `sub:fed2...:0_1`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1_2** (updateReserves):
- choreo:initiator → `0xBBB...`
- choreo:participant → `0xEEE...` (LiquidityPool)
- choreo:message → `call:req:fed2...:0_1_2`
- choreo:message → `call:res:fed2...:0_1_2`
- choreo:contained-by → `sub:fed2...:0_1`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_1:response** (Respond to swap):
- choreo:initiator → `0xBBB...` (reversed)
- choreo:participant → `0xAAA...` (reversed)
- choreo:message → `call:res:fed2...:0_1`
- choreo:contained-by → `sub:fed2...:root`
- choreo:instance → `choreoInst:0xfed2...`

**e:fed2...:0_2** (logSwap):
- choreo:initiator → `0xAAA...`
- choreo:participant → `0xFFF...` (SwapLogger)
- choreo:message → `call:req:fed2...:0_2`
- choreo:message → `call:res:fed2...:0_2`
- choreo:contained-by → `sub:fed2...:root`
- choreo:instance → `choreoInst:0xfed2...`

## Objects (22)

### Participants (7)

| Object ID | Object Type |
|-----------|-------------|
| `0x111...` | `EOA` |
| `0xAAA...` | `CA` |
| `0xBBB...` | `SwapRouter` |
| `0xCCC...` | `TokenContract` |
| `0xDDD...` | `BalanceOracle` |
| `0xEEE...` | `LiquidityPool` |
| `0xFFF...` | `SwapLogger` |

### Messages (11)

| Object ID | Object Type | Source (O2O choreo:source) | Target (O2O choreo:target) |
|-----------|-------------|----------------------------|----------------------------|
| `call:req:fed2...:root` | `swap call` | `0x111...` | `0xAAA...` |
| `call:req:fed2...:0_1` | `swap call` | `0xAAA...` | `0xBBB...` |
| `call:res:fed2...:0_1` | `swap call response` | `0xBBB...` | `0xAAA...` |
| `call:req:fed2...:0_1_1` | `transfer call` | `0xBBB...` | `0xCCC...` |
| `call:res:fed2...:0_1_1` | `transfer call response` | `0xCCC...` | `0xBBB...` |
| `call:req:fed2...:0_1_1_1` | `balanceOf call` | `0xCCC...` | `0xDDD...` |
| `call:res:fed2...:0_1_1_1` | `balanceOf call response` | `0xDDD...` | `0xCCC...` |
| `call:req:fed2...:0_1_2` | `updateReserves call` | `0xBBB...` | `0xEEE...` |
| `call:res:fed2...:0_1_2` | `updateReserves call response` | `0xEEE...` | `0xBBB...` |
| `call:req:fed2...:0_2` | `logSwap call` | `0xAAA...` | `0xFFF...` |
| `call:res:fed2...:0_2` | `logSwap call response` | `0xFFF...` | `0xAAA...` |

Messages breakdown: 1 root request (no response, EOA) + 5 x request/response pairs = 11

### Scoping Objects (3)

| Object ID | Object Type | O2O relations |
|-----------|-------------|---------------|
| `sub:fed2...:root` | `Subchoreography` | (none — outermost) |
| `sub:fed2...:0_1` | `Subchoreography` | choreo:contains from `sub:fed2...:root` |
| `sub:fed2...:0_1_1` | `Subchoreography` | choreo:contains from `sub:fed2...:0_1` |

### Choreography Instance (1)

| Object ID | Object Type |
|-----------|-------------|
| `choreoInst:0xfed2...` | `ChoreographyInstance` |

## Summary Counts

- Events: 8 (1 root request, 2 subchoreography request/response pairs [0_1, 0_1_1], 3 leaf tasks [0_1_1_1, 0_1_2, 0_2])
- Objects: 22 (7 participants, 11 messages, 3 scoping, 1 choreography instance)
- E2O relations: 42
- O2O relations: 24
