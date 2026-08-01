import pytest

from sanctuary.dice import Roll, parse_expr


def test_parse_simple():
    assert parse_expr("3d6") == (3, 6, 0, 0)


def test_parse_drop_lowest():
    assert parse_expr("4d6d1") == (4, 6, 1, 0)


def test_parse_modifier():
    assert parse_expr("1d20+3") == (1, 20, 0, 3)
    assert parse_expr("1d8-1") == (1, 8, 0, -1)


def test_parse_drop_and_modifier():
    assert parse_expr("4d6d1+2") == (4, 6, 1, 2)


def test_parse_rejects_nonsense():
    for bad in ["", "d6", "3d", "3x6", "3d6d", "0d6", "3d0", "4d6d4"]:
        with pytest.raises(ValueError):
            parse_expr(bad)


def test_roll_is_frozen():
    r = Roll(index=0, expr="1d6", faces=(4,), kept=(4,), mods=0,
             total=4, reason="", tags={})
    with pytest.raises(Exception):
        r.total = 99
