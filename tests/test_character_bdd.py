"""Step definitions for features/character.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary.character import (ABILITIES, ancestry, apply_ancestry, arrangeable,
                                 eligible_classes, game_class, meets_ancestry_minimums,
                                 roll_abilities, roll_exceptional_strength, roll_hit_points)
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


class _RaisingRoller:
    """Fails the scenario outright if a die is ever rolled."""
    log = ()

    def roll(self, expr, reason="", mods=0, **tags):
        raise AssertionError("should not roll - Strength was already settled")


@given(parsers.parse('a fighter whose Strength was already settled at {score:g} by an earlier exceptional roll'),
       target_fixture="exceptional_ctx")
def a_fighter_already_settled(score):
    return {"dice": _RaisingRoller(), "score": score, "cls": "fighter"}


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


@then(parsers.parse("the character's Strength is still {score:g}"))
def strength_is_still(exceptional_result, score):
    assert exceptional_result["result"] == score


@given(parsers.parse("a player choosing the {ancestry} ancestry"), target_fixture="chosen_ancestry")
def choosing_an_ancestry(ancestry):
    return ancestry


@when("the ancestral adjustments are applied to ability scores of 10 across the board",
      target_fixture="adjusted_scores")
def apply_adjustments(chosen_ancestry):
    return apply_ancestry({k: 10 for k in ABILITIES}, chosen_ancestry)


@then(parsers.parse("the {ability} score becomes {score:d}"))
def ability_becomes(adjusted_scores, ability, score):
    assert adjusted_scores[ability] == score


@when(parsers.parse("the player's ability scores are all {score:d}"), target_fixture="flat_scores")
def flat_ability_scores(score):
    return {k: score for k in ABILITIES}


@then(parsers.parse("the character {does_or_not} meet the {ancestry_label}'s ancestral requirements"))
def check_requirements(flat_scores, chosen_ancestry, does_or_not, ancestry_label):
    meets = meets_ancestry_minimums(flat_scores, chosen_ancestry)
    assert meets == (does_or_not == "does")


@then(parsers.parse("the player {can_or_cannot} become a {cls}"))
def can_become_class(chosen_ancestry, can_or_cannot, cls):
    allowed = cls in ancestry(chosen_ancestry)["allowed_classes"]
    assert allowed == (can_or_cannot == "can")


@then(parsers.parse("the {cls} level limit is unlimited"))
def class_level_limit_unlimited(chosen_ancestry, cls):
    assert ancestry(chosen_ancestry)["level_limits"].get(cls, 0) == 0


@then(parsers.parse("the {cls} level limit is {level:d}"))
def class_level_limit(chosen_ancestry, cls, level):
    assert ancestry(chosen_ancestry)["level_limits"][cls] == level


@given(parsers.parse("a character with every ability score at {score:d}"), target_fixture="flat_scores")
def a_character_with_every_score(score):
    return {k: score for k in ABILITIES}


@then(parsers.parse("the character cannot take up {cls} among a {ancestry_name}'s classes"))
def cannot_take_up_class(flat_scores, cls, ancestry_name):
    assert cls not in eligible_classes(flat_scores, ancestry_name)


@then(parsers.parse("the character can take up {cls} among a {ancestry_name}'s classes"))
def can_take_up_class(flat_scores, cls, ancestry_name):
    assert cls in eligible_classes(flat_scores, ancestry_name)


@given("a first-level fighter and a first-level magic-user, rolled with the same seed",
       target_fixture="two_hp_rolls")
def a_fighter_and_a_magic_user():
    fighter_dice = Dice(seed=99)
    magic_user_dice = Dice(seed=99)
    roll_hit_points(fighter_dice, "fighter", level=1, con_bonus=0)
    roll_hit_points(magic_user_dice, "magic-user", level=1, con_bonus=0)
    return fighter_dice, magic_user_dice


@then("the fighter's hit points come from a bigger die than the magic-user's")
def fighter_die_is_bigger(two_hp_rolls):
    fighter_dice, magic_user_dice = two_hp_rolls
    fighter_faces = int(fighter_dice.log[0].expr.split("d")[1])
    magic_user_faces = int(magic_user_dice.log[0].expr.split("d")[1])
    assert fighter_faces > magic_user_faces


@given(parsers.parse("a fighter of level {level:d} with a Constitution bonus of {bonus:d}"),
       target_fixture="hp_ctx")
def a_fighter_with_con_bonus(level, bonus):
    d = Dice(seed=3)
    hp = roll_hit_points(d, "fighter", level=level, con_bonus=bonus)
    return {"dice": d, "hp": hp, "level": level, "bonus": bonus}


@then("the bonus is added once for every level rolled")
def bonus_added_per_level(hp_ctx):
    rolled = sum(r.total for r in hp_ctx["dice"].log)
    assert hp_ctx["hp"] == rolled + hp_ctx["bonus"] * hp_ctx["level"]


@given(parsers.parse("a magic-user of level {level:d} with a Constitution penalty of {penalty:d}"),
       target_fixture="hp_ctx")
def a_magic_user_with_con_penalty(level, penalty):
    d = Dice(seed=4)
    hp = roll_hit_points(d, "magic-user", level=level, con_bonus=-penalty)
    return {"dice": d, "hp": hp, "level": level}


@then("the character still has at least 1 hit point per level")
def hp_floor(hp_ctx):
    assert hp_ctx["hp"] >= hp_ctx["level"]


@given(parsers.parse("a {cls} character"), target_fixture="chosen_class")
def a_class_character(cls):
    return cls


@then(parsers.parse("hit dice stop climbing at level {level:d}"))
def hit_dice_stop_at(chosen_class, level):
    assert game_class(chosen_class)["hit_dice_stop_level"] == level


@then(parsers.parse("every level after that grants a flat {flat_hp:d} hit points instead"))
def flat_hp_after(chosen_class, flat_hp):
    assert game_class(chosen_class)["fixed_hp_per_level_after"] == flat_hp


@given(parsers.parse("a magic-user of level {level:d} with a Constitution bonus of {bonus:d}"),
       target_fixture="hp_ctx")
def a_magic_user_with_con_bonus(level, bonus):
    d = Dice(seed=7)
    hp = roll_hit_points(d, "magic-user", level=level, con_bonus=bonus)
    return {"dice": d, "hp": hp, "level": level, "bonus": bonus}


@then("the Constitution bonus applies only to the levels that still rolled a hit die")
def con_bonus_applies_only_to_rolled_levels(hp_ctx):
    d = hp_ctx["dice"]
    stop = game_class("magic-user")["hit_dice_stop_level"]
    fixed = game_class("magic-user")["fixed_hp_per_level_after"]
    rolled_levels = len(d.log)
    assert rolled_levels == stop
    rolled = sum(r.total for r in d.log)
    fixed_levels = hp_ctx["level"] - stop
    expected = rolled + hp_ctx["bonus"] * rolled_levels + fixed * fixed_levels
    assert hp_ctx["hp"] == expected
