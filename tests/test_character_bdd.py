"""Step definitions for features/character.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary.character import arrangeable, roll_abilities, roll_exceptional_strength
from sanctuary.dice import Dice, Roll

scenarios("../features/character.feature")


@given(parsers.parse("a player generating a character in the {mode} mode"), target_fixture="mode")
def a_mode(mode):
    return mode


@when("the six ability scores are rolled", target_fixture="scores")
def roll_once(mode):
    return roll_abilities(Dice(seed=42), mode)


@when("the six ability scores are rolled twice with the same seed", target_fixture="two_rolls")
def roll_twice(mode):
    return roll_abilities(Dice(seed=42), mode), roll_abilities(Dice(seed=42), mode)


@then("the player may rearrange the results")
def may_rearrange(mode):
    assert arrangeable(mode)


@then("the player may not rearrange the results")
def may_not_rearrange(mode):
    assert not arrangeable(mode)


@then("every ability score is between 3 and 18")
def scores_in_range(scores):
    assert all(3 <= v <= 18 for v in scores.values())


@then("both rolls produce identical ability scores")
def rolls_match(two_rolls):
    first, second = two_rolls
    assert first == second


class _FixedPercentileRoller:
    """Duck-typed stand-in - a percentile of 00 (100) must give 19."""
    log = ()

    def roll(self, expr, reason="", mods=0, **tags):
        return Roll(index=0, expr=expr, faces=(100,), kept=(100,),
                    mods=0, total=100, reason=reason, tags=tags)


@given(parsers.parse('a character with {score:d} Strength and class "{cls}"'), target_fixture="exceptional_ctx")
def a_character_with_strength(score, cls):
    return {"dice": Dice(seed=1), "score": score, "cls": cls}


@given("a fighter whose exceptional strength percentile roll comes up 00", target_fixture="exceptional_ctx")
def a_fighter_rolling_00():
    return {"dice": _FixedPercentileRoller(), "score": 18, "cls": "fighter"}


@when("exceptional strength is checked", target_fixture="exceptional_result")
def check_exceptional_strength(exceptional_ctx):
    dice = exceptional_ctx["dice"]
    result = roll_exceptional_strength(dice, exceptional_ctx["score"], exceptional_ctx["cls"])
    return {"dice": dice, "result": result}


@then(parsers.parse("a die is {rolled_or_not} for exceptional strength"))
def die_rolled_or_not(exceptional_result, rolled_or_not):
    rolled = bool(exceptional_result["dice"].log)
    assert rolled == (rolled_or_not == "rolled")


@then("the character's Strength is 19")
def strength_is_19(exceptional_result):
    assert exceptional_result["result"] == 19
