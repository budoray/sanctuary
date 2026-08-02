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


def _d100_row(rows: list[list[str]], roll_total: int) -> list[str]:
    """The row of a d100 table covering `roll_total` (1-100), including the
    table's own "00" label for 100 - the last row on a d100 table is always
    the highest-value bucket, printed as "00" for the case a physical d100
    reads all zeroes."""
    for row in rows:
        if row and row[0].strip() == "00":
            if roll_total == 100:
                return row
            continue
        if row and tables.in_range(row[0], roll_total):
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
