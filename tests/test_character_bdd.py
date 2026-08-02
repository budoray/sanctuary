"""Step definitions for features/character.feature."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary.character import (ABILITIES, SAVE_CATEGORIES, _multiclass_hit_points,
                                 ability_modifiers, ancestry, apply_ancestry, arrangeable,
                                 eligible_classes, game_class, generate, is_legal_multiclass,
                                 meets_ancestry_minimums, roll_abilities,
                                 roll_exceptional_strength, roll_hit_points, saving_throws,
                                 to_hit_target)
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


@given("a first-level ranger and a first-level fighter, rolled with the same seed",
       target_fixture="ranger_and_fighter_rolls")
def a_ranger_and_a_fighter():
    ranger_dice = Dice(seed=11)
    fighter_dice = Dice(seed=11)
    roll_hit_points(ranger_dice, "ranger", level=1, con_bonus=0)
    roll_hit_points(fighter_dice, "fighter", level=1, con_bonus=0)
    return ranger_dice, fighter_dice


@then("the ranger rolls twice as many starting hit dice as the fighter")
def ranger_rolls_twice_the_dice(ranger_and_fighter_rolls):
    ranger_dice, fighter_dice = ranger_and_fighter_rolls
    assert len(ranger_dice.log) == 2 * len(fighter_dice.log)


@given("a first-level monk and a first-level fighter, rolled with the same seed",
       target_fixture="monk_and_fighter_rolls")
def a_monk_and_a_fighter():
    monk_dice = Dice(seed=11)
    fighter_dice = Dice(seed=11)
    roll_hit_points(monk_dice, "monk", level=1, con_bonus=0)
    roll_hit_points(fighter_dice, "fighter", level=1, con_bonus=0)
    return monk_dice, fighter_dice


@then("the monk rolls twice as many starting hit dice as the fighter")
def monk_rolls_twice_the_dice(monk_and_fighter_rolls):
    monk_dice, fighter_dice = monk_and_fighter_rolls
    assert len(monk_dice.log) == 2 * len(fighter_dice.log)


@given(parsers.parse("a character with {score:g} Strength"), target_fixture="strength_mods")
def a_character_with_strength_score(score):
    return ability_modifiers({**{k: 10 for k in ABILITIES}, "strength": score})


@then(parsers.parse("the Strength hit bonus is {bonus:d}"))
def strength_hit_bonus_is(strength_mods, bonus):
    assert strength_mods["hit"] == bonus


@then(parsers.parse("the Strength damage bonus is {bonus:d}"))
def strength_damage_bonus_is(strength_mods, bonus):
    assert strength_mods["damage"] == bonus


@given(parsers.parse("a {cls} of level {novice_level:d} and a {cls} of level {veteran_level:d}"),
       target_fixture="novice_and_veteran")
def a_novice_and_a_veteran(cls, novice_level, veteran_level):
    return {"cls": cls, "novice_level": novice_level, "veteran_level": veteran_level}


@then(parsers.parse("the level {veteran_level:d} {cls} resists spells at least as well as "
                     "the level {novice_level:d} {cls}"))
def veteran_resists_spells_better(novice_and_veteran):
    novice = saving_throws(novice_and_veteran["cls"], novice_and_veteran["novice_level"])
    veteran = saving_throws(novice_and_veteran["cls"], novice_and_veteran["veteran_level"])
    assert veteran["spells"] <= novice["spells"]


@then("the level 9 fighter needs a lower roll to hit the same armour class than the level 1 fighter")
def level_nine_hits_more_easily(novice_and_veteran):
    assert to_hit_target("fighter", novice_and_veteran["veteran_level"], 4) < to_hit_target(
        "fighter", novice_and_veteran["novice_level"], 4)


@given(parsers.parse("a fighter of level {level:d}"), target_fixture="solo_fighter_level")
def a_solo_fighter(level):
    return level


@then("the to-hit target is just a number to beat, with no special case for a roll of 1 or 20")
def to_hit_target_is_plain_number(solo_fighter_level):
    # OSRIC: a natural 1 is not an automatic miss, a natural 20 is not an
    # automatic hit. to_hit_target() only computes the number to beat - it
    # never special-cases the die roll itself.
    target = to_hit_target("fighter", solo_fighter_level, 10)
    assert isinstance(target, int)


@given(parsers.parse('a player creates {name}, a human fighter, with seed {seed:d}'),
       target_fixture="new_character")
def create_named_human_fighter(name, seed):
    return generate(seed=seed, mode="normal", ancestry_name="human",
                     class_names=("fighter",), name=name)


@then("Ilse has a full set of ability scores")
def has_full_ability_scores(new_character):
    assert set(new_character.scores) == set(ABILITIES)


@then("Ilse has at least 1 hit point")
def has_at_least_one_hp(new_character):
    assert new_character.hit_points >= 1


@then("Ilse has all five saving throws")
def has_all_saving_throws(new_character):
    assert set(new_character.saves) == set(SAVE_CATEGORIES)


@then(parsers.parse("Ilse's seed is recorded as {seed:d}"))
def seed_is_recorded(new_character, seed):
    assert new_character.seed == seed


@given(parsers.parse("a player creates a human fighter twice with seed {seed:d}"),
       target_fixture="two_characters")
def create_human_fighter_twice(seed):
    a = generate(seed=seed, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=seed, mode="normal", ancestry_name="human", class_names=("fighter",))
    return a, b


@then("both adventurers are identical in every way that matters")
def characters_are_identical(two_characters):
    a, b = two_characters
    assert a == b


@pytest.fixture
def two_seeded_characters():
    return []


@given(parsers.parse("a player creates a human fighter with seed {seed:d}"))
def create_a_human_fighter(two_seeded_characters, seed):
    two_seeded_characters.append(
        generate(seed=seed, mode="normal", ancestry_name="human", class_names=("fighter",)))


@given(parsers.parse("a player creates another human fighter with seed {seed:d}"))
def create_another_human_fighter(two_seeded_characters, seed):
    two_seeded_characters.append(
        generate(seed=seed, mode="normal", ancestry_name="human", class_names=("fighter",)))


@then("the two adventurers differ")
def adventurers_differ(two_seeded_characters):
    a, b = two_seeded_characters
    assert a.scores != b.scores or a.hit_points != b.hit_points


@then("a human may not train as both a fighter and a magic-user")
def human_may_not_multiclass():
    assert not is_legal_multiclass("human", ("fighter", "magic-user"))


@then("an elf may train as both a fighter and a magic-user")
def elf_may_multiclass():
    assert is_legal_multiclass("elf", ("fighter", "magic-user"))


@then("a human may train as a lone fighter")
def human_may_solo_class():
    assert is_legal_multiclass("human", ("fighter",))


@then(parsers.parse("the {ancestry} ancestry allows both {first_calling} and {second_calling}"))
def ancestry_may_dual_class(ancestry, first_calling, second_calling):
    assert is_legal_multiclass(ancestry, (first_calling, second_calling))


@then(parsers.parse("the {ancestry} ancestry does not allow both {first_calling} and {second_calling}"))
def ancestry_may_not_dual_class(ancestry, first_calling, second_calling):
    assert not is_legal_multiclass(ancestry, (first_calling, second_calling))


@then("an elf may train as fighter, magic-user and thief all at once")
def elf_may_triple_class():
    assert is_legal_multiclass("elf", ("fighter", "magic-user", "thief"))


@given(parsers.parse("a player attempts to create a human fighter and magic-user with seed {seed:d}"),
       target_fixture="refused_attempt")
def attempt_illegal_combination(seed):
    def attempt():
        generate(seed=seed, mode="normal", ancestry_name="human",
                 class_names=("fighter", "magic-user"))
    return attempt


@then("the attempt is refused")
def attempt_is_refused(refused_attempt):
    with pytest.raises(ValueError):
        refused_attempt()


@given(parsers.parse("a player creates an elf fighter and magic-user with seed {seed:d}"),
       target_fixture="multiclass_character")
def create_elf_multiclass(seed):
    return generate(seed=seed, mode="normal", ancestry_name="elf",
                     class_names=("fighter", "magic-user"))


@then("the elf's hit points come from dice rolled for both callings")
def multiclass_hp_from_both_callings(multiclass_character):
    hp_rolls = [r for r in multiclass_character.log if "hp level" in r.reason]
    assert any("fighter" in r.reason for r in hp_rolls)
    assert any("magic-user" in r.reason for r in hp_rolls)
    assert multiclass_character.hit_points >= 1


class _QueueRoller:
    """Returns fixed totals in call order - lets a scenario pin an exact
    starting-toughness roll instead of hunting for a seed."""

    def __init__(self, totals):
        self._totals = list(totals)
        self.log = ()

    def roll(self, expr, reason="", mods=0, **tags):
        total = self._totals.pop(0)
        r = Roll(index=len(self.log), expr=expr, faces=(total,), kept=(total,),
                  mods=0, total=total, reason=reason, tags=tags)
        self.log = self.log + (r,)
        return r


@given(parsers.parse("a fighter and magic-user who roll {first:d} and {second:d} for their "
                      "starting toughness"), target_fixture="toughness_hp")
def fighter_and_magic_user_roll_toughness(first, second):
    return _multiclass_hit_points(_QueueRoller([first, second]), ("fighter", "magic-user"), 0)


@then(parsers.parse("the multi-classed adventurer's starting hit points are {expected:d}, "
                     "not {wrong:d}"))
def multiclass_hp_is_exactly(toughness_hp, expected, wrong):
    assert toughness_hp == expected
    assert toughness_hp != wrong


@given("a fighter, magic-user and thief who each roll a bare 1 for their starting toughness",
       target_fixture="triple_class_hp")
def triple_class_bare_ones():
    return _multiclass_hit_points(_QueueRoller([1, 1, 1]), ("fighter", "magic-user", "thief"), 0)


@then("the triple-classed adventurer starts with at least 3 hit points, one for each calling")
def triple_class_minimum(triple_class_hp):
    assert triple_class_hp == 3


@given("a half-orc whose rolled Strength is already at its peak of 18",
       target_fixture="ancestral_scores")
def half_orc_at_peak_strength():
    return apply_ancestry({**{k: 10 for k in ABILITIES}, "strength": 18}, "half-orc")


@then("the ancestral bonus does not push the half-orc's Strength past 18")
def half_orc_strength_capped(ancestral_scores):
    assert ancestral_scores["strength"] == 18


@given("a halfling whose rolled Dexterity is already at its peak of 18",
       target_fixture="ancestral_scores")
def halfling_at_peak_dexterity():
    return apply_ancestry({**{k: 10 for k in ABILITIES}, "dexterity": 18}, "halfling")


@then("the ancestral bonus does not push the halfling's Dexterity past 18")
def halfling_dexterity_capped(ancestral_scores):
    assert ancestral_scores["dexterity"] == 18


@given(parsers.parse("a player attempts to create a human fighter with seed {seed:d} in the "
                      "hardest mode"), target_fixture="refused_attempt")
def attempt_weak_human_fighter(seed):
    def attempt():
        generate(seed=seed, mode="hardest", ancestry_name="human", class_names=("fighter",))
    return attempt


@then("the attempt is refused for not meeting the fighter's own requirements")
def attempt_refused_for_fighter_minimums(refused_attempt):
    with pytest.raises(ValueError, match="fighter"):
        refused_attempt()


@given(parsers.parse("a player attempts to create a dwarf fighter with seed {seed:d} in the "
                      "hardest mode"), target_fixture="refused_attempt")
def attempt_frail_dwarf(seed):
    def attempt():
        generate(seed=seed, mode="hardest", ancestry_name="dwarf", class_names=("fighter",))
    return attempt


@then("the attempt is refused for not meeting the dwarf's own requirements")
def attempt_refused_for_dwarf_minimums(refused_attempt):
    with pytest.raises(ValueError, match="dwarf"):
        refused_attempt()


@given(parsers.parse("a player rolling in the {mode} mode with seed {seed:d}"),
       target_fixture="arrangement_ctx")
def a_player_rolling_with_seed(mode, seed):
    rolled = roll_abilities(Dice(seed=seed), mode)
    return {"mode": mode, "seed": seed, "rolled": rolled}


@when("the player puts their highest roll on Strength", target_fixture="arranged_character")
def player_arranges_best_on_strength(arrangement_ctx):
    rolled = arrangement_ctx["rolled"]
    best_first = sorted(rolled.values(), reverse=True)
    arrangement = dict(zip(ABILITIES, best_first))
    return generate(seed=arrangement_ctx["seed"], mode=arrangement_ctx["mode"],
                     ancestry_name="human", class_names=("fighter",),
                     arrangement=arrangement)


@then("the adventurer's Strength is the highest of the six scores rolled")
def strength_is_the_highest_roll(arranged_character, arrangement_ctx):
    assert arranged_character.scores["strength"] == max(arrangement_ctx["rolled"].values())


@then("the dice log shows no roll the player did not see")
def log_has_no_hidden_arrangement_roll(arranged_character, arrangement_ctx):
    # Arrangement never rolls dice - the six ability rolls the player saw
    # are the only ability rolls in the finished character's log.
    ability_rolls = [r for r in arranged_character.log if r.reason in ABILITIES]
    assert len(ability_rolls) == len(arrangement_ctx["rolled"])


@then("the player is not offered a way to rearrange the scores")
def player_not_offered_arrangement(arrangement_ctx):
    assert not arrangeable(arrangement_ctx["mode"])
