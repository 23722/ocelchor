"""Tests for ocelchorvalidator.index — OCEL index builder."""

from __future__ import annotations

from ocelchorvalidator.index import OcelIndex, build_index


# --- swap_1 fixture (2 events, 8 objects) ---


class TestSwap1Index:
    """Verify all OcelIndex fields against swap_1_ocel.json."""

    def test_events_count(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert len(idx.events) == 2

    def test_events_keys(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root:request" in idx.events
        assert "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1" in idx.events

    def test_objects_count(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert len(idx.objects) == 8

    def test_objects_keys(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert "0x1111111111111111111111111111111111111111" in idx.objects
        assert "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in idx.objects
        assert "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in idx.objects
        assert "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root" in idx.objects
        assert "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1" in idx.objects
        assert "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1" in idx.objects
        assert "sub:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root" in idx.objects
        assert "choreoInst:0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca" in idx.objects

    def test_e2o_root_request(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        root_id = "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root:request"
        rels = idx.e2o[root_id]
        assert len(rels) == 4
        qualifiers = [q for _, q in rels]
        assert "choreo:initiator" in qualifiers
        assert "choreo:participant" in qualifiers
        assert "choreo:message" in qualifiers
        assert "choreo:instance" in qualifiers

    def test_e2o_swap_event(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        swap_id = "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1"
        rels = idx.e2o[swap_id]
        assert len(rels) == 6
        qualifiers = [q for _, q in rels]
        assert "choreo:initiator" in qualifiers
        assert "choreo:participant" in qualifiers
        assert qualifiers.count("choreo:message") == 2
        assert "choreo:contained-by" in qualifiers
        assert "choreo:instance" in qualifiers

    def test_o2o_message_relations(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        # call:req:...:root → choreo:source (0x111), choreo:target (0xaaa)
        root_msg = "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root"
        assert len(idx.o2o[root_msg]) == 2
        assert ("0x1111111111111111111111111111111111111111", "choreo:source") in idx.o2o[root_msg]
        assert ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "choreo:target") in idx.o2o[root_msg]

        # call:req:...:0_1 → choreo:source (0xaaa), choreo:target (0xbbb)
        swap_req = "call:req:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1"
        assert ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "choreo:source") in idx.o2o[swap_req]
        assert ("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "choreo:target") in idx.o2o[swap_req]

        # call:res:...:0_1 → choreo:source (0xbbb), choreo:target (0xaaa)
        swap_res = "call:res:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1"
        assert ("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "choreo:source") in idx.o2o[swap_res]
        assert ("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "choreo:target") in idx.o2o[swap_res]

    def test_choreo_events(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert len(idx.choreo_events) == 2

    def test_contained_events(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert len(idx.contained_events) == 1
        assert idx.contained_events[0]["id"] == "e:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:0_1"

    def test_scoping_objects(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert idx.scoping_objects == ["sub:abcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca:root"]

    def test_instance_objects(self, swap1_ocel: dict) -> None:
        idx = build_index(swap1_ocel)
        assert idx.instance_objects == ["choreoInst:0xabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabcabca"]


# --- swap_3 fixture (8 events, 22 objects, 3 scoping objects) ---


class TestSwap3Index:

    def test_choreo_events(self, swap3_ocel: dict) -> None:
        idx = build_index(swap3_ocel)
        assert len(idx.choreo_events) == 8

    def test_contained_events(self, swap3_ocel: dict) -> None:
        idx = build_index(swap3_ocel)
        assert len(idx.contained_events) == 7  # all except root:request

    def test_scoping_objects(self, swap3_ocel: dict) -> None:
        idx = build_index(swap3_ocel)
        assert len(idx.scoping_objects) == 3
        ids = set(idx.scoping_objects)
        tx = "fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"
        assert f"sub:{tx}:root" in ids
        assert f"sub:{tx}:0_1" in ids
        assert f"sub:{tx}:0_1_1" in ids

    def test_instance_objects(self, swap3_ocel: dict) -> None:
        idx = build_index(swap3_ocel)
        assert len(idx.instance_objects) == 1

    def test_o2o_contains_nesting(self, swap3_ocel: dict) -> None:
        idx = build_index(swap3_ocel)
        tx = "fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2fed2"
        root_sub = f"sub:{tx}:root"
        sub_0_1 = f"sub:{tx}:0_1"
        # root contains 0_1
        assert (sub_0_1, "choreo:contains") in idx.o2o[root_sub]
        # 0_1 contains 0_1_1
        sub_0_1_1 = f"sub:{tx}:0_1_1"
        assert (sub_0_1_1, "choreo:contains") in idx.o2o[sub_0_1]


# --- swap_root_only fixture (1 event, 4 objects, 0 scoping objects) ---


class TestSwapRootOnlyIndex:

    def test_choreo_events(self, swap_root_only_ocel: dict) -> None:
        idx = build_index(swap_root_only_ocel)
        assert len(idx.choreo_events) == 1

    def test_contained_events_empty(self, swap_root_only_ocel: dict) -> None:
        idx = build_index(swap_root_only_ocel)
        assert idx.contained_events == []

    def test_scoping_objects_empty(self, swap_root_only_ocel: dict) -> None:
        idx = build_index(swap_root_only_ocel)
        assert idx.scoping_objects == []

    def test_instance_objects(self, swap_root_only_ocel: dict) -> None:
        idx = build_index(swap_root_only_ocel)
        assert len(idx.instance_objects) == 1


# --- Edge case: empty log ---


class TestEmptyLog:

    def test_all_fields_empty(self) -> None:
        ocel = {
            "objectTypes": [],
            "eventTypes": [],
            "objects": [],
            "events": [],
        }
        idx = build_index(ocel)
        assert idx.events == {}
        assert idx.objects == {}
        assert idx.e2o == {}
        assert idx.o2o == {}
        assert idx.choreo_events == []
        assert idx.contained_events == []
        assert idx.scoping_objects == []
        assert idx.instance_objects == []
