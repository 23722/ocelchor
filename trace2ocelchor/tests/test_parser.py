"""Tests for input parsing and schema normalization."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from trace2choreo.models import CallType, InputParam
from trace2choreo.parser import (
    load_trace_file,
    normalize_call_frame,
    parse_timestamp,
)


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

class TestParseTimestamp:
    def test_z_suffix(self):
        ts = parse_timestamp({"$date": "2024-01-01T00:00:00Z"})
        assert ts == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_offset_suffix(self):
        ts = parse_timestamp({"$date": "2024-01-01T00:00:00+00:00"})
        assert ts == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_with_seconds(self):
        ts = parse_timestamp({"$date": "2023-03-31T05:42:47Z"})
        assert ts == datetime(2023, 3, 31, 5, 42, 47, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Top-level transaction parsing
# ---------------------------------------------------------------------------

class TestLoadTraceFile:
    def test_swap_1_basic_fields(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        assert len(traces) == 1
        t = traces[0]
        assert t.transaction_hash == "0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"
        assert t.function_name == "swapAssets"
        assert t.contract_address == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert t.sender == "0x1111111111111111111111111111111111111111"
        assert t.timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert t.block_number == 12345678
        assert t.gas_used == 50000
        assert t.value == 0

    def test_swap_1_top_level_inputs(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        t = traces[0]
        assert len(t.inputs) == 1
        assert t.inputs[0] == InputParam(name="amountIn", type="uint256", value=1000)

    def test_swap_1_internal_txs(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        t = traces[0]
        assert len(t.internal_txs) == 1
        frame = t.internal_txs[0]
        assert frame.call_id == "0_1"
        assert frame.activity == "swap"
        assert frame.call_type == CallType.CALL
        assert frame.from_addr == "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert frame.to_addr == "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        assert len(frame.calls) == 0

    def test_addresses_lowercased(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        t = traces[0]
        # All addresses should be lowercase
        assert t.contract_address == t.contract_address.lower()
        assert t.sender == t.sender.lower()
        assert t.internal_txs[0].from_addr == t.internal_txs[0].from_addr.lower()
        assert t.internal_txs[0].to_addr == t.internal_txs[0].to_addr.lower()

    def test_root_only_empty_internal_txs(self, data_dir):
        traces = load_trace_file(data_dir / "swap_root_only.json")
        assert len(traces) == 1
        assert len(traces[0].internal_txs) == 0

    def test_multi_tx_file(self, data_dir):
        traces = load_trace_file(data_dir / "swap_multi_tx.json")
        assert len(traces) == 2
        assert traces[0].function_name == "approve"
        assert traces[1].function_name == "swap"

    def test_multi_tx_different_hashes(self, data_dir):
        traces = load_trace_file(data_dir / "swap_multi_tx.json")
        assert traces[0].transaction_hash != traces[1].transaction_hash

    def test_missing_required_fields_skipped(self, tmp_path):
        """Transaction missing required fields should be skipped."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text('[{"functionName": "test"}]')
        traces = load_trace_file(bad_file)
        assert len(traces) == 0

    def test_single_object_not_array(self, tmp_path):
        """A single JSON object (not wrapped in array) should work."""
        single = tmp_path / "single.json"
        single.write_text('''{
            "functionName": "test",
            "transactionHash": "0xabc",
            "contractAddress": "0xdef",
            "sender": "0x123",
            "timestamp": {"$date": "2024-01-01T00:00:00Z"},
            "value": 0,
            "inputs": [],
            "internalTxs": []
        }''')
        traces = load_trace_file(single)
        assert len(traces) == 1
        assert traces[0].function_name == "test"


# ---------------------------------------------------------------------------
# Nested call frame parsing
# ---------------------------------------------------------------------------

class TestNestedCallFrames:
    def test_swap_2_one_nesting_level(self, data_dir):
        traces = load_trace_file(data_dir / "swap_2.json")
        frame = traces[0].internal_txs[0]
        assert frame.call_id == "0_1"
        assert frame.activity == "swap"
        assert len(frame.calls) == 1
        child = frame.calls[0]
        assert child.call_id == "0_1_1"
        assert child.activity == "transfer"
        assert len(child.calls) == 0

    def test_swap_3_two_nesting_levels(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3.json")
        frame_0_1 = traces[0].internal_txs[0]
        assert frame_0_1.call_id == "0_1"
        assert len(frame_0_1.calls) == 2  # 0_1_1 and 0_1_2

        frame_0_1_1 = frame_0_1.calls[0]
        assert frame_0_1_1.call_id == "0_1_1"
        assert len(frame_0_1_1.calls) == 1  # 0_1_1_1

        frame_0_1_1_1 = frame_0_1_1.calls[0]
        assert frame_0_1_1_1.call_id == "0_1_1_1"
        assert frame_0_1_1_1.call_type == CallType.STATICCALL
        assert len(frame_0_1_1_1.calls) == 0

        frame_0_1_2 = frame_0_1.calls[1]
        assert frame_0_1_2.call_id == "0_1_2"
        assert len(frame_0_1_2.calls) == 0

    def test_swap_3_sibling_at_base(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3.json")
        assert len(traces[0].internal_txs) == 2  # 0_1 and 0_2
        frame_0_2 = traces[0].internal_txs[1]
        assert frame_0_2.call_id == "0_2"
        assert frame_0_2.activity == "logSwap"


# ---------------------------------------------------------------------------
# Inconsistent schema handling
# ---------------------------------------------------------------------------

class TestInconsistentSchema:
    def test_inconsistent_parses_same_structure(self, data_dir):
        """swap_3_inconsistent should produce the same call tree as swap_3."""
        traces_clean = load_trace_file(data_dir / "swap_3.json")
        traces_dirty = load_trace_file(data_dir / "swap_3_inconsistent.json")

        assert len(traces_dirty) == 1
        t = traces_dirty[0]

        # Same top-level structure
        assert len(t.internal_txs) == 2
        assert t.internal_txs[0].call_id == "0_1"
        assert t.internal_txs[1].call_id == "0_2"

        # Same nesting
        frame_0_1 = t.internal_txs[0]
        assert len(frame_0_1.calls) == 2
        assert frame_0_1.calls[0].call_id == "0_1_1"
        assert frame_0_1.calls[1].call_id == "0_1_2"
        assert len(frame_0_1.calls[0].calls) == 1
        assert frame_0_1.calls[0].calls[0].call_id == "0_1_1_1"

    def test_inputsCall_as_hex_string(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3_inconsistent.json")
        frame_0_1_1_1 = traces[0].internal_txs[0].calls[0].calls[0]
        assert frame_0_1_1_1.inputs_call == "0x70a08231"
        assert isinstance(frame_0_1_1_1.inputs_call, str)

    def test_inputsCall_as_array(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        frame = traces[0].internal_txs[0]
        assert frame.inputs_call == []
        assert isinstance(frame.inputs_call, list)

    def test_missing_inputs_produces_empty_list(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3_inconsistent.json")
        # 0_1_1_1 has no decoded inputs, only inputsCall hex
        frame = traces[0].internal_txs[0].calls[0].calls[0]
        assert frame.inputs == []

    def test_missing_activity_defaults_to_undefined(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3_inconsistent.json")
        # 0_1_1_1 has no activity field
        frame = traces[0].internal_txs[0].calls[0].calls[0]
        assert frame.activity == "undefined"

    def test_missing_contractCalledName_is_none(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3_inconsistent.json")
        frame = traces[0].internal_txs[0].calls[0].calls[0]
        assert frame.contract_called_name is None

    def test_missing_calls_produces_empty_list(self, data_dir):
        """Leaf frames that omit 'calls' entirely should get empty list."""
        traces = load_trace_file(data_dir / "swap_3_inconsistent.json")
        # 0_2 has no calls/events keys
        frame_0_2 = traces[0].internal_txs[1]
        assert frame_0_2.calls == []


# ---------------------------------------------------------------------------
# Special call types
# ---------------------------------------------------------------------------

class TestSpecialCallTypes:
    def test_create_call_type(self, data_dir):
        traces = load_trace_file(data_dir / "swap_special_calls.json")
        frame_0_1 = traces[0].internal_txs[0]
        assert frame_0_1.call_type == CallType.CREATE

    def test_delegatecall_type(self, data_dir):
        traces = load_trace_file(data_dir / "swap_special_calls.json")
        frame_0_2_1 = traces[0].internal_txs[1].calls[0]
        assert frame_0_2_1.call_type == CallType.DELEGATECALL
        assert frame_0_2_1.activity == "swapExact"

    def test_undefined_activity(self, data_dir):
        traces = load_trace_file(data_dir / "swap_undefined_activity.json")
        frame_0_1_1 = traces[0].internal_txs[0].calls[0]
        assert frame_0_1_1.activity == "undefined"


# ---------------------------------------------------------------------------
# Reverted calls
# ---------------------------------------------------------------------------

class TestRevertedCalls:
    def test_reverted_call_has_error(self, data_dir):
        traces = load_trace_file(data_dir / "swap_reverted.json")
        frame_0_1_2 = traces[0].internal_txs[0].calls[1]
        assert frame_0_1_2.error == "execution reverted"
        assert frame_0_1_2.output == "0x"

    def test_non_reverted_call_has_no_error(self, data_dir):
        traces = load_trace_file(data_dir / "swap_reverted.json")
        frame_0_1_1 = traces[0].internal_txs[0].calls[0]
        assert frame_0_1_1.error is None


# ---------------------------------------------------------------------------
# Call frame inputs
# ---------------------------------------------------------------------------

class TestCallFrameInputs:
    def test_call_frame_inputs_parsed(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        frame = traces[0].internal_txs[0]
        assert len(frame.inputs) == 1
        assert frame.inputs[0] == InputParam(name="amountIn", type="uint256", value=1000)

    def test_call_frame_multiple_inputs(self, data_dir):
        traces = load_trace_file(data_dir / "swap_3.json")
        frame_0_1_1 = traces[0].internal_txs[0].calls[0]
        assert len(frame_0_1_1.inputs) == 2
        assert frame_0_1_1.inputs[0].name == "to"
        assert frame_0_1_1.inputs[1].name == "amount"

    def test_complex_input_name_converted_to_string(self, data_dir):
        """Seaport-style inputs where 'name' is a nested list, not a string."""
        traces = load_trace_file(data_dir / "0x06_truncated.json")
        # fulfillBasicOrder tx, frame 0_2 (execute on Conduit) has complex name
        fulfill_tx = [t for t in traces if t.function_name == "fulfillBasicOrder_efficient_6GL6yc"][0]
        frame_0_2 = fulfill_tx.internal_txs[1]  # execute call
        assert frame_0_2.activity == "execute"
        assert len(frame_0_2.inputs) == 1
        assert isinstance(frame_0_2.inputs[0].name, str)

    def test_output_preserved(self, data_dir):
        traces = load_trace_file(data_dir / "swap_1.json")
        frame = traces[0].internal_txs[0]
        assert frame.output == "0x00000000000000000000000000000000000000000000000000000000000003e3"


# ---------------------------------------------------------------------------
# DELEGATECALL from-address rewrite
# ---------------------------------------------------------------------------

class TestDelegatecallFromRewrite:
    """T1.1: Single DELEGATECALL child rewrite (0x5e_truncated, tx 0xcd4991...)."""

    @pytest.fixture(autouse=True)
    def _load(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        self.tx = [t for t in traces if t.transaction_hash.startswith("0xcd4991")][0]
        self.frame_0_1 = self.tx.internal_txs[0]
        self.frame_0_1_1 = self.frame_0_1.calls[0]

    def test_delegatecall_frame_keeps_original_from(self):
        assert self.frame_0_1.from_addr == "0x5efda50f22d34f262c29268506c5fa42cb56a1ce"

    def test_child_from_rewritten_to_delegatecall_to(self):
        assert self.frame_0_1_1.from_addr == "0xffbac21a641dcfe4552920138d90f3638b3c9fba"

    def test_child_to_unchanged(self):
        assert self.frame_0_1_1.to_addr == "0x77777feddddffc19ff86db637967013e6c6a116c"

    def test_child_call_type_unchanged(self):
        assert self.frame_0_1_1.call_type == CallType.CALL


class TestDelegatecallMultipleChildren:
    """T1.2: Multiple children rewrite (0x5e_truncated, tx 0x879a69fe...)."""

    @pytest.fixture(autouse=True)
    def _load(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        self.tx = [t for t in traces if t.transaction_hash.startswith("0x879a69fe")][0]
        self.frame_0_1 = self.tx.internal_txs[0]

    def test_all_direct_children_rewritten(self):
        governance = "0xffbac21a641dcfe4552920138d90f3638b3c9fba"
        for child in self.frame_0_1.calls:
            assert child.from_addr == governance, (
                f"Frame {child.call_id}: expected from={governance}, got {child.from_addr}"
            )

    def test_grandchild_of_delegatecall_not_rewritten(self):
        # 0_1_1 is CALL, so 0_1_1_1 should NOT be rewritten
        frame_0_1_1_1 = self.frame_0_1.calls[0].calls[0]
        assert frame_0_1_1_1.from_addr == "0x77777feddddffc19ff86db637967013e6c6a116c"


class TestDelegatecallChained:
    """T1.3: Nested DELEGATECALL (0x5e_truncated, tx 0xf4de99e9...)."""

    @pytest.fixture(autouse=True)
    def _load(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        self.tx = [t for t in traces if t.transaction_hash.startswith("0xf4de99e9")][0]
        self.frame_0_1 = self.tx.internal_txs[0]

    def test_direct_children_of_root_delegatecall_rewritten(self):
        governance_upgrade = "0xbf46f2222c0712caf2f13b8590732dbd964ce395"
        for child in self.frame_0_1.calls:
            assert child.from_addr == governance_upgrade, (
                f"Frame {child.call_id}: expected from={governance_upgrade}, got {child.from_addr}"
            )

    def test_nested_delegatecall_frame_keeps_from(self):
        # 0_1_1 is CALL (not DELEGATECALL), so 0_1_1_1 is not rewritten
        frame_0_1_1_1 = self.frame_0_1.calls[0].calls[0]
        assert frame_0_1_1_1.from_addr == "0x5b3f656c80e8ddb9ec01dd9018815576e9238c29"


class TestDelegatecallSyntheticChained:
    """T1.4: Synthetic chained DELEGATECALL to test recursive from rewrite."""

    @pytest.fixture(autouse=True)
    def _load(self):
        raw = {
            "callId": "0_1", "from": "A", "to": "B", "type": "DELEGATECALL",
            "activity": "proxy", "calls": [{
                "callId": "0_1_1", "from": "A", "to": "C", "type": "DELEGATECALL",
                "activity": "impl", "calls": [{
                    "callId": "0_1_1_1", "from": "A", "to": "D", "type": "CALL",
                    "activity": "transfer", "calls": []
                }]
            }]
        }
        self.frame = normalize_call_frame(raw)

    def test_chained_delegatecall_level_1(self):
        # No parent DELEGATECALL passed, so from stays as-is
        assert self.frame.from_addr == "a"

    def test_chained_delegatecall_level_2(self):
        # Parent (0_1) is DELEGATECALL → from = parent.to = B
        assert self.frame.calls[0].from_addr == "b"

    def test_chained_delegatecall_level_3(self):
        # Parent (0_1_1) is DELEGATECALL → from = parent.to = C
        assert self.frame.calls[0].calls[0].from_addr == "c"


# ---------------------------------------------------------------------------
# Ground truth: 0x55_truncated.json
# ---------------------------------------------------------------------------

class TestGroundTruth:
    def test_loads_all_transactions(self, data_dir):
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        assert len(traces) == 9

    def test_transaction_functions(self, data_dir):
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        names = [t.function_name for t in traces]
        assert names[0] == "transferOwnership"
        assert names[1] == "setLMPoolDeployer"
        assert names[2:8] == ["add"] * 6
        assert names[8] == "harvest"

    def test_root_only_transactions(self, data_dir):
        """First two transactions have no internal calls."""
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        assert len(traces[0].internal_txs) == 0
        assert len(traces[1].internal_txs) == 0

    def test_complex_transaction_has_internal_txs(self, data_dir):
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        # Third transaction (first 'add') should have internal calls
        assert len(traces[2].internal_txs) > 0

    def test_nested_calls_in_ground_truth(self, data_dir):
        """The 'add' transactions have nested call trees."""
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        t = traces[2]  # first 'add'
        # Should have a deploy call with nested CREATE
        deploy_frame = t.internal_txs[0]
        assert deploy_frame.activity == "deploy"
        assert len(deploy_frame.calls) > 0

    def test_real_timestamps(self, data_dir):
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        assert traces[0].timestamp.year == 2023
        assert traces[0].timestamp.month == 3

    def test_real_addresses_lowercased(self, data_dir):
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        t = traces[0]
        assert t.contract_address == "0x556b9306565093c855aea9ae92a594704c2cd59e"
        assert t.sender == "0x3af75af6f056d4d72c1675da919aebf908a109d6"

    def test_mixed_call_types(self, data_dir):
        """Ground truth contains CALL, STATICCALL, and CREATE types."""
        traces = load_trace_file(data_dir / "0x55_truncated.json")
        all_types = set()
        def collect_types(frame):
            all_types.add(frame.call_type)
            for c in frame.calls:
                collect_types(c)
        for t in traces:
            for f in t.internal_txs:
                collect_types(f)
        assert CallType.CALL in all_types
        assert CallType.STATICCALL in all_types
        assert CallType.CREATE in all_types


# ---------------------------------------------------------------------------
# Ground truth: 0x5e_truncated.json
# ---------------------------------------------------------------------------

class TestGroundTruth0x5e:
    def test_loads_all_transactions(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        assert len(traces) == 6

    def test_transaction_functions(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        names = [t.function_name for t in traces]
        assert names == ["lock", "lock", "delegate", "lock", "unlock", "lock"]

    def test_all_have_internal_txs(self, data_dir):
        traces = load_trace_file(data_dir / "0x5e_truncated.json")
        for t in traces:
            assert len(t.internal_txs) == 1


# ---------------------------------------------------------------------------
# Ground truth: 0xb1_truncated_broken.json
# (renamed from 0xb1_truncated.json to mark invalid callId annotations;
#  top-level transaction parsing is still valid and tested here)
# ---------------------------------------------------------------------------

class TestGroundTruth0xb1:
    def test_loads_all_transactions(self, data_dir):
        traces = load_trace_file(data_dir / "0xb1_truncated_broken.json")
        assert len(traces) == 6

    def test_transaction_functions(self, data_dir):
        traces = load_trace_file(data_dir / "0xb1_truncated_broken.json")
        names = [t.function_name for t in traces]
        assert names == ["bid", "bid", "bid", "bid", "cancelAuction", "bid"]

    def test_internal_tx_counts(self, data_dir):
        traces = load_trace_file(data_dir / "0xb1_truncated_broken.json")
        counts = [len(t.internal_txs) for t in traces]
        assert counts == [3, 3, 0, 3, 1, 3]
