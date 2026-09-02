"""OSRIC combat resolution helpers.

Implements melee/ranged attacks, damage, and spell effects using OSRIC
mechanics (THAC0 vs descending AC, ability modifiers, range penalties).
"""
from __future__ import annotations

import random
from typing import Any

from engine.dice import roll_expression
from rulesets.osric.adapter import (
    CLASS_FEATURES,
    COMBAT,
    constitution_hp_modifier,
    dexterity_modifier,
    get_class,
    get_equipment,
    strength_modifier,
)


def _roll_d20() -> int:
    return random.randint(1, 20)


def _find_equipped_weapon(inventory: list[dict], missile_only: bool = False) -> dict | None:
    for entry in inventory:
        if not entry.get("equipped"):
            continue
        item = get_equipment(entry["item_id"])
        if item.get("category") != "weapons":
            continue
        if missile_only and not item.get("missile", False):
            continue
        if not missile_only and item.get("missile", False):
            continue
        return item
    return None


def _find_any_equipped_weapon(inventory: list[dict]) -> dict | None:
    for entry in inventory:
        if not entry.get("equipped"):
            continue
        item = get_equipment(entry["item_id"])
        if item.get("category") == "weapons":
            return item
    return None


def resolve_attack(
    attacker: dict,
    defender: dict,
    ranged: bool = False,
    range_ft: int = 0,
    backstab: bool = False,
) -> dict[str, Any]:
    """Resolve a single melee or ranged attack using OSRIC THAC0 vs descending AC."""
    attacker_sheet = attacker.get("sheet", {})
    defender_sheet = defender.get("sheet", {})

    thac0 = attacker_sheet.get("thac0", 20)
    target_ac_desc = defender_sheet.get("armour_class_descending", 10)

    weapon = None
    damage_mod = 0
    to_hit_mod = 0
    range_penalty = 0
    backstab_multiplier = 1
    backstab_bonus = 0

    if ranged:
        weapon = _find_equipped_weapon(attacker.get("inventory", []), missile_only=True)
        if weapon is None:
            weapon = _find_any_equipped_weapon(attacker.get("inventory", []))
        dex_mods = dexterity_modifier(attacker["abilities"]["dexterity"])
        to_hit_mod = dex_mods.get("missile_to_hit", 0)
        if weapon and weapon.get("range") and weapon["range"] > 0:
            increments = max(0, (range_ft // weapon["range"]) - 1)
            range_penalty = increments * COMBAT.get("range_penalty_per_increment", -2)
            to_hit_mod += range_penalty
    else:
        weapon = _find_equipped_weapon(attacker.get("inventory", []), missile_only=False)
        if weapon is None:
            weapon = _find_any_equipped_weapon(attacker.get("inventory", []))
        str_mods = strength_modifier(attacker["abilities"]["strength"])
        to_hit_mod = str_mods.get("to_hit", 0)
        damage_mod = str_mods.get("damage", 0)

    if backstab:
        backstab_cfg = COMBAT.get("backstab", {"to_hit_bonus": 4, "damage_multiplier": 2})
        backstab_bonus = backstab_cfg.get("to_hit_bonus", 4)
        backstab_multiplier = backstab_cfg.get("damage_multiplier", 2)
        to_hit_mod += backstab_bonus

    damage_die = weapon.get("damage", COMBAT.get("unarmed_damage", "1d2")) if weapon else COMBAT.get("unarmed_damage", "1d2")
    weapon_name = weapon["name"] if weapon else "Unarmed"

    raw_roll = _roll_d20()
    roll = raw_roll + to_hit_mod
    needed = thac0 - target_ac_desc

    auto_hit = raw_roll == COMBAT.get("auto_hit", 20)
    auto_miss = raw_roll == COMBAT.get("auto_miss", 1)
    hit = auto_hit or (not auto_miss and roll >= needed)

    result: dict[str, Any] = {
        "attacker": attacker.get("name"),
        "defender": defender.get("name"),
        "raw_roll": raw_roll,
        "roll": roll,
        "needed": needed,
        "to_hit_mod": to_hit_mod,
        "range_penalty": range_penalty,
        "backstab": backstab,
        "backstab_bonus": backstab_bonus,
        "backstab_multiplier": backstab_multiplier,
        "hit": hit,
        "ranged": ranged,
        "weapon": weapon_name,
        "damage": 0,
        "damage_mod": damage_mod,
    }

    if hit:
        damage_roll = roll_expression(damage_die)["total"]
        result["damage"] = max(1, (damage_roll + damage_mod) * backstab_multiplier)
        result["damage_roll"] = damage_roll

    return result


def apply_damage(character: dict, damage: int) -> dict:
    """Apply damage to a character, respecting configured death/dying rules."""
    death_threshold = COMBAT.get("death_threshold", -10)
    sheet = character.setdefault("sheet", {})
    sheet["hit_points"] = max(death_threshold, sheet.get("hit_points", 0) - damage)
    character["hit_points"] = sheet["hit_points"]
    if sheet["hit_points"] <= death_threshold:
        sheet["hit_points"] = death_threshold
        character["hit_points"] = death_threshold
    return character


def is_alive(character: dict) -> bool:
    return character.get("sheet", {}).get("hit_points", 0) > COMBAT.get("death_threshold", -10)


def is_conscious(character: dict) -> bool:
    return character.get("sheet", {}).get("hit_points", 0) > COMBAT.get("unconscious_threshold", 0)


def heal_damage(character: dict, amount: int) -> dict:
    """Heal a character up to their maximum hit points."""
    sheet = character.setdefault("sheet", {})
    max_hp = sheet.get("max_hit_points", sheet.get("hit_points", 0))
    sheet["hit_points"] = min(max_hp, sheet.get("hit_points", 0) + amount)
    character["hit_points"] = sheet["hit_points"]
    return character


def _roll_2d6() -> int:
    return random.randint(1, 6) + random.randint(1, 6)


def check_morale(
    morale: int,
    bonus: int = 0,
    penalty: int = 0,
    roll: int | None = None,
) -> dict[str, Any]:
    """Roll 2d6 against a morale score; return pass/fail details.

    A roll less than or equal to the effective morale score holds; a higher
    roll breaks.  Bonuses raise the effective score, penalties lower it.
    """
    if roll is None:
        roll = _roll_2d6()
    effective = morale + bonus - penalty
    return {
        "roll": roll,
        "morale": morale,
        "effective": effective,
        "passed": roll <= effective,
    }


def check_surprise(
    party_alertness: int = 0,
    enemy_alertness: int = 0,
    party_roll: int | None = None,
    enemy_roll: int | None = None,
) -> dict[str, Any]:
    """Determine surprise for a new encounter.

    Alertness reduces the chance the party is surprised and increases the
    chance the enemy is surprised.  If no rolls are supplied, d6s are rolled.
    """
    cfg = COMBAT.get("surprise", {"chance_in_6": 2})
    base = cfg.get("chance_in_6", 2)
    party_threshold = max(1, base - party_alertness)
    enemy_threshold = min(5, base + enemy_alertness)
    if party_roll is None:
        party_roll = random.randint(1, 6)
    if enemy_roll is None:
        enemy_roll = random.randint(1, 6)
    return {
        "party_surprised": party_roll <= party_threshold,
        "enemy_surprised": enemy_roll <= enemy_threshold,
        "party_roll": party_roll,
        "enemy_roll": enemy_roll,
        "party_threshold": party_threshold,
        "enemy_threshold": enemy_threshold,
    }


def turn_undead(
    turner_level: int,
    undead_type: str,
    undead_hd: int = 1,
    class_id: str = "cleric",
    roll: int | None = None,
) -> dict[str, Any]:
    """Resolve a Turn Undead attempt against a single undead creature.

    Looks up the target number for the turning class and rolls d20 if no
    roll is supplied.  A natural 20 or a turner four or more levels above
    the undead's HD destroys it outright.
    """
    table = CLASS_FEATURES.get("turn_undead", {}).get(class_id, {})
    target = table.get(undead_type.lower())
    if target is None:
        return {"roll": roll, "target": None, "turned": False, "destroyed": False}
    if roll is None:
        roll = _roll_d20()
    success = roll >= target
    destroyed = success and (roll == 20 or turner_level > undead_hd + 3)
    return {
        "roll": roll,
        "target": target,
        "turned": success,
        "destroyed": destroyed,
    }
