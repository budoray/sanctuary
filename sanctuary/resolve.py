"""Combat resolution: attacks, saving throws, turning undead, morale, item
saves, initiative/rounds, movement and death.

OSRIC 3.0 Player Guide Chapter Six ("How to Play" -> Combat) plus the GM
Guide's SS2.1 monster ladders. Every function returns a record carrying
both the outcome and the arithmetic that produced it - the client renders
the reasoning, not just the number. Every die rolled here goes through
`sanctuary.dice.Dice`; nothing in this module calls `random` directly.

May import `sanctuary.character`, `sanctuary.tables` and `sanctuary.dice` -
nothing else of ours (`tests/test_invariants.py::test_dependency_chain_is_one_way`).
"""
import re
from dataclasses import dataclass
from functools import lru_cache

from sanctuary import character
from sanctuary import tables

# Mirrors character._AC_COLUMNS (a to-hit table's columns, AC 10 down to
# -10) - duplicated rather than reached across the module boundary as a
# private name.
_AC_COLUMNS = list(range(10, -11, -1))


def _int(cell: str) -> int:
    return int(str(cell).replace("+", "").replace("−", "-"))


# ---------------------------------------------------------------------------
# Monster ladders (GM Guide Table 2.1.2A / 2.1.3A / 2.1.3B, by hit dice)
# ---------------------------------------------------------------------------

_HD_MINUS = re.compile(r"^(\d+)-1$")
_HD_PLUS = re.compile(r"^(\d+)\+(\d+)$")


def _hd_base_and_bonus(hit_dice) -> tuple[float, bool]:
    """(n, has_bonus): `n` is the flat hit-dice count - OSRIC's "N-1" idiom
    (a monster weaker than a flat N hit dice, e.g. kobolds) reads as
    n - 0.5, distinct from and below flat N. `has_bonus` is True for the
    book's "N+M" bonus-hit-point notation (e.g. "1+1")."""
    s = str(hit_dice).strip()
    m = _HD_PLUS.match(s)
    if m:
        return float(m.group(1)), True
    m = _HD_MINUS.match(s)
    if m:
        return float(m.group(1)) - 0.5, False
    return float(s), False


def monster_to_hit_target(hit_dice, armour_class: int) -> int:
    """Table 2.1.2A: the monster to-hit ladder, keyed by hit dice instead
    of class level. `hit_dice` accepts the book's own notation: a flat
    int/float ("4"), the "N-1" idiom ("1-1"), or "N+M" bonus hit points
    ("1+1").

    ⚠ Row granularity is uneven: HD 1 gets two dedicated rows ("1" flat,
    "1+" with bonus hp), but HD 2 and up are paired into bands ("2-3+",
    "4-5+", ...) that absorb bonus hit points without moving to the next
    band - a monster with "2+3" HD matches "2-3+", the same row flat "2"
    or "3" would.
    """
    n, bonus = _hd_base_and_bonus(hit_dice)
    col = _AC_COLUMNS.index(int(armour_class))
    for row in tables.rows("2.1.2a"):
        label = row[0]
        if label == "<1-1":
            hit = n < 0.5
        elif label == "1-1":
            hit = n == 0.5
        elif label == "1":
            hit = n == 1 and not bonus
        elif label == "1+":
            hit = n == 1 and bonus
        else:
            bounds = label.rstrip("+").split("-")
            if len(bounds) == 1:
                hit = n >= float(bounds[0])  # "24+": open-ended top band
            else:
                lo, hi = (float(x) for x in bounds)
                hit = lo <= n <= hi
        if hit:
            return _int(row[1 + col])
    raise LookupError(f"no Table 2.1.2A row for hit dice {hit_dice!r}")


def monster_saving_throw(hit_dice, category: str, non_intelligent: bool = False) -> int:
    """Table 2.1.3A (or 2.1.3B for INT-0/non-intelligent monsters). Bonus
    hit points ("N+M") round UP to N+1 hit dice for band selection here -
    stated explicitly in the book's own note under Table 2.1.3B ("hit dice
    of 1+1 ... treated as ... 2 hit dice ... because 1+1 is greater than
    1"), unlike the to-hit table's finer per-HD bands where bonus hp stays
    within the same band.
    """
    n, bonus = _hd_base_and_bonus(hit_dice)
    value = n + 1 if bonus else n
    table_id = "2.1.3b" if non_intelligent else "2.1.3a"
    idx = character.SAVE_CATEGORIES.index(category)
    for row in tables.rows(table_id):
        if tables.in_range(row[0], value):
            return _int(row[1 + idx])
    raise LookupError(f"no {table_id} row for hit dice {hit_dice!r}")


# ---------------------------------------------------------------------------
# Attacks
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AttackResult:
    """The natural d20 face AND the modified total, kept separate so a
    client can show both - and so the nat-1/nat-20 rule stays checkable
    from the record alone."""
    natural: int
    roll_total: int
    target: int
    hit: bool
    modifiers: int
    damage: int | None = None
    damage_roll: object = None


def attack(d, attacker, target_ac: int, damage_expr: str = "1d6",
           magic_to_hit: int = 0, magic_damage: int = 0, situational: int = 0) -> AttackResult:
    """Resolve one attack. `attacker` is a `character.Character` (uses the
    best of its class to-hit ladders, per SS1.3.11 "Attacks and Saving
    Throws": "you can choose which of your classes' tables you use for
    combat and saving throws - pick the best one") or a monster's hit dice
    (Table 2.1.2A). A Character's Strength to-hit/damage modifiers are
    applied automatically; `magic_to_hit`/`magic_damage`/`situational`
    cover everything else (weapon/spell bonuses, cover, flanking, ...).

    ⚠ A natural 1 is NOT an automatic miss and a natural 20 is NOT an
    automatic hit - that is OSRIC's stated rule, not an oversight.
    Comparison of the modified roll against the target is the whole of
    it; neither face of the die is special-cased below.
    """
    if isinstance(attacker, character.Character):
        target = min(character.to_hit_target(cls, attacker.levels[cls], target_ac)
                      for cls in attacker.classes)
        str_hit = attacker.modifiers.get("hit", 0)
        str_dmg = attacker.modifiers.get("damage", 0)
    else:
        target = monster_to_hit_target(attacker, target_ac)
        str_hit = str_dmg = 0

    modifiers = str_hit + magic_to_hit + situational
    roll_obj = d.roll("1d20", reason="attack", kind="combat")
    natural = roll_obj.kept[0]
    total = roll_obj.total + modifiers
    hit = total >= target

    damage = None
    damage_roll = None
    if hit:
        damage_roll = d.roll(damage_expr, reason="damage",
                              mods=str_dmg + magic_damage, kind="combat")
        damage = damage_roll.total

    return AttackResult(natural=natural, roll_total=total, target=target, hit=hit,
                         modifiers=modifiers, damage=damage, damage_roll=damage_roll)


# ---------------------------------------------------------------------------
# Saving throws (character and monster) and item saves
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SaveResult:
    natural: int
    roll_total: int
    target: int
    success: bool
    category: str


def saving_throw(d, subject, category: str, natural_20_auto_succeeds: bool = False,
                  non_intelligent: bool = False) -> SaveResult:
    """`subject` is a `character.Character` (its precomputed best-of-class
    save target - `Character.saves` already applied SS1.3.11's "pick the
    best table" rule at generation time) or a monster's hit dice
    (Table 2.1.3A/2.1.3B).

    ⚠ A natural 1 on a saving throw ALWAYS fails - OSRIC's stated rule.
    A natural 20 auto-succeeding is an explicit house rule, off by default.
    """
    if isinstance(subject, character.Character):
        target = subject.saves[category]
    else:
        target = monster_saving_throw(subject, category, non_intelligent=non_intelligent)
    roll_obj = d.roll("1d20", reason="save", kind="combat")
    natural = roll_obj.kept[0]
    success = roll_obj.total >= target
    if natural == 1:
        success = False
    elif natural == 20 and natural_20_auto_succeeds:
        success = True
    return SaveResult(natural=natural, roll_total=roll_obj.total, target=target,
                       success=success, category=category)


# Table 1.6.4A's damage-type columns, in the order its rows list them.
ATTACK_FORMS = ("acid", "cold", "crushing_blow", "disintegrate", "fall",
                 "fire_magical", "fire_normal", "lightning")

# Every real material row leads with a letter, not a digit, so
# `tables.rows()` (built to drop wrapped HEADER text, which also leads with
# a letter) drops this whole table - read from the raw lines instead, same
# as character.py's armour table.
_ITEM_SAVE_ROW = re.compile(r"^([A-Za-z][A-Za-z/ ]*?)\s+((?:\d+\s+){7}\d+)$")


@lru_cache(maxsize=1)
def _item_save_table() -> dict:
    out = {}
    for line in tables.load("1.6.4a")["lines"]:
        m = _ITEM_SAVE_ROW.match(line.strip())
        if m:
            nums = [int(x) for x in m.group(2).split()]
            out[m.group(1).strip().lower()] = dict(zip(ATTACK_FORMS, nums))
    return out


ITEM_MATERIALS = tuple(sorted(_item_save_table()))


def item_saving_throw(d, material: str, attack_form: str, bonus: int = 0) -> SaveResult:
    """Table 1.6.4A. Same convention as every other save here: roll d20,
    total >= target succeeds (the item survives), and a natural 1 always
    fails - the book gives no separate rule for items, so this follows the
    general saving-throw convention rather than inventing a different one."""
    target = _item_save_table()[material.lower()][attack_form]
    roll_obj = d.roll("1d20", reason="item save", kind="combat")
    natural = roll_obj.kept[0]
    total = roll_obj.total + bonus
    success = total >= target and natural != 1
    return SaveResult(natural=natural, roll_total=total, target=target,
                       success=success, category=attack_form)


# ---------------------------------------------------------------------------
# Turning the undead (Table 1.6.5A)
# ---------------------------------------------------------------------------

_TURN_LEVEL_BANDS = ("1", "2", "3", "4", "5", "6", "7", "8", "9-13", "14-18", "19+")
_TURN_ROW = re.compile(r"^Type (\d+) (\S+)\s+(.*)$")
_NO_CHANCE = ("—", "–", "-", "�")  # em/en dash (and a
# mojibake fallback '�', seen when the corpus's em dash round-trips
# through a lossy codec) - the table's own symbol for "no chance to turn".

UNDEAD_TYPES = tuple(range(1, 14))  # Table 1.6.5A: Type 1 (skeleton) .. 13 (fiend)


@lru_cache(maxsize=1)
def _turn_undead_rows() -> dict:
    out = {}
    for line in tables.load("1.6.5a")["lines"]:
        m = _TURN_ROW.match(line.strip())
        if not m:
            continue
        values = m.group(3).split()
        if len(values) != len(_TURN_LEVEL_BANDS):
            continue  # a wrapped continuation line, not a real table row
        out[int(m.group(1))] = dict(zip(_TURN_LEVEL_BANDS, values))
    return out


def _turn_level_band(level: int) -> str:
    if level <= 8:
        return str(level)
    if level <= 13:
        return "9-13"
    if level <= 18:
        return "14-18"
    return "19+"


def paladin_turn_type(level: int) -> int:
    """The table's own footnote: for evil clerics turning paladins, treat
    the paladin as this undead Type by paladin level. Paladins can never
    be destroyed by turning, whatever the result (enforced by callers, not
    here - this only resolves which row to use)."""
    band = min((level + 1) // 2, 6)  # 1-2->1, 3-4->2, ..., 11+->6
    return 7 + band  # Type 8 (level 1-2) .. Type 13 (level 11+)


@dataclass(frozen=True)
class TurnResult:
    cell: str
    roll: int | None
    success: bool
    affected: int | None
    destroyed: bool
    controlled: bool


def turn_undead(d, cleric_level: int, undead_type: int, alignment: str = "good",
                 is_fiend_or_paladin: bool = False) -> TurnResult:
    """Table 1.6.5A. `alignment` is "good"/"neutral" (a successful D/D*
    result automatically destroys the undead) or "evil" (never destroys;
    may instead roll to control - "Chance to Control", d100 61-100).
    `affected` is None for a "T" result: the book says "turned
    automatically" with no die roll for how many, unlike D/D*/a numbered
    result which each name an explicit dice expression.
    """
    row = _turn_undead_rows().get(undead_type)
    if row is None:
        raise KeyError(f"no Table 1.6.5A row for undead type {undead_type}")
    cell = row[_turn_level_band(cleric_level)]

    if cell in _NO_CHANCE:
        return TurnResult(cell=cell, roll=None, success=False, affected=0,
                           destroyed=False, controlled=False)

    roll = None
    if cell not in ("T", "D", "D*"):
        roll_obj = d.roll("1d20", reason="turn undead", kind="combat")
        roll = roll_obj.kept[0]
        if roll < _int(cell):
            return TurnResult(cell=cell, roll=roll, success=False, affected=0,
                               destroyed=False, controlled=False)

    if cell == "T":
        affected = None  # "the creature is turned automatically" - no count rolled
    elif cell == "D*":
        expr = "1d2" if is_fiend_or_paladin else "1d6+6"
        affected = d.roll(expr, reason="turned count", kind="combat").total
    else:  # "D" or a passed numbered check
        expr = "1d2" if is_fiend_or_paladin else "2d6"
        affected = d.roll(expr, reason="turned count", kind="combat").total

    destroyed = cell in ("D", "D*") and alignment in ("good", "neutral")
    controlled = False
    if alignment == "evil" and cell != "T":
        pct = d.roll("1d100", reason="chance to control", kind="combat").total
        controlled = pct >= 61

    return TurnResult(cell=cell, roll=roll, success=True, affected=affected,
                       destroyed=destroyed, controlled=controlled)


# ---------------------------------------------------------------------------
# Morale (Table 1.6.8A)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MoraleResult:
    roll: int
    base: int
    adjusted: int
    passed: bool
    outcome: str  # "holds" | "retreats" | "surrenders"


def morale(d, hit_dice: float, modifiers: int = 0) -> MoraleResult:
    """"The general calculation for monster morale is 50% plus 5% per hit
    die. Roll equal to or less than, and the monster succeeds." Table
    1.6.8A's situational modifiers (all cumulative) are added to the ROLL,
    not the base, matching the book's own worked phrasing ("adjust the die
    roll with modifiers").

    A failure by 25% or less "generally" retreats; "51% or higher"
    surrenders (osric.txt SS1.6.8) - the 26-50% band is left to the GM's
    judgement of the situation in the book's own text, so this classifies
    it as "retreats" (the more common outcome the text describes) rather
    than invent a threshold the rules don't state.
    """
    base = 50 + 5 * hit_dice
    roll = d.roll("1d100", reason="morale", kind="combat").total
    adjusted = roll + modifiers
    passed = adjusted <= base
    outcome = "holds"
    if not passed:
        margin = adjusted - base
        outcome = "surrenders" if margin > 50 else "retreats"
    return MoraleResult(roll=roll, base=int(base), adjusted=adjusted,
                         passed=passed, outcome=outcome)


# ---------------------------------------------------------------------------
# Time and movement
# ---------------------------------------------------------------------------

# Segments per round (Player Guide SS1.6.1); rounds per turn is the other
# fixed conversion the engine needs (a turn is 10 rounds - 10 minutes of
# game time at 1 minute/round, per SS1.6.1's own framing).
SEGMENTS_PER_ROUND = 10
ROUNDS_PER_TURN = 10


def _row_weight_cap(row: list[str]) -> float:
    """The upper bound of extra weight (over unencumbered) a Table
    1.5.3.3A row covers, parsed from its own leading weight-range text -
    every row's raw shape differs ("1 to 40 lbs over...", "41-80 lbs
    over...", "121+ lbs over...") because the extractor keeps prose
    exactly as printed."""
    first = row[0]
    if first.isdigit() and len(row) > 2 and row[1] == "to":
        return float(row[2])
    if first.endswith("+"):
        return float("inf")
    if "-" in first:
        return float(first.split("-")[1])
    raise ValueError(f"unrecognised encumbrance row: {row}")


def _row_movement_fraction(row: list[str]) -> float:
    text = " ".join(row)
    if "Cannot Move" in text:
        return 0.0
    if "Three Quarter" in text:
        return 0.75
    if "Half" in text:
        return 0.5
    if "Quarter" in text:
        return 0.25
    raise ValueError(f"unrecognised encumbrance row: {row}")


@lru_cache(maxsize=1)
def _encumbrance_bands() -> tuple:
    # The table's own "Unencumbered" row leads with a letter, not a digit,
    # so `tables.rows()` drops it as a wrapped-header candidate - it is the
    # table's own baseline (0 extra lbs, full movement) rather than a
    # figure this needs to read out of the corpus.
    bands = [(0.0, 1.0)]
    for row in tables.rows("1.5.3.3a"):
        bands.append((_row_weight_cap(row), _row_movement_fraction(row)))
    return tuple(sorted(bands))


def movement_rate(base_move: float, weight_over_unencumbered: float) -> float:
    """Table 1.5.3.3A: movement rate falls off in steps as carried weight
    passes the character's unencumbered allowance (a separate
    Strength-based figure - Table 1.1.2A's `encumbrance_lbs`, already
    exposed by `character.ability_modifiers` - not looked up here)."""
    for cap, fraction in _encumbrance_bands():
        if weight_over_unencumbered <= cap:
            return base_move * fraction
    raise AssertionError("unreachable: Table 1.5.3.3A's last band is open-ended (121+)")


# ---------------------------------------------------------------------------
# Initiative and combat rounds (Player Guide SS1.6.1, "Order of Events")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Surprise:
    """SS1.6.1.1: each side rolls 1d6; a result of 1-2 means surprised for
    that many segments (3-6 means not surprised, absent a monster's own
    special surprise rule - not modelled here, since it is per-monster
    data this engine does not yet carry). A Dexterity surprise bonus
    negates segments for the character who has it ("+2 surprise bonus
    means -2 surprise segments" - the book's own example).
    ⚠ ponytail: a bonus large enough to be a PENALTY creating surprise on
    an otherwise-unsurprised roll of 3+ is not modelled - add it if a
    monster with a surprise penalty needs it."""
    a_segments: int
    b_segments: int

    @property
    def a_acts_free(self) -> int:
        """Segments in which A can act while B is still surprised."""
        return max(0, self.b_segments - self.a_segments)

    @property
    def b_acts_free(self) -> int:
        return max(0, self.a_segments - self.b_segments)


def determine_surprise(d, a_bonus: int = 0, b_bonus: int = 0) -> Surprise:
    a_roll = d.roll("1d6", reason="surprise a", kind="combat").total
    b_roll = d.roll("1d6", reason="surprise b", kind="combat").total
    a_segments = max(0, (a_roll if a_roll <= 2 else 0) - a_bonus)
    b_segments = max(0, (b_roll if b_roll <= 2 else 0) - b_bonus)
    return Surprise(a_segments=a_segments, b_segments=b_segments)


@dataclass(frozen=True)
class Initiative:
    """SS1.6.1.3: each side rolls 1d6; the LOWER result is the segment
    that side acts in (and thus acts first) - "a low roll goes earlier and
    is better." A tie means both sides act simultaneously."""
    a_segment: int
    b_segment: int

    @property
    def first(self) -> str:
        if self.a_segment < self.b_segment:
            return "a"
        if self.b_segment < self.a_segment:
            return "b"
        return "tied"


def roll_initiative(d) -> Initiative:
    a = d.roll("1d6", reason="initiative a", kind="combat").total
    b = d.roll("1d6", reason="initiative b", kind="combat").total
    return Initiative(a_segment=a, b_segment=b)


@dataclass(frozen=True)
class CombatRound:
    """One combat round: 10 six-second segments (SEGMENTS_PER_ROUND).
    Steps 4-5 of the Order of Events resolve the side with the LOWER
    initiative segment first, its results taking effect, before the other
    side acts - a tie resolves simultaneously (Player Guide SS1.6.1.3,
    "Tie Rolls"). Segments 7-10 exist only for delayed actions and spells
    already cast with a longer casting time; nothing new is declared
    there, so this model does not enumerate them as separate phases."""
    number: int
    initiative: Initiative

    @property
    def order(self) -> tuple[str, ...]:
        if self.initiative.first == "tied":
            return ("simultaneous",)
        second = "b" if self.initiative.first == "a" else "a"
        return (self.initiative.first, second)


# ---------------------------------------------------------------------------
# Damage and death (SS1.6.6)
# ---------------------------------------------------------------------------

# "When hit points reach 0, the character is unconscious and will continue
# to lose one hit point per round from blood loss until death occurs at
# -10 hp." "-6 hit points or below, the scars of the wound will likely be
# borne for the rest of the character's life."
DEATH_THRESHOLD = -10
SCARRING_THRESHOLD = -6


@dataclass(frozen=True)
class DamageResult:
    hit_points: int
    unconscious: bool
    dead: bool
    scarred: bool


def apply_damage(current_hp: int, damage: int) -> DamageResult:
    """SS1.6.6: hp<=0 is unconscious; death at -10 or below; -6 or below
    scars. "Any additional damage suffered by an unconscious creature
    (other than the bleeding...) will kill the creature instantly" is the
    CALLER's responsibility to enforce (call this again with the extra hit
    and treat any result under DEATH_THRESHOLD, or already unconscious, as
    fatal) - this function only classifies the hp total after one hit."""
    hp = current_hp - damage
    return DamageResult(
        hit_points=hp,
        unconscious=hp <= 0,
        dead=hp <= DEATH_THRESHOLD,
        scarred=hp <= SCARRING_THRESHOLD,
    )


def bleed_out(hp: int) -> int:
    """One round of unconsciousness: lose 1 hp to blood loss, unless
    already at the death threshold (SS1.6.6). "Stopped immediately in the
    same round that aid...is administered" is a caller decision (simply
    don't call this that round), not modelled as a flag here."""
    return hp - 1 if hp > DEATH_THRESHOLD else hp
