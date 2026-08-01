import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.extract import find_tables, normalise, slug

SAMPLE = """
 TABLE 1.1.2A: STRENGTH
STRENGTH TO HIT  DAMAGE
3 -3 -1 0 1 0
4-5 -2 -1 10 1 0
Notes:
- To-hit modifiers apply to your roll.

 TABLE 1.2.0A: REQUIRED ABILITY SCORES
CLASS STR
Fighter 9
"""


def test_normalise_expands_ligatures():
    assert normalise("eﬀect") == "effect"
    assert normalise("suﬃcient") == "sufficient"
    assert normalise("ﬁrst") == "first"


def test_normalise_leaves_en_dashes_alone():
    # En-dashes are meaningful in ranges (4-5, 18.01-18.50); do not mangle them.
    assert "–" in normalise("4–5")


def test_slug():
    assert slug("REQUIRED ABILITY SCORES") == "required_ability_scores"
    assert slug("Fighter To-Hit Table") == "fighter_to_hit_table"


def test_find_tables_splits_on_headers():
    tables = find_tables(SAMPLE)
    assert [t["id"] for t in tables] == ["1.1.2a", "1.2.0a"]
    assert tables[0]["name"] == "STRENGTH"
    assert tables[1]["name"] == "REQUIRED ABILITY SCORES"


def test_find_tables_keeps_data_rows_verbatim():
    first = find_tables(SAMPLE)[0]
    assert "3 -3 -1 0 1 0" in first["lines"]
    assert "4-5 -2 -1 10 1 0" in first["lines"]


def test_find_tables_stops_a_block_at_prose():
    first = find_tables(SAMPLE)[0]
    assert not any("To-hit modifiers apply" in ln for ln in first["lines"])


def test_find_tables_stops_a_block_at_page_marker():
    text = """
 TABLE 1.1.2A: STRENGTH
3 -3 -1 0 1 0
=== PAGE 2 ===
4-5 -2 -1 10 1 0
"""
    first = find_tables(text)[0]
    assert first["lines"] == ["3 -3 -1 0 1 0"]


def test_find_tables_drops_page_furniture_but_keeps_surrounding_rows():
    text = """
 TABLE 1.1.2A: STRENGTH
3 -3 -1 0 1 0
44 | OSRIC 3.0 - PART ONE: CREATING A CHARACTER
 CHAPTER THREE: CHARACTER CLASS  | 43
4-5 -2 -1 10 1 0
"""
    first = find_tables(text)[0]
    assert first["lines"] == ["3 -3 -1 0 1 0", "4-5 -2 -1 10 1 0"]


def test_normalise_folds_nbsp_to_plain_space():
    assert normalise("4 5") == "4 5"
