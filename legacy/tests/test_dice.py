import pytest

from sanctuary.dice import Roll, parse_expr, Dice


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


def test_roll_totals_and_records():
    d = Dice(seed=12345)
    r = d.roll("3d6", reason="strength")
    assert len(r.faces) == 3
    assert all(1 <= f <= 6 for f in r.faces)
    assert r.kept == r.faces
    assert r.total == sum(r.faces)
    assert r.reason == "strength"
    assert r.index == 0


def test_drop_lowest_keeps_the_best_three():
    d = Dice(seed=999)
    r = d.roll("4d6d1")
    assert len(r.faces) == 4
    assert len(r.kept) == 3
    assert sorted(r.kept) == sorted(r.faces)[1:]
    assert r.total == sum(r.kept)


def test_modifier_is_added_and_recorded_separately():
    d = Dice(seed=7)
    r = d.roll("1d20", mods=3)
    assert r.mods == 3
    assert r.total == sum(r.kept) + 3


def test_log_is_append_only_and_monotonic():
    d = Dice(seed=1)
    for i in range(5):
        d.roll("1d6", reason=f"r{i}")
    assert [r.index for r in d.log] == [0, 1, 2, 3, 4]
    assert [r.reason for r in d.log] == ["r0", "r1", "r2", "r3", "r4"]


def test_same_seed_same_sequence_is_identical():
    def session(seed):
        d = Dice(seed=seed)
        d.roll("3d6", reason="a")
        d.roll("4d6d1", reason="b")
        d.roll("1d20", mods=2, reason="c")
        return [(r.expr, r.faces, r.kept, r.total) for r in d.log]

    assert session(42) == session(42)
    assert session(42) != session(43)


def test_tags_are_carried():
    d = Dice(seed=5)
    r = d.roll("1d20", reason="attack", kind="attack", actor="ilse")
    assert r.tags == {"kind": "attack", "actor": "ilse"}


def test_log_cannot_be_mutated_through_the_property():
    d = Dice(seed=5)
    d.roll("1d6")
    log = d.log
    assert isinstance(log, tuple)
    assert len(d.log) == 1
