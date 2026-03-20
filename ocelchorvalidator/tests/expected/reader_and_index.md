# Test Plan: reader.py and index.py

## reader.py — OCEL 2.0 JSON Loader

### Positive cases

- **Load swap_1_ocel.json**: Returns dict with required keys (`objectTypes`, `eventTypes`, `objects`, `events`). `len(events) == 2`, `len(objects) == 8`.
- **Load swap_3_ocel.json**: Returns dict, `len(events) == 8`.
- **Load 0x5e_0xcd4_ocel.json**: Real-world data parses without error.

### Negative cases

- **Non-existent file**: `read_ocel(Path("nonexistent.json"))` → `ValueError` with "Cannot read".
- **Invalid JSON**: File containing `{broken` → `ValueError` with "Invalid JSON".
- **Not a JSON object**: File containing `[1, 2, 3]` → `ValueError` with "Expected a JSON object".
- **Missing required keys**: File containing `{"objectTypes": []}` (missing `eventTypes`, `objects`, `events`) → `ValueError` with "Missing required OCEL 2.0 keys".

---

## index.py — OCEL Index Builder

### swap_1 fixture (2 events, 8 objects, 1 instance, 1 scoping object)

#### `events` — dict with 2 entries

| Event ID | Type |
|----------|------|
| `e:abc...:root:request` | Request swapAssets |
| `e:abc...:0_1` | swap |

#### `objects` — dict with 8 entries

| Object ID | Type |
|-----------|------|
| `0x111...` | EOA |
| `0xaaa...` | CA |
| `0xbbb...` | SwapPool |
| `call:req:abc...:root` | swapAssets call |
| `call:req:abc...:0_1` | swap call |
| `call:res:abc...:0_1` | swap call response |
| `subchoreographyInstance:abc...:root` | subchoreographyInstance |
| `choreographyInstance:0xabc...` | choreographyInstance |

#### `e2o` — event-to-object relations

- `e:...:root:request` → 4 relations: `choreo:initiator` (0x111), `choreo:participant` (0xaaa), `choreo:message` (call:req:...:root), `choreo:instance` (choreographyInstance:...)
- `e:...:0_1` → 6 relations: `choreo:initiator` (0xaaa), `choreo:participant` (0xbbb), `choreo:message` (call:req:...:0_1), `choreo:message` (call:res:...:0_1), `choreo:contained-by` (subchoreographyInstance:...:root), `choreo:instance` (choreographyInstance:...)

#### `o2o` — object-to-object relations

- `call:req:...:root` → `choreo:source` (0x111), `choreo:target` (0xaaa)
- `call:req:...:0_1` → `choreo:source` (0xaaa), `choreo:target` (0xbbb)
- `call:res:...:0_1` → `choreo:source` (0xbbb), `choreo:target` (0xaaa)

#### Derived indexes

- `choreo_events`: 2 events (both have `choreo:instance`)
- `contained_events`: 1 event (`e:...:0_1` has `choreo:contained-by`)
- `scoping_objects`: `["subchoreographyInstance:abc...:root"]`
- `instance_objects`: `["choreographyInstance:0xabc..."]`

### swap_3 fixture (8 events, 22 objects, 1 instance, 3 scoping objects)

- `choreo_events`: 8 events
- `contained_events`: 7 events (all except `root:request`)
- `scoping_objects`: 3 (`subchoreographyInstance:...:root`, `subchoreographyInstance:...:0_1`, `subchoreographyInstance:...:0_1_1`)
- `instance_objects`: 1
- `o2o` includes `choreo:contains`: `subchoreographyInstance:...:root` → `subchoreographyInstance:...:0_1`, `subchoreographyInstance:...:0_1` → `subchoreographyInstance:...:0_1_1`

### swap_root_only fixture (1 event, 4 objects, 1 instance, 0 scoping objects)

- `choreo_events`: 1 event
- `contained_events`: empty list
- `scoping_objects`: empty list
- `instance_objects`: 1

### Edge case: empty log

- OCEL with `"events": [], "objects": [], "objectTypes": [], "eventTypes": []`
- All index fields empty (empty dicts/lists)
