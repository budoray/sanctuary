"""Fast unit tests for the OSRIC rule helpers used by Sanctuary."""
from __future__ import annotations

import random


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


def test_crooked_tower_clear_reaches_level_two():
    """A full Crooked Tower clear must fund 2nd level for every OSRIC class."""
    from rulesets.osric.adapter import CLASSES, xp_for_next_level

    kill_xp = 150 + 175 + 225 + 500 + 100
    grik_purse = 250
    chests = 400 + 500
    clear_xp = 550
    total = kill_xp + grik_purse + chests + clear_xp
    assert total == 2850
    for class_id in CLASSES:
        need = xp_for_next_level(class_id, 1)
        assert total >= need, f"{class_id} needs {need} XP to reach 2nd, tower pays {total}"


def test_level_one_tutorial_bonus(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 10)
    att = _attacker()
    att["class"] = "fighter"
    att["sheet"]["level"] = 1
    result = osric_combat.resolve_attack(att, _defender())
    assert result["to_hit_mod"] == 2
    assert result["roll"] == 12


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


def test_saving_throw_success(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 15)
    character = {"sheet": {"saving_throws": {"death_paralysis_poison": 14}}}
    result = osric_combat.saving_throw(character, "death_paralysis_poison")
    assert result["roll"] == 15
    assert result["target"] == 14
    assert result["success"] is True


def test_saving_throw_fail(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 5)
    character = {"sheet": {"saving_throws": {"death_paralysis_poison": 14}}}
    result = osric_combat.saving_throw(character, "death_paralysis_poison")
    assert result["success"] is False


def test_saving_throw_natural_20_always_succeeds(monkeypatch):
    character = {"sheet": {"saving_throws": {"spells": 20}}}
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 20)
    result = osric_combat.saving_throw(character, "spells")
    assert result["success"] is True


def test_saving_throw_natural_1_always_fails(monkeypatch):
    character = {"sheet": {"saving_throws": {"spells": 2}}}
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 1)
    result = osric_combat.saving_throw(character, "spells")
    assert result["success"] is False


def test_saving_throw_wisdom_bonus_against_spells(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 10)
    character = {
        "abilities": {"wisdom": 18},
        "sheet": {"saving_throws": {"spells": 14}},
    }
    result = osric_combat.saving_throw(character, "spells")
    assert result["modifier"] == 4
    assert result["effective_target"] == 10
    assert result["success"] is True


def test_initiative_party_wins_with_high_dex(monkeypatch):
    monkeypatch.setattr(osric_combat.random, "randint", lambda a, b: 4)
    party = [{"abilities": {"dexterity": 18}}]
    enemies = [{"abilities": {"dexterity": 10}}]
    result = osric_combat.roll_initiative(party, enemies)
    assert result["side_a"]["total"] == 1.0
    assert result["side_b"]["total"] == 4.0
    assert result["winner"] == "party"


def test_initiative_enemy_wins(monkeypatch):
    monkeypatch.setattr(osric_combat.random, "randint", lambda a, b: 4)
    party = [{"abilities": {"dexterity": 10}}]
    enemies = [{"abilities": {"dexterity": 18}}]
    result = osric_combat.roll_initiative(party, enemies)
    assert result["winner"] == "enemies"


def test_initiative_tie(monkeypatch):
    monkeypatch.setattr(osric_combat.random, "randint", lambda a, b: 4)
    party = [{"abilities": {"dexterity": 10}}]
    enemies = [{"abilities": {"dexterity": 10}}]
    result = osric_combat.roll_initiative(party, enemies)
    assert result["winner"] == "tie"


def test_check_reaction_attitude_boundaries():
    assert osric_combat.check_reaction(roll=3)["attitude"] == "hostile"
    assert osric_combat.check_reaction(roll=5)["attitude"] == "hostile"
    assert osric_combat.check_reaction(roll=6)["attitude"] == "uncertain"
    assert osric_combat.check_reaction(roll=8)["attitude"] == "uncertain"
    assert osric_combat.check_reaction(roll=9)["attitude"] == "friendly"
    assert osric_combat.check_reaction(roll=12)["attitude"] == "friendly"


def test_check_reaction_modifier_shifts_attitude():
    # A roll of 5 is normally hostile, but +4 makes it friendly.
    result = osric_combat.check_reaction(modifier=4, roll=5)
    assert result["modified"] == 9
    assert result["attitude"] == "friendly"


def test_resolve_sleep_applies_condition():
    caster = {"name": "Mage", "class": "magic_user"}
    result = osric_spells.resolve_spell(caster, "sleep")
    assert result["condition"] == "sleeping"
    assert result["duration"] == 4
    assert result["hit"] is True


def test_resolve_charm_person_failed_save_applies_condition(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 5)
    caster = {"name": "Mage", "class": "magic_user"}
    target = {"name": "Guard", "sheet": {"saving_throws": {"spells": 12}}}
    result = osric_spells.resolve_spell(caster, "charm_person", target=target)
    assert result["saving_throw"]["success"] is False
    assert result["condition"] == "charmed"
    assert result["hit"] is True


def test_resolve_charm_person_successful_save_no_condition(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 18)
    caster = {"name": "Mage", "class": "magic_user"}
    target = {"name": "Guard", "sheet": {"saving_throws": {"spells": 12}}}
    result = osric_spells.resolve_spell(caster, "charm_person", target=target)
    assert result["saving_throw"]["success"] is True
    assert result["condition"] is None
    assert result["hit"] is False


def test_bless_grants_plus_one_to_hit(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 10)
    attacker = _attacker()
    attacker["sheet"]["active_spells"] = [{"spell_id": "bless", "rounds_remaining": 6}]
    result = osric_combat.resolve_attack(attacker, _defender())
    # STR 10 gives +0; Bless gives +1.
    assert result["to_hit_mod"] == 1


def test_shield_improves_defender_ac(monkeypatch):
    monkeypatch.setattr(osric_combat, "_roll_d20", lambda: 10)
    attacker = _attacker()
    defender = _defender(ac_descending=10)
    defender["sheet"]["active_spells"] = [{"spell_id": "shield", "rounds_remaining": 5}]
    result = osric_combat.resolve_attack(attacker, defender)
    # Without Shield, roll 10 + 0 STR = 10, needed 10, hits.
    # With Shield, target AC descending becomes 9, needed 11, misses.
    assert result["hit"] is False
