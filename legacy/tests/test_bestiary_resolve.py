"""Measures `bestiary.resolve_name` against the GM Guide's own D100 monster
tables (2.7.3.2a-j) - the tables `procgen._roll_monster`/the wandering-table
walk actually draw encounters from (see `sanctuary/procgen.py`'s
`_MONSTER_LEVEL_LETTERS` loop). This is the fix for the reported defect:
"generated encounters cannot be fought" because the printed name and the
bestiary's slug don't match.

The resolution rate is asserted with a floor, not pinned exactly, so a
`data/monsters/` split or a resolver improvement that raises it doesn't fail
the gate - but a REGRESSION (a change that silently makes fewer names
resolve) does. See `tests/test_bestiary.py::test_the_full_corpus_is_302_monsters`
for the corpus-side half of this fix.
"""
import re

import pytest

from sanctuary import bestiary, tables

_DASH = re.compile(r"[–—-]")
_TABLE_IDS = tuple(f"2.7.3.2{letter}" for letter in "abcdefghij")


def _is_d100_spec(cell: str) -> bool:
    """True for a genuine d100 range/value cell ("05-07", "31-40", "00"),
    false for a wrap-continuation row's leaked non-range first field - the
    same distinction `procgen._d100_match` draws for a rolled value."""
    parts = [p for p in _DASH.split(cell.strip()) if p]
    return bool(parts) and all(p.isdigit() or p in ("00", "0") for p in parts)


def every_encounter_table_name() -> set[str]:
    """Every distinct monster name printed across all ten monster-level D100
    tables, extracted the same way `procgen._roll_monster` reads a row
    (`row[1:-2]` - the cells between the d100 range and the trailing
    encountered/lair-count dice - joined and stripped of a trailing comma)."""
    names = set()
    for table_id in _TABLE_IDS:
        for row in tables.rows(table_id):
            if len(row) < 4 or not _is_d100_spec(row[0]):
                continue
            names.add(" ".join(row[1:-2]).rstrip(","))
    return names


# Locked-in floor: 122/186 names resolve today (65.6%), up from 70/183 (38.3%
# - the exact count of names varies a few percent across environments with
# the raw table extraction, hence a floor rather than a pinned count) with
# plain exact-slug lookup, and effectively 0 in practice pre-fix (the
# reported bug - nearly every encounter hit an unresolvable name because a
# handful of high-frequency table entries, like "Wolf, Dire", covered a huge
# share of the d100 rolls and every one of them failed to slug-match).
_MIN_RESOLUTION_RATE = 0.60


def test_most_encounter_table_names_resolve_to_a_bestiary_monster():
    names = every_encounter_table_name()
    assert len(names) > 150, "sanity check: table extraction found too few names"

    resolved = {n: bestiary.resolve_name(n) for n in names}
    hits = [n for n, m in resolved.items() if m is not None]
    misses = sorted(n for n, m in resolved.items() if m is None)
    rate = len(hits) / len(names)

    print(f"\nresolve_name: {len(hits)}/{len(names)} ({rate:.1%}) of encounter-table "
          f"names resolve to a bestiary monster")
    if misses:
        print(f"unresolved ({len(misses)}): {misses}")

    assert rate >= _MIN_RESOLUTION_RATE, (
        f"resolution rate regressed to {rate:.1%} ({len(hits)}/{len(names)}), "
        f"below the {_MIN_RESOLUTION_RATE:.0%} floor. Unresolved: {misses}")


@pytest.mark.parametrize("printed_name,expected_slug", [
    ("Frog, Giant", "frog_giant"),               # already slug-order; no change needed
    ("Spectral Troll", "troll_spectral"),          # bare word-order reversal
    ("Wolf, Dire", "wolf_dire"),                   # was a collapsed, mislabeled file
    ("Lycanthrope, Werebear", "lycanthrope_werebear"),   # was a collapsed file
    ("Lycanthrope, Werewolf", "lycanthrope_werewolf"),
    ("Elemental, Fire", "elemental_fire"),         # was a collapsed file
    ("Naga, Guardian", "naga_guardian"),           # was a collapsed file
    ("Zombie", "zombie"),                          # was a collapsed file
    ("Devil, Assagim", "assagim_nipheribu_nuperibbo"),  # category dropped; proper noun kept
    ("Mobat", "bat_mobat"),                        # single word inside another heading's name
    ("Bugbear 1d6", "bugbear"),                    # trailing dice-quantity suffix stripped
])
def test_resolve_name_handles_the_documented_cases(printed_name, expected_slug):
    m = bestiary.resolve_name(printed_name)
    assert m is not None, f"{printed_name!r} did not resolve"
    assert bestiary._slug(m["name"]) == expected_slug


def test_resolve_name_refuses_to_guess_a_genuinely_absent_monster():
    # OSRIC 3.0's corpus has no "Barghest" or "Roper" entry at all - verified
    # against the raw source, not an extraction gap (unlike "Wolf, Dire",
    # which turned out to be real but mislabeled - see wolf_dire.yaml).
    # Resolving one of these anyway would be exactly the wrong-monster-is-
    # worse-than-honest-arbitration failure this function exists to avoid.
    assert bestiary.resolve_name("Barghest") is None
    assert bestiary.resolve_name("Roper") is None


def test_resolve_name_never_resolves_a_bare_stopword():
    # "Giant" alone matches dozens of corpus files ("frog_giant",
    # "troll_giant", "giant_hill", ...) - picking one would be a guess.
    assert bestiary.resolve_name("Giant") is None
