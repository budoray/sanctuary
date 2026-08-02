"""Unit tests for sanctuary.procgen - the D-1..D-24 random dungeon generator."""
import pytest

from sanctuary import module, procgen

_REQUIRED_MODULE_KEYS = ("title", "version", "party_guidance", "background", "start")
_REQUIRED_AREA_KEYS = ("id", "name", "description", "exits", "contents", "monsters",
                        "treasure", "discoveries")
_REQUIRED_EXIT_KEYS = ("to", "kind", "hidden")
_REQUIRED_REGION_KEYS = ("id", "areas", "check", "table")


def test_same_seed_produces_a_byte_identical_dungeon():
    a = procgen.generate_dungeon(1234, target_areas=15)
    b = procgen.generate_dungeon(1234, target_areas=15)
    assert a == b


def test_different_seeds_produce_different_dungeons():
    a = procgen.generate_dungeon(1, target_areas=15)
    b = procgen.generate_dungeon(2, target_areas=15)
    assert a != b


def test_every_area_is_reachable_from_the_start_with_no_items():
    doc = procgen.generate_dungeon(99, target_areas=20)
    all_ids = {a["id"] for a in doc["areas"]}
    assert procgen.reachable_area_ids(doc) == all_ids


def test_exits_reciprocate_unless_one_way():
    doc = procgen.generate_dungeon(3, target_areas=25)
    by_id = {a["id"]: a for a in doc["areas"]}
    for area in doc["areas"]:
        for exit_ in area["exits"]:
            back = by_id[exit_["to"]]["exits"]
            reciprocates = any(e["to"] == area["id"] for e in back)
            if not reciprocates:
                assert exit_["kind"] == "stairs"


def test_emitted_shape_matches_the_campaign_format_contract():
    doc = procgen.generate_dungeon(5, target_areas=10)
    assert isinstance(doc["module"], dict)
    for key in _REQUIRED_MODULE_KEYS:
        assert key in doc["module"], key
    assert isinstance(doc["module"]["title"], str)
    assert isinstance(doc["module"]["party_guidance"]["size"], list)

    assert isinstance(doc["regions"], list) and doc["regions"]
    for region in doc["regions"]:
        for key in _REQUIRED_REGION_KEYS:
            assert key in region, key
        assert len(region["table"]["entries"]) == int(region["table"]["die"].lstrip("d"))

    assert isinstance(doc["areas"], list) and doc["areas"]
    for area in doc["areas"]:
        for key in _REQUIRED_AREA_KEYS:
            assert key in area, key
        assert isinstance(area["id"], int)
        assert isinstance(area["description"], str)
        for exit_ in area["exits"]:
            for key in _REQUIRED_EXIT_KEYS:
                assert key in exit_, key
            assert isinstance(exit_["hidden"], bool)

    for key in ("monsters", "items", "mechanics"):
        assert doc[key] == []


def test_generated_dungeon_loads_through_the_real_module_validator():
    doc = procgen.generate_dungeon(6, target_areas=10)
    module.load(doc)  # raises ModuleError on any problem


def test_target_areas_is_met_exactly():
    for target in (1, 2, 5, 20):
        doc = procgen.generate_dungeon(42, target_areas=target)
        assert len(doc["areas"]) == target


def test_target_areas_below_one_is_rejected():
    with pytest.raises(ValueError):
        procgen.generate_dungeon(1, target_areas=0)


def test_fudges_are_tagged_and_reasoned_in_the_roll_log():
    _, dice_ = procgen.generate_dungeon(1, target_areas=12, return_dice=True)
    fudge_rolls = procgen.fudges(dice_)
    assert fudge_rolls
    for r in fudge_rolls:
        assert r.tags.get("fudge") is True
        assert r.reason.startswith("fudge:")


def test_every_roll_comes_from_the_shared_dice_log():
    _, dice_ = procgen.generate_dungeon(10, target_areas=10, return_dice=True)
    assert len(dice_.log) > 0
    assert all(hasattr(r, "total") for r in dice_.log)


@pytest.mark.parametrize("seed", range(200))
def test_two_hundred_seeds_never_crash_and_stay_playable(seed):
    doc = procgen.generate_dungeon(seed, target_areas=(seed % 20) + 3, dungeon_level=(seed % 5) + 1)
    assert doc["areas"]
    all_ids = {a["id"] for a in doc["areas"]}
    assert procgen.reachable_area_ids(doc) == all_ids
    module.load(doc)


def test_reachable_area_ids_on_a_hand_built_graph():
    doc = {
        "areas": [
            {"id": 1, "exits": [{"to": 2, "kind": "door", "hidden": False}]},
            {"id": 2, "exits": [{"to": 1, "kind": "door", "hidden": False}]},
            {"id": 3, "exits": []},  # unreachable
        ]
    }
    assert procgen.reachable_area_ids(doc) == {1, 2}


def test_reachable_area_ids_on_empty_areas_is_empty():
    assert procgen.reachable_area_ids({"areas": []}) == set()
