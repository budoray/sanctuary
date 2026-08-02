"""Random dungeon generator - OSRIC 3.0 Gamemaster Guide §2.7.1-2.7.3.

The seven-step procedure (§2.7.1, tables D-1..D-24) walks a corridor from a
starting area, rolling shape, exits, and contents as it goes. This module
implements it as a breadth-first walk over a graph of numbered areas and
EMITS the campaign format (design §8.1) directly - a dict shaped exactly
like `sanctuary.module`'s contract. It does not invent a parallel
representation; the concurrent module.py agent loads what this writes.

⚠ Every roll goes through `sanctuary.dice.Dice` - nothing here calls
`random`. Rolls tagged `fudge=True` are the GM "freely fudge impossible
results" cases the book calls out explicitly: a corridor walk that won't
terminate, a room-count budget that runs out, a "0 exits" result that
would strand the generator. Rolls tagged `reroll=True` are re-rolls the
BOOK ITSELF instructs (D-4's "16-20 re-roll", D-18's wandering-monster
"if you're just creating a map, re-roll this result") - not improvisation.

Reachability is proved by construction: every area but the first is
created by walking an exit out of an area already in the graph, so the
graph is connected from area 1 outward before any edge is ever removed.
`reachable_area_ids` re-derives this by BFS instead of trusting that
argument, because a construction invariant that is never re-checked is
just an assertion nobody ran.
"""
import re
from functools import lru_cache

from sanctuary import tables
from sanctuary.dice import Dice

_DASH = re.compile(r"[–—-]")

# Corridor-walk step cap (§2.7.1 step 7: "corridor continues 30ft, then
# D-18"). The book's own loop (D-18 -> D-21/D-24 -> D-18 ...) has no
# guaranteed terminal condition; real dungeons published with this
# algorithm run to a handful of segments. Bounded here, and exceeding it
# is logged as a fudge rather than hidden.
_MAX_CORRIDOR_STEPS = 8
_MAX_SIZE_REROLLS = 5


# --------------------------------------------------------------------
# Table plumbing
# --------------------------------------------------------------------

def _d100_match(spec: str, value: int) -> bool:
    """OSRIC d100 tables write '100' as '00' (e.g. '99-00'), which
    `tables.in_range` reads as literal 0 and so never matches. Own matcher
    for d100 specs only; d20 tables use `tables.in_range` unmodified.

    Some monster tables (e.g. 2.7.3.2f) wrap a long entry's name across
    several lines; the tail of the wrap (a bare dice expression like
    "1d3 1") survives `tables.rows()` as its own row because it happens
    to start with a digit. That is corpus noise, not a real row - a spec
    that isn't a plain number/range never matches, rather than crashing
    every later lookup on that table."""
    parts = [p for p in _DASH.split(spec.strip()) if p]
    try:
        nums = [100 if p in ("00", "0") else int(p) for p in parts]
    except ValueError:
        return False
    if not nums:
        return False
    if len(nums) == 1:
        return value == nums[0]
    return nums[0] <= value <= nums[-1]


def _row_d20(dice_: Dice, table_id: str, reason: str, **tags):
    """Roll 1d20 on a standard single-column D-table and return the
    matching row (list of whitespace-split fields)."""
    roll = dice_.roll("1d20", reason=reason, table=table_id, **tags)
    for row in tables.rows(table_id):
        if not row:
            continue
        try:
            if tables.in_range(row[0], roll.total):
                return row, roll.total
        except ValueError:
            continue  # a row label OSRIC's own hit-dice idiom makes ambiguous
    raise LookupError(f"{table_id}: no row covers {roll.total}")


def _row_d100(dice_: Dice, table_id: str, reason: str, min_fields: int = 1, **tags):
    """`min_fields` skips wrap-continuation debris that survives
    `tables.rows()` as its own row (see `_d100_match`'s docstring) but is
    too short to be a genuine entry for this table's shape.

    A handful of entries are unrecoverable from the corpus this way (the
    wrap ate the row's own dice-range label, not just its name) - e.g.
    2.7.3.2f's "31-35 Devil, Manalishi" leaves no row at all covering
    31-35. Rather than crash the whole dungeon on that gap, fudge: fall
    back to the first well-shaped row and log it, the same as any other
    impossible table result."""
    roll = dice_.roll("1d100", reason=reason, table=table_id, **tags)
    candidates = [r for r in tables.rows(table_id) if r and len(r) >= min_fields]
    for row in candidates:
        if _d100_match(row[0], roll.total):
            return row, roll.total
    dice_.roll("1d2", reason=f"fudge: {table_id} has no row covering "
               f"{roll.total} (a wrapped entry ate its own range label); "
               "falling back to the table's first entry", fudge=True)
    return candidates[0], roll.total


@lru_cache(maxsize=None)
def _d1_labels() -> dict[int, str]:
    """D-1 prints two columns per line ('1 Use area I 4 Use area IV').
    Parsed once from the extracted lines rather than hand-typed, so a
    re-extraction that changes the wording still flows through."""
    out = {}
    lines = tables.load("d-1")["lines"][1:]  # drop the header line
    for line in lines:
        m = re.match(
            r"(\d+)\s+(Use area \S+)\s+(\d+)\s+(Use area \S+)", line.strip())
        if m:
            out[int(m.group(1))] = m.group(2)
            out[int(m.group(3))] = m.group(4)
    return out


def _is_dice_expr(text: str) -> bool:
    return bool(re.match(r"^\d+d\d+([+-]\d+)?$", text))


# --------------------------------------------------------------------
# Step 2: shape and size (D-2a/D-2b -> D-3 -> D-4)
# --------------------------------------------------------------------

_SPECIAL_DIM = re.compile(r"(\d+)ft\s*[×x]\s*(\d+)ft")


def _roll_size(dice_: Dice, chamber: bool):
    """Returns (sqft, shape_label)."""
    table_id = "d-2b" if chamber else "d-2a"
    row, _ = _row_d20(dice_, table_id, f"{table_id}: room/chamber size")
    text = " ".join(row[1:])
    m = _SPECIAL_DIM.search(text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        return w * h, "rectangular"

    # "Special*" - roll D-3 for shape, then D-4 for its square footage.
    shape_row, _ = _row_d20(dice_, "d-3", "D-3: special room/chamber shape")
    shape = shape_row[-1].rstrip("*")

    for attempt in range(_MAX_SIZE_REROLLS):
        size_row, _ = _row_d20(
            dice_, "d-4", "D-4: unusual room size",
            reroll=(attempt > 0))
        cell = size_row[-1].rstrip("*")
        if cell.lower() == "re-roll":
            continue
        return int(cell.replace(",", "")), shape

    # Book's own reroll branch never resolved within budget - fudge a
    # mid-table size rather than loop forever.
    dice_.roll("1d2", reason="fudge: D-4 reroll loop exceeded budget; "
               "picking the table's middle result", fudge=True)
    return 2500, shape


# --------------------------------------------------------------------
# Step 3: number of exits (D-5, keyed on area)
# --------------------------------------------------------------------

def _roll_num_exits(dice_: Dice, sqft: int) -> int:
    row, _ = _row_d20(dice_, "d-5", "D-5: number of exits")
    if row[1].lower() == "any":
        cell = row[2]
    else:
        # "< 500 N > 500 M" -> small-room count is row[3], large is row[6]
        cell = row[3] if sqft < 500 else row[6]
    cell = cell.rstrip("*")
    if re.match(r"^\d+d\d+$", cell):
        return dice_.roll(cell, reason="D-5: exit count (variable)").total
    return int(cell)


# --------------------------------------------------------------------
# Step 4: exit wall (D-6, flavour only)
# --------------------------------------------------------------------

def _roll_exit_wall(dice_: Dice) -> str:
    row, _ = _row_d20(dice_, "d-6", "D-6: exit location")
    return " ".join(row[1:]).lower()


# --------------------------------------------------------------------
# Step 5/7: corridor walk (D-7/D-20, D-18, D-19, D-21, D-24, D-13)
# --------------------------------------------------------------------

def _walk_corridor(dice_: Dice, from_chamber: bool):
    """Walks the corridor tables until a terminal result: a new area
    (door or passage, maybe hidden, maybe one-way), or a dead end (None).

    Returns (kind, hidden, one_way) or None for a dead end.
    """
    if from_chamber:
        row, _ = _row_d20(dice_, "d-7", "D-7: chamber exit direction")
    else:
        row, _ = _row_d20(dice_, "d-20", "D-20: behind the door")
        text = " ".join(row[1:]).lower()
        if "room" in text or "table d-2" in text:
            return "door", False, False

    for step in range(_MAX_CORRIDOR_STEPS):
        row, _ = _row_d20(dice_, "d-18", "D-18: corridor, 30ft on")
        result = " ".join(row[1:]).lower()

        if "chamber" in result:
            return "passage", False, False
        if "dead end" in result:
            return None
        if "door" in result:
            _row_d20(dice_, "d-19", "D-19: door location")
            return "door", False, False
        if "side passage" in result:
            side_row, _ = _row_d20(dice_, "d-21", "D-21: side passage")
            side_text = " ".join(side_row[1:]).lower()
            if "intersection" in side_text:
                continue  # a junction, not a terminal - keep walking
            return "passage", False, False
        if "stairs" in result:
            stair_row, _ = _row_d20(dice_, "d-13", "D-13: stairs")
            stair_text = " ".join(stair_row[1:]).lower()
            one_way = "dead end" not in stair_text
            return "stairs", False, one_way
        if "turn" in result:
            dice_.roll("1d20", reason="D-24: turn", table="d-24")
            continue
        if "continue straight" in result:
            continue
        if "wandering monster" in result:
            # The book: "If you're just creating a map, re-roll this
            # result" - a book-instructed reroll, not GM improvisation.
            dice_.roll("1d20", reason="D-18: wandering monster mid-walk, "
                       "re-rolling per book instruction (map generation)",
                       table="d-18", reroll=True)
            continue
        return "passage", False, False

    dice_.roll("1d2", reason=f"fudge: corridor walk exceeded "
               f"{_MAX_CORRIDOR_STEPS} steps without a terminal result; "
               "forcing a chamber", fudge=True)
    return "passage", False, False


# --------------------------------------------------------------------
# Step 6: room contents (D-8 + subtables)
# --------------------------------------------------------------------

_MONSTER_LEVEL_LETTERS = "abcdefghij"


def _dungeon_row(dungeon_level: int) -> list[str]:
    for line in tables.load("2.7.3.1a")["lines"][2:]:
        fields = line.split()
        label = fields[0]
        m = re.match(r"^(\d+)(?:–(\d+))?\+?$", label)
        if label.endswith("+"):
            lo = int(label.rstrip("+"))
            if dungeon_level >= lo:
                return fields
            continue
        if m:
            lo = int(m.group(1))
            hi = int(m.group(2)) if m.group(2) else lo
            if lo <= dungeon_level <= hi:
                return fields
    return tables.load("2.7.3.1a")["lines"][2].split()  # level-1 fallback


def _monster_level(dice_: Dice, dungeon_level: int) -> int:
    row = _dungeon_row(dungeon_level)
    roll = dice_.roll("1d20", reason="2.7.3.1a: monster level for dungeon "
                       f"level {dungeon_level}", table="2.7.3.1a")
    columns = row[1:]
    for i, cell in enumerate(columns):
        if cell in ("—", "-", "–"):
            continue
        try:
            if tables.in_range(cell, roll.total):
                return i + 1
        except ValueError:
            continue
    usable = [i for i, c in enumerate(columns) if c not in ("—", "-", "–")]
    dice_.roll("1d2", reason=f"fudge: 2.7.3.1a row for dungeon level "
               f"{dungeon_level} doesn't cover roll {roll.total}; using "
               "the deepest available column", fudge=True)
    return (usable[-1] + 1) if usable else 1


def _roll_monster(dice_: Dice, dungeon_level: int) -> str:
    level = _monster_level(dice_, dungeon_level)
    letter = _MONSTER_LEVEL_LETTERS[min(level, 10) - 1]
    table_id = f"2.7.3.2{letter}"
    row, _ = _row_d100(dice_, table_id, f"{table_id}: monster", min_fields=4)
    name = " ".join(row[1:-2]).rstrip(",")
    lair_cell = row[-2]
    # A handful of entries (e.g. Rot Grub's lair count) are non-dice cells
    # like "N/A" or a flat number; only spend a roll when there's an
    # actual expression to roll.
    if _is_dice_expr(lair_cell):
        count = dice_.roll(lair_cell, reason=f"{table_id}: number in lair").total
    elif re.match(r"^\d+$", lair_cell):
        count = int(lair_cell)
    else:
        count = 1
    return f"{count} × {name}"


def _roll_treasure_amount(dice_: Dice, dungeon_level: int, guarded: bool) -> str:
    row, value = _row_d20(dice_, "d-12", "D-12: treasure amount")
    cell = " ".join(row[1:])

    if value == 20:
        return "1 magic item"
    if value == 19:
        chance = dice_.roll("1d8", reason="D-12: magic item chance (19)").total
        return "1 magic item" if chance >= 6 else "nothing of value"
    if value == 18:
        chance = dice_.roll("1d8", reason="D-12: gems or jewellery (18)").total
        if chance <= 5:
            n = dice_.roll("1d3", reason="D-12: gem count").total
            return f"{n} gems"
        return "1 piece of jewellery"

    m = re.match(r"^(\d+)d(\d+)×(\d+)\s*([a-z]+)$", cell.replace(" ", ""))
    if not m:
        return cell
    count, faces, mult, unit = m.groups()
    count = int(count) * max(1, dungeon_level)
    if guarded:
        count += 1  # "roll twice and add 1 to each roll"
        total = (dice_.roll(f"{count}d{faces}", reason="D-12: guarded coin roll").total
                 + dice_.roll(f"{count}d{faces}", reason="D-12: guarded coin roll (2nd)").total)
    else:
        total = dice_.roll(f"{count}d{faces}", reason="D-12: coin roll").total
    return f"{total * int(mult)} {unit}"


def _roll_contents(dice_: Dice, dungeon_level: int):
    """Returns (contents, monsters, treasure, discoveries) lists."""
    contents: list[str] = []
    monsters: list[str] = []
    treasure: list[str] = []
    discoveries: list[dict] = []

    _, value = _row_d20(dice_, "d-8", "D-8: room contents")

    has_monster = value in range(8, 18)
    has_treasure = value in range(12, 18) or value == 20
    is_trick_or_trap = value == 19
    is_stairs = value == 18

    if has_monster:
        monsters.append(_roll_monster(dice_, dungeon_level))

    if has_treasure:
        guarded = has_monster
        hide_roll = dice_.roll("1d6", reason="D-9: hidden/guarded treasure "
                                "(50% chance)")
        hidden = hide_roll.total <= 3
        if hidden:
            hide_row, _ = _row_d20(dice_, "d-11", "D-11: treasure hidden by/in")
            scope = " ".join(hide_row[1:]).lower()
            amount = _roll_treasure_amount(dice_, dungeon_level, guarded)
            trap_row, _ = _row_d20(dice_, "d-10", "D-10: treasure guards/wards")
            contents.append(f"trap guarding hidden treasure: {' '.join(trap_row[1:]).lower()}")
            discoveries.append({
                "what": amount,
                "trigger": {"action": "search", "scope": scope, "chance": "1-in-6", "per": "turn"},
            })
        else:
            container_row, _ = _row_d20(dice_, "d-9", "D-9: treasure container")
            container = " ".join(container_row[1:]).lower()
            amount = _roll_treasure_amount(dice_, dungeon_level, guarded)
            treasure.append(f"{amount} in {container}")

    if is_stairs:
        stair_row, _ = _row_d20(dice_, "d-13", "D-13: stairs (in-room)")
        contents.append(f"stairs: {' '.join(stair_row[1:]).lower()}")

    if is_trick_or_trap:
        trap_roll = dice_.roll("1d2", reason="2.7.2: trick or trap")
        feature_row, _ = _row_d100(dice_, "2.7.2.2a", "2.7.2.2a: trick/trap feature")
        effect_row, _ = _row_d100(dice_, "2.7.2.2b", "2.7.2.2b: trick/trap effect")
        feature = " ".join(feature_row[1:]).rstrip("*").lower()
        effect = " ".join(effect_row[1:]).lower()
        kind = "Trap" if trap_roll.total == 1 else "Trick"
        contents.append(f"{kind}: {feature} — {effect}")

    if not (has_monster or has_treasure or is_stairs or is_trick_or_trap):
        contents.append("empty")

    return contents, monsters, treasure, discoveries


# --------------------------------------------------------------------
# Top level: the seven-step walk
# --------------------------------------------------------------------

def _make_area(dice_: Dice, area_id: int, dungeon_level: int, chamber: bool, label_hint: str = ""):
    sqft, shape = _roll_size(dice_, chamber)
    n_exits = _roll_num_exits(dice_, sqft)
    contents, monsters, treasure, discoveries = _roll_contents(dice_, dungeon_level)
    desc = f"A {shape} {'chamber' if chamber else 'room'} of roughly {sqft} sq ft."
    if label_hint:
        desc = f"{label_hint} {desc}"
    area = {
        "id": area_id,
        "name": f"Area {area_id}",
        "description": desc,
        "exits": [],
        "contents": contents,
        "monsters": monsters,
        "treasure": treasure,
        "discoveries": discoveries,
    }
    return area, n_exits


def generate_dungeon(seed: int, *, target_areas: int = 12, dungeon_level: int = 1,
                      title: str = "A Generated Dungeon", return_dice: bool = False):
    """Runs the D-1..D-24 procedure and returns a module dict shaped
    exactly per the S3 campaign format (design §8.1). Same seed, same
    `target_areas`/`dungeon_level` -> byte-identical output.

    `return_dice=True` additionally returns the `Dice` instance used, so a
    caller (a test, a debugging session) can inspect `dice.log` for the
    fudges this generation made - each fudge roll is tagged `fudge=True`
    with a `reason` naming what was impossible and how it was resolved."""
    if target_areas < 1:
        raise ValueError("target_areas must be at least 1")

    dice_ = Dice(seed)
    d1_roll = dice_.roll("1d6", reason="D-1: starting area shape", table="d-1")
    start_label = _d1_labels().get(d1_roll.total, "the starting area")

    areas: dict[int, dict] = {}
    area1, n_exits = _make_area(dice_, 1, dungeon_level, chamber=True,
                                 label_hint=f"The starting area ({start_label}).")
    areas[1] = area1

    from collections import deque
    queue: deque[tuple[int, int]] = deque()
    queue.append((1, n_exits))
    next_id = 2

    while queue and target_areas > 1:
        area_id, exits_left = queue.popleft()
        for _ in range(exits_left):
            if len(areas) >= target_areas:
                continue  # budget spent - stop growing this exit onward

            wall = _roll_exit_wall(dice_)
            walked = _walk_corridor(dice_, from_chamber=True)
            if walked is None:
                if len(areas) == 1 and not queue and next_id == 2:
                    # The only area rolled and every exit dead-ended - a
                    # one-room dungeon nobody asked for. Force a passage
                    # rather than ship fewer areas than target_areas.
                    dice_.roll("1d2", reason="fudge: only area rolled 0 "
                               "usable exits; forcing a passage so the "
                               "dungeon isn't a single sealed room",
                               fudge=True)
                    walked = ("passage", False, False)
                else:
                    continue

            kind, hidden, one_way = walked
            new_area, new_n_exits = _make_area(
                dice_, next_id, dungeon_level, chamber=False,
                label_hint=f"Reached via {'an' if wall[:1] in 'aeiou' else 'a'}"
                           f" {wall} exit.")
            areas[next_id] = new_area
            areas[area_id]["exits"].append({"to": next_id, "kind": kind, "hidden": hidden})
            if not one_way:
                new_area["exits"].append({"to": area_id, "kind": kind, "hidden": hidden})
            queue.append((next_id, new_n_exits))
            next_id += 1

    # A dead final area can leave the queue empty before the budget is
    # spent (every exit came back a dead end). Keep chaining fresh areas
    # off the last one made until the budget is met, rather than ship a
    # dungeon smaller than asked for.
    starved_guard = 0
    while len(areas) < target_areas and starved_guard < target_areas * 4:
        starved_guard += 1
        source_id = max(areas)
        dice_.roll("1d2", reason=f"fudge: every exit dead-ended before "
                   f"reaching {target_areas} areas; chaining a fresh "
                   f"passage off area {source_id}", fudge=True)
        wall = _roll_exit_wall(dice_)
        new_area, new_n_exits = _make_area(
            dice_, next_id, dungeon_level, chamber=False,
            label_hint=f"Reached via {'an' if wall[:1] in 'aeiou' else 'a'}"
                       f" {wall} exit.")
        areas[next_id] = new_area
        areas[source_id]["exits"].append({"to": next_id, "kind": "passage", "hidden": False})
        new_area["exits"].append({"to": source_id, "kind": "passage", "hidden": False})
        next_id += 1

    ordered_areas = [areas[i] for i in sorted(areas)]

    # One dungeon-wide wandering region, per §2.7.3.1's "roll a d20, cross-
    # reference the dungeon level" directions - the check cadence is the
    # OSRIC standard (1-in-6 per turn).
    wandering_names = []
    for _ in range(8):
        level = _monster_level(dice_, dungeon_level)
        letter = _MONSTER_LEVEL_LETTERS[min(level, 10) - 1]
        row, _ = _row_d100(dice_, f"2.7.3.2{letter}", "wandering table stock", min_fields=4)
        wandering_names.append(" ".join(row[1:-2]).rstrip(","))

    doc = {
        "module": {
            "title": title,
            "version": "1.0",
            "party_guidance": {"size": [4, 6], "total_levels": [dungeon_level, dungeon_level + 2]},
            "background": f"Generated by sanctuary.procgen, seed {seed}, dungeon level {dungeon_level}.",
            "start": f"The party stands at area 1, {start_label}.",
        },
        "regions": [
            {
                "id": "whole-dungeon",
                "areas": [1, next_id - 1],
                "check": {"chance": "1-in-6", "every": "1 turn"},
                "table": {"die": "d8", "entries": wandering_names},
            }
        ],
        "areas": ordered_areas,
        "monsters": [],
        "items": [],
        "mechanics": [],
    }
    return (doc, dice_) if return_dice else doc


def fudges(dice_: Dice) -> list:
    """Every roll in `dice_.log` tagged `fudge=True` - the book's "freely
    fudge impossible results" cases (see `generate_dungeon`'s
    `return_dice`), logged rather than hidden."""
    return [r for r in dice_.log if r.tags.get("fudge")]


def reachable_area_ids(doc: dict) -> set:
    """BFS over `exits` from area 1, with zero items - every exit this
    generator emits is passable by an empty-handed party (a hidden exit
    needs finding, not an item; a trap needs a save, not a key), so plain
    graph reachability IS progressive reach here. Re-derived independently
    of the construction that built the graph, not trusted from it."""
    by_id = {a["id"]: a for a in doc["areas"]}
    if not by_id:
        return set()
    start = min(by_id)
    seen = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for exit_ in by_id[current].get("exits") or []:
            to = exit_["to"]
            if to in by_id and to not in seen:
                seen.add(to)
                frontier.append(to)
    return seen
