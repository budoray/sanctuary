"""Character generation: abilities, ancestry, class, derived statistics.

Every random step rolls through `Dice`, so a character is fully reproducible
from (seed, choices). That is also what makes a reroll honest rather than a
slot machine.
"""
from functools import lru_cache
from pathlib import Path

import yaml

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
