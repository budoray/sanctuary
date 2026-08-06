import pytest

from backend.app.engine import items


def test_generate_loot_returns_known_item():
    loot = items.generate_loot()
    assert "instance_id" in loot
    assert loot["item_id"] in items.LOOT_TABLE


def test_equip_item_moves_to_slot_and_swaps():
    char_state = {"inventory": [], "equipment": {}}
    sword = items.generate_loot()
    # Force a sword for this test.
    sword = {**items.LOOT_TABLE["short_sword"], "instance_id": "sw01", "item_id": "short_sword", "slot": "main_hand"}
    items.add_item(char_state, sword)
    equipped = items.equip_item(char_state, sword["instance_id"])
    assert equipped is sword
    assert char_state["equipment"]["main_hand"] is sword
    assert sword not in char_state["inventory"]

    axe = {**items.LOOT_TABLE["short_sword"], "instance_id": "axe01", "item_id": "short_sword", "slot": "main_hand"}
    items.add_item(char_state, axe)
    displaced = items.equip_item(char_state, axe["instance_id"])
    assert displaced is axe
    assert char_state["equipment"]["main_hand"] is axe
    assert sword in char_state["inventory"]


def test_use_consumable_restores_hp_and_removes():
    char_state = {"inventory": [], "equipment": {}, "hit_points": 5, "max_hp": 20}
    potion = items.generate_loot()
    # Force a potion for this test.
    potion = {
        "instance_id": "pot01",
        "item_id": "healing_potion",
        **items.LOOT_TABLE["healing_potion"],
    }
    items.add_item(char_state, potion)
    restore = items.use_consumable(char_state, potion["instance_id"])
    assert restore == 10
    assert potion not in char_state["inventory"]


def test_apply_gear_increases_ac_and_damage():
    token = {"ac": 10, "damage": "1d6", "ranged_damage": "1d6"}
    char_state = {
        "inventory": [],
        "equipment": {
            "body": {
                "instance_id": "arm01",
                "item_id": "leather_armor",
                **items.LOOT_TABLE["leather_armor"],
            },
            "main_hand": {
                "instance_id": "wpn01",
                "item_id": "short_sword",
                **items.LOOT_TABLE["short_sword"],
            },
        },
    }
    items.apply_gear(char_state, token)
    assert token["ac"] == 12
    assert token["damage_bonus"] == 1
