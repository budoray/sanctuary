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
