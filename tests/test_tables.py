import pytest

from sanctuary import tables


def test_load_returns_the_document():
    t = tables.load("1.1.2a")
    assert "STRENGTH" in t["name"].upper()
    assert t["lines"]


def test_load_unknown_table_raises():
    with pytest.raises(KeyError):
        tables.load("9.9.9z")


def test_a_split_table_refuses_to_load_as_one_and_names_its_parts():
    """1.4.2.3a is three files. Silently returning one of them is how 26
    tables would vanish from a corpus that still round-trips."""
    with pytest.raises(LookupError) as e:
        tables.load("1.4.2.3a")
    assert "1.4.2.3a_general_equipment.yaml" in str(e.value)


def test_parts_returns_every_file_for_a_split_table():
    docs = tables.parts("1.4.2.3a")
    assert len(docs) == 3
    assert all(d["id"] == "1.4.2.3a" for d in docs)
    assert {d["name"] for d in docs} == {
        "GENERAL  EQUIPMENT", "1: CONTAINERS", "2: MOUNTS AND PACK ANIMALS"}


def test_parts_of_a_single_file_table_is_a_one_item_list():
    assert len(tables.parts("1.3.4.4a")) == 1


def test_no_committed_table_is_unreachable():
    """Every file in data/tables must be reachable through the index - the
    guard against an id-keying scheme that drops files on the floor."""
    from pathlib import Path as _P
    reachable = {p for group in tables._index().values() for p in group}
    on_disk = set(_P(tables._DIR).glob("*.yaml"))
    assert reachable == on_disk, f"unreachable: {sorted(on_disk - reachable)}"


def test_in_range_handles_single_values():
    assert tables.in_range("3", 3)
    assert not tables.in_range("3", 4)


def test_in_range_handles_en_dash_ranges():
    assert tables.in_range("4–5", 4)
    assert tables.in_range("4–5", 5)
    assert not tables.in_range("4–5", 6)


def test_in_range_handles_hyphen_ranges():
    assert tables.in_range("4-5", 5)


def test_in_range_handles_exceptional_strength():
    assert tables.in_range("18.01–18.50", 18.25)
    assert not tables.in_range("18.01–18.50", 18.60)
    assert tables.in_range("18.51–18.75", 18.75)


def test_in_range_handles_open_ended():
    assert tables.in_range("19+", 25)
    assert tables.in_range("19+", 19)
    assert not tables.in_range("19+", 18)


def test_ability_row_finds_the_strength_row():
    row = tables.ability_row("1.1.2a", 18)
    assert row[0].startswith("18")
    # STRENGTH  TO HIT  DAMAGE  ENCUMBRANCE ...
    assert row[1] == "+1"
    assert row[2] == "+2"


def test_ability_row_finds_an_exceptional_strength_row():
    row = tables.ability_row("1.1.2a", 18.60)
    assert row[0].replace("–", "-") == "18.51-18.75"
    assert row[1] == "+2"
