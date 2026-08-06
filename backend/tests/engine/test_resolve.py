import pytest

from backend.app.engine.resolve import attack, saving_throw, monster_to_hit_target
from backend.app.engine.character import generate
from backend.app.engine.dice import Dice


def test_monster_to_hit_target():
    target = monster_to_hit_target("1", 5)
    assert isinstance(target, int)


def _make_fighter(seed: int) -> object:
    from backend.tests.engine.test_character import _arrange_for_fighter
    arrangement = _arrange_for_fighter(seed)
    return generate(seed=seed, mode="flexible", ancestry_name="human", class_names=["fighter"], name="Hero", arrangement=arrangement)


def test_attack_hit_or_miss():
    d = Dice(seed=1)
    char = _make_fighter(1)
    result = attack(d, char, target_ac=10)
    assert result.natural in range(1, 21)
    assert result.hit in (True, False)


def test_saving_throw():
    d = Dice(seed=1)
    char = _make_fighter(1)
    result = saving_throw(d, char, "spells")
    assert result.natural in range(1, 21)
    assert result.success in (True, False)
