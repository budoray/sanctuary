"""Step definitions for features/dice.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary.dice import Dice

scenarios("../features/dice.feature")


@given("a dice engine seeded for a session", target_fixture="dice")
def a_dice_engine():
    return Dice(seed=42)


@given(parsers.parse("a dice engine seeded with {seed:d}"), target_fixture="seed")
def a_seed(seed):
    return seed


@when(parsers.parse('a player rolls for "{reason}"'), target_fixture="roll")
def roll_for_reason(dice, reason):
    return dice.roll("1d20", reason=reason)


@then(parsers.parse('the log\'s newest entry gives the reason "{reason}"'))
def newest_entry_reason(dice, reason):
    assert dice.log[-1].reason == reason


@when("the same sequence of rolls is made twice with that seed", target_fixture="two_tellings")
def two_tellings(seed):
    def session():
        d = Dice(seed=seed)
        d.roll("3d6", reason="a")
        d.roll("4d6d1", reason="b")
        d.roll("1d20", mods=2, reason="c")
        return [(r.expr, r.faces, r.kept, r.total) for r in d.log]

    return session(), session()


@then("both tellings are identical, roll for roll")
def tellings_are_identical(two_tellings):
    first, second = two_tellings
    assert first == second


@when("a player rolls three six-sided dice for Strength", target_fixture="roll")
def roll_three_d6(dice):
    return dice.roll("3d6", reason="Strength")


@then("the log shows every individual die alongside the total")
def log_shows_every_die(roll):
    assert len(roll.faces) == 3
    assert roll.total == sum(roll.faces)


@when("a player rolls four six-sided dice and drops the lowest", target_fixture="roll")
def roll_four_drop_lowest(dice):
    return dice.roll("4d6d1", reason="ability score")


@then("three dice are kept and the dropped one is excluded from the total")
def three_kept(roll):
    assert len(roll.faces) == 4
    assert len(roll.kept) == 3
    assert sorted(roll.kept) == sorted(roll.faces)[1:]
    assert roll.total == sum(roll.kept)


@when("a player rolls a twenty-sided die with a +3 bonus for an attack", target_fixture="roll")
def roll_d20_plus_3(dice):
    return dice.roll("1d20", mods=3, reason="attack")


@then("the log shows the bonus apart from the dice")
def bonus_recorded_separately(roll):
    assert roll.mods == 3


@then("the total is the dice plus the bonus")
def total_is_dice_plus_bonus(roll):
    assert roll.total == sum(roll.kept) + roll.mods
