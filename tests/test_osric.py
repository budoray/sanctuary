"""Tests for OSRIC ruleset adapter."""
from __future__ import annotations

import pytest

from rulesets.osric.adapter import (
    create_character_data,
    meets_requirements,
    roll_3d6,
    roll_ability_scores,
)


def test_roll_3d6_range():
    for _ in range(100):
        assert 3 <= roll_3d6() <= 18


def test_roll_ability_scores():
    scores = roll_ability_scores()
    assert set(scores.keys()) == {
        "strength",
        "intelligence",
        "wisdom",
        "dexterity",
        "constitution",
        "charisma",
    }
    for v in scores.values():
        assert 3 <= v <= 18


def test_valid_human_fighter():
    data = create_character_data("human", "fighter", "True Neutral", "Test")
    assert data["ancestry"] == "human"
    assert data["class"] == "fighter"
    assert "abilities" in data
    assert data["hit_points"] > 0


def test_invalid_ancestry_class():
    ok, errors = meets_requirements(
        "halfling", "magic_user", "True Neutral", roll_ability_scores()
    )
    assert not ok
    assert any("Halfling cannot be Magic-User" in e for e in errors)


def test_paladin_requires_high_charisma():
    ok, errors = meets_requirements(
        "human",
        "paladin",
        "Lawful Good",
        {a: 10 for a in roll_ability_scores().keys()},
    )
    assert not ok
    assert any("charisma" in e.lower() for e in errors)
