"""Loot and equipment helpers.

Items are simple effect carriers. Equipment bonuses are applied when a
character enters a session so the token reflects the gear they are wearing.
"""
from __future__ import annotations

import uuid
from typing import Any

from backend.app.engine.dice import Dice


LOOT_TABLE: dict[str, dict[str, Any]] = {
    "leather_armor": {
        "name": "Leather Armor",
        "type": "armor",
        "slot": "body",
        "effects": {"ac_bonus": 2},
    },
    "chain_shirt": {
        "name": "Chain Shirt",
        "type": "armor",
        "slot": "body",
        "effects": {"ac_bonus": 4},
    },
    "plate_mail": {
        "name": "Plate Mail",
        "type": "armor",
        "slot": "body",
        "effects": {"ac_bonus": 6},
    },
    "short_sword": {
        "name": "Short Sword",
        "type": "weapon",
        "slot": "main_hand",
        "effects": {"damage_bonus": 1},
    },
    "longsword": {
        "name": "Longsword",
        "type": "weapon",
        "slot": "main_hand",
        "effects": {"damage_bonus": 2},
    },
    "longbow": {
        "name": "Longbow",
        "type": "weapon",
        "slot": "main_hand",
        "effects": {"ranged_damage_override": "1d8"},
    },
    "shield": {
        "name": "Wooden Shield",
        "type": "shield",
        "slot": "off_hand",
        "effects": {"ac_bonus": 1},
    },
    "tower_shield": {
        "name": "Tower Shield",
        "type": "shield",
        "slot": "off_hand",
        "effects": {"ac_bonus": 2},
    },
    "healing_potion": {
        "name": "Potion of Healing",
        "type": "potion",
        "slot": "consumable",
        "effects": {"hp_restore": 10},
    },
    "ring_of_protection": {
        "name": "Ring of Protection",
        "type": "ring",
        "slot": "finger",
        "effects": {"ac_bonus": 1},
    },
    "ring_of_might": {
        "name": "Ring of Might",
        "type": "ring",
        "slot": "finger",
        "effects": {"damage_bonus": 1},
    },
    "boots_of_striding": {
        "name": "Boots of Striding",
        "type": "boots",
        "slot": "feet",
        "effects": {"ac_bonus": 1},
    },
    "crown_of_wisdom": {
        "name": "Crown of Wisdom",
        "type": "helm",
        "slot": "head",
        "effects": {"ac_bonus": 1},
    },
}


def generate_loot(level: int = 1, d: Dice | None = None) -> dict[str, Any]:
    """Return one random loot item instance, with mild level scaling.

    Higher levels slightly favour non-consumable gear and may add a small
    damage or AC bonus to ordinary items.
    """
    d = d or Dice(seed=0)
    item_id = d.choice(list(LOOT_TABLE.keys()), reason="loot table", kind="loot")
    template = LOOT_TABLE[item_id]
    item = {
        "instance_id": str(uuid.uuid4())[:8],
        "item_id": item_id,
        **template,
    }

    # Scale non-potion gear upward at higher levels.
    if level > 1 and item.get("slot") != "consumable":
        effects = dict(item.get("effects", {}))
        bonus = min(level // 3, 2)
        if bonus:
            if "ac_bonus" in effects:
                effects["ac_bonus"] = effects["ac_bonus"] + bonus
            if "damage_bonus" in effects:
                effects["damage_bonus"] = effects["damage_bonus"] + bonus
            item["effects"] = effects
            item["name"] = f"+{bonus} {item['name']}"
    return item


def _equipment_bonuses(equipment: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Sum AC and damage bonuses from equipped items."""
    bonuses: dict[str, Any] = {"ac_bonus": 0, "damage_bonus": 0}
    ranged_override: str | None = None
    for slot, item in equipment.items():
        if not item:
            continue
        effects = item.get("effects", {})
        bonuses["ac_bonus"] += effects.get("ac_bonus", 0)
        bonuses["damage_bonus"] += effects.get("damage_bonus", 0)
        if "ranged_damage_override" in effects:
            ranged_override = effects["ranged_damage_override"]
    bonuses["ranged_damage_override"] = ranged_override
    return bonuses


def apply_gear(character_state: dict[str, Any], token: dict[str, Any]) -> None:
    """Mutate a session token to include equipment bonuses."""
    equipment = character_state.get("equipment", {})
    bonuses = _equipment_bonuses(equipment)
    token["ac"] = token.get("ac", 10) + bonuses["ac_bonus"]
    token["damage_bonus"] = bonuses["damage_bonus"]
    if bonuses["ranged_damage_override"]:
        token["ranged_damage"] = bonuses["ranged_damage_override"]


def default_inventory() -> dict[str, Any]:
    return {"inventory": [], "equipment": {}}


def add_item(character_state: dict[str, Any], item: dict[str, Any]) -> None:
    """Add a loot item to a character's inventory."""
    if "inventory" not in character_state:
        character_state["inventory"] = []
    character_state["inventory"].append(item)


def equip_item(character_state: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
    """Equip an inventory item, returning any item displaced from the slot."""
    inventory = character_state.get("inventory", [])
    item = next((i for i in inventory if i.get("instance_id") == instance_id), None)
    if not item:
        return None
    slot = item.get("slot")
    if not slot:
        return None
    equipment = character_state.setdefault("equipment", {})
    previous = equipment.get(slot)
    equipment[slot] = item
    inventory.remove(item)
    if previous:
        inventory.append(previous)
    return item


def use_consumable(character_state: dict[str, Any], instance_id: str) -> int:
    """Use a consumable item and return HP restored (0 if not a potion/usable)."""
    inventory = character_state.get("inventory", [])
    item = next((i for i in inventory if i.get("instance_id") == instance_id), None)
    if not item:
        return 0
    if item.get("slot") != "consumable":
        return 0
    restore = item.get("effects", {}).get("hp_restore", 0)
    if restore:
        inventory.remove(item)
    return restore
