"""Tests for the dice engine and roll endpoint."""
from __future__ import annotations

import pytest

from engine.dice import DiceError, roll_expression


def test_roll_simple_die():
    result = roll_expression("d20")
    assert result["expression"] == "d20"
    assert len(result["parts"]) == 1
    assert result["parts"][0]["count"] == 1
    assert result["parts"][0]["sides"] == 20
    assert 1 <= result["total"] <= 20


def test_roll_multiple_dice():
    result = roll_expression("3d6")
    assert result["parts"][0]["count"] == 3
    assert result["parts"][0]["sides"] == 6
    assert 3 <= result["total"] <= 18


def test_roll_with_modifier():
    result = roll_expression("1d8+2")
    assert 3 <= result["total"] <= 10


def test_roll_compound_expression():
    result = roll_expression("d6+d4+3")
    assert 5 <= result["total"] <= 13


def test_roll_negative_modifier():
    result = roll_expression("1d20-1")
    assert 0 <= result["total"] <= 19


def test_invalid_expression():
    with pytest.raises(DiceError):
        roll_expression("")
    with pytest.raises(DiceError):
        roll_expression("abc")
    with pytest.raises(DiceError):
        roll_expression("0d6")


def test_roll_endpoint(client):
    res = client.post("/api/roll", data={"expression": "2d6+3"})
    assert res.status_code == 200
    data = res.json()
    assert data["expression"] == "2d6+3"
    assert 5 <= data["total"] <= 15
    assert len(data["parts"]) == 2


def test_roll_endpoint_rejects_invalid(client):
    res = client.post("/api/roll", data={"expression": "not-dice"})
    assert res.status_code == 400
