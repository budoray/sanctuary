"""OSRIC ruleset adapter for Sanctuary.

Loads data-driven rules from YAML and exposes creation/validation helpers.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml

from engine.dice import roll_expression

_RULESET_DIR = Path(__file__).parent
_DATA_DIR = _RULESET_DIR / "data"


def _load_yaml(name: str) -> Any:
    with open(_DATA_DIR / name, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


ANCESTRIES: dict[str, dict] = _load_yaml("ancestries.yaml")
CLASSES: dict[str, dict] = _load_yaml("classes.yaml")
ALIGNMENTS: list[str] = _load_yaml("alignments.yaml")
ABILITIES: dict = _load_yaml("abilities.yaml")
ABILITY_MODIFIERS: dict = _load_yaml("ability_modifiers.yaml")
SAVING_THROWS: dict[str, dict] = _load_yaml("saving_throws.yaml")
THAC0: dict[str, int] = _load_yaml("thac0.yaml")
STARTING_GOLD: dict[str, dict] = _load_yaml("starting_gold.yaml")
EQUIPMENT: dict = _load_yaml("equipment.yaml")


ABILITY_ORDER = ABILITIES["abilities"]


def _equipment_map() -> dict[str, dict]:
    items: dict[str, dict] = {}
    for category in ("armour", "shields", "weapons", "gear"):
        for item in EQUIPMENT.get(category, []):
            items[item["id"]] = {**item, "category": category}
    return items


EQUIPMENT_BY_ID: dict[str, dict] = _equipment_map()


def roll_3d6() -> int:
    return sum(random.randint(1, 6) for _ in range(3))


def roll_ability_scores() -> dict[str, int]:
    return {ability: roll_3d6() for ability in ABILITY_ORDER}


def ancestry_ids() -> list[str]:
    return list(ANCESTRIES.keys())


def class_ids() -> list[str]:
    return list(CLASSES.keys())


def equipment_ids() -> list[str]:
    return list(EQUIPMENT_BY_ID.keys())


def get_equipment(item_id: str) -> dict:
    return EQUIPMENT_BY_ID[item_id]


def equipment_options() -> list[dict]:
    """Return equipment items in a UI-friendly form."""
    return [
        {"id": iid, "name": item["name"], "category": item["category"]}
        for iid, item in EQUIPMENT_BY_ID.items()
    ]


def get_ancestry(ancestry_id: str) -> dict:
    return ANCESTRIES[ancestry_id]


def get_class(class_id: str) -> dict:
    return CLASSES[class_id]


def roll_dice(dice: str) -> int:
    return roll_expression(dice)["total"]


def apply_ancestry_adjustments(
    ancestry_id: str, abilities: dict[str, int]
) -> dict[str, int]:
    """Apply ancestral ability adjustments and cap post-adjustment scores."""
    ancestry = get_ancestry(ancestry_id)
    adjusted = dict(abilities)
    for ability, delta in ancestry.get("ability_adjustments", {}).items():
        adjusted[ability] = adjusted.get(ability, 0) + delta
    for ability, cap in ancestry.get("ability_score_caps", {}).items():
        if adjusted.get(ability, 0) > cap:
            adjusted[ability] = cap
    return adjusted


def meets_requirements(
    ancestry_id: str, class_id: str, alignment: str, abilities: dict[str, int]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    ancestry = get_ancestry(ancestry_id)
    klass = get_class(class_id)

    if class_id not in ancestry["allowed_classes"]:
        errors.append(f"{ancestry['name']} cannot be {klass['name']}.")

    for req, value in klass.get("ability_score_requirements", {}).items():
        if abilities.get(req, 0) < value:
            errors.append(
                f"{klass['name']} requires {req} >= {value} (rolled {abilities.get(req)})."
            )

    for req, value in ancestry.get("ability_score_requirements", {}).items():
        if abilities.get(req, 0) < value:
            errors.append(
                f"{ancestry['name']} requires {req} >= {value} (rolled {abilities.get(req)})."
            )

    for minimum, value in ancestry.get("ability_score_minimums", {}).items():
        if abilities.get(minimum, 0) < value:
            errors.append(
                f"{ancestry['name']} requires {minimum} >= {value} after adjustments (got {abilities.get(minimum)})."
            )

    for cap, value in ancestry.get("ability_score_caps", {}).items():
        if abilities.get(cap, 0) > value:
            errors.append(
                f"{ancestry['name']} caps {cap} at {value} (got {abilities.get(cap)})."
            )

    if alignment not in klass.get("allowed_alignments", ALIGNMENTS):
        errors.append(f"{klass['name']} cannot be {alignment}.")

    return (not errors, errors)


def strength_modifier(score: int) -> dict[str, int]:
    return ABILITY_MODIFIERS["strength"].get(score, {"to_hit": 0, "damage": 0})


def dexterity_modifier(score: int) -> dict[str, int]:
    return ABILITY_MODIFIERS["dexterity"].get(
        score,
        {
            "surprise": 0,
            "missile_to_hit": 0,
            "initiative_missile": 0,
            "ac_descending": 0,
            "ac_ascending": 0,
            "agility_save": 0,
        },
    )


def constitution_hp_modifier(score: int, fighter_type: bool = False) -> int:
    row = ABILITY_MODIFIERS["constitution"].get(
        score, {"hp_modifier": 0, "fighter_extra_hp": 0}
    )
    extra = row.get("fighter_extra_hp", 0) if fighter_type else 0
    return row["hp_modifier"] + extra


def intelligence_modifier(score: int) -> dict[str, int]:
    return ABILITY_MODIFIERS["intelligence"].get(score, {"bonus_languages": 0})


def wisdom_modifier(score: int) -> dict[str, int]:
    return ABILITY_MODIFIERS["wisdom"].get(score, {"mental_save": 0})


def charisma_modifier(score: int) -> dict[str, int]:
    return ABILITY_MODIFIERS["charisma"].get(
        score, {"sidekick_limit": 0, "loyalty": 0, "reaction": 0}
    )


def base_armour_class(dexterity: int) -> int:
    mod = dexterity_modifier(dexterity)["ac_ascending"]
    return 10 + mod


def compute_armour_class(abilities: dict[str, int], inventory: list[dict]) -> dict[str, int]:
    """Compute descending and ascending AC from equipped armour, shield, and DEX."""
    dex_mod = dexterity_modifier(abilities["dexterity"])

    equipped_armour = None
    equipped_shield = None
    for entry in inventory:
        if not entry.get("equipped"):
            continue
        item = EQUIPMENT_BY_ID.get(entry.get("item_id", ""), {})
        if item.get("category") == "armour":
            equipped_armour = item
        elif item.get("category") == "shields":
            equipped_shield = item

    if equipped_armour:
        descending = equipped_armour["ac_descending"] + dex_mod["ac_descending"]
        ascending = equipped_armour["ac_ascending"] + dex_mod["ac_ascending"]
    else:
        descending = 10 + dex_mod["ac_descending"]
        ascending = 10 + dex_mod["ac_ascending"]

    if equipped_shield:
        descending += equipped_shield.get("ac_descending_modifier", 0)
        ascending += equipped_shield.get("ac_ascending_modifier", 0)

    return {"descending": descending, "ascending": ascending}


def inventory_weight(inventory: list[dict]) -> float:
    total = 0.0
    for entry in inventory:
        item = EQUIPMENT_BY_ID.get(entry.get("item_id", ""), {})
        weight = item.get("weight")
        if weight is None:
            continue
        total += float(weight) * max(1, entry.get("quantity", 1))
    return total


def armour_movement_cap(inventory: list[dict]) -> int | None:
    """Return the strictest movement cap from equipped armour, if any."""
    cap = None
    for entry in inventory:
        if not entry.get("equipped"):
            continue
        item = EQUIPMENT_BY_ID.get(entry.get("item_id", ""), {})
        if item.get("category") == "armour":
            item_cap = item.get("movement_cap")
            if item_cap is not None and (cap is None or item_cap < cap):
                cap = item_cap
    return cap


def compute_movement(ancestry_id: str, inventory: list[dict]) -> int:
    base = get_ancestry(ancestry_id).get("base_movement", 120)
    cap = armour_movement_cap(inventory)
    if cap is not None and cap < base:
        return cap
    return base


def starting_hit_points(class_id: str, constitution: int) -> int:
    """First-level hit points: roll class hit dice and apply CON modifier per die."""
    klass = get_class(class_id)
    hit_die = klass.get("hit_die", 8)
    dice_count = klass.get("starting_hit_dice", 1)
    con_mod = constitution_hp_modifier(constitution, klass.get("fighter_type", False))
    total = 0
    for _ in range(dice_count):
        roll = random.randint(1, hit_die)
        total += max(1, roll + con_mod)
    return total


def roll_starting_gold(class_id: str) -> int:
    spec = STARTING_GOLD[class_id]
    return roll_dice(spec["dice"]) * spec.get("multiplier", 1)


def build_sheet(
    ancestry_id: str,
    class_id: str,
    alignment: str,
    abilities: dict[str, int],
    hit_points: int,
    inventory: list[dict] | None = None,
    starting_gold: int | None = None,
) -> dict[str, Any]:
    """Assemble the first-level OSRIC character sheet."""
    ancestry = get_ancestry(ancestry_id)
    klass = get_class(class_id)
    inventory = inventory or []
    if starting_gold is None:
        starting_gold = roll_starting_gold(class_id)

    ac = compute_armour_class(abilities, inventory)

    return {
        "level": 1,
        "xp": 0,
        "next_level_xp": klass.get("next_level_xp", 0),
        "hit_points": hit_points,
        "max_hit_points": hit_points,
        "armour_class": ac["ascending"],
        "armour_class_descending": ac["descending"],
        "thac0": THAC0.get(class_id, 20),
        "base_movement": ancestry.get("base_movement", 120),
        "movement": compute_movement(ancestry_id, inventory),
        "starting_gold": starting_gold,
        "remaining_gold": starting_gold,
        "alignment": alignment,
        "saving_throws": dict(SAVING_THROWS.get(class_id, {})),
        "ability_modifiers": {
            "strength": strength_modifier(abilities["strength"]),
            "dexterity": dexterity_modifier(abilities["dexterity"]),
            "constitution": {
                "hp_modifier": constitution_hp_modifier(
                    abilities["constitution"], klass.get("fighter_type", False)
                ),
                **{
                    k: v
                    for k, v in ABILITY_MODIFIERS["constitution"]
                    .get(abilities["constitution"], {})
                    .items()
                    if k != "fighter_extra_hp"
                },
            },
            "intelligence": intelligence_modifier(abilities["intelligence"]),
            "wisdom": wisdom_modifier(abilities["wisdom"]),
            "charisma": charisma_modifier(abilities["charisma"]),
        },
        "inventory": {
            "items": inventory,
            "weight": inventory_weight(inventory),
        },
    }


def _inventory_index(inventory: list[dict], item_id: str) -> int | None:
    for i, entry in enumerate(inventory):
        if entry.get("item_id") == item_id:
            return i
    return None


def add_item(
    inventory: list[dict],
    item_id: str,
    quantity: int = 1,
    equipped: bool = False,
    class_id: str = "",
) -> list[dict]:
    """Add a piece of equipment to the inventory."""
    if item_id not in EQUIPMENT_BY_ID:
        raise ValueError(f"Unknown equipment: {item_id}")
    quantity = max(1, int(quantity))
    idx = _inventory_index(inventory, item_id)
    result = [dict(e) for e in inventory]
    if idx is not None:
        result[idx]["quantity"] = result[idx].get("quantity", 1) + quantity
        if equipped:
            result = equip_item(result, item_id, class_id=class_id)
    else:
        entry = {"item_id": item_id, "quantity": quantity, "equipped": equipped}
        result.append(entry)
        if equipped:
            result = equip_item(result, item_id, class_id=class_id)
    return result


def remove_item(inventory: list[dict], item_id: str) -> list[dict]:
    """Remove an item entirely from the inventory."""
    return [e for e in inventory if e.get("item_id") != item_id]


def equip_item(inventory: list[dict], item_id: str, class_id: str = "") -> list[dict]:
    """Equip an item, enforcing one equipped armour and one shield at a time."""
    if item_id not in EQUIPMENT_BY_ID:
        raise ValueError(f"Unknown equipment: {item_id}")
    item = EQUIPMENT_BY_ID[item_id]
    if class_id:
        ok, error = can_equip(class_id, item_id)
        if not ok:
            raise ValueError(error)
    result = [dict(e) for e in inventory]
    idx = _inventory_index(result, item_id)
    if idx is None:
        result.append({"item_id": item_id, "quantity": 1, "equipped": True})
    else:
        result[idx]["equipped"] = True

    category = item.get("category")
    for i, entry in enumerate(result):
        if entry.get("item_id") == item_id:
            continue
        other = EQUIPMENT_BY_ID.get(entry.get("item_id", ""), {})
        if entry.get("equipped") and other.get("category") == category and category in (
            "armour",
            "shields",
        ):
            result[i]["equipped"] = False
    return result


def unequip_item(inventory: list[dict], item_id: str) -> list[dict]:
    """Unequip an item without removing it from inventory."""
    result = [dict(e) for e in inventory]
    idx = _inventory_index(result, item_id)
    if idx is not None:
        result[idx]["equipped"] = False
    return result


def can_equip(class_id: str, item_id: str) -> tuple[bool, str]:
    """Check whether a class is permitted to use a given piece of equipment."""
    klass = get_class(class_id)
    item = EQUIPMENT_BY_ID.get(item_id)
    if not item:
        return False, f"Unknown equipment: {item_id}"

    category = item.get("category")
    if category == "armour":
        allowed = klass.get("armour_allowed", [])
        if "all" in allowed or item_id in allowed:
            return True, ""
        return False, f"{klass['name']} cannot wear {item['name']}."
    if category == "shields":
        if klass.get("shields_allowed", False):
            return True, ""
        return False, f"{klass['name']} cannot use shields."
    if category == "weapons":
        allowed = klass.get("weapons_allowed", [])
        if "all" in allowed or item_id in allowed:
            return True, ""
        return False, f"{klass['name']} cannot use {item['name']}."
    return True, ""


def create_character_data(
    ancestry_id: str, class_id: str, alignment: str, name: str
) -> dict[str, Any]:
    raw_abilities = roll_ability_scores()
    abilities = apply_ancestry_adjustments(ancestry_id, raw_abilities)
    ok, errors = meets_requirements(ancestry_id, class_id, alignment, abilities)
    if not ok:
        raise ValueError("; ".join(errors))

    hit_points = starting_hit_points(class_id, abilities["constitution"])
    starting_gold = roll_starting_gold(class_id)
    inventory: list[dict] = []
    sheet = build_sheet(
        ancestry_id,
        class_id,
        alignment,
        abilities,
        hit_points,
        inventory=inventory,
        starting_gold=starting_gold,
    )

    return {
        "name": name,
        "ancestry": ancestry_id,
        "class": class_id,
        "alignment": alignment,
        "abilities": abilities,
        "hit_points": hit_points,
        "starting_gold": starting_gold,
        "inventory": inventory,
        "sheet": sheet,
    }


def serialise_character(row: dict) -> dict:
    """Convert a database row into an API-friendly dict."""
    abilities = {
        "strength": row["strength"],
        "intelligence": row["intelligence"],
        "wisdom": row["wisdom"],
        "dexterity": row["dexterity"],
        "constitution": row["constitution"],
        "charisma": row["charisma"],
    }
    inventory = row.get("inventory") or []
    sheet = build_sheet(
        row["ancestry"],
        row["class"],
        row["alignment"],
        abilities,
        row["hit_points"],
        inventory=inventory,
        starting_gold=row.get("starting_gold", 0),
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "ancestry": row["ancestry"],
        "class": row["class"],
        "alignment": row["alignment"],
        "abilities": abilities,
        "hit_points": row["hit_points"],
        "starting_gold": row.get("starting_gold", 0),
        "inventory": inventory,
        "sheet": sheet,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }
