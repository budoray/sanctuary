"""Step definitions for features/character.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary.character import arrangeable, roll_abilities
from sanctuary.dice import Dice

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
