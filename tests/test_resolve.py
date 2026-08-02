import pytest

from sanctuary import character as C
from sanctuary import resolve as R
from sanctuary.dice import Dice


# ---------------------------------------------------------------------------
# Attacks: natural 1 / natural 20
# ---------------------------------------------------------------------------

class _FixedRoller:
    """Duck-typed Dice stand-in that returns a pinned d20 face (and lets
    everything else fall through to a real Dice), so a natural-1/natural-20
    test doesn't have to search for a seed."""

    def __init__(self, faces, real):
        self._faces = list(faces)
        self._real = real

    @property
    def log(self):
        return self._real.log

    def roll(self, expr, reason="", mods=0, **tags):
        if expr == "1d20" and self._faces:
            from sanctuary.dice import Roll
            face = self._faces.pop(0)
            r = Roll(index=len(self._real._log), expr=expr, faces=(face,), kept=(face,),
                      mods=mods, total=face + mods, reason=reason, tags=tags)
            self._real._log.append(r)
            return r
        return self._real.roll(expr, reason=reason, mods=mods, **tags)


def _character(cls, level=1, hit_mod=0, damage_mod=0, con=10):
    """A minimal Character built directly (bypassing `generate()`'s ability
    rolls and eligibility checks, which are Chapter 1's concern) - just
    enough of the dataclass's shape for resolve.py to read: `.classes`,
    `.levels`, `.modifiers` and `.saves`."""
    classes = (cls,)
    return C.Character(
        name="test", ancestry="human", classes=classes, levels={cls: level},
        scores={a: con if a == "constitution" else 10 for a in C.ABILITIES},
        hit_points=10, armour_class=10,
        saves=C._multiclass_saves(classes, level),
        modifiers={"hit": hit_mod, "damage": damage_mod, "encumbrance_lbs": 0},
        seed=1,
    )


def test_natural_1_can_still_hit_with_enough_bonus():
    d = _FixedRoller([1], Dice(seed=1))
    result = R.attack(d, "1", target_ac=10, magic_to_hit=25)
    assert result.natural == 1
    assert result.hit is True


def test_natural_20_can_still_miss_an_unreachable_target():
    d = _FixedRoller([20], Dice(seed=1))
    # Table 2.1.2A hit dice 24, AC -10 needs a 12 - out of reach once -30
    # situational is applied, even to a natural 20.
    result = R.attack(d, 24, target_ac=-10, situational=-30)
    assert result.natural == 20
    assert result.hit is False


def test_natural_1_always_fails_a_saving_throw_even_with_bonus():
    real = Dice(seed=1)
    c = _character("fighter")
    d = _FixedRoller([1], real)
    result = R.saving_throw(d, c, "spells")
    assert result.natural == 1
    assert result.success is False


def test_natural_20_does_not_auto_succeed_a_save_by_default():
    real = Dice(seed=1)
    c = _character("fighter")
    d = _FixedRoller([20], real)
    result = R.saving_throw(d, c, "spells")
    assert result.natural == 20
    assert result.success == (20 >= c.saves["spells"])


def test_natural_20_auto_succeeds_a_save_only_when_the_house_rule_is_on():
    real = Dice(seed=1)
    c = _character("magic-user")
    d = _FixedRoller([20], real)
    result = R.saving_throw(d, c, "spells", natural_20_auto_succeeds=True)
    assert result.success is True


# ---------------------------------------------------------------------------
# Attacks: full path against a character, parametrised across all ten classes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", C.CLASSES)
@pytest.mark.parametrize("level", (1, 5, 10))
def test_attack_uses_the_characters_to_hit_ladder(cls, level):
    c = _character(cls, level=level)
    d = Dice(seed=9)
    result = R.attack(d, c, target_ac=5)
    expected_target = C.to_hit_target(cls, level, 5)
    assert result.target == expected_target


def test_attack_reproducibility_same_seed_same_log():
    c = _character("fighter")
    d1 = Dice(seed=42)
    d2 = Dice(seed=42)
    r1 = R.attack(d1, c, target_ac=4)
    r2 = R.attack(d2, c, target_ac=4)
    assert r1 == r2
    assert [rl.total for rl in d1.log] == [rl.total for rl in d2.log]


def test_multiclass_attack_uses_the_best_of_its_classes_ladders():
    c = C.Character(
        name="test", ancestry="elf", classes=("fighter", "magic-user"),
        levels={"fighter": 1, "magic-user": 1},
        scores={a: 10 for a in C.ABILITIES}, hit_points=10, armour_class=10,
        saves=C._multiclass_saves(("fighter", "magic-user"), 1),
        modifiers={"hit": 0, "damage": 0, "encumbrance_lbs": 0}, seed=1,
    )
    fighter_target = C.to_hit_target("fighter", 1, 3)
    mu_target = C.to_hit_target("magic-user", 1, 3)
    d = Dice(seed=1)
    result = R.attack(d, c, target_ac=3)
    assert result.target == min(fighter_target, mu_target)


def test_attack_applies_strength_hit_and_damage_modifiers():
    c = _character("fighter", hit_mod=2, damage_mod=3)
    d = Dice(seed=1)
    result = R.attack(d, c, target_ac=10)
    assert result.modifiers == 2
    if result.hit:
        assert result.damage == result.damage_roll.total


# ---------------------------------------------------------------------------
# Monster ladders
# ---------------------------------------------------------------------------

def test_monster_to_hit_matches_the_printed_table_row():
    # Table 2.1.2A: hit dice "1", AC 0 -> 19 needed.
    assert R.monster_to_hit_target("1", 0) == 19


def test_monster_bonus_hit_dice_use_the_dedicated_row_not_the_next_band():
    # "1+1" HD stays on the "1+" row (better than flat 1, worse than 2 HD).
    flat = R.monster_to_hit_target("1", 0)
    bonus = R.monster_to_hit_target("1+1", 0)
    two_hd = R.monster_to_hit_target("2", 0)
    assert bonus < flat
    assert bonus > two_hd


def test_monster_saving_throw_rounds_bonus_hit_dice_up_a_band():
    # osric.txt's own worked example: "1+1 hit dice ... treated as a
    # monster with 2 hit dice ... because 1+1 is greater than 1."
    assert (R.monster_saving_throw("1+1", "spells")
            == R.monster_saving_throw("2", "spells"))


def test_monster_saving_throw_non_intelligent_uses_the_other_table():
    normal = R.monster_saving_throw("3", "aimed_magic_items", non_intelligent=False)
    non_int = R.monster_saving_throw("3", "aimed_magic_items", non_intelligent=True)
    assert normal != non_int


def test_monster_attack_reads_hit_dice_instead_of_a_character_ladder():
    d = Dice(seed=1)
    result = R.attack(d, "8", target_ac=2)
    assert result.target == R.monster_to_hit_target("8", 2)
    assert result.modifiers == 0  # no Strength bonus on a bare hit-dice attacker


# ---------------------------------------------------------------------------
# Turning the undead
# ---------------------------------------------------------------------------

def test_low_level_cleric_cannot_turn_a_lich():
    d = Dice(seed=1)
    result = R.turn_undead(d, cleric_level=1, undead_type=12)
    assert result.success is False
    assert result.affected == 0


def test_a_high_enough_level_auto_turns_a_skeleton():
    d = Dice(seed=1)
    result = R.turn_undead(d, cleric_level=4, undead_type=1)
    assert result.cell == "T"
    assert result.success is True
    assert result.destroyed is False  # turned, not destroyed


def test_good_cleric_destroying_result_is_marked_destroyed():
    d = Dice(seed=1)
    result = R.turn_undead(d, cleric_level=6, undead_type=1, alignment="good")
    assert result.cell == "D"
    assert result.destroyed is True
    assert 2 <= result.affected <= 12  # 2d6


def test_evil_cleric_never_destroys_only_may_control():
    d = Dice(seed=1)
    result = R.turn_undead(d, cleric_level=6, undead_type=1, alignment="evil")
    assert result.destroyed is False


def test_paladin_turn_type_matches_the_footnote_bands():
    assert R.paladin_turn_type(1) == 8
    assert R.paladin_turn_type(2) == 8
    assert R.paladin_turn_type(3) == 9
    assert R.paladin_turn_type(11) == 13
    assert R.paladin_turn_type(20) == 13


# ---------------------------------------------------------------------------
# Morale
# ---------------------------------------------------------------------------

def test_morale_base_is_fifty_plus_five_per_hit_die():
    d = Dice(seed=1)
    result = R.morale(d, hit_dice=8)
    assert result.base == 90  # book's own worked example


def test_morale_modifiers_move_the_roll_not_the_base():
    d = Dice(seed=1)
    result = R.morale(d, hit_dice=1, modifiers=-100)
    assert result.passed is True
    assert result.base == 55


# ---------------------------------------------------------------------------
# Item saves
# ---------------------------------------------------------------------------

def test_item_save_natural_1_always_fails():
    real = Dice(seed=1)
    d = _FixedRoller([1], real)
    result = R.item_saving_throw(d, "wood", "fire_normal", bonus=100)
    assert result.natural == 1
    assert result.success is False


def test_item_save_looks_up_the_right_material_and_form():
    assert R._item_save_table()["metal"]["lightning"] == 11


# ---------------------------------------------------------------------------
# Movement and encumbrance
# ---------------------------------------------------------------------------

def test_unencumbered_movement_is_full():
    assert R.movement_rate(120, 0) == 120


def test_heavily_encumbered_movement_drops_to_a_quarter():
    assert R.movement_rate(120, 100) == 30


def test_overloaded_cannot_move():
    assert R.movement_rate(120, 200) == 0


# ---------------------------------------------------------------------------
# Initiative, surprise and rounds
# ---------------------------------------------------------------------------

def test_lower_initiative_roll_acts_first():
    d = Dice(seed=2)
    initiative = R.roll_initiative(d)
    rnd = R.CombatRound(number=1, initiative=initiative)
    if initiative.a_segment < initiative.b_segment:
        assert rnd.order == ("a", "b")
    elif initiative.b_segment < initiative.a_segment:
        assert rnd.order == ("b", "a")
    else:
        assert rnd.order == ("simultaneous",)


def test_surprise_bonus_negates_surprise_segments():
    # osric.txt's own example: side rolled a 2, +2 surprise bonus -> not
    # surprised at all (2 - 2 = 0).
    class _StubDice:
        def __init__(self):
            self.log = ()

        def roll(self, expr, reason="", mods=0, **tags):
            from sanctuary.dice import Roll
            face = 2 if reason == "surprise a" else 1
            r = Roll(index=0, expr=expr, faces=(face,), kept=(face,), mods=0,
                      total=face, reason=reason, tags=tags)
            self.log = self.log + (r,)
            return r

    result = R.determine_surprise(_StubDice(), a_bonus=2)
    assert result.a_segments == 0


# ---------------------------------------------------------------------------
# Damage and death
# ---------------------------------------------------------------------------

def test_zero_hit_points_is_unconscious_not_dead():
    result = R.apply_damage(current_hp=3, damage=3)
    assert result.hit_points == 0
    assert result.unconscious is True
    assert result.dead is False


def test_minus_ten_hit_points_is_dead():
    result = R.apply_damage(current_hp=0, damage=10)
    assert result.hit_points == -10
    assert result.dead is True


def test_minus_six_or_below_scars():
    assert R.apply_damage(0, 6).scarred is True
    assert R.apply_damage(0, 5).scarred is False


def test_bleed_out_stops_at_the_death_threshold():
    assert R.bleed_out(-10) == -10
    assert R.bleed_out(-9) == -10
    assert R.bleed_out(0) == -1


# ---------------------------------------------------------------------------
# Dependency chain / no second RNG (belt-and-braces alongside test_invariants.py)
# ---------------------------------------------------------------------------

def test_resolve_does_not_import_random_directly():
    import ast
    from pathlib import Path
    source = Path(R.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not (isinstance(node, ast.Import)
                    and any(a.name == "random" for a in node.names))
