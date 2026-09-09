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
    dexterity_modifier,
    get_equipment,
    strength_modifier,
    wisdom_modifier,
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


def _active_spell_bonuses(character: dict) -> dict[str, int]:
    """Return combat modifiers from active spells on a character sheet."""
    bonuses = {"to_hit_mod": 0, "damage_mod": 0, "ac_descending_mod": 0, "ac_ascending_mod": 0}
    sheet = character.get("sheet", {}) if isinstance(character, dict) else {}
    for entry in sheet.get("active_spells", []):
        sid = entry.get("spell_id", "")
        if sid == "bless":
            bonuses["to_hit_mod"] += 1
        elif sid == "shield":
            bonuses["ac_ascending_mod"] += 1
            bonuses["ac_descending_mod"] -= 1
    return bonuses


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
    target_ac_asc = defender_sheet.get("armour_class", 20 - target_ac_desc)

    attacker_spells = _active_spell_bonuses(attacker)
    defender_spells = _active_spell_bonuses(defender)

    weapon = None
    damage_mod = 0
    to_hit_mod = attacker.get("to_hit_mod", 0)
    range_penalty = 0
    backstab_multiplier = 1
    backstab_bonus = 0

    # Apply Shield and other AC-improving spells to the defender.
    target_ac_desc += defender_spells["ac_descending_mod"]
    target_ac_asc += defender_spells["ac_ascending_mod"]

    if ranged:
        weapon = _find_equipped_weapon(attacker.get("inventory", []), missile_only=True)
        if weapon is None:
            weapon = _find_any_equipped_weapon(attacker.get("inventory", []))
        dex_mods = dexterity_modifier(attacker["abilities"]["dexterity"])
        to_hit_mod += dex_mods.get("missile_to_hit", 0)
        if weapon and weapon.get("range") and weapon["range"] > 0:
            increments = max(0, (range_ft // weapon["range"]) - 1)
            range_penalty = increments * COMBAT.get("range_penalty_per_increment", -2)
            to_hit_mod += range_penalty
    else:
        weapon = _find_equipped_weapon(attacker.get("inventory", []), missile_only=False)
        if weapon is None:
            weapon = _find_any_equipped_weapon(attacker.get("inventory", []))
        str_mods = strength_modifier(attacker["abilities"]["strength"])
        to_hit_mod += str_mods.get("to_hit", 0)
        damage_mod = str_mods.get("damage", 0)

    # Apply active spell bonuses (Bless, etc.) after ability modifiers.
    to_hit_mod += attacker_spells["to_hit_mod"]

    if backstab:
        backstab_cfg = COMBAT.get("backstab", {"to_hit_bonus": 4, "damage_multiplier": 2})
        backstab_bonus = backstab_cfg.get("to_hit_bonus", 4)
        backstab_multiplier = backstab_cfg.get("damage_multiplier", 2)
        to_hit_mod += backstab_bonus

    natural_damage = attacker.get("damage")
    if weapon and natural_damage:
        damage_die = natural_damage
        weapon_name = weapon.get("name", "natural attack")
    elif weapon:
        damage_die = weapon.get("damage", COMBAT.get("unarmed_damage", "1d2"))
        weapon_name = weapon["name"]
    elif natural_damage:
        damage_die = natural_damage
        weapon_name = "natural attack"
    else:
        damage_die = COMBAT.get("unarmed_damage", "1d2")
        weapon_name = "Unarmed"

    # Tutorial band: level 1 player characters get a +2 accuracy bonus so
    # the Crooked Tower is winnable even with streaky d20 rolls.
    klass = attacker.get("class") or attacker_sheet.get("class")
    if attacker_sheet.get("level") == 1 and klass:
        to_hit_mod += 2

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
        damage_result = roll_expression(damage_die)
        damage_roll = damage_result["total"]
        total_damage_mod = damage_mod + attacker.get("damage_mod", 0)
        result["damage"] = max(1, (damage_roll + total_damage_mod) * backstab_multiplier)
        result["damage_roll"] = damage_roll
        result["damage_die"] = damage_die
        result["damage_parts"] = damage_result.get("parts", [])

    result["damage_die"] = result.get("damage_die", damage_die)
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


def saving_throw(
    character: dict,
    save_key: str,
    target: int | None = None,
    modifier: int = 0,
    roll: int | None = None,
) -> dict[str, Any]:
    """Roll a saving throw for a character.

    Uses the character's sheet value for ``save_key`` unless a target number is
    supplied.  Wisdom grants its mental-save modifier against spells.  A natural
    20 always succeeds and a natural 1 always fails.
    """
    sheet = character.get("sheet", {})
    saves = sheet.get("saving_throws", {})
    target_number = target if target is not None else saves.get(save_key)
    if target_number is None:
        raise ValueError(f"Unknown saving throw key: {save_key}")

    if save_key == "spells":
        wis = character.get("abilities", {}).get("wisdom", 10)
        modifier += wisdom_modifier(wis).get("mental_save", 0)

    effective_target = target_number - modifier
    if roll is None:
        roll = _roll_d20()

    auto_success = roll == 20
    auto_fail = roll == 1
    success = auto_success or (not auto_fail and roll >= effective_target)

    return {
        "save_key": save_key,
        "target": target_number,
        "modifier": modifier,
        "effective_target": effective_target,
        "roll": roll,
        "success": success,
    }


def roll_initiative(
    side_a: list[dict],
    side_b: list[dict],
    side_a_name: str = "party",
    side_b_name: str = "enemies",
    roll_a: int | None = None,
    roll_b: int | None = None,
) -> dict[str, Any]:
    """Roll side-based initiative for two sides.

    Each side rolls 1d6 and adds its average DEX initiative-missile reaction
    modifier.  Lower total wins; equal totals are a tie.
    """

    def average_modifier(members: list[dict]) -> float:
        if not members:
            return 0.0
        total = 0.0
        for member in members:
            dex = member.get("abilities", {}).get("dexterity", 10)
            total += dexterity_modifier(dex).get("initiative_missile", 0)
        return round(total / len(members), 1)

    mod_a = average_modifier(side_a)
    mod_b = average_modifier(side_b)
    r_a = roll_a if roll_a is not None else random.randint(1, 6)
    r_b = roll_b if roll_b is not None else random.randint(1, 6)
    total_a = r_a + mod_a
    total_b = r_b + mod_b

    if total_a < total_b:
        winner = side_a_name
    elif total_b < total_a:
        winner = side_b_name
    else:
        winner = "tie"

    return {
        "side_a": {"name": side_a_name, "roll": r_a, "modifier": mod_a, "total": total_a},
        "side_b": {"name": side_b_name, "roll": r_b, "modifier": mod_b, "total": total_b},
        "winner": winner,
    }


def check_reaction(modifier: int = 0, roll: int | None = None) -> dict[str, Any]:
    """Roll a 2d6 reaction check and map the result to an attitude.

    A positive modifier (e.g., high charisma) makes a friendly result more
    likely; a negative modifier makes hostility more likely.
    """
    if roll is None:
        roll = _roll_2d6()
    modified = roll + modifier
    table = COMBAT.get("reaction", {}).get(
        "table",
        [
            {"attitude": "hostile", "max": 5},
            {"attitude": "uncertain", "max": 8},
            {"attitude": "friendly", "max": 12},
        ],
    )
    attitude = None
    for entry in table:
        if modified <= entry["max"]:
            attitude = entry["attitude"]
            break
    if attitude is None:
        attitude = table[-1]["attitude"]

    return {
        "roll": roll,
        "modifier": modifier,
        "modified": modified,
        "attitude": attitude,
    }
