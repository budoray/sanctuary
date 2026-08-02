"""The Chapter 2 spell catalogue: loading, spells-per-day, and memorisation.

May import sanctuary.tables and sanctuary.dice. Must NOT import
sanctuary.character - tests/test_invariants.py::test_dependency_chain_is_one_way
enforces the one-way dependency chain once spells is added to it.

No `random` here: spell slots and memorisation are deterministic table
lookups, nothing rolled.

Rangers and paladins are OUT OF SCOPE for this chapter. OSRIC gives them
limited spellcasting at higher level from other lists, and modelling that
correctly needs work this chapter didn't spec - `spells_per_day` raises
ValueError for anything but the four pure casters rather than guessing.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

from sanctuary import tables

_DIR = Path(__file__).resolve().parent.parent / "data" / "spells"

# class name -> (advancement table id, number of spell-slot columns)
_CASTER_TABLES = {
    "cleric": ("1.3.2.4a", 7),
    "druid": ("1.3.3.4a", 7),
    "illusionist": ("1.3.5.4a", 7),
    "magic-user": ("1.3.6.4a", 9),
}

# Only magic-user and illusionist need a spell scribed in a book before it
# can be memorised - clerics and druids pray and may memorise any spell of
# the right class/level from the catalogue.
_BOOK_REQUIRED = {"magic-user", "illusionist"}

_DASH_ONLY = re.compile(r"^[–—-]+$")


@lru_cache(maxsize=None)
def load_all() -> tuple[dict, ...]:
    """Every spell record in data/spells/, as loaded YAML dicts."""
    return tuple(
        yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in sorted(_DIR.glob("*.yaml"))
    )


def by_slug(slug: str) -> list[dict]:
    """Every class variant sharing a spell's slug (see the Chapter 2 report
    for why variants are never merged: their header stats genuinely
    differ per class)."""
    return [r for r in load_all() if r["slug"] == slug]


def get(slug: str, class_name: str) -> dict:
    for r in load_all():
        if r["slug"] == slug and r["class"] == class_name:
            return r
    raise KeyError(f"no spell {slug!r} for {class_name!r}")


def _logical_rows(table_id: str) -> list[list[str]]:
    """Whitespace-split rows from an advancement table, with a wrapped notes
    column (e.g. druid level 3's "Druid's Knowledge; Wilderness  Movement")
    folded back onto the row it belongs to. A line starting the row proper
    always opens with the character level as a plain integer; a
    continuation line (the wrapped tail of a notes column) never does -
    that's the only signal available, and it's sufficient here."""
    rows: list[list[str]] = []
    for line in tables.load(table_id)["lines"]:
        tokens = line.split()
        if tokens and tokens[0].isdigit():
            rows.append(tokens)
        elif rows:
            rows[-1].extend(tokens)
    return rows


def spells_per_day(class_name: str, level: int) -> list[int]:
    """Spell slots per spell-level (1..N) for a caster class at a character
    level, read from that class's own advancement table. The reliable
    invariant, regardless of what free-text notes a row injects between the
    hit-dice field and the slot columns (see IMPROVEMENTS.md's other
    table-quirk entries for the general shape of this problem): the LAST N
    whitespace-split fields of the row are always the spell-slot counts,
    where N is the number of spell levels that class's table prints."""
    if class_name not in _CASTER_TABLES:
        raise ValueError(
            f"{class_name!r} is not one of the four pure casters "
            f"({', '.join(_CASTER_TABLES)}); ranger/paladin spellcasting is "
            "out of scope for this chapter"
        )
    table_id, n = _CASTER_TABLES[class_name]
    for row in _logical_rows(table_id):
        if int(row[0]) == level:
            return [0 if _DASH_ONLY.match(t) else int(t) for t in row[-n:]]
    raise LookupError(f"no {class_name} advancement row for level {level}")


class Memorised:
    """A caster's currently-memorised spells, one list of slugs per spell
    level, sized to spells_per_day(class_name, level).

    - The same spell may be memorised into more than one slot.
    - forget() frees a slot for something else.
    - magic-user/illusionist may only memorise from their spell book
      (pass `spellbook`, an iterable of slugs); cleric/druid have no such
      restriction.
    - A reversible spell is one slot entry either way; casting chooses the
      orientation at cast time, so there is no separate "reversed" slot.
    """

    def __init__(self, class_name: str, level: int):
        self.class_name = class_name
        self.level = level
        self._capacity = spells_per_day(class_name, level)
        self.slots: dict[int, list[str]] = {
            i + 1: [] for i, cap in enumerate(self._capacity)
        }

    def memorise(self, spell_level: int, slug: str, spellbook=None) -> None:
        if self.class_name in _BOOK_REQUIRED:
            if spellbook is None or slug not in spellbook:
                raise ValueError(
                    f"{self.class_name} may only memorise spells in their "
                    f"spell book; {slug!r} is not in it"
                )
        capacity = self._capacity[spell_level - 1]
        if len(self.slots[spell_level]) >= capacity:
            raise ValueError(
                f"no free level-{spell_level} slot ({capacity} available, "
                f"all in use)"
            )
        self.slots[spell_level].append(slug)

    def forget(self, spell_level: int, slug: str) -> None:
        self.slots[spell_level].remove(slug)
