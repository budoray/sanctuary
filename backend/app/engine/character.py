"""Character generation: abilities, ancestry, class, derived statistics.

Every random step rolls through `Dice`, so a character is fully reproducible
from (seed, choices). That is also what makes a reroll honest rather than a
slot machine.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.engine import tables
from backend.app.engine.dice import Dice
from backend.app.rulesets.base import Ruleset
from backend.app.rulesets.loader import load_ruleset

# Default ruleset for backward-compatible module-level constants and for any
# function called without an explicit ruleset argument.
_DEFAULT_RULESET = load_ruleset("osric")

ABILITIES = _DEFAULT_RULESET.ABILITIES
GEN_MODES = _DEFAULT_RULESET.GEN_MODES
ANCESTRIES = _DEFAULT_RULESET.ANCESTRIES
CLASSES = _DEFAULT_RULESET.CLASSES
EXCEPTIONAL_CLASSES = _DEFAULT_RULESET.EXCEPTIONAL_CLASSES

# OSRIC 3.0 names four generation modes. This is a player-facing choice,
# not a configuration value.
_MODE_EXPR = {
    "hardest": "3d6",     # 3d6 in order
    "difficult": "3d6",   # 3d6, arrange to taste
    "normal": "4d6d1",    # 4d6 drop lowest, in order
    "flexible": "4d6d1",  # 4d6 drop lowest, arrange
}
_ARRANGEABLE = {"difficult", "flexible"}


# Caches for ruleset content keyed by ruleset id, since Ruleset instances are
# not hashable (they carry dictionaries).
_ANCESTRIES_CACHE: dict[str, dict] = {}
_CLASSES_CACHE: dict[str, dict] = {}


def _ruleset(ruleset: Ruleset | None) -> Ruleset:
    return ruleset or _DEFAULT_RULESET


def _tables_dir(ruleset: Ruleset | None) -> Path | None:
    return _ruleset(ruleset).content_path("tables")


def arrangeable(mode: str) -> bool:
    """May the player rearrange the rolled scores across abilities?"""
    return mode in _ARRANGEABLE


def roll_abilities(d: Dice, mode: str, ruleset: Ruleset | None = None) -> dict[str, int]:
    """Roll the six ability scores. Arrange modes return them in roll order;
    rearranging is the player's move, made later against this result."""
    rs = _ruleset(ruleset)
    modes = tuple(m["value"] for m in rs.gen_modes)
    if mode not in modes:
        raise ValueError(f"unknown generation mode: {mode!r}")
    expr = _MODE_EXPR[mode]
    return {name: d.roll(expr, reason=name).total for name in rs.abilities}


def apply_arrangement(rolled: dict, arrangement: dict | None, mode: str,
                      ruleset: Ruleset | None = None) -> dict:
    """The player's chosen assignment of the six already-rolled values to the
    six abilities - `difficult` and `flexible` exist precisely so a player
    can do this. No dice are rolled here; this only reorders what
    `roll_abilities` already produced, which is what keeps a seeded replay
    honest with or without an arrangement.

    `arrangement` is None for "take the dice as they fall" - `rolled`
    passes through unchanged. Otherwise it must name every ability exactly
    once and use exactly the multiset of values `rolled` produced - not a
    substitute value from thin air.
    """
    abilities = _ruleset(ruleset).abilities
    if arrangement is None:
        return rolled
    if not arrangeable(mode):
        raise ValueError(
            f"{mode} mode does not allow rearranging ability scores - only "
            f"{'/'.join(sorted(_ARRANGEABLE))} do")
    if set(arrangement) != set(abilities):
        raise ValueError(
            f"arrangement must assign every ability exactly once: "
            f"got {sorted(arrangement)}, need {sorted(abilities)}")
    if sorted(arrangement.values()) != sorted(rolled.values()):
        raise ValueError(
            f"arrangement must be a permutation of the rolled scores "
            f"{sorted(rolled.values())}, not {sorted(arrangement.values())}")
    return dict(arrangement)


def roll_exceptional_strength(d: Dice, score: int, cls: str,
                              ruleset: Ruleset | None = None) -> float:
    """Percentile strength for an eligible 18.

    Returns 18.01-18.99 as a decimal, or 19.0 on a percentile roll of 00 (100).
    Returns `score` unchanged when the character is not eligible - and rolls no
    dice at all in that case, so the log stays honest.
    """
    exceptional_classes = _ruleset(ruleset).EXCEPTIONAL_CLASSES
    if score != 18 or cls not in exceptional_classes:
        return score
    pct = d.roll("1d100", reason="exceptional strength", kind="chargen").total
    if pct >= 100:
        return 19.0
    return round(18 + pct / 100, 2)


def _ancestries(ruleset: Ruleset | None = None) -> dict:
    rs = _ruleset(ruleset)
    if rs.id not in _ANCESTRIES_CACHE:
        _ANCESTRIES_CACHE[rs.id] = rs.load_yaml("ancestries")
    return _ANCESTRIES_CACHE[rs.id]


def ancestry(name: str, ruleset: Ruleset | None = None) -> dict:
    """OSRIC 3.0 §1.2.1-1.2.7: one ancestry's adjustments, limits and class access."""
    a = _ancestries(ruleset).get(name)
    if a is None:
        raise KeyError(f"unknown ancestry: {name!r}")
    return a


# Table 1.2.0A's universal floor/ceiling for any ability an ancestry's own
# `minimums`/`maximums` does not override (data/ancestries.yaml records only
# the ability/ancestry pairs where the book differs from this default).
_DEFAULT_ABILITY_MIN, _DEFAULT_ABILITY_MAX = 3, 18


def apply_ancestry(scores: dict, name: str, ruleset: Ruleset | None = None) -> dict:
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
    a = ancestry(name, ruleset)
    out = dict(scores)
    for k, delta in a["ability_adjustments"].items():
        out[k] = out.get(k, 0) + delta
    for k in out:
        out[k] = min(out[k], a["maximums"].get(k, _DEFAULT_ABILITY_MAX))
    return out


def meets_ancestry_minimums(scores: dict, name: str, ruleset: Ruleset | None = None) -> bool:
    """Table 1.2.0A minimums and maximums, checked AFTER ancestral
    adjustments. Every ability defaults to the universal 3-18 range unless
    the ancestry lists its own bound - the same defaults apply_ancestry
    clamps against, so the two agree on what "too high" means."""
    a = ancestry(name, ruleset)
    abilities = _ruleset(ruleset).abilities
    for k in abilities:
        v = scores.get(k, 0)
        if v < a["minimums"].get(k, _DEFAULT_ABILITY_MIN):
            return False
        if v > a["maximums"].get(k, _DEFAULT_ABILITY_MAX):
            return False
    return True


def _classes(ruleset: Ruleset | None = None) -> dict:
    rs = _ruleset(ruleset)
    if rs.id not in _CLASSES_CACHE:
        _CLASSES_CACHE[rs.id] = rs.load_yaml("classes")
    return _CLASSES_CACHE[rs.id]


def game_class(name: str, ruleset: Ruleset | None = None) -> dict:
    """OSRIC 3.0 §1.3.1-1.3.10: one class's requirements, hit die and tables."""
    c = _classes(ruleset).get(name)
    if c is None:
        raise KeyError(f"unknown class: {name!r}")
    return c


def eligible_classes(scores: dict, ancestry_name: str, ruleset: Ruleset | None = None) -> list[str]:
    """Classes this character may take: allowed by ancestry AND meeting the
    class's own ability minimums."""
    rs = _ruleset(ruleset)
    allowed = set(ancestry(ancestry_name, rs)["allowed_classes"])
    out = []
    for name in tuple(_classes(rs).keys()):
        if name not in allowed:
            continue
        if any(scores.get(k, 0) < v for k, v in game_class(name, rs)["minimums"].items()):
            continue
        out.append(name)
    return out


def roll_hit_points(d: Dice, cls: str, level: int, con_bonus: int,
                    ruleset: Ruleset | None = None) -> int:
    """Hit points for `level` levels of `cls`.

    Past the level where hit dice stop (per class - see classes.yaml),
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
    c = game_class(cls, ruleset)
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


def ability_modifiers(scores: dict, ruleset: Ruleset | None = None) -> dict:
    """Combat-relevant modifiers derived from Table 1.1.2A (Strength).

    Strength-only for now - Dexterity (AC/missile) and Constitution (hp)
    modifiers arrive in a later chapter.
    """
    strength_row = tables.ability_row("1.1.2a", scores["strength"], tables_dir=_tables_dir(ruleset))
    return {
        "hit": _int(strength_row[1]),
        "damage": _int(strength_row[2]),
        "encumbrance_lbs": _int(strength_row[3]),
    }


_CON_ROW = re.compile(r"^(\d+)\s+([+-]?\d+)(.*)$")
_CON_EXCEPTIONAL = re.compile(r"\(\+(\d+)\s+for\s+fighters")


def _constitution_rows(ruleset: Ruleset | None = None) -> list[str]:
    """Table 1.1.4A's data rows, wrapped continuation lines re-joined.

    Row 19's text wraps onto a second physical line ("and rangers) 100 99")
    that does not start with a digit, so the generic `tables.rows()` filter
    (built for the common case of a wrapped HEADER, not a wrapped ROW) drops
    it - the fighters/paladins/rangers bonus for score 19 would otherwise be
    silently lost. Re-joined by hand here rather than teaching the generic
    parser a one-table special case.
    """
    lines = tables.load("1.1.4a", tables_dir=_tables_dir(ruleset))["lines"][1:]  # drop the header line
    merged: list[str] = []
    for line in lines:
        if re.match(r"^\s*\d", line):
            merged.append(line.strip())
        else:
            merged[-1] += " " + line.strip()
    return merged


def constitution_hp_bonus(score: float, cls: str, ruleset: Ruleset | None = None) -> int:
    """Table 1.1.4A's Constitution hit-point modifier for `score`.

    Fighters, paladins and rangers get a BETTER bonus at 17+ - the table
    spells it out per-row as a parenthetical ("+2 (+3 for fighters,
    paladins, and rangers)"), not as a separate column, so it is only
    honoured for EXCEPTIONAL_CLASSES; every other class uses the base
    figure that appears before the parenthesis.
    """
    exceptional_classes = _ruleset(ruleset).EXCEPTIONAL_CLASSES
    for line in _constitution_rows(ruleset):
        m = _CON_ROW.match(line)
        if int(m.group(1)) != int(score):
            continue
        if cls in exceptional_classes:
            exc = _CON_EXCEPTIONAL.search(m.group(3))
            if exc:
                return int(exc.group(1))
        return int(m.group(2))
    raise LookupError(f"no Constitution hit-point row for score {score}")


# Table 1.1.3A's AC ADJUSTMENT column: always the third-from-last field of a
# row (the row itself wraps its "initiative effect" cell to a variable
# number of words - "0" for scores 6-14, "+3 to initiative segment" at the
# extremes - so the AC adjustment can only be found counting from the END:
# ..., ac_adjustment, [bracketed alternate], agility_save_modifier).
def dexterity_ac_adjustment(score: float, ruleset: Ruleset | None = None) -> int:
    """Table 1.1.3A's Dexterity defensive AC adjustment (descending AC:
    negative is better)."""
    for row in tables.rows("1.1.3a", tables_dir=_tables_dir(ruleset)):
        if int(row[0]) == int(score):
            return _int(row[-3])
    raise LookupError(f"no Dexterity AC adjustment row for score {score}")


def dexterity_surprise_adjustment(score: float, ruleset: Ruleset | None = None) -> int:
    """Table 1.1.3A's surprise modifier: positive means the character is
    harder to surprise (subtracts segments), negative means easier."""
    for row in tables.rows("1.1.3a", tables_dir=_tables_dir(ruleset)):
        if int(row[0]) == int(score):
            return _int(row[1])
    raise LookupError(f"no Dexterity surprise row for score {score}")


_ARMOUR_ROW = re.compile(
    r"^([A-Za-z][A-Za-z,\s]*?)\s+\S+\s+\S+\s+([+-]?\d+)\s*\[[+-]?\d+\]\*{0,2}\s")


def _armour_ac_by_name(ruleset: Ruleset | None = None) -> dict[str, int]:
    """Table 1.4.2.G's ARMOUR TYPE -> descending base AC.

    Every armour row's name leads with a letter, not a digit, so
    `tables.rows()` (which keeps only digit/`<`-led lines, to drop wrapped
    headers) drops every row of this table - it is read from the raw lines
    instead. `Helmet` has no `[bracket]` (its AC is "n/a", free with any
    suit) and is skipped; the footnote/example lines below the table have
    no bracket either and are skipped the same way.
    """
    out = {}
    for line in tables.load("1.4.2.g", tables_dir=_tables_dir(ruleset))["lines"]:
        m = _ARMOUR_ROW.match(line.strip())
        if m:
            out[m.group(1).strip().lower()] = int(m.group(2))
    return out


ARMOUR_TYPES = tuple(sorted(_armour_ac_by_name()))

# "Shields improve your armour class by 1 point" (osric.txt, Table 1.4.2.G
# footnote **) - true of small, medium and large alike; which of the three
# limits how many incoming attacks it defends against per round is a
# combat-round bookkeeping concern for whoever resolves an attack, not part
# of the character's baseline AC.
SHIELD_AC_BONUS = 1

# The to-hit tables (character and monster ladders alike) only cover AC 10
# down to -10 - Table 2.1.2A's own header is exactly that span.
_AC_MIN, _AC_MAX = -10, 10


def armour_class(dex_score: float, armour: str | None = None, shield: bool = False,
                 ruleset: Ruleset | None = None) -> int:
    """Descending AC (lower is better) from armour, shield and the
    Dexterity defensive adjustment (Table 1.1.3A). `armour=None` is
    unarmoured (base 10, per the table's own "NO ARMOUR ... AC 10" note)."""
    base = 10 if armour is None else _armour_ac_by_name(ruleset)[armour.lower()]
    if shield:
        base -= SHIELD_AC_BONUS
    ac = base + dexterity_ac_adjustment(dex_score, ruleset)
    return max(_AC_MIN, min(_AC_MAX, ac))


def saving_throws(cls: str, level: int, ruleset: Ruleset | None = None) -> dict:
    """The five saving-throw targets for a class at a level."""
    table_id = game_class(cls, ruleset)["saving_throw_table"]
    for row in tables.rows(table_id, tables_dir=_tables_dir(ruleset)):
        if tables.in_range(row[0], level) and len(row) >= 6:
            return dict(zip(SAVE_CATEGORIES, (_int(c) for c in row[1:6])))
    raise LookupError(f"no saving-throw row for {cls} level {level}")


def to_hit_target(cls: str, level: int, armour_class: int, ruleset: Ruleset | None = None) -> int:
    """The d20 result needed to hit `armour_class`.

    A natural 1 is NOT an automatic miss and a natural 20 is NOT an automatic
    hit - that is OSRIC's stated rule, not a bug. This computes the target
    only; rolling and comparing against it belongs to whoever resolves an
    attack.
    """
    table_id = game_class(cls, ruleset)["to_hit_table"]
    col = _AC_COLUMNS.index(int(armour_class))
    for row in tables.rows(table_id, tables_dir=_tables_dir(ruleset)):
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
    # Progression fields persisted across sessions.
    xp: int = 0
    level: int = 1
    gold: int = 0
    inventory: tuple = field(default=(), compare=False)
    equipment: dict = field(default_factory=dict, compare=False)


def is_legal_multiclass(ancestry_name: str, class_names, ruleset: Ruleset | None = None) -> bool:
    """One class is always legal if the ancestry allows it. More than one must
    appear in that ancestry's own multiclass_combinations (OSRIC 3.0
    SS1.3.11) - humans have none (dual-classing, SS1.3.12, is a different
    mechanism entirely and not covered here)."""
    names = list(class_names)
    allowed = set(ancestry(ancestry_name, ruleset)["allowed_classes"])
    if not set(names) <= allowed:
        return False
    if len(names) == 1:
        return True
    combos = [sorted(c) for c in ancestry(ancestry_name, ruleset).get("multiclass_combinations", [])]
    return sorted(names) in combos


def _multiclass_saves(class_names, level: int = 1, ruleset: Ruleset | None = None) -> dict:
    """SS1.3.11 "Attacks and Saving Throws": a multi-classed character may
    use whichever of their classes' tables is best in each category - so the
    saves are the best (lowest) target per category across all classes, not
    just the first-listed one."""
    all_saves = [saving_throws(c, level, ruleset) for c in class_names]
    return {cat: min(s[cat] for s in all_saves) for cat in SAVE_CATEGORIES}


def _multiclass_hit_points(d: Dice, class_names, scores: dict, ruleset: Ruleset | None = None) -> int:
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

    Constitution's hp bonus is looked up PER CLASS (`scores`, not a flat
    `con_bonus` int) because fighters/paladins/rangers get a better bonus
    at 17+ Constitution than every other class - a fighter/magic-user
    multi-class rolls its fighter level with the better figure and its
    magic-user level with the ordinary one.
    """
    n = len(class_names)
    total = 0
    for cls in class_names:
        con_bonus = constitution_hp_bonus(scores["constitution"], cls, ruleset)
        class_roll = roll_hit_points(d, cls, 1, con_bonus, ruleset)
        total += max(1, class_roll // n)
    return total


def generate(seed: int, mode: str, ancestry_name: str, class_names,
             name: str = "", arrangement: dict | None = None,
             ruleset: Ruleset | None = None) -> Character:
    """Roll a complete first-level character. Fully reproducible from
    (seed, mode, ancestry, classes, arrangement).

    `arrangement`, when given, assigns the six already-rolled scores to
    abilities in a player-chosen order (only legal in `difficult` and
    `flexible` mode - see `apply_arrangement`). It never re-rolls: the roll
    log is identical with or without an arrangement, only which ability
    each already-rolled value lands on changes.
    """
    rs = _ruleset(ruleset)
    class_names = tuple(class_names)
    if not is_legal_multiclass(ancestry_name, class_names, rs):
        raise ValueError(
            f"{ancestry_name} may not be {'/'.join(class_names)}")

    d = Dice(seed=seed)
    rolled = roll_abilities(d, mode, rs)
    arranged = apply_arrangement(rolled, arrangement, mode, rs)
    scores = apply_ancestry(arranged, ancestry_name, rs)

    # Table 1.2.0A's own title is "Required Ability Scores AFTER ANCESTRAL
    # BONUSES" - checked here, immediately after apply_ancestry, and before
    # exceptional Strength (which only ever raises an 18, never lowers a
    # score below a floor).
    if not meets_ancestry_minimums(scores, ancestry_name, rs):
        raise ValueError(
            f"{ancestry_name} ability scores do not meet Table 1.2.0A after "
            f"ancestral bonuses: {scores}")

    # Exceptional Strength applies if ANY of the character's classes is
    # fighter/paladin/ranger (osric.txt:650-655), not only the first-listed
    # one. Rolled exactly once against the pre-resolution score - feeding
    # roll_exceptional_strength its own output would silently re-roll an
    # already-settled Strength.
    exceptional_classes = rs.EXCEPTIONAL_CLASSES
    exceptional_cls = next(
        (c for c in class_names if c in exceptional_classes), class_names[0])
    scores["strength"] = roll_exceptional_strength(d, scores["strength"], exceptional_cls, rs)

    # Each class's own §1.3.N.1 "Minimum Scores", checked against the final
    # (post-exceptional-Strength) scores. is_legal_multiclass already
    # confirmed the ancestry allows every class in class_names, so a class
    # missing from eligible_classes here can only be a failed ability
    # minimum - eligible_classes is the same function tests/test_character.py
    # already exercises for this, wired onto the generation path for real.
    eligible = eligible_classes(scores, ancestry_name, rs)
    for cls in class_names:
        if cls not in eligible:
            short = {
                ability: threshold
                for ability, threshold in game_class(cls, rs)["minimums"].items()
                if scores.get(ability, 0) < threshold
            }
            raise ValueError(
                f"{ancestry_name} does not meet {cls}'s ability minimums: {short}")

    mods = ability_modifiers(scores, rs)
    hit_points = _multiclass_hit_points(d, class_names, scores, rs)

    return Character(
        name=name,
        ancestry=ancestry_name,
        classes=class_names,
        levels={c: 1 for c in class_names},
        scores=scores,
        hit_points=hit_points,
        # No equipment system yet (Chapter 4+), so a freshly generated
        # character starts unarmoured, unshielded: base AC 10 adjusted only
        # by Dexterity (Table 1.1.3A). Passing real armour/shield choices
        # in is exactly what armour_class() is for once equipment lands.
        armour_class=armour_class(scores["dexterity"], ruleset=rs),
        saves=_multiclass_saves(class_names, 1, rs),
        modifiers=mods,
        seed=seed,
        log=d.log,
    )
