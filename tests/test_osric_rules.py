"""Fast unit tests for the OSRIC rule helpers used by Sanctuary."""
from __future__ import annotations

import random

import pytest

from engine import dice as dice_engine
from rulesets.osric import adapter
from rulesets.osric import combat as osric_combat
from rulesets.osric import spells as osric_spells


def _attacker(weapon: str = "sword_long", strength: int = 10, dexterity: int = 10) -> dict:
    return {
        "name": "Hero",
        "abilities": {
            "strength": strength,
            "intelligence": 10,
            "wisdom": 10,
            "dexterity": dexterity,
            "constitution": 10,
            "charisma": 10,
        },
        "inventory": [{"item_id": weapon, "quantity": 1, "equipped": True}],
        "sheet": {"thac0": 20},
    }


def _defender(ac_descending: int = 10) -> dict:
    return {
        "name": "Target",
        "abilities": {"strength": 10, "dexterity": 10, "constitution": 10},
        "inventory": [],
        "sheet": {"armour_class_descending": ac_descending},
    }


def test_resolve_attack_hit(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 15)
    monkeypatch.setattr(dice_engine.random, "randint", lambda a, b: 4)

    result = osric_combat.resolve_attack(_attacker(), _defender())
    assert result["hit"] is True
    assert result["raw_roll"] == 15
    assert result["needed"] == 10
    assert result["damage"] == 4


def test_resolve_attack_miss(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 5)
    result = osric_combat.resolve_attack(_attacker(), _defender())
    assert result["hit"] is False
    assert result["damage"] == 0


def test_resolve_attack_auto_hit(monkeypatch):
    """A natural 20 hits regardless of the target AC."""
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 20)
    monkeypatch.setattr(dice_engine.random, "randint", lambda a, b: 6)

    result = osric_combat.resolve_attack(_attacker(), _defender(ac_descending=0))
    assert result["hit"] is True
    assert result["raw_roll"] == 20
    assert result["damage"] == 6


def test_resolve_attack_auto_miss(monkeypatch):
    """A natural 1 misses regardless of the target AC."""
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 1)
    result = osric_combat.resolve_attack(_attacker(), _defender(ac_descending=20))
    assert result["hit"] is False
    assert result["damage"] == 0


def test_resolve_attack_damage_range(monkeypatch):
    """Damage for a long sword stays inside the 1d8 range."""
    sides_seen = set()
    for value in range(1, 9):
        monkeypatch.setattr(dice_engine.random, "randint", lambda a, b, v=value: v)
        monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 15)
        result = osric_combat.resolve_attack(_attacker(), _defender())
        assert result["hit"] is True
        assert 1 <= result["damage"] <= 8
        sides_seen.add(result["damage"])
    assert sides_seen == set(range(1, 9))


def test_check_morale_pass_and_fail():
    assert osric_combat.check_morale(7, roll=7)["passed"] is True
    assert osric_combat.check_morale(7, roll=8)["passed"] is False


def test_check_morale_bonus_and_penalty():
    assert osric_combat.check_morale(7, bonus=2, roll=8)["passed"] is True
    assert osric_combat.check_morale(7, penalty=2, roll=6)["passed"] is False


def test_check_surprise_default_chance():
    result = osric_combat.check_surprise(party_roll=1, enemy_roll=6)
    assert result["party_surprised"] is True
    assert result["enemy_surprised"] is False


def test_check_surprise_alertness_shifts_thresholds():
    result = osric_combat.check_surprise(
        party_alertness=1, enemy_alertness=1, party_roll=1, enemy_roll=2
    )
    # Base chance is 2; +1 alertness makes party threshold 1 and enemy threshold 3.
    assert result["party_threshold"] == 1
    assert result["enemy_threshold"] == 3
    assert result["party_surprised"] is True
    assert result["enemy_surprised"] is True


def test_turn_undead_high_roll_turns_low_hd():
    result = osric_combat.turn_undead(
        turner_level=1, undead_type="skeleton", undead_hd=1, roll=15
    )
    assert result["turned"] is True
    assert result["destroyed"] is False


def test_turn_undead_natural_twenty_destroys():
    result = osric_combat.turn_undead(
        turner_level=1, undead_type="skeleton", undead_hd=1, roll=20
    )
    assert result["turned"] is True
    assert result["destroyed"] is True


def test_turn_undead_low_roll_fails():
    result = osric_combat.turn_undead(
        turner_level=1, undead_type="skeleton", undead_hd=1, roll=5
    )
    assert result["turned"] is False
    assert result["destroyed"] is False


def test_turn_undead_level_gap_destroys_without_twenty():
    result = osric_combat.turn_undead(
        turner_level=6, undead_type="skeleton", undead_hd=1, roll=10
    )
    assert result["turned"] is True
    assert result["destroyed"] is True


def test_create_fighter(monkeypatch):
    """A fighter can be created with applied abilities, positive HP, and min gold."""
    # Lock every d6/d4/etc. roll to 1 so HP is deterministic and gold is clamped to min_gold.
    monkeypatch.setattr(random, "randint", lambda a, b: 1)

    abilities = {
        "strength": 13,
        "intelligence": 10,
        "wisdom": 10,
        "dexterity": 10,
        "constitution": 10,
        "charisma": 10,
    }
    hero = adapter.create_character_data(
        ancestry_id="human",
        class_id="fighter",
        alignment="Lawful Good",
        name="Test Fighter",
        abilities=abilities,
    )

    assert hero["class"] == "fighter"
    assert hero["abilities"] == abilities
    assert hero["hit_points"] > 0
    assert hero["starting_gold"] >= adapter.STARTING_GOLD["fighter"]["min_gold"]
    assert hero["sheet"]["thac0"] == 20


def test_resolve_heal_spell(monkeypatch):
    monkeypatch.setattr(dice_engine.random, "randint", lambda a, b: 5)
    cleric = {"name": "Cleric", "class": "cleric"}
    result = osric_spells.resolve_spell(cleric, "cure_light_wounds")
    assert result["heal"] == 5
    assert result["damage"] == 0


def test_resolve_damage_spell(monkeypatch):
    monkeypatch.setattr(dice_engine.random, "randint", lambda a, b: 3)
    mage = {"name": "Mage", "class": "magic_user"}
    result = osric_spells.resolve_spell(mage, "magic_missile")
    assert result["damage"] == 4  # 1d4+1 with a rolled 3
    assert result["heal"] == 0


def test_apply_and_heal_damage():
    character = {"sheet": {"hit_points": 10, "max_hit_points": 10}}
    osric_combat.apply_damage(character, 4)
    assert character["sheet"]["hit_points"] == 6
    assert character["hit_points"] == 6

    osric_combat.heal_damage(character, 20)
    assert character["sheet"]["hit_points"] == 10
    assert character["hit_points"] == 10
