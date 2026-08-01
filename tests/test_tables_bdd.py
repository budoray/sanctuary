"""Step definitions for features/tables.feature."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import tables

scenarios("../features/tables.feature")


@given("the fighter to-hit table", target_fixture="table_id")
def fighter_table():
    return "1.3.4.4c"


@given("the monster to-hit table", target_fixture="table_id")
def monster_table():
    return "2.1.2a"


@given(
    "the general equipment table, which the book split across three pages",
    target_fixture="table_id",
)
def split_equipment_table():
    return "1.4.2.3a"


@given("the Wisdom table", target_fixture="table_id")
def wisdom_table():
    return "1.1.6a"


@when(
    parsers.parse(
        "a level {level:d} fighter looks up the roll needed to hit armour class {ac:d}"
    ),
    target_fixture="row",
)
def look_up_to_hit_row(table_id, level, ac):
    assert ac == 10  # the only column this scenario exercises
    return tables.ability_row(table_id, level)


@then(parsers.parse("the roll required is {roll:d}"))
def roll_required_is(row, roll):
    assert int(row[1]) == roll


@when("a GM asks for every part of that table", target_fixture="parts")
def ask_for_every_part(table_id):
    return tables.parts(table_id)


@then("all three parts come back, none of them mistaken for the whole")
def three_parts_come_back(parts):
    assert len(parts) == 3
    with pytest.raises(LookupError):
        tables.load("1.4.2.3a")


@when(
    "a GM looks up the row for a monster with exactly 1 Hit Die",
    target_fixture="lookup",
)
def look_up_one_hit_die(table_id):
    try:
        return ("row", tables.ability_row(table_id, 1))
    except ValueError as e:
        return ("refused", e)


@then("the lookup does not silently hand back the sub-1-Hit-Die row")
def not_the_sub_hit_die_row(lookup):
    kind, result = lookup
    if kind == "row":
        assert result[0] != "1-1"
    else:
        assert isinstance(result, ValueError)


@when(
    parsers.parse(
        "a character with Wisdom {score:d} looks up their mental saving throw modifier"
    ),
    target_fixture="row",
)
def look_up_wisdom_modifier(table_id, score):
    return tables.ability_row(table_id, score)


@then(parsers.parse("the modifier is {modifier}"))
def modifier_is(row, modifier):
    assert row[1] == modifier
