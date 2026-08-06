import pytest

from backend.app.engine.character import generate, roll_abilities, Dice, ABILITIES, CLASSES, ANCESTRIES


def test_roll_abilities_length():
    d = Dice(seed=1)
    scores = roll_abilities(d, "normal")
    assert set(scores) == set(ABILITIES)


def _arrange_for_fighter(seed: int) -> dict:
    """Return an arrangement of the rolled scores that meets fighter minimums."""
    from backend.app.engine.character import game_class
    d = Dice(seed=seed)
    rolled = roll_abilities(d, "flexible")
    scores = sorted(rolled.values(), reverse=True)
    mins = game_class("fighter")["minimums"]
    # Assign highest to abilities with highest minimums first.
    order = sorted(ABILITIES, key=lambda a: mins.get(a, 0), reverse=True)
    arrangement = {}
    for ability in order:
        min_val = mins.get(ability, 3)
        # pick the highest remaining score that satisfies the minimum
        for i, val in enumerate(scores):
            if val >= min_val:
                arrangement[ability] = scores.pop(i)
                break
        else:
            arrangement[ability] = scores.pop(0)
    return arrangement


def test_generate_human_fighter():
    arrangement = _arrange_for_fighter(42)
    char = generate(seed=42, mode="flexible", ancestry_name="human", class_names=["fighter"], name="Test", arrangement=arrangement)
    assert char.name == "Test"
    assert char.ancestry == "human"
    assert char.classes == ("fighter",)
    assert char.hit_points > 0
    assert char.armour_class <= 10


def test_generate_illegal_multiclass():
    with pytest.raises(ValueError):
        generate(seed=1, mode="normal", ancestry_name="human", class_names=["fighter", "magic-user"])


def test_arrangeable_modes():
    from backend.app.engine.character import arrangeable
    assert arrangeable("flexible")
    assert not arrangeable("hardest")
