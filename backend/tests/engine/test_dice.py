import pytest

from backend.app.engine.dice import Dice, parse_expr


def test_parse_expr_basic():
    assert parse_expr("3d6") == (3, 6, 0, 0)


def test_parse_expr_with_drop_and_mod():
    assert parse_expr("4d6d1+2") == (4, 6, 1, 2)


def test_roll_logs_and_replays():
    d1 = Dice(seed=12345)
    r1 = d1.roll("3d6", reason="test")
    r2 = d1.roll("1d20")

    d2 = Dice(seed=12345)
    s1 = d2.roll("3d6", reason="test")
    s2 = d2.roll("1d20")

    assert d1.log == d2.log
    assert r1.faces == s1.faces
    assert r2.faces == s2.faces


def test_roll_total_within_range():
    d = Dice(seed=1)
    r = d.roll("3d6")
    assert 3 <= r.total <= 18


def test_drop_lowest():
    d = Dice(seed=42)
    r = d.roll("4d6d1")
    assert len(r.faces) == 4
    assert len(r.kept) == 3
    assert r.total == sum(r.kept)
