import pytest

from backend.app.engine.tables import load, rows, ability_row, in_range


def test_load_table():
    doc = load("1.1.2a")
    assert "lines" in doc


def test_rows_not_empty():
    data = rows("1.1.2a")
    assert len(data) > 0


def test_ability_row():
    row = ability_row("1.1.2a", 15)
    assert row


def test_in_range_single():
    assert in_range("15", 15)


def test_in_range_range():
    assert in_range("3-5", 4)
