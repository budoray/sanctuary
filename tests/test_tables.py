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
    """2.9.1e is three files (GRAVEYARD ENCOUNTERS, printed across three
    pages). Silently returning one of them is how 26 tables would vanish
    from a corpus that still round-trips."""
    with pytest.raises(LookupError) as e:
        tables.load("2.9.1e")
    assert "2.9.1e_graveyard_encounters_part_1.yaml" in str(e.value)


def test_parts_returns_every_file_for_a_split_table():
    docs = tables.parts("2.9.1e")
    assert len(docs) == 3
    assert all(d["id"] == "2.9.1e" for d in docs)
    assert {d["name"] for d in docs} == {
        "GRAVEYARD  ENCOUNTERS (PART 1)", "GRAVEYARD  ENCOUNTERS (PART 2)",
        "GRAVEYARD  ENCOUNTERS (PART 2) CONTINUED"}


def test_sub_numbered_table_ids_are_not_merged_into_their_parent():
    """`TABLE 1.4.2.3A.1: CONTAINERS` and `TABLE 1.4.2.3A.2: MOUNTS AND PACK
    ANIMALS` used to fall into the id-group regex's `[:.]` separator and
    come out as id `1.4.2.3a` with a mangled name (`"1: CONTAINERS"`),
    merging three unrelated tables (General Equipment, Containers, Mounts
    and Pack Animals) under one id that then had to raise on load(). The
    `(?:\\.\\d+)?` tail in `_HEADER` keeps the sub-number as part of the id
    instead."""
    assert tables.load("1.4.2.3a")["name"] == "GENERAL  EQUIPMENT"
    assert tables.load("1.4.2.3a.1")["name"] == "CONTAINERS"
    assert tables.load("1.4.2.3a.2")["name"] == "MOUNTS AND PACK ANIMALS"


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


def test_in_range_reads_a_leading_minus_as_a_negative_value_not_a_range():
    # No Chapter 1 table has a negative first cell, but monster and treasure
    # tables do - "-3" must be the single value -3, not the range separator
    # producing the positive value 3 (`_DASH.split("-3")` -> ('', '3')).
    assert tables.in_range("-3", -3)
    assert not tables.in_range("-3", 3)


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


TO_HIT_TABLES = [
    "2.1.2a", "1.3.1.4d", "1.3.2.4c", "1.3.3.4c", "1.3.4.4c", "1.3.5.4c",
    "1.3.6.4c", "1.3.7.4d", "1.3.8.4c", "1.3.9.4c", "1.3.10.4f",
]


@pytest.mark.parametrize("table_id", TO_HIT_TABLES)
def test_rows_drops_the_armour_class_header(table_id):
    """The header `10 9 8 7 ... -10` starts with a digit like any data row,
    but it is armour classes, not a level or hit-dice row, and must not be
    mistaken for one."""
    for row in tables.rows(table_id):
        assert row != ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1",
                        "0", "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8",
                        "-9", "-10"]


def test_ability_row_level_10_fighter_is_not_the_header():
    """A level-10 fighter's row label is `10`, identical to the header row's
    first field - the exact collision the header-drop bug hid."""
    row = tables.ability_row("1.3.4.4c", 10)
    assert row[0] == "10"
    assert row[1] == "1"  # roll to hit AC 10


@pytest.mark.parametrize("level,expected", [(1, "10"), (9, "2"), (10, "1"), (20, "-9")])
def test_ability_row_to_hit_ac10_by_level(level, expected):
    """Roll needed to hit AC 10, for a fighter (1.3.4.4c) at several levels -
    including 10, the one the header bug corrupted."""
    row = tables.ability_row("1.3.4.4c", level)
    assert row[1] == expected


def test_in_range_refuses_ambiguous_equal_endpoint_range():
    """`1-1` is OSRIC's "one hit die minus one" idiom, not a genuine range -
    a real range is never written with identical endpoints. Reading it as the
    numeric range [1, 1] would make it collapse to `value == 1` and shadow
    the bare `1` row."""
    with pytest.raises(ValueError):
        tables.in_range("1-1", 1)


def test_parts_of_unknown_table_raises():
    with pytest.raises(KeyError):
        tables.parts("9.9.9z")


def test_in_range_empty_spec_is_false():
    assert not tables.in_range("", 3)


def test_in_range_malformed_less_than_is_false():
    assert not tables.in_range("<abc", 1)


def test_in_range_non_numeric_spec_is_false():
    assert not tables.in_range("N/A", 1)


def test_in_range_dash_only_spec_is_false():
    assert not tables.in_range("-", 1)


def test_ability_row_raises_when_no_row_covers_score():
    with pytest.raises(LookupError):
        tables.ability_row("1.1.2a", 999)


def test_ability_row_hit_dice_one_is_not_the_minus_one_row():
    """A full 1 Hit Die monster must not silently land on the sub-1-HD row.
    Monster hit-dice notation gets its own accessor in Chapter 5; here the
    contract is just that `in_range`'s ambiguity is not swallowed."""
    with pytest.raises(ValueError):
        tables.ability_row("2.1.2a", 1)


ABILITY_TABLES = ["1.1.2a", "1.1.3a", "1.1.4a", "1.1.5a", "1.1.6a", "1.1.7a"]


@pytest.mark.parametrize("table_id", ABILITY_TABLES)
def test_ability_tables_keep_all_their_rows(table_id):
    """Regression guard for the round-1 fix that widened `_is_ac_header` too
    far: a two-field score-to-modifier row (e.g. Wisdom's `3 -3`) is also
    all-integer and strictly decreasing, and briefly got read as a header
    too, deleting every row in Intelligence and all of Wisdom."""
    rows = tables.rows(table_id)
    assert len(rows) >= 14  # every ability table covers score 3 through 19+
    row = tables.ability_row(table_id, 10)
    assert row[0].startswith("10") or row[0] == "9-11"


@pytest.mark.parametrize("table_id", TO_HIT_TABLES)
def test_ac_header_absent_and_first_row_is_a_real_label(table_id):
    """The AC header (21 fields wide) must be gone, and the first surviving
    row must be a level/HD label, not a header fragment."""
    rows = tables.rows(table_id)
    assert rows
    assert not tables._is_ac_header(rows[0])
    assert not any(tables._is_ac_header(row) for row in rows)


# Tables whose real rows are keyed by a text label (an ancestry, a weapon
# name, an item, a hireling) rather than a number - `rows()`'s `^\s*[<\d]`
# prefilter is a numeric-row detector by design (see the brief), so these
# always read as zero rows. Reviewed by hand against data/tables/*.yaml.
ZERO_ROW_ALLOWLIST = {
    "1.2.0a",     # ability score ranges keyed by ancestry name (Dwarf, Elf, ...)
    "1.3.10.4d",  # thief skill adjustments keyed by ancestry name
    "1.4.2.3a",   # general equipment keyed by item name (Ale, pint / Bedroll / ...)
    "1.4.2.3a.1", # containers keyed by item name (Barrel / Basket / ...)
    "1.4.2.3a.2", # mounts and pack animals keyed by animal name
    "1.4.2.3b",   # melee weapons keyed by weapon name (Axe, battle / Club / ...)
    "1.4.2.g",    # armour keyed by armour name (Banded / Chain mail / ...)
    "1.6.8a",     # morale modifiers keyed by situation text, not a number
    "2.13.4a",    # rod/staff/wand charges keyed by device type text
    "2.13.6.1f",  # sword special-power prose, no row structure at all
    "2.13.6.1h",  # sword ego rules prose, no row structure at all
    "2.14.1a",    # stronghold costs keyed by structure name
    "2.2.1a",     # hireling wages keyed by hireling name
    "2.2.2a",     # expert hireling wages keyed by hireling name
    "2.2.2b",     # soldier wages keyed by unit name
    "2.2.2c",     # ship crew wages keyed by role name
    "2.2.2d",     # armour production keyed by armour name
    "2.2.2e",     # weapon production keyed by weapon name
    "2.2.2j",     # sage fields of study, prose plus percentile lists
    "2.2.2k",     # sage chance to know, keyed by question type text
    "2.2.2m",     # information discovery cost, keyed by question type text
    "2.2.2n",     # complex weapon production keyed by weapon name
    "2.2.7.1b",   # witch-priest level cap keyed by ancestry name
    "2.2.7.1c",   # witch-priest spell list keyed by spell name
    "2.2.7.2b",   # witch-crafter level cap keyed by ancestry name
    "2.2.7.2c",   # witch-crafter divine spells keyed by spell name
    "2.2.7.2d",   # witch-crafter arcane spells keyed by spell name
}


def test_no_unreviewed_table_yields_zero_rows():
    """Every single-file table in the corpus either has rows or is on the
    reviewed allow-list above. `rows()` only handles multi-file (split)
    tables' constituent files, not the ambiguous id itself, so those are
    skipped here - use `parts()` for them."""
    unexpected = []
    for table_id, paths in tables._index().items():
        if len(paths) > 1:
            continue
        if not tables.rows(table_id) and table_id not in ZERO_ROW_ALLOWLIST:
            unexpected.append(table_id)
    assert not unexpected, f"zero rows, not on the allow-list: {unexpected}"


def test_rows_drops_a_leaked_section_heading():
    """`1.1.5a` (Intelligence) ends with the next section's heading,
    `1.1.6. WISDOM`, sitting right after Intelligence's own rows. It starts
    with a digit like a real row and must not be one."""
    for row in tables.rows("1.1.5a"):
        assert row != ["1.1.6.", "WISDOM"]
