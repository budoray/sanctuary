"""Native OSRIC ruleset adapter for the dungeon-crawl game.

Loads data-driven rules from YAML and exposes creation/validation helpers.
All formulas and constants are read from config/ so they can be modded.
"""
from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from engine.dice import roll_expression
from rulesets.osric import loader


ANCESTRIES: dict[str, dict] = loader.load_data("ancestries.yaml")
CLASSES: dict[str, dict] = loader.load_data("classes.yaml")
ALIGNMENTS: list[str] = loader.load_data("alignments.yaml")
ABILITIES: dict = loader.load_data("abilities.yaml")
ABILITY_MODIFIERS: dict = loader.load_data("ability_modifiers.yaml")
SAVING_THROWS: dict[str, dict] = loader.load_data("saving_throws.yaml")
THAC0: dict[str, int] = loader.load_data("thac0.yaml")
STARTING_GOLD: dict[str, dict] = loader.load_data("starting_gold.yaml")
EQUIPMENT: dict = loader.load_data("equipment.yaml")
CLASS_FEATURES: dict = loader.load_data("class_features.yaml")

CORE: dict = loader.load_config("core.yaml")
ROLLING: dict = loader.load_config("rolling.yaml")
PROGRESSION: dict = loader.load_config("progression.yaml")
COMBAT: dict = loader.load_config("combat.yaml")


ABILITY_ORDER: list[str] = CORE.get("ability_order", ABILITIES.get("abilities", []))


def _equipment_map() -> dict[str, dict]:
    items: dict[str, dict] = {}
    for category in ("armour", "shields", "weapons", "gear"):
        for item in EQUIPMENT.get(category, []):
            items[item["id"]] = {**item, "category": category}
    return items


EQUIPMENT_BY_ID: dict[str, dict] = _equipment_map()


def class_features(class_id: str) -> dict[str, Any]:
    """Return class abilities, thief skills, and starting package for a class."""
    return {
        "starting_package": CLASS_FEATURES.get("starting_packages", {}).get(class_id),
        "abilities": CLASS_FEATURES.get("abilities", {}).get(class_id, []),
        "thief_skills": CLASS_FEATURES.get("thief_skills", {}) if class_id == "thief" else {},
    }


def _roll_dice_expression(dice: str) -> int:
    return roll_expression(dice)["total"]


def _drop_lowest(rolls: list[int], n: int) -> list[int]:
    return sorted(rolls)[n:]


def _roll_method_config(method: str) -> dict:
    cfg = ROLLING.get("methods", {}).get(method)
    if not cfg:
        raise ValueError(f"Unknown roll method: {method}")
    return cfg


def roll_ability_scores(method: str = "3d6_in_order") -> dict[str, int]:
    """Roll ability scores using the named method from config."""
    cfg = _roll_method_config(method)
    assign = cfg.get("assign", "in_order")
    if assign == "pool":
        raise ValueError(f"Use roll_ability_pool for method {method}")

    dice = cfg["dice"]
    drop = cfg.get("drop_lowest", 0)
    rolls_per = cfg.get("rolls_per_ability", 1)
    keep = cfg.get("keep", "highest")

    result: dict[str, int] = {}
    for ability in ABILITY_ORDER:
        rolls = [_roll_dice_expression(dice) for _ in range(rolls_per)]
        if drop:
            rolls = _drop_lowest(rolls, drop)
        if keep == "highest":
            result[ability] = max(rolls)
        else:
            result[ability] = min(rolls)
    return result


def roll_ability_pool(method: str = "3d6") -> list[int]:
    """Roll a pool of six ability scores for assign-to-taste creation."""
    cfg = _roll_method_config(method) if method in ROLLING.get("methods", {}) else None
    if cfg and cfg.get("assign") == "pool":
        dice = cfg.get("pool_dice", cfg["dice"])
        size = cfg.get("pool_size", 6)
    elif cfg:
        dice = cfg["dice"]
        size = 6
    else:
        # Fallback for raw dice strings like "3d6" or "4d6_drop_lowest".
        dice = method
        size = 6
    return [_roll_dice_expression(dice) for _ in range(size)]


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


def base_armour_class() -> dict[str, int]:
    cfg = CORE.get("base_armour_class", {"descending": 10, "ascending": 10})
    return {"descending": cfg["descending"], "ascending": cfg["ascending"]}


def compute_armour_class(abilities: dict[str, int], inventory: list[dict]) -> dict[str, Any]:
    """Compute descending and ascending AC from equipped armour, shield, and DEX."""
    dex_mod = dexterity_modifier(abilities["dexterity"])
    base = base_armour_class()

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

    armour_desc = 0
    armour_asc = 0
    shield_desc = 0
    shield_asc = 0

    if equipped_armour:
        armour_desc = equipped_armour["ac_descending"] - base["descending"]
        armour_asc = equipped_armour["ac_ascending"] - base["ascending"]

    if equipped_shield:
        shield_desc = equipped_shield.get("ac_descending_modifier", 0)
        shield_asc = equipped_shield.get("ac_ascending_modifier", 0)

    descending = base["descending"] + armour_desc + shield_desc + dex_mod["ac_descending"]
    ascending = base["ascending"] + armour_asc + shield_asc + dex_mod["ac_ascending"]

    return {
        "descending": descending,
        "ascending": ascending,
        "breakdown": {
            "base": {"descending": base["descending"], "ascending": base["ascending"]},
            "armour": {
                "name": equipped_armour["name"] if equipped_armour else None,
                "descending": armour_desc,
                "ascending": armour_asc,
            },
            "shield": {
                "name": equipped_shield["name"] if equipped_shield else None,
                "descending": shield_desc,
                "ascending": shield_asc,
            },
            "dexterity": {
                "descending": dex_mod["ac_descending"],
                "ascending": dex_mod["ac_ascending"],
            },
        },
    }


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
    base = get_ancestry(ancestry_id).get(
        "base_movement", CORE.get("base_movement", {}).get("default", 120)
    )
    cap = armour_movement_cap(inventory)
    if cap is not None and cap < base:
        return cap
    return base


def compute_encumbrance(inventory: list[dict]) -> dict[str, Any]:
    """Return encumbrance tier, movement penalty, and effective movement."""
    weight = inventory_weight(inventory)
    tiers = COMBAT.get("encumbrance", {})
    min_movement = COMBAT.get("min_movement", 30)
    for key, cfg in tiers.items():
        if weight <= cfg.get("max_weight", 999999):
            penalty = cfg.get("movement_penalty", 0)
            return {
                "tier": key,
                "label": cfg.get("label", key),
                "weight": round(weight, 1),
                "max_weight": cfg.get("max_weight"),
                "movement_penalty": penalty,
            }
    # Fallback if config is empty.
    return {"tier": "light", "label": "Light", "weight": round(weight, 1), "max_weight": None, "movement_penalty": 0}


def encumbered_movement(base_movement: int, inventory: list[dict]) -> int:
    """Base movement after encumbrance penalty, but not below min_movement."""
    enc = compute_encumbrance(inventory)
    min_movement = COMBAT.get("min_movement", 30)
    return max(min_movement, base_movement - enc.get("movement_penalty", 0))


def starting_hit_points(class_id: str, constitution: int) -> int:
    """First-level hit points: roll class hit dice and apply CON modifier per die."""
    klass = get_class(class_id)
    cfg = PROGRESSION["hp"]["first_level"]
    hit_die = klass.get("hit_die", 8)
    dice_count = klass.get("starting_hit_dice", 1)
    con_mod = constitution_hp_modifier(constitution, klass.get("fighter_type", False))
    min_hp = cfg.get("min_hp_per_die", 1)
    total = 0
    for _ in range(dice_count):
        roll = random.randint(1, hit_die)
        total += max(min_hp, roll + con_mod)
    return total


def roll_starting_gold(class_id: str) -> int:
    spec = STARTING_GOLD[class_id]
    gold = roll_dice(spec["dice"]) * spec.get("multiplier", 1)
    if "min_gold" in spec:
        gold = max(gold, spec["min_gold"])
    return gold


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
    con_mod = constitution_hp_modifier(abilities["constitution"], klass.get("fighter_type", False))
    base_movement = ancestry.get("base_movement", 120)
    enc = compute_encumbrance(inventory)

    return {
        "level": 1,
        "xp": 0,
        "next_level_xp": klass.get("next_level_xp", 0),
        "hit_points": hit_points,
        "max_hit_points": hit_points,
        "hit_die": f"1d{klass.get('hit_die', 8)}",
        "hp_breakdown": {
            "hit_die": f"1d{klass.get('hit_die', 8)}",
            "con_modifier": con_mod,
        },
        "armour_class": ac["ascending"],
        "armour_class_descending": ac["descending"],
        "ac_breakdown": ac["breakdown"],
        "thac0": THAC0.get(class_id, 20),
        "base_movement": base_movement,
        "movement": encumbered_movement(base_movement, inventory),
        "encumbrance": enc,
        "starting_gold": starting_gold,
        "remaining_gold": starting_gold,
        "alignment": alignment,
        "saving_throws": dict(SAVING_THROWS.get(class_id, {})),
        "turn_undead": CLASS_FEATURES.get("turn_undead", {}).get(class_id),
        "ancestry_traits": ancestry.get("traits", []),
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
    ancestry_id: str,
    class_id: str,
    alignment: str,
    name: str,
    roll_method: str = "3d6_in_order",
    abilities: dict[str, int] | None = None,
) -> dict[str, Any]:
    if abilities is None:
        raw_abilities = roll_ability_scores(roll_method)
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


def _match_thac0_group(class_id: str, klass: dict) -> dict:
    groups = PROGRESSION.get("thac0", {}).get("groups", [])
    for group in groups:
        cond = group.get("condition", {})
        if cond.get("fighter_type") and klass.get("fighter_type"):
            return group
        if ids := cond.get("class_ids"):
            if class_id in ids:
                return group
    return {"base": 20, "step": 1, "step_reduction": 0, "min_value": 1}


def thac0_for_level(class_id: str, level: int) -> int:
    """THAC0 progression by class and level, driven by config."""
    level = max(1, level)
    klass = get_class(class_id)
    group = _match_thac0_group(class_id, klass)
    base = group.get("base", 20)
    step = group.get("step", 1)
    reduction = group.get("step_reduction", 0)
    min_value = group.get("min_value", 1)
    return max(min_value, base - ((level - 1) // step) * reduction)


def saving_throws_for_level(class_id: str, level: int) -> dict[str, int]:
    """Saving-throw improvement driven by config."""
    base = SAVING_THROWS.get(class_id, {})
    cfg = PROGRESSION.get("saving_throws", {}).get("improvement", {})
    levels_per = cfg.get("levels_per_bonus", 4)
    bonus = cfg.get("bonus", -1)
    min_value = cfg.get("min_value", 1)
    times = max(0, (level - 1) // levels_per)
    return {
        k: max(min_value, v + times * bonus)
        for k, v in base.items()
        if isinstance(v, int)
    }


def xp_for_next_level(class_id: str, current_level: int) -> int:
    """XP thresholds driven by config."""
    current_level = max(1, current_level)
    klass = get_class(class_id)
    cfg = PROGRESSION.get("xp", {}).get("formula", {})
    base = klass.get(cfg.get("base_field", "next_level_xp"), 2000)
    multiplier = cfg.get("multiplier", 2)
    exponent_key = cfg.get("exponent", "level_minus_1")
    if exponent_key == "level_minus_1":
        exponent = current_level - 1
    else:
        exponent = current_level
    return int(base * (multiplier ** exponent))


def level_up_hit_points(class_id: str, constitution: int, current_max_hp: int) -> int:
    """Roll hit die + CON modifier for a new level."""
    cfg = PROGRESSION["hp"]["level_up"]
    klass = get_class(class_id)
    hit_die = klass.get("hit_die", 8)
    con_mod = constitution_hp_modifier(constitution, klass.get("fighter_type", False))
    min_gain = cfg.get("min_hp_gained", 1)
    return max(min_gain, random.randint(1, hit_die) + con_mod)


def level_up(character: dict) -> dict:
    """Apply one OSRIC level-up to a character dict and return the updated dict."""
    class_id = character["class"]
    abilities = character["abilities"]
    sheet = character["sheet"]

    new_level = sheet["level"] + 1
    hp_gain = level_up_hit_points(class_id, abilities["constitution"], sheet["max_hit_points"])
    new_max_hp = sheet["max_hit_points"] + hp_gain

    sheet["level"] = new_level
    sheet["max_hit_points"] = new_max_hp
    sheet["hit_points"] = new_max_hp
    sheet["thac0"] = thac0_for_level(class_id, new_level)
    sheet["saving_throws"] = saving_throws_for_level(class_id, new_level)
    sheet["next_level_xp"] = xp_for_next_level(class_id, new_level)
    sheet["movement"] = compute_movement(character["ancestry"], sheet["inventory"]["items"])

    slots = sheet.get("spell_slots", {})
    slot_cfg = PROGRESSION.get("spell_slots", {})
    caster_classes = slot_cfg.get("caster_classes", [])
    per_level = slot_cfg.get("per_level", [])
    if class_id in caster_classes:
        for row in per_level:
            if row.get("level") == new_level:
                for slot_level, count in row.get("slots", {}).items():
                    slots[slot_level] = slots.get(slot_level, 0) + count
                break
        else:
            # Default: +1 first-level slot per level if no explicit row.
            slots["1"] = slots.get("1", 0) + 1
    sheet["spell_slots"] = slots

    character["hit_points"] = new_max_hp
    return character


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
