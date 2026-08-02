import pytest

from sanctuary.character import ABILITIES, GEN_MODES, arrangeable, roll_abilities
from sanctuary.dice import Dice


def test_all_four_modes_exist():
    assert GEN_MODES == ("hardest", "difficult", "normal", "flexible")


def test_hardest_rolls_3d6_in_order():
    d = Dice(seed=1)
    scores = roll_abilities(d, "hardest")
    assert list(scores) == list(ABILITIES)
    assert all(3 <= v <= 18 for v in scores.values())
    assert [r.expr for r in d.log] == ["3d6"] * 6


def test_normal_rolls_4d6_drop_lowest():
    d = Dice(seed=2)
    scores = roll_abilities(d, "normal")
    assert all(3 <= v <= 18 for v in scores.values())
    assert [r.expr for r in d.log] == ["4d6d1"] * 6


def test_difficult_uses_3d6_and_is_arrangeable():
    d = Dice(seed=3)
    roll_abilities(d, "difficult")
    assert [r.expr for r in d.log] == ["3d6"] * 6
    assert arrangeable("difficult")
    assert not arrangeable("hardest")


def test_flexible_uses_4d6_and_is_arrangeable():
    d = Dice(seed=4)
    roll_abilities(d, "flexible")
    assert [r.expr for r in d.log] == ["4d6d1"] * 6
    assert arrangeable("flexible")
    assert not arrangeable("normal")


def test_every_roll_carries_its_ability_as_the_reason():
    d = Dice(seed=5)
    roll_abilities(d, "normal")
    assert [r.reason for r in d.log] == list(ABILITIES)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        roll_abilities(Dice(seed=6), "easiest")


def test_generation_is_reproducible_from_the_seed():
    assert roll_abilities(Dice(seed=99), "normal") == roll_abilities(Dice(seed=99), "normal")


from sanctuary.character import EXCEPTIONAL_CLASSES, roll_exceptional_strength


def test_only_fighters_paladins_and_rangers_roll():
    assert set(EXCEPTIONAL_CLASSES) == {"fighter", "paladin", "ranger"}


def test_non_eligible_class_keeps_a_plain_18():
    d = Dice(seed=1)
    assert roll_exceptional_strength(d, 18, "thief") == 18
    assert d.log == ()


def test_score_below_18_never_rolls():
    d = Dice(seed=1)
    assert roll_exceptional_strength(d, 17, "fighter") == 17
    assert d.log == ()


def test_eligible_18_rolls_d100_and_returns_a_decimal():
    d = Dice(seed=1)
    result = roll_exceptional_strength(d, 18, "fighter")
    assert d.log[0].expr == "1d100"
    assert 18.01 <= result <= 19.0


def test_percentile_100_means_nineteen():
    from sanctuary.dice import Roll

    class FixedRoller:
        """Duck-typed stand-in - a percentile of 00 (100) must give 19."""
        log = ()

        def roll(self, expr, reason="", mods=0, **tags):
            return Roll(index=0, expr=expr, faces=(100,), kept=(100,),
                        mods=0, total=100, reason=reason, tags=tags)

    assert roll_exceptional_strength(FixedRoller(), 18, "fighter") == 19.0


def test_exceptional_strength_reads_the_right_table_row():
    from sanctuary import tables
    # 18.51-18.75 gives +2 to hit, +3 damage per Table 1.1.2A.
    row = tables.ability_row("1.1.2a", 18.60)
    assert row[1] == "+2" and row[2] == "+3"


class _RaisingRoller:
    """Duck-typed stand-in that fails the test if a die is ever rolled."""
    log = ()

    def roll(self, expr, reason="", mods=0, **tags):
        raise AssertionError("should not roll - Strength was already settled")


@pytest.mark.parametrize("resolved_score", [18.5, 18.99, 19.0])
def test_an_already_settled_exceptional_strength_is_not_rerolled(resolved_score):
    assert roll_exceptional_strength(_RaisingRoller(), resolved_score, "fighter") == resolved_score


def test_plain_18_still_rolls_exactly_one_die_for_an_eligible_class():
    d = Dice(seed=1)
    roll_exceptional_strength(d, 18, "fighter")
    assert len(d.log) == 1
    assert d.log[0].expr == "1d100"


def test_plain_18_point_0_still_rolls_exactly_one_die_for_an_eligible_class():
    d = Dice(seed=1)
    roll_exceptional_strength(d, 18.0, "fighter")
    assert len(d.log) == 1
    assert d.log[0].expr == "1d100"


from sanctuary.character import (ANCESTRIES, ancestry, apply_ancestry,
                                 meets_ancestry_minimums)


def test_seven_ancestries():
    assert set(ANCESTRIES) == {
        "dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human"}


def test_every_ancestry_has_the_full_shape():
    for name in ANCESTRIES:
        a = ancestry(name)
        for key in ("ability_adjustments", "minimums", "maximums",
                    "allowed_classes", "level_limits"):
            assert key in a, f"{name} missing {key}"
        assert a["allowed_classes"], f"{name} allows no classes"


def test_humans_have_no_adjustments_but_three_universal_class_ceilings():
    a = ancestry("human")
    assert a["ability_adjustments"] == {}
    assert a["level_limits"] == {"assassin": 15, "druid": 14, "monk": 17}
    assert len(a["allowed_classes"]) == 10


def test_no_ancestry_carries_the_universal_ceilings_unless_the_book_says_so():
    # Assassin 15 / Druid 14 / Monk 17 are ceilings no one of any ancestry
    # exceeds (OSRIC 3.0 SS1.2.7.3) - they land on the human row because
    # humans have no ancestral limit of their own to be lower. Another
    # ancestry may only carry one of these numbers if the book gives that
    # ancestry that exact cap for that class.
    book_matches = {
        "dwarf": {},
        "elf": {},
        "gnome": {},
        "half-elf": {"druid": 14},
        "halfling": {},
        "half-orc": {"assassin": 15},
    }
    for name, expected in book_matches.items():
        limits = ancestry(name)["level_limits"]
        for cls, ceiling in (("assassin", 15), ("druid", 14), ("monk", 17)):
            if cls in expected:
                assert limits.get(cls) == expected[cls], f"{name}/{cls} should be {expected[cls]}"
            else:
                assert limits.get(cls) != ceiling, (
                    f"{name} carries the universal {cls} ceiling without book support")


def test_apply_ancestry_adjusts_scores():
    scores = {k: 10 for k in ABILITIES}
    adjusted = apply_ancestry(scores, "dwarf")
    assert adjusted["constitution"] == 11
    assert adjusted["charisma"] == 9
    assert scores["constitution"] == 10, "apply_ancestry must not mutate its input"


def test_minimums_are_checked_after_adjustment():
    low = {k: 6 for k in ABILITIES}
    assert not meets_ancestry_minimums(low, "dwarf")
    ok = {k: 14 for k in ABILITIES}
    assert meets_ancestry_minimums(ok, "dwarf")


def test_humans_accept_any_scores():
    assert meets_ancestry_minimums({k: 3 for k in ABILITIES}, "human")


def test_unknown_ancestry_raises():
    with pytest.raises(KeyError):
        ancestry("orc")


@pytest.mark.parametrize("name", ANCESTRIES)
def test_ancestral_bonuses_never_push_a_score_past_the_ancestrys_own_maximum(name):
    # Table 1.2.0A's ceiling applies whether or not data/ancestries.yaml
    # bothers to spell it out - an ability omitted from `maximums` still has
    # the universal ceiling of 18, and apply_ancestry must clamp to it, not
    # just to the ceilings that happen to be listed.
    a = ancestry(name)
    maxed = {k: 18 for k in ABILITIES}
    adjusted = apply_ancestry(maxed, name)
    for k, v in adjusted.items():
        ceiling = a["maximums"].get(k, 18)
        assert v <= ceiling, f"{name} {k}: {v} exceeds Table 1.2.0A's ceiling of {ceiling}"


def test_half_orc_strength_clamps_to_eighteen_not_nineteen():
    # osric.txt:983: half-orc Strength maximum is 18. A rolled 18 plus the
    # ancestry's +1 Strength bonus must clamp back to 18 (then be eligible
    # for exceptional Strength resolution), not sail through to 19.
    scores = {**{k: 10 for k in ABILITIES}, "strength": 18}
    assert apply_ancestry(scores, "half-orc")["strength"] == 18


def test_halfling_dexterity_clamps_to_eighteen_not_nineteen():
    # osric.txt:1610 area: halfling Dexterity maximum is 18 (never spelled
    # out in data/ancestries.yaml because it equals the universal default -
    # that omission is exactly what let the +1 Dexterity bonus through
    # before this fix).
    scores = {**{k: 10 for k in ABILITIES}, "dexterity": 18}
    assert apply_ancestry(scores, "halfling")["dexterity"] == 18
    assert not meets_ancestry_minimums({**{k: 10 for k in ABILITIES}, "dexterity": 19}, "halfling")


from sanctuary import tables
from sanctuary.character import CLASSES, eligible_classes, game_class, roll_hit_points


def test_ten_classes():
    assert set(CLASSES) == {
        "assassin", "cleric", "druid", "fighter", "illusionist", "magic-user",
        "monk", "paladin", "ranger", "thief"}


def test_every_class_names_its_three_tables():
    for name in CLASSES:
        c = game_class(name)
        for key in ("advancement_table", "saving_throw_table", "to_hit_table"):
            tables.load(c[key])  # raises if the table is not in the corpus


def test_eligibility_respects_class_minimums():
    weak = {k: 6 for k in ABILITIES}
    assert "fighter" not in eligible_classes(weak, "human")
    strong = {k: 16 for k in ABILITIES}
    assert "fighter" in eligible_classes(strong, "human")


def test_eligibility_respects_ancestry_class_access():
    strong = {k: 18 for k in ABILITIES}  # paladin needs CHA 17
    assert "paladin" not in eligible_classes(strong, "dwarf")
    assert "paladin" in eligible_classes(strong, "human")


def test_hit_points_use_the_class_hit_die():
    d = Dice(seed=1)
    roll_hit_points(d, "fighter", level=1, con_bonus=0)
    assert d.log[0].expr == "1d10"
    d2 = Dice(seed=1)
    roll_hit_points(d2, "magic-user", level=1, con_bonus=0)
    assert d2.log[0].expr == "1d4"


def test_constitution_bonus_applies_per_level():
    d = Dice(seed=3)
    hp = roll_hit_points(d, "fighter", level=3, con_bonus=2)
    rolled = sum(r.total for r in d.log)
    assert hp == rolled + 6


def test_hit_points_never_drop_below_one_per_level():
    d = Dice(seed=4)
    assert roll_hit_points(d, "magic-user", level=2, con_bonus=-3) >= 2


def test_hit_dice_stop_levels_match_the_book():
    # OSRIC 3.0 SS1.3.N.4a: the last level whose HIT DICE column is a bare
    # integer, and the flat hp/level once it switches to "X+Y*". Assassin,
    # druid and monk never reach an "X+Y*" row at all - their tables end at
    # a hard level cap (assassin's is an explicit XP ceiling; druid's and
    # monk's are singular-titleholder caps), so their "fixed" figure is 0
    # and unreachable in play.
    expected = {
        "assassin": (15, 0), "cleric": (9, 2), "druid": (14, 0),
        "fighter": (9, 3), "illusionist": (10, 1), "magic-user": (11, 1),
        "monk": (17, 0), "paladin": (9, 3), "ranger": (10, 2), "thief": (10, 2),
    }
    for name, (stop, fixed) in expected.items():
        c = game_class(name)
        assert c["hit_dice_stop_level"] == stop, name
        assert c["fixed_hp_per_level_after"] == fixed, name


def test_constitution_bonus_stops_when_hit_dice_stop():
    # A magic-user stops rolling at 11th level (osric.txt:797's general
    # summary and the table's own HD column both say 11; one footnote in
    # the class's own section misprints "10th" - the table and the general
    # rule agree, so 11 wins). Levels past that gain a flat +1/level with
    # NO Constitution adjustment.
    d = Dice(seed=7)
    hp = roll_hit_points(d, "magic-user", level=13, con_bonus=5)
    assert len(d.log) == 11, "only levels 1-11 roll a die"
    rolled = sum(r.total for r in d.log)
    assert hp == rolled + 5 * 11 + 2 * 1


def test_unknown_class_raises():
    with pytest.raises(KeyError):
        game_class("barbarian")


def test_ranger_rolls_two_hit_dice_at_first_level():
    # osric.txt:3654-3657: "Unlike other classes rangers get an extra hit
    # die at first level. Your starting hit points are 2d8..."
    d = Dice(seed=5)
    hp = roll_hit_points(d, "ranger", level=1, con_bonus=0)
    assert [r.expr for r in d.log] == ["1d8", "1d8"]
    assert hp == sum(r.total for r in d.log)


def test_constitution_bonus_applies_to_both_of_a_rangers_first_level_dice():
    # "...if you have a constitution bonus to your hit points, then this
    # applies to both of your hit dice" (osric.txt:3656-3657).
    d = Dice(seed=5)
    hp = roll_hit_points(d, "ranger", level=1, con_bonus=2)
    rolled = sum(r.total for r in d.log)
    assert hp == rolled + 2 * 2  # +2 applied once per die, twice at level 1


def test_constitution_bonus_applies_once_per_level_after_first():
    d = Dice(seed=5)
    hp = roll_hit_points(d, "ranger", level=2, con_bonus=2)
    assert len(d.log) == 3  # 2 dice at level 1, 1 at level 2
    rolled = sum(r.total for r in d.log)
    assert hp == rolled + 2 * 3  # bonus applied once per die rolled overall


@pytest.mark.parametrize("cls", [c for c in CLASSES if c not in ("ranger", "monk")])
def test_only_the_ranger_and_monk_roll_extra_dice_at_first_level(cls):
    d = Dice(seed=6)
    roll_hit_points(d, cls, level=1, con_bonus=0)
    assert len(d.log) == 1, f"{cls} should roll exactly one hit die at 1st level"


@pytest.mark.parametrize("cls", CLASSES)
def test_hit_dice_at_first_level_matches_the_class_own_advancement_table(cls):
    # A per-class hardcoded assertion (the old test only ever checked ranger)
    # is exactly why the monk's missing second hit die survived - this reads
    # the level-1 HIT DICE cell straight out of every class's own table
    # instead. Every advancement table's header line reads "LEVEL XP NEEDED
    # HIT DICE" - the first three columns, universal across all ten tables -
    # so column index 2 of the level-1 row is always the HIT DICE cell.
    # Selected by row[1] == "0" rather than merely row[0] == "1": a couple of
    # these tables also leak a wrapped spell-slot sub-header ("1 2 3 4") that
    # itself starts with a level-shaped "1" - but level 1 always costs 0 XP
    # in every one of these tables, and the leaked header never has "0" in
    # its second field, so this picks the real data row and skips the leak.
    c = game_class(cls)
    row = next(r for r in tables.rows(c["advancement_table"]) if r[0] == "1" and r[1] == "0")
    assert int(row[2]) == c["hit_dice_at_first_level"], (
        f"{cls}'s hit_dice_at_first_level disagrees with its own table: "
        f"table says {row[2]!r}, data/classes.yaml says {c['hit_dice_at_first_level']}")


import re

from sanctuary.character import SAVE_CATEGORIES, ability_modifiers, saving_throws, to_hit_target

# Same axis the to-hit tables print: armour classes descending from 10 to -10.
_AC_COLUMNS = list(range(10, -11, -1))


def _row_level(label: str) -> float:
    """A level guaranteed to fall inside a table row's label, for test setup."""
    return float(re.split(r"[–—-]", label.rstrip("+"))[0])


def test_strength_modifiers_come_from_the_table():
    mods = ability_modifiers({**{k: 10 for k in ABILITIES}, "strength": 18})
    assert mods["hit"] == 1
    assert mods["damage"] == 2


def test_exceptional_strength_modifiers():
    mods = ability_modifiers({**{k: 10 for k in ABILITIES}, "strength": 18.60})
    assert mods["hit"] == 2
    assert mods["damage"] == 3


def test_average_scores_give_no_modifiers():
    mods = ability_modifiers({k: 10 for k in ABILITIES})
    assert mods["hit"] == 0
    assert mods["damage"] == 0


def test_fighter_saving_throws_at_level_one():
    # Table 1.3.4.4B, row 1-2: 16 / 17 / 14 / 15 / 17. The brief quotes this
    # exact row and it matches the corpus.
    saves = saving_throws("fighter", 1)
    assert saves["aimed_magic_items"] == 16
    assert saves["breath_weapons"] == 17
    assert saves["death_paralysis_poison"] == 14
    assert saves["petrifaction_polymorph"] == 15
    assert saves["spells"] == 17


def test_fighter_saving_throws_improve_with_level():
    assert saving_throws("fighter", 13)["spells"] < saving_throws("fighter", 1)["spells"]


def test_fighter_to_hit_targets():
    # Table 1.3.4.4C: level 1 needs 10 vs AC 10, and 19 vs AC 1. The brief's
    # own inline comment says "20 vs AC 1", which is wrong - but the
    # assertion it actually wrote checks 19, which matches the book.
    assert to_hit_target("fighter", 1, 10) == 10
    assert to_hit_target("fighter", 1, 1) == 19


def test_higher_level_hits_more_easily():
    assert to_hit_target("fighter", 9, 4) < to_hit_target("fighter", 1, 4)


@pytest.mark.parametrize("cls", CLASSES)
def test_saving_throws_match_the_corpus_at_every_row(cls):
    # Cross-checks every row of every class's own saving-throw table (not
    # just level 1 and not just fighter) against what saving_throws() returns,
    # so a wrong table id or a swapped column is caught for all ten classes.
    table_id = game_class(cls)["saving_throw_table"]
    for row in tables.rows(table_id):
        level = _row_level(row[0])
        expected = dict(zip(SAVE_CATEGORIES, (int(c) for c in row[1:6])))
        assert saving_throws(cls, level) == expected, f"{cls} level {level}"


@pytest.mark.parametrize("cls", CLASSES)
def test_to_hit_targets_match_the_corpus_at_every_row(cls):
    # Same idea for to-hit: every level row, every armour class column, for
    # every class - a prior task shipped a bug that hid behind fighter-only
    # coverage.
    table_id = game_class(cls)["to_hit_table"]
    for row in tables.rows(table_id):
        level = _row_level(row[0])
        for ac, cell in zip(_AC_COLUMNS, row[1:]):
            assert to_hit_target(cls, level, ac) == int(cell), f"{cls} level {level} AC {ac}"


@pytest.mark.parametrize("cls", CLASSES)
def test_saving_throws_never_worsen_with_level(cls):
    table_id = game_class(cls)["saving_throw_table"]
    rows = tables.rows(table_id)
    first = saving_throws(cls, _row_level(rows[0][0]))
    last = saving_throws(cls, _row_level(rows[-1][0]))
    for category in SAVE_CATEGORIES:
        assert last[category] <= first[category], f"{cls} {category} got worse with level"


@pytest.mark.parametrize("cls", CLASSES)
def test_to_hit_targets_never_worsen_with_level(cls):
    table_id = game_class(cls)["to_hit_table"]
    rows = tables.rows(table_id)
    first_level, last_level = _row_level(rows[0][0]), _row_level(rows[-1][0])
    assert to_hit_target(cls, last_level, 4) <= to_hit_target(cls, first_level, 4)


# Only the fighter's saving-throw table carries an explicit "0" row (0-level
# fighting-men); every other class's saving-throw table starts at level 1.
@pytest.mark.parametrize("cls", [c for c in CLASSES if c != "fighter"])
def test_level_zero_raises_saving_throws_for_every_class_but_the_fighter(cls):
    with pytest.raises(LookupError, match=f"{cls} level 0"):
        saving_throws(cls, 0)


# The to-hit table has the same "0" row for BOTH the fighter and the ranger -
# the book reprints the fighter's exact progression for the ranger, 0-level
# row included (verified: tables.rows() gives both tables the same first row
# "0", every other class's first row is "1" or a "1-N" range).
@pytest.mark.parametrize("cls", [c for c in CLASSES if c not in ("fighter", "ranger")])
def test_level_zero_raises_to_hit_for_every_class_but_the_fighter_and_ranger(cls):
    with pytest.raises(LookupError, match=f"{cls} level 0"):
        to_hit_target(cls, 0, 10)


@pytest.mark.parametrize("cls", ["fighter", "ranger"])
def test_fighter_and_ranger_level_zero_to_hit_resolves(cls):
    # Table 1.3.4.4C / 1.3.9.4C row "0": these are the two classes whose
    # to-hit table covers 0-level fighting-men.
    assert to_hit_target(cls, 0, 10) == 11


def test_fighter_level_zero_saving_throws_resolves():
    # Table 1.3.4.4B row "0": the fighter is the one class whose
    # saving-throw table covers 0-level fighting-men.
    assert saving_throws("fighter", 0)["spells"] == 19


# Assassin, druid and monk have closed top rows with no "N+" - a hard XP/title
# ceiling, not an extraction gap (see data/classes.yaml's header comment).
@pytest.mark.parametrize("cls, ceiling", [("assassin", 15), ("druid", 14), ("monk", 17)])
def test_level_above_a_hard_capped_class_ceiling_raises(cls, ceiling):
    with pytest.raises(LookupError, match=f"{cls} level {ceiling + 1}"):
        saving_throws(cls, ceiling + 1)
    with pytest.raises(LookupError, match=f"{cls} level {ceiling + 1}"):
        to_hit_target(cls, ceiling + 1, 10)


from sanctuary.character import Character, generate, is_legal_multiclass


def test_generate_produces_a_complete_character():
    # seed=11: a human fighter meets the fighter's own Strength-9 minimum at
    # this seed under "normal" (4d6d1) - generate() now enforces that
    # minimum (Critical 3), so a seed picked without checking it can raise
    # instead of building a character.
    c = generate(seed=11, mode="normal", ancestry_name="human",
                 class_names=("fighter",), name="Ilse")
    assert isinstance(c, Character)
    assert c.name == "Ilse"
    assert c.ancestry == "human"
    assert c.classes == ("fighter",)
    assert c.levels == {"fighter": 1}
    assert set(c.scores) == set(ABILITIES)
    assert c.hit_points >= 1
    assert set(c.saves) == set(SAVE_CATEGORIES)
    assert c.seed == 11


def test_generation_is_reproducible():
    a = generate(seed=13, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=13, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert a == b


def test_different_seeds_give_different_characters():
    a = generate(seed=1, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=3, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert a.scores != b.scores or a.hit_points != b.hit_points


def test_log_is_excluded_from_character_equality():
    # Two characters built from the same inputs compare equal even though
    # `log` carries per-instance Roll objects - it is excluded from
    # dataclass equality by design (field(compare=False)).
    a = generate(seed=5, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=5, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert a.log == b.log  # still identical in this case, but...
    assert a == b  # ...equality does not depend on it
    object.__setattr__(a, "log", ())  # would fail if `log` were part of `__eq__`
    assert a == b


def test_humans_may_not_multiclass():
    assert not is_legal_multiclass("human", ("fighter", "magic-user"))


def test_elves_may_multiclass_fighter_magic_user():
    assert is_legal_multiclass("elf", ("fighter", "magic-user"))


def test_multiclass_must_be_allowed_by_ancestry():
    assert not is_legal_multiclass("dwarf", ("fighter", "magic-user"))


def test_single_class_is_always_legal_for_an_allowed_class():
    assert is_legal_multiclass("human", ("fighter",))


def test_generate_rejects_an_illegal_combination():
    with pytest.raises(ValueError):
        generate(seed=1, mode="normal", ancestry_name="human",
                 class_names=("fighter", "magic-user"))


def test_generate_rejects_a_class_the_rolled_scores_do_not_qualify_for():
    # seed=1, mode="hardest" (3d6 in order), human fighter: rolls a Strength
    # of 8, below the fighter's own minimum of 9 (osric.txt:2447). Before
    # this fix generate() only checked ancestry class-access, never a
    # class's own ability minimums, so this returned a legal (illegally
    # weak) fighter.
    with pytest.raises(ValueError, match="fighter"):
        generate(seed=1, mode="hardest", ancestry_name="human", class_names=("fighter",))


def test_generate_rejects_scores_below_the_ancestrys_own_floor():
    # seed=2, mode="hardest", dwarf: rolls a Strength of 3, below the
    # dwarf's own Table 1.2.0A floor of 8.
    with pytest.raises(ValueError, match="dwarf"):
        generate(seed=2, mode="hardest", ancestry_name="dwarf", class_names=("fighter",))


def test_unlisted_class_for_an_ancestry_is_illegal_even_alone():
    # A dwarf may never be a magic-user at all - illegal whether alone or
    # combined with anything else.
    assert not is_legal_multiclass("dwarf", ("magic-user",))


# Every ancestry's multiclass_combinations, transcribed and line-cited
# against the book in data/ancestries.yaml. Verifies both directions: every
# listed combination is legal, and the universe of two-class combinations
# NOT listed for that ancestry is illegal.
_ANCESTRY_COMBOS = {
    "dwarf": [("fighter", "thief")],
    "elf": [("fighter", "magic-user"), ("fighter", "thief"), ("magic-user", "thief"),
            ("fighter", "magic-user", "thief")],
    "gnome": [("fighter", "illusionist"), ("fighter", "thief"), ("illusionist", "thief")],
    "half-elf": [("cleric", "fighter"), ("cleric", "ranger"), ("cleric", "magic-user"),
                 ("fighter", "magic-user"), ("fighter", "thief"),
                 ("cleric", "fighter", "magic-user"), ("fighter", "magic-user", "thief")],
    "halfling": [("fighter", "thief")],
    "half-orc": [("cleric", "fighter"), ("cleric", "thief"), ("cleric", "assassin"),
                 ("fighter", "thief"), ("fighter", "assassin")],
    "human": [],
}


@pytest.mark.parametrize("name", ANCESTRIES)
def test_every_ancestry_carries_its_book_multiclass_combinations(name):
    a = ancestry(name)
    assert "multiclass_combinations" in a
    got = [tuple(c) for c in a["multiclass_combinations"]]
    assert sorted(sorted(c) for c in got) == sorted(sorted(c) for c in _ANCESTRY_COMBOS[name])


@pytest.mark.parametrize("name, combo", [
    (name, combo) for name, combos in _ANCESTRY_COMBOS.items() for combo in combos
])
def test_every_book_combination_is_legal(name, combo):
    assert is_legal_multiclass(name, combo)


@pytest.mark.parametrize("name", ANCESTRIES)
def test_no_ancestry_permits_a_class_pair_outside_its_own_list(name):
    import itertools
    allowed = ancestry(name)["allowed_classes"]
    legal_pairs = {tuple(sorted(c)) for c in _ANCESTRY_COMBOS[name] if len(c) == 2}
    for a, b in itertools.combinations(sorted(allowed), 2):
        expect_legal = (a, b) in legal_pairs
        assert is_legal_multiclass(name, (a, b)) == expect_legal, f"{name}: {a}/{b}"


# One seed per class, each hand-picked to clear that class's own §1.3.N.1
# ability minimums under mode="normal" - a single shared seed no longer
# works for every class now that generate() enforces those minimums
# (Critical 3); a class that used to slip through under-strength no longer
# generates at all.
_HUMAN_CLASS_SEEDS = {
    "assassin": 3, "cleric": 1, "druid": 3, "fighter": 1, "illusionist": 37,
    "magic-user": 1, "monk": 3, "paladin": 40, "ranger": 24, "thief": 1,
}


@pytest.mark.parametrize("cls", CLASSES)
def test_generate_a_human_of_every_class(cls):
    # Site-wide standard: exercise all ten classes, not just fighter -
    # a prior task shipped a class-specific bug that survived because only
    # fighter was ever generated end to end.
    c = generate(seed=_HUMAN_CLASS_SEEDS[cls], mode="normal",
                 ancestry_name="human", class_names=(cls,))
    assert c.classes == (cls,)
    assert c.levels == {cls: 1}
    assert c.hit_points >= 1
    assert set(c.saves) == set(SAVE_CATEGORIES)


# One seed per ancestry, each clearing both that ancestry's own Table 1.2.0A
# minimums and its first allowed class's minimums under mode="normal" - see
# _HUMAN_CLASS_SEEDS above for why a shared seed no longer works.
_ANCESTRY_SEEDS = {
    "dwarf": 3, "elf": 3, "gnome": 3, "half-elf": 3,
    "halfling": 3, "half-orc": 14, "human": 3,
}


@pytest.mark.parametrize("name", ANCESTRIES)
def test_generate_one_character_per_ancestry(name):
    # Site-wide standard: exercise all seven ancestries, not just human/elf.
    cls = ancestry(name)["allowed_classes"][0]
    c = generate(seed=_ANCESTRY_SEEDS[name], mode="normal",
                 ancestry_name=name, class_names=(cls,))
    assert c.ancestry == name
    assert c.hit_points >= 1


def test_ranger_generates_at_first_level_with_its_extra_hit_die():
    c = generate(seed=24, mode="normal", ancestry_name="half-elf", class_names=("ranger",))
    hp_rolls = [r for r in c.log if "hp level" in r.reason]
    assert len(hp_rolls) == 2
    # Chapter 3 wires the real Constitution hp bonus in - each die floors at
    # 1 (plus bonus) individually, per roll_hit_points' own docstring.
    con_bonus = constitution_hp_bonus(c.scores["constitution"], "ranger")
    assert c.hit_points == sum(max(1, r.total + con_bonus) for r in hp_rolls)


from sanctuary.character import _multiclass_hit_points, constitution_hp_bonus
from sanctuary.dice import Roll


class _QueueRoller:
    """Duck-typed stand-in that returns fixed totals in call order, one per
    die - so a multiclass hp test can pin exact arithmetic instead of
    searching for a seed that happens to produce the numbers we want."""

    def __init__(self, totals):
        self._totals = list(totals)
        self.log = ()

    def roll(self, expr, reason="", mods=0, **tags):
        total = self._totals.pop(0)
        r = Roll(index=len(self.log), expr=expr, faces=(total,), kept=(total,),
                  mods=0, total=total, reason=reason, tags=tags)
        self.log = self.log + (r,)
        return r


def test_multiclass_hit_points_divide_each_class_roll_before_summing():
    # OSRIC 3.0 SS1.3.11 "Gaining Hit Points": the Erix Uncle example rolls
    # ONE class's die, adds Constitution, and divides THAT roll by the
    # number of classes - it never sums multiple classes' rolls first. This
    # pins fighter=7, magic-user=3 (both odd, n=2), chosen because the two
    # readings disagree: sum-then-divide gives (7+3)//2 = 5, but the book's
    # divide-per-class-then-sum gives floor(7/2) + floor(3/2) = 3 + 1 = 4.
    # This test fails under the old (wrong) sum-then-divide behaviour.
    # Constitution 10 sits in Table 1.1.4A's flat 0-bonus band for every
    # class, so this still isolates the division arithmetic being tested.
    roller = _QueueRoller([7, 3])
    hp = _multiclass_hit_points(roller, ("fighter", "magic-user"), {"constitution": 10})
    assert hp == 4


def test_multiclass_hit_points_divide_each_of_three_classes_before_summing():
    # Same disagreement, three classes (elf fighter/magic-user/thief, all
    # odd rolls): sum-then-divide gives (7+3+5)//3 = 5, but the book's
    # divide-per-class-then-sum gives floor(7/3) + floor(3/3) + floor(5/3)
    # = 2 + 1 + 1 = 4.
    roller = _QueueRoller([7, 3, 5])
    hp = _multiclass_hit_points(roller, ("fighter", "magic-user", "thief"), {"constitution": 10})
    assert hp == 4


def test_multiclass_hit_points_floor_applies_per_class_not_once_overall():
    # osric.txt:793's "always gain at least 1hp" is applied per class
    # contribution, consistent with each class's level-1 being its own
    # gaining-a-level event (and with how roll_hit_points already floors
    # the ranger's two 1st-level dice individually - Task 11's precedent).
    # Consequence, stated explicitly: a three-class character's minimum
    # starting hp is 3 (1 per class), not 1. Rolls of 1 on every die, with
    # 3 classes, would give floor(1/3) = 0 per class without the floor;
    # with it, each class contributes at least 1.
    roller = _QueueRoller([1, 1, 1])
    hp = _multiclass_hit_points(roller, ("fighter", "magic-user", "thief"), {"constitution": 10})
    assert hp == 3


def test_multiclass_hit_points_ranger_dice_stay_one_classs_contribution():
    # A ranger's extra 1st-level die (2d8, SS1.3.9) is rolled by
    # roll_hit_points as a single class total - it must be divided by the
    # class count once, as ONE class's contribution, not treated as if the
    # ranger were two classes. cleric rolls 7, ranger rolls 5+5=10:
    # cleric contributes floor(7/2)=3, ranger contributes floor(10/2)=5,
    # total 8 - not floor(7/2) + floor(5/2) + floor(5/2) = 3+2+2 = 7, which
    # is what you'd get by mistakenly treating the ranger's two dice as two
    # separate classes.
    roller = _QueueRoller([7, 5, 5])
    hp = _multiclass_hit_points(roller, ("cleric", "ranger"), {"constitution": 10})
    assert hp == 8


def test_multiclass_hit_points_include_a_rangers_extra_first_level_die():
    # End-to-end: a ranger contributes 2d8 (its own extra first-level die)
    # through generate(), and both dice go into the ranger's single
    # class-contribution before it's divided by the class count.
    c = generate(seed=24, mode="normal", ancestry_name="half-elf",
                 class_names=("cleric", "ranger"))
    hp_rolls = [r for r in c.log if "hp level" in r.reason]
    assert len(hp_rolls) == 3  # 1 cleric die + 2 ranger dice
    cleric_bonus = constitution_hp_bonus(c.scores["constitution"], "cleric")
    ranger_bonus = constitution_hp_bonus(c.scores["constitution"], "ranger")
    cleric_roll = max(1, hp_rolls[0].total + cleric_bonus)
    ranger_roll = (max(1, hp_rolls[1].total + ranger_bonus)
                   + max(1, hp_rolls[2].total + ranger_bonus))
    assert c.hit_points == max(1, cleric_roll // 2) + max(1, ranger_roll // 2)


def test_exceptional_strength_applies_when_any_class_in_the_combo_qualifies():
    # A fighter/magic-user elf still qualifies for exceptional Strength
    # because fighter is one of its classes, even though it's not the only
    # one - eligibility isn't limited to the first-listed class.
    c = generate(seed=1, mode="normal", ancestry_name="elf",
                 class_names=("magic-user", "fighter"))
    pct_rolls = [r for r in c.log if r.expr == "1d100"]
    if c.scores["strength"] == 18:
        # Only certain seeds land exactly on 18 pre-exceptional-roll; when
        # they do, a percentile roll must have happened.
        assert pct_rolls
    # Whatever the roll, exceptional strength was checked at most once.
    assert len(pct_rolls) <= 1


def test_multiclass_saving_throws_take_the_best_of_every_class():
    # SS1.3.11 "Attacks and Saving Throws": a multi-classed character may use
    # whichever class's table is best, category by category.
    c = generate(seed=3, mode="normal", ancestry_name="elf",
                 class_names=("fighter", "magic-user"))
    fighter_saves = saving_throws("fighter", 1)
    magic_user_saves = saving_throws("magic-user", 1)
    for category in SAVE_CATEGORIES:
        assert c.saves[category] == min(fighter_saves[category], magic_user_saves[category])


def test_generate_defers_constitution_hp_adjustment_and_armour_class():
    c = generate(seed=1, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert c.armour_class == 10


from sanctuary.character import apply_arrangement


def test_arrangement_none_passes_rolled_scores_through_unchanged():
    rolled = {name: v for name, v in zip(ABILITIES, range(3, 9))}
    assert apply_arrangement(rolled, None, "hardest") is rolled


def test_arrangement_rejected_for_a_non_arrangeable_mode():
    rolled = {name: v for name, v in zip(ABILITIES, range(3, 9))}
    arrangement = dict(zip(ABILITIES, reversed(range(3, 9))))
    with pytest.raises(ValueError, match="hardest"):
        apply_arrangement(rolled, arrangement, "hardest")


def test_arrangement_rejected_for_normal_mode_too():
    rolled = {name: v for name, v in zip(ABILITIES, range(3, 9))}
    arrangement = dict(zip(ABILITIES, reversed(range(3, 9))))
    with pytest.raises(ValueError, match="normal"):
        apply_arrangement(rolled, arrangement, "normal")


def test_arrangement_reassigns_values_to_abilities():
    rolled = dict(zip(ABILITIES, (8, 9, 10, 11, 12, 13)))
    # Put the highest roll (13) on strength instead of where it landed (charisma).
    arrangement = dict(zip(ABILITIES, (13, 12, 11, 10, 9, 8)))
    result = apply_arrangement(rolled, arrangement, "difficult")
    assert result["strength"] == 13
    assert result["charisma"] == 8


def test_arrangement_must_cover_every_ability_exactly_once():
    rolled = dict(zip(ABILITIES, (8, 9, 10, 11, 12, 13)))
    incomplete = {k: v for k, v in list(rolled.items())[:5]}  # missing charisma
    with pytest.raises(ValueError, match="every ability"):
        apply_arrangement(rolled, incomplete, "flexible")


def test_arrangement_must_be_a_permutation_not_a_substitution():
    # No sneaking a 17 in for a rolled 7 - every value must come from `rolled`.
    rolled = dict(zip(ABILITIES, (7, 9, 10, 11, 12, 13)))
    cheating = dict(rolled)
    cheating["strength"] = 17
    with pytest.raises(ValueError, match="permutation"):
        apply_arrangement(rolled, cheating, "flexible")


def test_arrangement_rejects_duplicating_one_value_and_dropping_another():
    rolled = dict(zip(ABILITIES, (7, 9, 10, 11, 12, 13)))
    duplicated = dict(rolled)
    duplicated["strength"] = duplicated["dexterity"]  # 9, dropping the rolled 7
    with pytest.raises(ValueError, match="permutation"):
        apply_arrangement(rolled, duplicated, "flexible")


def test_generate_rejects_an_arrangement_in_a_non_arrangeable_mode():
    arrangement = dict(zip(ABILITIES, range(3, 9)))
    with pytest.raises(ValueError, match="normal"):
        generate(seed=1, mode="normal", ancestry_name="human",
                 class_names=("fighter",), arrangement=arrangement)


def test_generate_rejects_a_non_permutation_arrangement():
    rolled = roll_abilities(Dice(seed=1), "flexible")
    cheating = dict(rolled)
    cheating["strength"] = max(rolled.values()) + 1  # not among the rolled values
    with pytest.raises(ValueError, match="permutation"):
        generate(seed=1, mode="flexible", ancestry_name="human",
                 class_names=("fighter",), arrangement=cheating)


def test_generate_with_arrangement_is_reproducible():
    rolled = roll_abilities(Dice(seed=13), "flexible")
    arrangement = dict(zip(ABILITIES, sorted(rolled.values(), reverse=True)))
    a = generate(seed=13, mode="flexible", ancestry_name="human",
                 class_names=("fighter",), arrangement=arrangement)
    b = generate(seed=13, mode="flexible", ancestry_name="human",
                 class_names=("fighter",), arrangement=arrangement)
    assert a == b
    assert a.scores == arrangement


def test_arrangement_does_not_change_the_roll_log():
    # Arrangement assigns already-rolled values - it never re-rolls, so the
    # log is identical whether or not (and however) the player arranges.
    rolled = roll_abilities(Dice(seed=13), "flexible")
    arrangement = dict(zip(ABILITIES, sorted(rolled.values(), reverse=True)))
    plain = generate(seed=13, mode="flexible", ancestry_name="human", class_names=("fighter",))
    arranged = generate(seed=13, mode="flexible", ancestry_name="human",
                         class_names=("fighter",), arrangement=arrangement)
    assert plain.log == arranged.log


def test_arrangement_can_rearrange_a_character_into_legibility():
    # The whole point of the arrangeable modes: a set of rolled scores that
    # fails a class's minimums in roll order can pass once the player puts
    # the right value on the right ability. mode="hardest" (3d6 in order),
    # seed=1, human fighter is refused for a sub-9 Strength in roll order
    # (see test_generate_rejects_a_class_the_rolled_scores_do_not_qualify_for);
    # the same six values, arranged so the highest lands on Strength, must
    # succeed in "difficult" mode (which rolls the same 3d6 expression).
    rolled = roll_abilities(Dice(seed=1), "difficult")
    best_first = sorted(rolled.values(), reverse=True)
    arrangement = dict(zip(ABILITIES, best_first))
    c = generate(seed=1, mode="difficult", ancestry_name="human",
                 class_names=("fighter",), arrangement=arrangement)
    assert c.scores["strength"] == best_first[0]
