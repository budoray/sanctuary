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


@pytest.mark.parametrize("cls", [c for c in CLASSES if c != "ranger"])
def test_only_the_ranger_rolls_extra_dice_at_first_level(cls):
    d = Dice(seed=6)
    roll_hit_points(d, cls, level=1, con_bonus=0)
    assert len(d.log) == 1, f"{cls} should roll exactly one hit die at 1st level"
