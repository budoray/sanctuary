"""Character generation: abilities, ancestry, class, derived statistics.

Every random step rolls through `Dice`, so a character is fully reproducible
from (seed, choices). That is also what makes a reroll honest rather than a
slot machine.
"""
from dataclasses import dataclass, field
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


# Table 1.2.0A's universal floor/ceiling for any ability an ancestry's own
# `minimums`/`maximums` does not override (data/ancestries.yaml records only
# the ability/ancestry pairs where the book differs from this default).
_DEFAULT_ABILITY_MIN, _DEFAULT_ABILITY_MAX = 3, 18


def apply_ancestry(scores: dict, name: str) -> dict:
    """Ancestral adjustments applied to a copy of `scores`, then clamped to
    Table 1.2.0A's ceiling for each ability: "After making these
    modifications, your scores must fall within the required limitations of
    the Ancestry... Scores too high for the maximum may be lowered to fit"
    (osric.txt:1000-1003, repeated per-ancestry). An ability the ancestry
    lists no maximum for keeps the universal ceiling of 18 - that default is
    exactly what this used to skip enforcing, letting a rolled 18 plus a +1
    ancestral bonus (half-orc Strength, halfling Dexterity) sail past Table
    1.2.0A's own top row. The book only ever lowers a score that's too high;
    it never raises one that ends up too low, so there is no floor clamp
    here - a score that lands below the ancestry's minimum fails ancestry
    eligibility instead (see meets_ancestry_minimums)."""
    a = ancestry(name)
    out = dict(scores)
    for k, delta in a["ability_adjustments"].items():
        out[k] = out.get(k, 0) + delta
    for k in out:
        out[k] = min(out[k], a["maximums"].get(k, _DEFAULT_ABILITY_MAX))
    return out


def meets_ancestry_minimums(scores: dict, name: str) -> bool:
    """Table 1.2.0A minimums and maximums, checked AFTER ancestral
    adjustments. Every ability defaults to the universal 3-18 range unless
    the ancestry lists its own bound - the same defaults apply_ancestry
    clamps against, so the two agree on what "too high" means."""
    a = ancestry(name)
    for k in ABILITIES:
        v = scores.get(k, 0)
        if v < a["minimums"].get(k, _DEFAULT_ABILITY_MIN):
            return False
        if v > a["maximums"].get(k, _DEFAULT_ABILITY_MAX):
            return False
    return True


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


@dataclass(frozen=True)
class Character:
    """A complete first-level character, reproducible from
    (seed, mode, ancestry, classes). `log` is excluded from equality so two
    characters rolled with the same inputs compare equal regardless of any
    incidental logging differences.
    """
    name: str
    ancestry: str
    classes: tuple[str, ...]
    levels: dict
    scores: dict
    hit_points: int
    armour_class: int
    saves: dict
    modifiers: dict
    seed: int
    log: tuple = field(default=(), compare=False)


def is_legal_multiclass(ancestry_name: str, class_names) -> bool:
    """One class is always legal if the ancestry allows it. More than one must
    appear in that ancestry's own multiclass_combinations (OSRIC 3.0
    SS1.3.11) - humans have none (dual-classing, SS1.3.12, is a different
    mechanism entirely and not covered here)."""
    names = list(class_names)
    allowed = set(ancestry(ancestry_name)["allowed_classes"])
    if not set(names) <= allowed:
        return False
    if len(names) == 1:
        return True
    combos = [sorted(c) for c in ancestry(ancestry_name).get("multiclass_combinations", [])]
    return sorted(names) in combos


def _multiclass_saves(class_names, level: int = 1) -> dict:
    """SS1.3.11 "Attacks and Saving Throws": a multi-classed character may
    use whichever of their classes' tables is best in each category - so the
    saves are the best (lowest) target per category across all classes, not
    just the first-listed one."""
    all_saves = [saving_throws(c, level) for c in class_names]
    return {cat: min(s[cat] for s in all_saves) for cat in SAVE_CATEGORIES}


def _multiclass_hit_points(d: Dice, class_names, con_bonus: int) -> int:
    """SS1.3.11 "Gaining Hit Points": "you calculate your new hp by rolling
    the right dice for your class, applying your constitution modifier if
    any, and THEN DIVIDING BY THE NUMBER OF CLASSES YOU HAVE. Drop any
    fractions." The worked example (Erix Uncle, fighter/cleric/thief) rolls
    ONE class's die, adds Constitution, and divides THAT single roll by the
    class count - it never sums multiple classes' rolls before dividing.

    A first-level multi-classed character gains level 1 in every class at
    once, so this applies the book's arithmetic once per class and sums the
    (already-divided) contributions: contribution = floor((class's roll +
    con_bonus) / class_count), summed across classes.

    The general "always gain at least 1hp" rule (osric.txt:793) is applied
    per class contribution, not once to the total - each class's level-1 is
    its own gaining-a-level event, consistent with how roll_hit_points
    already floors the ranger's two 1st-level dice individually (Task 11).
    Consequence: a three-class character's minimum starting hp is 3, not 1.

    The ranger's extra 1st-level die (2d8, Constitution applied to both,
    per SS1.3.9) is rolled by roll_hit_points as a single number - it is
    still just ONE class's contribution to this formula, divided by the
    class count like any other class's roll.
    """
    n = len(class_names)
    total = 0
    for cls in class_names:
        class_roll = roll_hit_points(d, cls, 1, con_bonus)
        total += max(1, class_roll // n)
    return total


def generate(seed: int, mode: str, ancestry_name: str, class_names,
             name: str = "") -> Character:
    """Roll a complete first-level character. Fully reproducible from
    (seed, mode, ancestry, classes)."""
    class_names = tuple(class_names)
    if not is_legal_multiclass(ancestry_name, class_names):
        raise ValueError(
            f"{ancestry_name} may not be {'/'.join(class_names)}")

    d = Dice(seed=seed)
    scores = apply_ancestry(roll_abilities(d, mode), ancestry_name)

    # Table 1.2.0A's own title is "Required Ability Scores AFTER ANCESTRAL
    # BONUSES" - checked here, immediately after apply_ancestry, and before
    # exceptional Strength (which only ever raises an 18, never lowers a
    # score below a floor).
    if not meets_ancestry_minimums(scores, ancestry_name):
        raise ValueError(
            f"{ancestry_name} ability scores do not meet Table 1.2.0A after "
            f"ancestral bonuses: {scores}")

    # Exceptional Strength applies if ANY of the character's classes is
    # fighter/paladin/ranger (osric.txt:650-655), not only the first-listed
    # one. Rolled exactly once against the pre-resolution score - feeding
    # roll_exceptional_strength its own output would silently re-roll an
    # already-settled Strength.
    exceptional_cls = next(
        (c for c in class_names if c in EXCEPTIONAL_CLASSES), class_names[0])
    scores["strength"] = roll_exceptional_strength(d, scores["strength"], exceptional_cls)

    # Each class's own §1.3.N.1 "Minimum Scores", checked against the final
    # (post-exceptional-Strength) scores. is_legal_multiclass already
    # confirmed the ancestry allows every class in class_names, so a class
    # missing from eligible_classes here can only be a failed ability
    # minimum - eligible_classes is the same function tests/test_character.py
    # already exercises for this, wired onto the generation path for real.
    eligible = eligible_classes(scores, ancestry_name)
    for cls in class_names:
        if cls not in eligible:
            short = {
                ability: threshold
                for ability, threshold in game_class(cls)["minimums"].items()
                if scores.get(ability, 0) < threshold
            }
            raise ValueError(
                f"{ancestry_name} does not meet {cls}'s ability minimums: {short}")

    mods = ability_modifiers(scores)
    con_bonus = 0  # Constitution hp adjustment lands with Chapter 3.
    hit_points = _multiclass_hit_points(d, class_names, con_bonus)

    return Character(
        name=name,
        ancestry=ancestry_name,
        classes=class_names,
        levels={c: 1 for c in class_names},
        scores=scores,
        hit_points=hit_points,
        armour_class=10,  # armour lands with Chapter 3.
        saves=_multiclass_saves(class_names, 1),
        modifiers=mods,
        seed=seed,
        log=d.log,
    )
