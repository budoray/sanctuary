"""Character generation: abilities, ancestry, class, derived statistics.

Every random step rolls through `Dice`, so a character is fully reproducible
from (seed, choices). That is also what makes a reroll honest rather than a
slot machine.
"""
from functools import lru_cache
from pathlib import Path

import yaml

from sanctuary import tables
from sanctuary.dice import Dice

ABILITIES = ("strength", "dexterity", "constitution",
             "intelligence", "wisdom", "charisma")

# OSRIC 3.0 names four generation modes. This is a player-facing choice,
# not a configuration value.
GEN_MODES = ("hardest", "difficult", "normal", "flexible")

_MODE_EXPR = {
    "hardest": "3d6",     # 3d6 in order
    "difficult": "3d6",   # 3d6, arrange to taste
    "normal": "4d6d1",    # 4d6 drop lowest, in order
    "flexible": "4d6d1",  # 4d6 drop lowest, arrange
}
_ARRANGEABLE = {"difficult", "flexible"}


def arrangeable(mode: str) -> bool:
    """May the player rearrange the rolled scores across abilities?"""
    return mode in _ARRANGEABLE


def roll_abilities(d: Dice, mode: str) -> dict[str, int]:
    """Roll the six ability scores. Arrange modes return them in roll order;
    rearranging is the player's move, made later against this result."""
    if mode not in GEN_MODES:
        raise ValueError(f"unknown generation mode: {mode!r}")
    expr = _MODE_EXPR[mode]
    return {name: d.roll(expr, reason=name).total for name in ABILITIES}


# Only these classes roll percentile strength. For everyone else an 18 is an 18.
EXCEPTIONAL_CLASSES = ("fighter", "paladin", "ranger")


def roll_exceptional_strength(d: Dice, score: int, cls: str) -> float:
    """Percentile strength for an eligible 18.

    Returns 18.01-18.99 as a decimal, or 19.0 on a percentile roll of 00 (100).
    Returns `score` unchanged when the character is not eligible - and rolls no
    dice at all in that case, so the log stays honest.
    """
    if score != 18 or cls not in EXCEPTIONAL_CLASSES:
        return score
    pct = d.roll("1d100", reason="exceptional strength", kind="chargen").total
    if pct >= 100:
        return 19.0
    return round(18 + pct / 100, 2)


_DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _ancestries() -> dict:
    return yaml.safe_load((_DATA / "ancestries.yaml").read_text(encoding="utf-8"))


ANCESTRIES = ("dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human")


def ancestry(name: str) -> dict:
    """OSRIC 3.0 §1.2.1-1.2.7: one ancestry's adjustments, limits and class access."""
    a = _ancestries().get(name)
    if a is None:
        raise KeyError(f"unknown ancestry: {name!r}")
    return a


def apply_ancestry(scores: dict, name: str) -> dict:
    """Ancestral adjustments applied to a copy of `scores`."""
    out = dict(scores)
    for k, delta in ancestry(name)["ability_adjustments"].items():
        out[k] = out.get(k, 0) + delta
    return out


def meets_ancestry_minimums(scores: dict, name: str) -> bool:
    """Table 1.2.0A minimums, checked AFTER ancestral adjustments."""
    a = ancestry(name)
    if any(scores.get(k, 0) < v for k, v in a["minimums"].items()):
        return False
    return not any(scores.get(k, 0) > v for k, v in a["maximums"].items())


@lru_cache(maxsize=1)
def _classes() -> dict:
    return yaml.safe_load((_DATA / "classes.yaml").read_text(encoding="utf-8"))


CLASSES = ("assassin", "cleric", "druid", "fighter", "illusionist",
           "magic-user", "monk", "paladin", "ranger", "thief")


def game_class(name: str) -> dict:
    """OSRIC 3.0 §1.3.1-1.3.10: one class's requirements, hit die and tables."""
    c = _classes().get(name)
    if c is None:
        raise KeyError(f"unknown class: {name!r}")
    return c


def eligible_classes(scores: dict, ancestry_name: str) -> list[str]:
    """Classes this character may take: allowed by ancestry AND meeting the
    class's own ability minimums."""
    allowed = set(ancestry(ancestry_name)["allowed_classes"])
    out = []
    for name in CLASSES:
        if name not in allowed:
            continue
        if any(scores.get(k, 0) < v for k, v in game_class(name)["minimums"].items()):
            continue
        out.append(name)
    return out


def roll_hit_points(d: Dice, cls: str, level: int, con_bonus: int) -> int:
    """Hit points for `level` levels of `cls`.

    Past the level where hit dice stop (per class - see data/classes.yaml),
    the class gains flat hit points instead of rolling, and Constitution
    adjustments no longer apply - every class's own table footnote says so
    explicitly.

    A ranger rolls TWO hit dice at 1st level, per `hit_dice_at_first_level`
    (osric.txt:3654-3657: "Your starting hit points are 2d8, and if you have
    a constitution bonus to your hit points, then this applies to both of
    your hit dice"). The floor of "always gain at least 1hp" (osric.txt:793)
    is applied per hit die, not per level - each die is its own roll-plus-
    Constitution event in the book's own wording, so a ranger's 1st level
    floors at 2hp (one per die), not 1.
    """
    c = game_class(cls)
    die = c["hit_die"]
    stop = c["hit_dice_stop_level"]
    total = 0
    for lvl in range(1, int(level) + 1):
        if lvl <= stop:
            dice_this_level = c["hit_dice_at_first_level"] if lvl == 1 else 1
            for _ in range(dice_this_level):
                rolled = d.roll(f"1{die}", reason=f"{cls} hp level {lvl}", kind="chargen").total
                total += max(1, rolled + con_bonus)
        else:
            total += c["fixed_hp_per_level_after"]
    return total


# Column order of every class saving-throw table (verified against
# 1.3.4.4b FIGHTER SAVING THROWS and cross-checked against 1.3.6.4b
# MAGIC-USER, 1.3.7.4c MONK and 1.3.10.4e THIEF): aimed magic items, breath
# weapons, death/paralysis/poison, petrifaction/polymorph, spells.
SAVE_CATEGORIES = ("aimed_magic_items", "breath_weapons",
                   "death_paralysis_poison", "petrifaction_polymorph", "spells")

# A to-hit table's columns are armour classes descending from 10 to -10.
_AC_COLUMNS = list(range(10, -11, -1))


def _int(cell: str) -> int:
    return int(str(cell).replace("+", "").replace("−", "-"))


def ability_modifiers(scores: dict) -> dict:
    """Combat-relevant modifiers derived from Table 1.1.2A (Strength).

    Strength-only for now - Dexterity (AC/missile) and Constitution (hp)
    modifiers arrive in a later chapter.
    """
    strength_row = tables.ability_row("1.1.2a", scores["strength"])
    return {
        "hit": _int(strength_row[1]),
        "damage": _int(strength_row[2]),
        "encumbrance_lbs": _int(strength_row[3]),
    }


def saving_throws(cls: str, level: int) -> dict:
    """The five saving-throw targets for a class at a level."""
    table_id = game_class(cls)["saving_throw_table"]
    for row in tables.rows(table_id):
        if tables.in_range(row[0], level) and len(row) >= 6:
            return dict(zip(SAVE_CATEGORIES, (_int(c) for c in row[1:6])))
    raise LookupError(f"no saving-throw row for {cls} level {level}")


def to_hit_target(cls: str, level: int, armour_class: int) -> int:
    """The d20 result needed to hit `armour_class`.

    A natural 1 is NOT an automatic miss and a natural 20 is NOT an automatic
    hit - that is OSRIC's stated rule, not a bug. This computes the target
    only; rolling and comparing against it belongs to whoever resolves an
    attack.
    """
    table_id = game_class(cls)["to_hit_table"]
    col = _AC_COLUMNS.index(int(armour_class))
    for row in tables.rows(table_id):
        if tables.in_range(row[0], level):
            return _int(row[1 + col])
    raise LookupError(f"no to-hit row for {cls} level {level}")
