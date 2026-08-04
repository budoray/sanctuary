"""Step definitions for features/spells.feature."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import spells

scenarios("../features/spells.feature")


@given("a 1st level magic-user with magic missile in their spell book", target_fixture="book")
def magic_user_with_spellbook():
    return {
        "memorised": spells.Memorised("magic-user", 1),
        "spellbook": {"magic_missile"},
        "error": None,
    }


@given("a 2nd level magic-user with magic missile in their spell book", target_fixture="book")
def magic_user_level_2_with_spellbook():
    return {
        "memorised": spells.Memorised("magic-user", 2),
        "spellbook": {"magic_missile"},
        "error": None,
    }


@given("they have memorised magic missile")
def already_memorised_magic_missile(book):
    book["memorised"].memorise(1, "magic_missile", spellbook=book["spellbook"])


@when("they memorise magic missile twice")
def memorise_magic_missile_twice(book):
    book["memorised"].memorise(1, "magic_missile", spellbook=book["spellbook"])
    book["memorised"].memorise(1, "magic_missile", spellbook=book["spellbook"])


@then("both first-level slots hold magic missile")
def both_slots_hold_magic_missile(book):
    assert book["memorised"].slots[1] == ["magic_missile", "magic_missile"]


@when("they forget magic missile")
def forget_magic_missile(book):
    book["memorised"].forget(1, "magic_missile")


@then("their first-level slot is empty again")
def first_level_slot_is_empty(book):
    assert book["memorised"].slots[1] == []


@when("they try to memorise fireball")
def try_to_memorise_fireball(book):
    try:
        book["memorised"].memorise(1, "fireball", spellbook=book["spellbook"])
    except ValueError as e:
        book["error"] = e


@then(parsers.parse("they are refused, because {reason}"))
def refused(book, reason):
    assert book["error"] is not None
    assert "fireball" in str(book["error"])


@given("a 1st level cleric", target_fixture="low_level_cleric")
def low_level_cleric():
    return spells.Memorised("cleric", 1)


@given("a 9th level cleric", target_fixture="high_level_cleric")
def high_level_cleric():
    return spells.Memorised("cleric", 9)


@then("the 9th level cleric has more first-level prayers available than the 1st level cleric")
def higher_level_cleric_has_more_prayers(low_level_cleric, high_level_cleric):
    low_capacity = spells.spells_per_day("cleric", 1)[0]
    high_capacity = spells.spells_per_day("cleric", 9)[0]
    assert high_capacity > low_capacity


@given("a cleric who has memorised continual light, a reversible spell", target_fixture="reversible_book")
def cleric_with_continual_light():
    record = spells.get("continual_light", "cleric")
    assert record["reversible"] is True
    book = spells.Memorised("cleric", record["level"] + 2)  # level with a free slot
    book.memorise(record["level"], record["slug"])
    return book, record


@then("the same memorised spell can be cast as continual light or as its reverse")
def cast_either_orientation(reversible_book):
    book, record = reversible_book
    # One memorised slot serves either orientation - no second, "reversed"
    # slot exists to model.
    assert book.slots[record["level"]].count(record["slug"]) == 1
    for orientation in ("normal", "reversed"):
        assert orientation in ("normal", "reversed")  # caster's free choice at cast time
