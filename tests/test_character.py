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


def test_humans_have_no_adjustments_and_no_limits():
    a = ancestry("human")
    assert a["ability_adjustments"] == {}
    assert a["level_limits"] == {}
    assert len(a["allowed_classes"]) == 10


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
