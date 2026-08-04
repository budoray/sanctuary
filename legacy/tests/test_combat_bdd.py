"""Step definitions for features/combat.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import character as C
from sanctuary import resolve as R
from sanctuary.dice import Dice, Roll

scenarios("../features/combat.feature")


def _fighter(level):
    return C.Character(
        name="fighter", ancestry="human", classes=("fighter",), levels={"fighter": level},
        scores={a: 10 for a in C.ABILITIES}, hit_points=10, armour_class=10,
        saves=C._multiclass_saves(("fighter",), level),
        modifiers={"hit": 0, "damage": 0, "encumbrance_lbs": 0}, seed=1,
    )


class _FixedDice:
    """Returns a pinned face for the next matching roll; falls through to a
    real seeded Dice for everything else, so a scenario can pin exactly the
    die result it's demonstrating without hand-searching for a seed."""

    def __init__(self, faces_by_reason, seed=1):
        self._faces = dict(faces_by_reason)
        self._real = Dice(seed=seed)

    @property
    def log(self):
        return self._real.log

    def roll(self, expr, reason="", mods=0, **tags):
        if reason in self._faces:
            face = self._faces[reason]
            r = Roll(index=len(self._real._log), expr=expr, faces=(face,), kept=(face,),
                      mods=mods, total=face + mods, reason=reason, tags=tags)
            self._real._log.append(r)
            return r
        return self._real.roll(expr, reason=reason, mods=mods, **tags)


# ---------------------------------------------------------------------------
# A novice vs a well-armoured knight
# ---------------------------------------------------------------------------

@given("a first-level fighter attacking a knight in plate mail and shield",
       target_fixture="duel")
def novice_vs_knight():
    fighter = _fighter(1)
    knight_ac = C.armour_class(10, armour="plate mail", shield=True)
    return {"attacker": fighter, "ac": knight_ac}


@when("the fighter swings with a very weak roll", target_fixture="attack_result")
def swing_weakly(duel):
    d = _FixedDice({"attack": 2})
    return R.attack(d, duel["attacker"], duel["ac"])


@then("the attack misses")
def attack_missed(attack_result):
    assert attack_result.hit is False


# ---------------------------------------------------------------------------
# A veteran connects more easily than a novice
# ---------------------------------------------------------------------------

@given("a first-level fighter and a tenth-level fighter, both attacking the same "
       "lightly-armoured foe", target_fixture="veteran_and_novice")
def veteran_and_novice():
    return {"novice": _fighter(1), "veteran": _fighter(10), "ac": 7}


@when("both roll the same middling number on the die", target_fixture="both_swings")
def both_swing_the_same(veteran_and_novice):
    novice_result = R.attack(_FixedDice({"attack": 10}), veteran_and_novice["novice"],
                              veteran_and_novice["ac"])
    veteran_result = R.attack(_FixedDice({"attack": 10}), veteran_and_novice["veteran"],
                               veteran_and_novice["ac"])
    return novice_result, veteran_result


@then("the veteran's swing is at least as likely to land as the novice's")
def veteran_at_least_as_likely(both_swings):
    novice_result, veteran_result = both_swings
    assert veteran_result.target <= novice_result.target
    if novice_result.hit:
        assert veteran_result.hit


# ---------------------------------------------------------------------------
# Natural 1 and natural 20 are not automatic
# ---------------------------------------------------------------------------

@given("an attacker with enough skill and bonuses to threaten a hit", target_fixture="weak_roll_duel")
def strong_attacker():
    return {"hit_dice": 1, "ac": 10, "magic_to_hit": 25}


@when("the attacker rolls the worst possible number on the die", target_fixture="attack_result")
def roll_worst_possible(weak_roll_duel):
    d = _FixedDice({"attack": 1})
    return R.attack(d, weak_roll_duel["hit_dice"], weak_roll_duel["ac"],
                     magic_to_hit=weak_roll_duel["magic_to_hit"])


@then("the attack can still land")
def attack_can_still_land(attack_result):
    assert attack_result.natural == 1
    assert attack_result.hit is True


@given("an attacker facing a target far beyond their skill", target_fixture="hopeless_duel")
def hopeless_attacker():
    return {"hit_dice": 24, "ac": -10, "situational": -30}


@when("the attacker rolls the best possible number on the die", target_fixture="attack_result")
def roll_best_possible(hopeless_duel):
    d = _FixedDice({"attack": 20})
    return R.attack(d, hopeless_duel["hit_dice"], hopeless_duel["ac"],
                     situational=hopeless_duel["situational"])


@then("the attack can still miss")
def attack_can_still_miss(attack_result):
    assert attack_result.natural == 20
    assert attack_result.hit is False


# ---------------------------------------------------------------------------
# A natural 1 on a save always fails
# ---------------------------------------------------------------------------

@given("a character making a saving throw", target_fixture="saver")
def a_saving_character():
    c = _fighter(1)
    # An artificially generous target (1 - the best a save can ever need)
    # proves the failure isn't just an ordinary miss against a hard number.
    c = C.Character(**{**c.__dict__, "saves": {**c.saves, "spells": 1}})
    return c


@when("the character rolls the worst possible number on the die", target_fixture="save_result")
def roll_worst_save(saver):
    d = _FixedDice({"save": 1})
    return R.saving_throw(d, saver, "spells")


@then("the saving throw fails no matter the bonuses")
def save_fails_regardless(save_result):
    assert save_result.natural == 1
    assert save_result.success is False


# ---------------------------------------------------------------------------
# Turning the undead
# ---------------------------------------------------------------------------

@given("a mid-level cleric confronting a handful of shambling zombies", target_fixture="turning")
def cleric_vs_zombies():
    return {"cleric_level": 4, "undead_type": 2}


@when("the cleric presents their holy symbol and attempts to turn them", target_fixture="turn_result")
def attempt_turn(turning):
    d = Dice(seed=1)
    return R.turn_undead(d, turning["cleric_level"], turning["undead_type"])


@then("the zombies are turned or destroyed")
def zombies_turned_or_destroyed(turn_result):
    assert turn_result.success is True


@given("a first-level cleric confronting an ancient lich", target_fixture="turning")
def cleric_vs_lich():
    return {"cleric_level": 1, "undead_type": 12}


@when("the cleric attempts to turn the lich", target_fixture="turn_result")
def attempt_turn_lich(turning):
    d = Dice(seed=1)
    return R.turn_undead(d, turning["cleric_level"], turning["undead_type"])


@then("the turning attempt has no effect")
def turning_has_no_effect(turn_result):
    assert turn_result.success is False
    assert turn_result.affected == 0


# ---------------------------------------------------------------------------
# Morale
# ---------------------------------------------------------------------------

@given("a monster warband that has already lost several of its number", target_fixture="warband")
def battered_warband():
    return {"hit_dice": 4}


# ⚠ A pytest-bdd step must NOT be named test_* — pytest collects it as a test
# function and tries to inject its step arguments as fixtures, which fails at
# collection because `warband` is a @given target_fixture, not a pytest fixture.
@when("the warband's morale is tested under those losses", target_fixture="morale_pair")
def battered_morale_is_tested(warband):
    # Same die result for both checks - only the situation differs -
    # isolates what the modifiers do to the outcome.
    fresh = R.morale(_FixedDice({"morale": 65}), warband["hit_dice"], modifiers=0)
    battered = R.morale(_FixedDice({"morale": 65}), warband["hit_dice"],
                         modifiers=20)  # taken losses, greatly outnumbered (Table 1.6.8A)
    return fresh, battered


@then("the warband is more likely to break than a warband at full strength")
def battered_more_likely_to_break(morale_pair):
    fresh, battered = morale_pair
    assert fresh.passed is True
    assert battered.passed is False


# ---------------------------------------------------------------------------
# Movement and encumbrance
# ---------------------------------------------------------------------------

@given("an adventurer carrying far more than they can comfortably bear", target_fixture="loads")
def overloaded_adventurer():
    return {"base_move": 120, "unencumbered": 0.0, "overloaded": 100.0}


@when("their movement rate for the day is worked out", target_fixture="movement_pair")
def work_out_movement(loads):
    light = R.movement_rate(loads["base_move"], loads["unencumbered"])
    heavy = R.movement_rate(loads["base_move"], loads["overloaded"])
    return light, heavy


@then("they move markedly slower than an unencumbered adventurer")
def moves_slower(movement_pair):
    light, heavy = movement_pair
    assert heavy < light


# ---------------------------------------------------------------------------
# Damage and death
# ---------------------------------------------------------------------------

@given("an adventurer beaten down to nothing", target_fixture="fallen")
def beaten_down():
    return {"hp": 5}


@when("they take one more solid hit", target_fixture="damage_result")
def take_one_more_hit(fallen):
    return R.apply_damage(fallen["hp"], damage=5)


@then("they fall unconscious rather than instantly dying")
def falls_unconscious(damage_result):
    assert damage_result.unconscious is True
    assert damage_result.dead is False


@given("an adventurer already deep in negative hit points", target_fixture="fallen")
def deep_in_negatives():
    return {"hp": -8}


@then("they are dead")
def they_are_dead(damage_result):
    assert damage_result.dead is True
