"""Treasure and loot classes (OSRIC 3.0 GM Guide, Chapters Twelve and Thirteen).

Loot classes (Hoard 1-9, Individual 1-5, Cache 1-12) live in
data/treasure/loot_classes.yaml - each line of a class is checked
independently on d100, so a hoard can come up entirely empty. Gemstone and
jewellery values come from the book's own Tables 2.12.4a and 2.12.5a (the
latter supplemented by data/treasure/jewellery_types.yaml - see that file's
`note` for why data/tables/2.12.5a is missing its second page).

May import sanctuary.tables and sanctuary.dice, per the dependency chain in
tests/test_invariants.py. Nothing here imports sanctuary.character, and
nothing here imports `random` - every die comes from the Dice instance
the caller passes in.
"""
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from sanctuary import tables
from sanctuary.dice import Dice

_DIR = Path(__file__).resolve().parent.parent / "data" / "treasure"

# Table 2.12.5a's fixed per-tier dice, in the order jewellery_types.yaml's
# `tiers` lists them. Every row in that table uses the same six dice - only
# which tiers a given item form can reach varies (a null in `tiers` means
# out of reach for that form).
TIER_DICE = (
    ("silver", "1d10", 100),
    ("silver_gold", "2d6", 100),
    ("gold", "3d6", 100),
    ("silver_gems", "5d6", 100),
    ("gold_gems", "2d4", 1000),
    ("exceptional", "2d6", 1000),
)


@lru_cache(maxsize=None)
def _loot_classes() -> dict:
    doc = yaml.safe_load((_DIR / "loot_classes.yaml").read_text(encoding="utf-8"))
    return doc["classes"]


@lru_cache(maxsize=None)
def _jewellery_rows() -> list[dict]:
    doc = yaml.safe_load((_DIR / "jewellery_types.yaml").read_text(encoding="utf-8"))
    return doc["rows"]


def loot_class_names() -> list[str]:
    """Every loot class id, e.g. 'hoard_1', 'individual_3', 'cache_12'."""
    return list(_loot_classes())


@dataclass(frozen=True)
class TreasureLine:
    """One line of a rolled hoard: a kind of treasure and how much of it.

    `amount` is coin count for cp/sp/ep/gp/pp, a piece count for gems/
    jewellery/map, and an item count for magic_item (the type of each magic
    item is resolved separately - a loot class only says how many and of
    what rough sort, per `spec`).
    """
    kind: str
    amount: int
    spec: str = ""


def _qty(dice: Dice, expr: str, multiplier: int, kind: str, class_name: str) -> int:
    """Roll `expr` (or take it as a literal count, for fixed magic-item
    counts like Hoard 1's "3 magic items") and apply the line's multiplier."""
    if "d" in expr:
        total = dice.roll(expr, reason=f"{class_name} {kind} amount", kind=kind).total
    else:
        total = int(expr)
    return total * multiplier


def roll_hoard(dice: Dice, class_name: str) -> list[TreasureLine]:
    """Roll one loot class. Each line is checked independently on d100 (skipped
    for an `always` class, i.e. Individual 1-5, which has no chance to fail);
    the hoard can come back empty if every line's roll misses.
    """
    cls = _loot_classes().get(class_name)
    if cls is None:
        raise KeyError(f"no loot class {class_name!r}")
    always = bool(cls.get("always"))
    out: list[TreasureLine] = []
    for line in cls["lines"]:
        if not always:
            check = dice.roll(
                "1d100", reason=f"{class_name} {line['kind']} chance", kind=line["kind"]
            ).total
            if check > line["percent"]:
                continue
        amount = _qty(dice, line["qty"], line["multiplier"], line["kind"], class_name)
        out.append(TreasureLine(kind=line["kind"], amount=amount, spec=line.get("spec", "")))
    return out


# Table 2.12.4a: GEMSTONE VALUE. tables.rows() yields one row per d100
# bucket (the wrapped description word on some rows, e.g. "Stone" trailing
# onto its own line, doesn't start with a digit and is dropped by rows() -
# harmless here, the category label below is transcribed straight from the
# book rather than reassembled from the truncated row).
_GEM_CATEGORIES = (
    "Ornamental Stone",
    "Semi-Precious Stone",
    "Fancy Stone",
    "Precious Stone",
    "Gem",
    "Jewel",
)


def _d100_spec(spec: str) -> str:
    """Rewrite a d100 row label's own "00" (meaning 100, a physical d100
    reading all zeroes) to a literal "100" - both the bare "00" form (Table
    2.12.4a's last row) and the "X-00" range form (Table 2.13.1n's "96-00",
    etc.). tables.in_range has no way to read a range that wraps through 00
    (see data/treasure/jewellery_types.yaml's note, which hits the same
    thing), so every d100 table lookup in this module normalises here first
    rather than re-solving it per table."""
    s = spec.strip()
    if s.endswith("00") and s != "100":
        return s[:-2] + "100"
    return s


def _d100_row(rows: list[list[str]], roll_total: int) -> list[str]:
    """The row of a d100 table covering `roll_total` (1-100)."""
    for row in rows:
        if row and tables.in_range(_d100_spec(row[0]), roll_total):
            return row
    raise LookupError(f"no row covers d100 roll {roll_total}")


def gem_value(dice: Dice) -> tuple[int, str]:
    """Roll Table 2.12.4a: (value in gp, category label)."""
    roll = dice.roll("1d100", reason="gem value bucket", kind="gem").total
    rows = tables.rows("2.12.4a")
    row = _d100_row(rows, roll)
    idx = rows.index(row)
    expr = row[1]
    if "×" in expr:
        dice_expr, mult = expr.split("×", 1)
        multiplier = int(mult.replace(",", ""))
    else:
        dice_expr, multiplier = expr, 1
    value = dice.roll(dice_expr, reason="gem value", kind="gem").total * multiplier
    return value, _GEM_CATEGORIES[idx]


def _tier_index_for(dice: Dice, tiers: list[str | None]) -> int:
    """Roll d10 for jewellery composition, and find which tier of `tiers`
    (a form's six d10 breakpoints, some possibly out of reach) covers it."""
    roll = dice.roll("1d10", reason="jewellery composition").total
    for i, spec in enumerate(tiers):
        if spec is None:
            continue
        if tables.in_range(spec, roll):
            return i
    # Every row's reachable tiers cover the full 1-10 range between them (no
    # gaps in the source), so this is unreached in practice; fail loudly
    # rather than silently picking a tier if a future row violates that.
    raise LookupError(f"no jewellery tier covers d10 roll {roll} in {tiers}")


def jewellery(dice: Dice) -> tuple[int, str, str]:
    """Roll Table 2.12.5a: (value in gp, item form, composition tier)."""
    roll = dice.roll("1d100", reason="jewellery form", kind="jewellery").total
    row = _d100_row(
        [[r["range"], r["item"]] for r in _jewellery_rows()], roll
    )
    idx = next(i for i, r in enumerate(_jewellery_rows()) if r["range"] == row[0])
    entry = _jewellery_rows()[idx]
    tier_i = _tier_index_for(dice, entry["tiers"])
    tier_name, tier_dice, tier_mult = TIER_DICE[tier_i]
    value = dice.roll(tier_dice, reason="jewellery value", kind="jewellery").total * tier_mult
    return value, entry["item"], tier_name


# ---------------------------------------------------------------------------
# Magic items (Chapter Thirteen): type -> subtype -> specific item.
#
# Table 2.13.1a's own printed cross-references are OCR-mangled ("Table
# 2.13.P" instead of 2.13.1p, "Table 2.13.D" instead of 2.13.1d, "Table
# 2.13.G" instead of 2.13.1g - see data/tables/2.13.1a_determining_type_of_
# magic_item.yaml) - not parseable, so the d20 -> category mapping below is
# hardcoded from the table's own d20 ranges instead, which print cleanly.
#
# Fully wired to a specific item here: miscellaneous magic (2.13.1p rarity
# tier -> 1q/1r/1s/1t), special swords (2.13.1n) and special miscellaneous
# weapons (2.13.1o), and ioun stones (2.13.1u) - all flat d100 tables with
# one name and one value per row. Potions (2.13.1f), rings (2.13.1g),
# rods/staves/wands (2.13.1h), scroll subtype (2.13.1i/1j/1k), and the sword/
# armour "+N or special" property tables (2.13.1c/1m) each wrap a single row
# across several raw lines AND embed their own nested "Roll 1d100: (a-b): X;
# (c-d): Y" sub-roll in the cell text - tables.rows() does not reassemble
# those (it tokenizes per raw line, so a wrapped row loses its continuation
# and a value line can be mistaken for a fresh row). Resolving those needs a
# raw-line row-grouper this chapter doesn't yet have; roll_magic_item_type
# still names the category so a caller knows what to roll for by hand.
MAGIC_ITEM_TYPES = (
    (1, 3, "armour_or_shield"),
    (4, 6, "miscellaneous_magic"),
    (7, 9, "miscellaneous_weapon"),
    (10, 13, "potion"),
    (14, 14, "ring"),
    (15, 15, "rod_staff_wand"),
    (16, 18, "scroll"),
    (19, 20, "sword"),
)

# Table 2.13.1p: MISCELLANEOUS MAGIC ITEMS - RARITY.
_RARITY_TABLES = {(1, 50): "2.13.1q", (51, 70): "2.13.1r", (71, 90): "2.13.1s", (91, 99): "2.13.1t"}


@dataclass(frozen=True)
class MagicItem:
    """A specific magic item reached at the end of a determination chain.
    `table_id` + `name` is enough for a caller to look up
    data/items/<slug(name)>.yaml for its verbatim description."""
    name: str
    table_id: str
    value_gp: str  # as printed - "22,000", "see entry", "n/a", ...


def roll_magic_item_type(dice: Dice) -> str:
    """Table 2.13.1a: which family of magic item this is."""
    roll = dice.roll("1d20", reason="magic item type").total
    for lo, hi, category in MAGIC_ITEM_TYPES:
        if lo <= roll <= hi:
            return category
    raise LookupError(f"no Table 2.13.1a category covers d20 roll {roll}")


def _name_and_value(fields: list[str]) -> tuple[str, str]:
    """Split a flat item-table row's fields (after the leading range) into
    (name, value) - value is normally the trailing "22,000"/"n/a" token, but
    a handful of rows spell it "see entry" (two tokens)."""
    if len(fields) >= 2 and fields[-2:] == ["see", "entry"]:
        return " ".join(fields[:-2]), "see entry"
    return " ".join(fields[:-1]), fields[-1]


@lru_cache(maxsize=None)
def _overflow_rows() -> dict:
    doc = yaml.safe_load((_DIR / "misc_magic_items_overflow.yaml").read_text(encoding="utf-8"))
    return doc["rows"]


def _rows(table_id: str) -> list[list[str]]:
    """tables.rows(table_id), plus this chapter's own overflow rows for a
    table the shared extractor truncated at a page break (see
    misc_magic_items_overflow.yaml's note) - concatenated so every caller
    here sees one continuous table regardless of which file a row lives in.

    A handful of rows in the shared extraction (e.g. 2.13.1s's "Bag of
    Tricks" at range 06, three names and three values on six separate
    lines) print a name on a line that doesn't start with a digit, which
    tables.rows()'s per-line filter drops - leaving a bare range with no
    name at all. Those single-field rows are filtered out here; the
    overflow file supplies a usable (if simplified) replacement for each
    range this actually affects.
    """
    rows = [r for r in tables.rows(table_id) if len(r) >= 2]
    for entry in _overflow_rows().get(table_id, []):
        rows.append([entry["range"], *entry["name"].split(), entry["value"]])
    return rows


def _flat_item(dice: Dice, table_id: str, expr: str = "1d100", reason: str = "magic item") -> MagicItem:
    """Roll `expr` against a flat "range, name..., value" table (2.13.1n,
    1o, 1q, 1r, 1s, 1t, 1u all have this shape)."""
    roll = dice.roll(expr, reason=reason, kind=table_id).total
    row = _d100_row(_rows(table_id), roll)
    name, value = _name_and_value(row[1:])
    return MagicItem(name=name, table_id=table_id, value_gp=value)


def roll_special_sword(dice: Dice) -> MagicItem:
    """Table 2.13.1n: SPECIAL MAGIC SWORDS."""
    return _flat_item(dice, "2.13.1n", reason="special sword")


def roll_special_weapon(dice: Dice) -> MagicItem:
    """Table 2.13.1o: SPECIAL MAGIC MISCELLANEOUS WEAPONS."""
    return _flat_item(dice, "2.13.1o", reason="special miscellaneous weapon")


def roll_ioun_stone(dice: Dice) -> MagicItem:
    """Table 2.13.1u: IOUN STONES SUBTABLE. Re-rolls on the table's own
    "re-roll, ignoring results over 96" instruction (rows 97-00)."""
    while True:
        item = _flat_item(dice, "2.13.1u", reason="ioun stone")
        if not item.name.lower().startswith("re-roll"):
            return item


def roll_miscellaneous_magic_item(dice: Dice) -> MagicItem:
    """Table 2.13.1p (rarity) -> 2.13.1q/1r/1s/1t (specific item). A "00"
    result is "Roll Twice, Ignoring This Result" - resolved by rolling
    again rather than returning a pair, since every caller here wants one
    item per call."""
    while True:
        tier_roll = dice.roll("1d100", reason="miscellaneous magic item rarity").total
        if tier_roll == 100:
            continue  # "00": roll twice, ignoring this result
        table_id = next(t for (lo, hi), t in _RARITY_TABLES.items() if lo <= tier_roll <= hi)
        return _flat_item(dice, table_id, reason="miscellaneous magic item")
