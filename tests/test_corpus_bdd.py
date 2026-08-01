"""Step definitions for features/corpus.feature."""
from pathlib import Path

from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import tables

scenarios("../features/corpus.feature")

_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"

# Pinned by tests/test_corpus.py::test_abandoned_tables_are_the_reviewed_set -
# ids the extractor set aside as duplicate captions with no data row of their
# own. Each still has a surviving committed table under the same id, from the
# sibling block that did have data.
_ABANDONED = {"1.3.7.4b", "1.6.12c", "2.12.5a", "2.2.2b", "2.8.1b", "2.9.1a"}


@given("the full corpus of extracted tables", target_fixture="corpus_ids")
def full_corpus():
    return set(tables._index())


@then(parsers.parse("{count:d} tables can be found by id"))
def n_tables_findable(corpus_ids, count):
    assert len(corpus_ids) == count


@given(
    parsers.parse("the table {table_id}, which the book printed across {parts:d} pages"),
    target_fixture="table_id",
)
def a_split_table(table_id):
    return table_id


@when("a reader asks for every part of it", target_fixture="found_parts")
def ask_for_every_part(table_id):
    return tables.parts(table_id)


@then(parsers.parse("all {parts:d} parts come back complete"))
def all_parts_come_back(found_parts, parts):
    assert len(found_parts) == parts
    assert all(p["lines"] for p in found_parts)


@given("the fighter to-hit table", target_fixture="table_id")
def fighter_table():
    return "1.3.4.4c"


@when("a reader opens it twice", target_fixture="two_readings")
def open_it_twice(table_id):
    return tables.load(table_id), tables.load(table_id)


@then("both readings match exactly, word for word")
def readings_match(two_readings):
    first, second = two_readings
    assert first == second


@then("none of them contain a typographic ligature character")
def no_ligatures(corpus_ids):
    ligatures = [chr(c) for c in range(0xFB00, 0xFB07)]
    for path in _DIR.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        assert not any(lig in text for lig in ligatures), path.name


@given("the tables the extractor set aside as unusable", target_fixture="unusable")
def unusable_tables():
    return _ABANDONED


@then("every one of them still has a surviving entry in the corpus")
def still_in_corpus(unusable):
    committed_ids = {p.name.split("_", 1)[0] for p in _DIR.glob("*.yaml")}
    assert unusable <= committed_ids
