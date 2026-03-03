# Test Data Summary

Ground truth schema reference: `0x55_truncated.json` (real Ethereum transaction traces from PancakeSwap MasterChef v3).

## swap_1.json

Simple leaf-only transaction. EOA `0x111...111` calls `swapAssets()` on contract `0xAAA...AAA`. One internal call (`0_1`): `0xAAA` calls `swap()` on `0xBBB` (SwapPool). No nested calls — produces a single choreography task event.

## swap_2.json

One nesting level, matching the paper's demonstration scenario (Section 6). EOA `0x111...111` calls `swap()` on `0xAAA...AAA`. Internal call `0_1`: `0xAAA` calls `swap()` on `0xBBB` (SwapRouter), which contains nested call `0_1_1`: `0xBBB` calls `transfer()` on `0xCCC` (TokenContract). Triggers the request-response subchoreography pattern for `0_1`.

## swap_3.json

Two nesting levels with sibling calls. Same EOA and top-level contract. Call tree:

- `0_1`: `0xAAA` → `0xBBB` swap (subchoreography)
  - `0_1_1`: `0xBBB` → `0xCCC` transfer (subchoreography)
    - `0_1_1_1`: `0xCCC` → `0xDDD` balanceOf (STATICCALL, leaf)
  - `0_1_2`: `0xBBB` → `0xEEE` updateReserves (leaf)
- `0_2`: `0xAAA` → `0xFFF` logSwap (leaf)

Exercises nested subchoreography patterns, sibling calls at multiple depths, and mixed call types (CALL/STATICCALL).

## swap_3_inconsistent.json

Same transaction logic as `swap_3`, but with field inconsistencies matching the ground truth:

- Varied field ordering within CallFrame objects
- `inputsCall` as hex string instead of array on some calls
- Missing `inputs` (decoded parameters) on calls with only raw calldata
- Missing `activity` and `contractCalledName` on undecoded calls
- Missing `calls`/`events` arrays on leaf frames (omitted instead of empty)

Used to test that the parser handles optional/missing fields gracefully.

## swap_root_only.json

Transaction with empty `internalTxs`. EOA `0x111...111` calls `approve()` on `0xCCC` (TokenContract). No internal calls at all — produces only the root choreography task event, no subchoreography pattern. Tests the simplest possible case.

## swap_multi_tx.json

Two transactions in one file sharing participants. First: EOA `0x111...111` calls `approve()` on `0xCCC` (root-only, no internal calls). Second: same EOA calls `swap()` on `0xAAA`, which internally calls `swap()` on `0xBBB` (SwapRouter), containing `transfer()` on `0xCCC` (TokenContract). Tests global participant deduplication across traces (0x111, 0xAAA, 0xBBB, 0xCCC appear in both transactions) and separate choreography instance creation.

## swap_undefined_activity.json

Transaction where a nested call has `activity: "undefined"`. EOA `0x111...111` calls `swap()` on `0xAAA`. Internal call `0_1`: `0xAAA` calls `swap()` on `0xBBB`, which contains `0_1_1`: `0xBBB` calls an undecoded function on `0xCCC` (`activity: "undefined"`, only raw `inputsCall` hex, no decoded `inputs`, no `contractCalledName`). Tests fallback label handling and warnings for undecoded calls.

## swap_special_calls.json

Transaction with CREATE and DELEGATECALL call types. EOA `0x111...111` calls `deployAndSwap()` on `0xAAA`. Two base-level internal calls:

- `0_1`: `0xAAA` → `0x222` CREATE (deploys a new contract, `activity: "undefined"`, no `contractCalledName`)
- `0_2`: `0xAAA` → `0xBBB` swap (SwapRouter), containing `0_2_1`: `0xBBB` → `0xCCC` DELEGATECALL to `swapExact()` (SwapImplementation)

Tests CREATE handling (new contract as `to` address, undefined activity), DELEGATECALL as separate participant interaction, and call-type filtering (`--call-types`).

## swap_reverted.json

Transaction with a reverted internal call. EOA `0x111...111` calls `swap()` on `0xAAA`. Internal call `0_1`: `0xAAA` calls `swap()` on `0xBBB` (SwapRouter), containing two child calls:

- `0_1_1`: `0xBBB` → `0xCCC` transfer (succeeds normally)
- `0_1_2`: `0xBBB` → `0xEEE` updateReserves (reverted — `output: "0x"`, `error: "execution reverted"`)

Tests `--exclude-reverted` (default: skip `0_1_2`) and `--include-reverted` (include it with `reverted: true` attribute).
