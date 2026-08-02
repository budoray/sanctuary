"""The play runtime: a state machine over a loaded module.

Tracks party position, real elapsed time (turns), wandering-monster checks
per region, action/time-gated discoveries, combat through `sanctuary.resolve`,
and treasure/XP. `session.py` sits above this and drives it; this module
does not know or care which driver is in use.

⚠ Tier-3 abilities (design §7.2) are never silently dropped: a monster
whose special attack the engine cannot execute is flagged in
`Combat.pending_decisions`, and `attack_round` refuses to run combat until
every pending decision has been acknowledged via `decide()`.

⚠ Reproducibility is the whole guarantee: the same seed plus the same
sequence of calls against this module's public functions produces an
identical `State.dice.log` and an identical resulting state, end to end.

May import `sanctuary.module`, `sanctuary.procgen`, `sanctuary.bestiary`,
`sanctuary.treasure`, `sanctuary.resolve`, `sanctuary.character`,
`sanctuary.spells`, `sanctuary.dice` - nothing left of itself in the §5
chain (tests/test_invariants.py::test_dependency_chain_is_one_way).
"""
import re
from dataclasses import dataclass, field

from sanctuary import bestiary, resolve, treasure
from sanctuary.character import Character
from sanctuary.dice import Dice
from sanctuary.module import Module

# --------------------------------------------------------------------
# Small parsers for the module format's free-text fields. None of these
# roll dice of their own outside the `Dice` instance passed in.
# --------------------------------------------------------------------

_FIXED_QTY = re.compile(r"^(\d+)\s*[×x]\s*(.+)$")
_DICE_QTY = re.compile(r"^(\d+d\d+)\s+(.+)$")
_SEE_SUFFIX = re.compile(r"\s*\(see \w+\)\s*$", re.IGNORECASE)
_CHANCE = re.compile(r"^(\d+)-in-(\d+)$")
_EVERY = re.compile(r"^(\d+)\s*(turn|hour)s?$")
_LEAD_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?")
_HD_NOTATION = re.compile(r"^(\d+)([+-]\d+)?$")
_LEAD_INT = re.compile(r"-?\d+")
_SIMPLE_ATTACK = re.compile(r"\d+d\d+([+-]\d+)?")
_LOOT_TOKEN = re.compile(r"\b(hoard|individual|cache)\s+(\d+)\b", re.IGNORECASE)

# Design §7.2 tier-2 vocabulary: the verbs the engine actually models
# (loosely, as a keyword match over ability prose). Anything a monster
# carries that doesn't match one of these is tier 3 and gets surfaced.
_TIER2_KEYWORDS = (
    "save-or-die", "save or die", "poison", "energy drain", "level drain",
    "paraly", "breath weapon", "regenerat", "magic resist", "swallow",
    "charm", "fear", "petrif",
)


def _clean_name(name: str) -> str:
    return _SEE_SUFFIX.sub("", name).strip()


def parse_quantity_line(dice_: Dice, line: str, reason: str) -> tuple[int, str]:
    """"3 × Silt Lurker" -> (3, "Silt Lurker"); "1d4 giant rats" -> (rolled
    count, "giant rats"); "the Custodian" -> (1, "the Custodian")."""
    m = _FIXED_QTY.match(line)
    if m:
        return int(m.group(1)), _clean_name(m.group(2))
    m = _DICE_QTY.match(line)
    if m:
        n = dice_.roll(m.group(1), reason=reason).total
        return max(1, n), _clean_name(m.group(2))
    return 1, _clean_name(line)


def parse_chance(spec: str) -> tuple[int, int]:
    """"1-in-6" -> (1, 6)."""
    m = _CHANCE.match(str(spec).strip())
    if not m:
        raise ValueError(f"bad chance spec: {spec!r}")
    return int(m.group(1)), int(m.group(2))


def parse_every(spec: str) -> int:
    """"3 turns" -> 3; "1 hour" -> 6 (turns per hour, OSRIC standard)."""
    m = _EVERY.match(str(spec).strip())
    if not m:
        raise ValueError(f"bad cadence spec: {spec!r}")
    n, unit = int(m.group(1)), m.group(2)
    return n * 6 if unit == "hour" else n


def _split_attacks(text: str) -> tuple[list[str], list[str]]:
    """A monster's `melee_attacks`/`attacks` prose, split on "or" into the
    alternatives the engine can execute (a plain NdM damage die) and the
    ones it can't (tier 3 - "or the Weeping Font")."""
    parts = [p.strip() for p in re.split(r"\bor\b", text) if p.strip()]
    modeled, tier3 = [], []
    for p in parts:
        (modeled if _SIMPLE_ATTACK.search(p) else tier3).append(p)
    return modeled or [text], tier3


def _tier3_from_abilities(abilities) -> list[str]:
    out = []
    for a in abilities or []:
        if isinstance(a, dict):
            heading, text = str(a.get("heading", "")), str(a.get("text", ""))
        else:
            heading, text = "", str(a)
        blob = f"{heading} {text}".lower()
        if not any(k in blob for k in _TIER2_KEYWORDS):
            out.append(heading or text[:60])
    return out


def _hd_and_hp_expr(hit_dice_field) -> tuple[str, str]:
    """(hd_notation, hp_expr). Bestiary records write hit dice as a
    rollable expression ("1d8-1  hit points"); module-local monsters
    write OSRIC's HD notation directly ("3+1", "6"). Either way we need
    both a table-lookup notation and something `Dice.roll` accepts."""
    s = str(hit_dice_field).strip()
    m = _LEAD_DICE.match(s)
    if m:
        n, faces, mod = m.groups()
        hp_expr = f"{n}d{faces}{mod or ''}"
        if mod and mod.startswith("-"):
            notation = f"{n}-1"
        elif mod and mod.startswith("+"):
            notation = f"{n}+1"
        else:
            notation = n
        return notation, hp_expr
    m = _HD_NOTATION.match(s)
    n = m.group(1) if m else "1"
    # ponytail: a module-local monster without a dice-shaped hit_dice
    # field defaults to d8 per HD (OSRIC's standard HD). Upgrade path: add
    # a `hit_die` field to the schema if a monster needs a different one.
    return (s if m else "1"), f"{n}d8"


@dataclass
class MonsterInstance:
    name: str
    hd_notation: str
    armour_class: int
    hp: int
    max_hp: int
    attacks: list[str]
    xp: int
    loot: str = ""
    tier3: tuple[str, ...] = ()
    alive: bool = True


def _instantiate_monster(dice_: Dice, record: dict) -> MonsterInstance:
    hd_notation, hp_expr = _hd_and_hp_expr(record.get("hit_dice", "1"))
    ac_match = _LEAD_INT.match(str(record.get("armour_class", "10")))
    ac = int(ac_match.group()) if ac_match else 10
    hp = max(1, dice_.roll(hp_expr, reason=f"{record['name']} hit points").total)
    attacks_text = str(record.get("attacks") or record.get("melee_attacks") or "1d6")
    modeled, tier3 = _split_attacks(attacks_text)
    tier3 = tier3 + _tier3_from_abilities(record.get("abilities"))
    xp = record.get("xp")
    if xp is None:
        xp_m = re.search(r"\d+", str(record.get("experience", "0")))
        xp = int(xp_m.group()) if xp_m else 0
    return MonsterInstance(
        name=record["name"], hd_notation=hd_notation, armour_class=ac,
        hp=hp, max_hp=hp, attacks=modeled, xp=int(xp),
        loot=str(record.get("loot", "")), tier3=tuple(tier3),
    )


def _find_monster_record(module_: Module, name: str) -> dict | None:
    for m in module_.doc.get("monsters") or []:
        if m.get("name", "").lower() == name.lower():
            return m
    return bestiary.resolve_name(name)


# --------------------------------------------------------------------
# Runtime state
# --------------------------------------------------------------------

@dataclass
class Combat:
    monsters: list[MonsterInstance]
    round: int = 0
    unresolved: list[str] = field(default_factory=list)  # names with no record found


@dataclass
class State:
    seed: int
    dice: Dice
    module: Module
    party: list[Character]
    hp: dict
    max_hp: dict
    area_id: int
    turns: int = 0
    region_counters: dict = field(default_factory=dict)
    visited: set = field(default_factory=set)
    known_hidden_exits: set = field(default_factory=set)
    found_discoveries: set = field(default_factory=set)
    depleted_treasure: set = field(default_factory=set)
    cleared_areas: set = field(default_factory=set)
    xp: int = 0
    inventory: list = field(default_factory=list)
    combat: Combat | None = None
    combat_area_id: int | None = None
    pending_decisions: list = field(default_factory=list)
    log: list = field(default_factory=list)
    finished: bool = False


def party_key(c: Character, i: int) -> str:
    return c.name or f"pc{i}"


def new_game(module_: Module, party: list, seed: int) -> State:
    """Start a delve. `party` is a list of `character.Character`."""
    if not party:
        raise ValueError("a delve needs at least one character")
    start_id = module_.areas[0]["id"]
    hp = {party_key(c, i): c.hit_points for i, c in enumerate(party)}
    st = State(seed=seed, dice=Dice(seed), module=module_, party=list(party),
               hp=dict(hp), max_hp=dict(hp), area_id=start_id)
    st.visited.add(start_id)
    st.log.append(f"The party begins: {module_.doc['module']['start'].strip()}")
    _maybe_start_area_combat(st)
    return st


def _area(st: State, area_id: int | None = None) -> dict:
    return st.module.area(area_id if area_id is not None else st.area_id)


def _region_for(st: State, area_id: int) -> dict | None:
    for r in st.module.regions:
        lo, hi = r["areas"]
        if lo <= area_id <= hi:
            return r
    return None


def _wandering_check(st: State, region: dict) -> None:
    numerator, denom = parse_chance(region["check"]["chance"])
    roll = st.dice.roll(f"1d{denom}", reason=f"wandering check ({region['id']})",
                         kind="wandering").total
    if roll > numerator:
        return
    entries = region["table"]["entries"]
    die = region["table"]["die"]
    idx_roll = st.dice.roll(f"1{die}", reason=f"wandering table ({region['id']})",
                             kind="wandering").total
    entry = entries[(idx_roll - 1) % len(entries)]
    st.log.append(f"Wandering encounter: {entry}")
    count, name = parse_quantity_line(st.dice, entry, reason="wandering monster count")
    record = _find_monster_record(st.module, name)
    if record is None:
        st.pending_decisions.append({
            "kind": "unresolvable_monster", "name": name,
            "detail": f"the wandering table named {name!r}, which matches no "
                       "bestiary entry or module-local monster - the DM must "
                       "arbitrate this encounter directly.",
        })
        return
    monsters = [_instantiate_monster(st.dice, record) for _ in range(count)]
    _start_combat(st, monsters)


def advance_time(st: State, turns: int) -> None:
    """Elapse `turns` game-turns at the party's current area, running each
    covering region's wandering check on its own cadence."""
    if turns <= 0:
        return
    region = _region_for(st, st.area_id)
    st.turns += turns
    if region is None:
        return
    every = parse_every(region["check"]["every"])
    counter = st.region_counters.get(region["id"], 0) + turns
    while counter >= every:
        counter -= every
        _wandering_check(st, region)
        if st.combat is not None:
            break  # an encounter interrupts further checks until resolved
    st.region_counters[region["id"]] = counter


def describe(st: State) -> dict:
    area = _area(st)
    exits = [e for e in area.get("exits") or []
             if not e.get("hidden") or (st.area_id, e["to"]) in st.known_hidden_exits]
    if st.combat is not None and st.combat_area_id == st.area_id:
        monsters_here = [m.name for m in st.combat.monsters if m.alive]
    elif st.area_id in st.cleared_areas:
        monsters_here = []
    else:
        monsters_here = list(area.get("monsters") or [])
    treasure_here = [] if st.area_id in st.depleted_treasure else list(area.get("treasure") or [])
    return {
        "area_id": st.area_id,
        "name": area["name"],
        "description": area["description"],
        "exits": exits,
        "contents": area.get("contents") or [],
        "monsters": monsters_here,
        "treasure": treasure_here,
        "turns": st.turns,
        "in_combat": st.combat is not None,
        "pending_decisions": list(st.pending_decisions),
        "finished": st.finished,
    }


def _monsters_blocking(st: State) -> bool:
    return st.combat is not None and any(m.alive for m in st.combat.monsters)


def move(st: State, to_area_id: int) -> None:
    if st.finished:
        raise ValueError("the delve is already finished")
    if _monsters_blocking(st):
        raise ValueError("cannot leave while monsters are still standing")
    area = _area(st)
    exit_ = next((e for e in area.get("exits") or [] if e["to"] == to_area_id), None)
    if exit_ is None:
        raise ValueError(f"no exit from area {st.area_id} to {to_area_id}")
    if exit_.get("hidden") and (st.area_id, to_area_id) not in st.known_hidden_exits:
        raise ValueError(f"the way to area {to_area_id} has not been found yet")
    st.area_id = to_area_id
    st.visited.add(to_area_id)
    st.log.append(f"The party moves to {_area(st)['name']}.")
    advance_time(st, 1)
    _maybe_start_area_combat(st)


def _maybe_start_area_combat(st: State) -> None:
    if st.combat is not None or st.area_id in st.cleared_areas:
        return
    area = _area(st)
    lines = area.get("monsters") or []
    if not lines:
        return
    monsters, unresolved = [], []
    for line in lines:
        count, name = parse_quantity_line(st.dice, line, reason=f"area {st.area_id} monster count")
        record = _find_monster_record(st.module, name)
        if record is None:
            unresolved.append(name)
            continue
        monsters.extend(_instantiate_monster(st.dice, record) for _ in range(count))
    if monsters or unresolved:
        _start_combat(st, monsters, unresolved)


def _start_combat(st: State, monsters: list[MonsterInstance], unresolved: list[str] | None = None) -> None:
    st.combat = Combat(monsters=monsters, unresolved=list(unresolved or []))
    st.combat_area_id = st.area_id
    for m in monsters:
        if m.tier3:
            st.pending_decisions.append({
                "kind": "tier3_ability", "monster": m.name,
                "detail": f"{m.name} has abilities this engine cannot execute: "
                          f"{', '.join(m.tier3)} - the DM must adjudicate them.",
            })
    for name in st.combat.unresolved:
        st.pending_decisions.append({
            "kind": "unresolvable_monster", "name": name,
            "detail": f"{name!r} matches no bestiary entry or module-local "
                       "monster - the DM must arbitrate this encounter directly.",
        })
    st.log.append(f"Combat begins: {', '.join(m.name for m in monsters) or 'an unresolvable foe'}.")


def decide(st: State, index: int, ruling: str) -> None:
    """Acknowledge one pending tier-3/unresolvable decision with the
    player's (acting-as-DM) ruling, recorded to the log rather than
    executed - see design §7.2. Combat will not resolve rounds while any
    decision remains pending."""
    if not (0 <= index < len(st.pending_decisions)):
        raise ValueError(f"no pending decision at index {index}")
    d = st.pending_decisions.pop(index)
    st.log.append(f"Ruling on {d.get('monster') or d.get('name')}: {ruling}")
    if d.get("kind") == "unresolvable_monster" and st.combat is not None \
            and d["name"] in st.combat.unresolved:
        st.combat.unresolved.remove(d["name"])
        if st.combat.monsters and all(not m.alive for m in st.combat.monsters) \
                and not st.combat.unresolved:
            _resolve_victory(st)
        elif not st.combat.monsters and not st.combat.unresolved:
            st.combat = None
            st.cleared_areas.add(st.combat_area_id)
            st.combat_area_id = None


def attack_round(st: State, target_index: int = 0) -> dict:
    """Resolve one combat round: the party attacks `target_index` (an
    index into `combat.monsters`), then any surviving monster retaliates.
    Refuses while a tier-3/unresolvable decision is still pending - the
    engine never silently proceeds past one (design §7.2)."""
    if st.combat is None:
        raise ValueError("no combat in progress")
    if st.pending_decisions:
        raise ValueError("pending decisions must be resolved before combat can continue")
    combat = st.combat
    combat.round += 1
    alive_monsters = [m for m in combat.monsters if m.alive]
    if not alive_monsters:
        raise ValueError("no living monsters to attack - use decide() to close out combat")
    if not (0 <= target_index < len(combat.monsters)) or not combat.monsters[target_index].alive:
        target_index = combat.monsters.index(alive_monsters[0])
    target = combat.monsters[target_index]

    events = []
    for i, c in enumerate(st.party):
        key = party_key(c, i)
        if st.hp[key] <= 0 or not target.alive:
            continue
        result = resolve.attack(st.dice, c, target.armour_class, damage_expr="1d6")
        events.append({"attacker": key, "target": target.name, "hit": result.hit,
                        "damage": result.damage})
        if result.hit:
            target.hp -= result.damage or 0
            if target.hp <= 0:
                target.alive = False
                st.log.append(f"{target.name} is defeated.")

    for m_idx, m in enumerate(combat.monsters):
        if not m.alive:
            continue
        living_pcs = [(i, c) for i, c in enumerate(st.party) if st.hp[party_key(c, i)] > 0]
        if not living_pcs:
            break
        # Spread attacks round-robin across the living party rather than
        # every monster focusing the same one - a full alpha strike from
        # every attacker onto a single PC every round is not how a mob
        # actually fights, and made a single unlucky round unrecoverable.
        i, c = living_pcs[m_idx % len(living_pcs)]
        key = party_key(c, i)
        result = resolve.attack(st.dice, m.hd_notation, c.armour_class, damage_expr="1d6")
        events.append({"attacker": m.name, "target": key, "hit": result.hit,
                        "damage": result.damage})
        if result.hit:
            st.hp[key] -= result.damage or 0

    if all(st.hp[party_key(c, i)] <= 0 for i, c in enumerate(st.party)):
        st.combat = None
        st.combat_area_id = None
        st.finished = True
        st.log.append("The party is defeated.")
        return {"events": events, "combat_over": True, "party_defeated": True}

    if all(not m.alive for m in combat.monsters) and not combat.unresolved:
        _resolve_victory(st)
    elif alive_monsters:
        hd_num = re.match(r"[\d.]+", alive_monsters[0].hd_notation)
        morale_result = resolve.morale(st.dice, hit_dice=float(hd_num.group()) if hd_num else 1.0)
        if not morale_result.passed:
            for m in alive_monsters:
                m.alive = False
            st.log.append(f"The surviving monsters {morale_result.outcome}.")
            _resolve_victory(st)

    return {"events": events, "combat_over": st.combat is None}


def _resolve_victory(st: State) -> None:
    combat = st.combat
    st.combat = None
    st.cleared_areas.add(st.combat_area_id)
    st.combat_area_id = None
    total_xp = sum(m.xp for m in combat.monsters)
    st.xp += total_xp
    st.log.append(f"The party gains {total_xp} XP.")
    for m in combat.monsters:
        tokens = _LOOT_TOKEN.findall(m.loot)
        for kind, n in tokens:
            slug = f"{kind.lower()}_{n}"
            if slug in treasure.loot_class_names():
                for line in treasure.roll_hoard(st.dice, slug):
                    st.inventory.append(f"{line.amount} {line.kind} ({m.name})")


def flee(st: State) -> None:
    """Break off combat without finishing it - no XP, no treasure, the
    monsters remain standing next time the party returns."""
    if st.combat is None:
        raise ValueError("no combat to flee")
    st.combat = None
    st.pending_decisions = [d for d in st.pending_decisions if d.get("kind") != "tier3_ability"]
    st.log.append("The party flees.")


def search(st: State, scope: str | None = None) -> list[str]:
    if _monsters_blocking(st):
        raise ValueError("cannot search while monsters are still standing")
    advance_time(st, 1)
    found = []
    area = _area(st)
    for idx, disc in enumerate(area.get("discoveries") or []):
        key = (st.area_id, idx)
        if key in st.found_discoveries:
            continue
        trigger = disc["trigger"]
        if trigger.get("action") != "search":
            continue
        disc_scope = str(trigger.get("scope", "")).lower()
        if scope is not None and disc_scope and scope.lower() not in disc_scope \
                and disc_scope not in scope.lower():
            continue
        hit = True
        if trigger.get("chance"):
            numerator, denom = parse_chance(trigger["chance"])
            roll = st.dice.roll(f"1d{denom}", reason=f"discovery check ({disc['what']})",
                                 kind="discovery").total
            hit = roll <= numerator
        if hit:
            st.found_discoveries.add(key)
            found.append(disc["what"])
            st.log.append(f"Discovery: {disc['what']}")
            for e in area.get("exits") or []:
                if e.get("hidden"):
                    st.known_hidden_exits.add((st.area_id, e["to"]))
    return found


def rest(st: State, turns: int = 1) -> None:
    if _monsters_blocking(st):
        raise ValueError("cannot rest while monsters are still standing")
    advance_time(st, turns)
    st.log.append(f"The party rests {turns} turn(s).")


def take_treasure(st: State) -> list[str]:
    if _monsters_blocking(st):
        raise ValueError("cannot take treasure while monsters are still standing")
    area = _area(st)
    if st.area_id in st.depleted_treasure:
        return []
    lines = list(area.get("treasure") or [])
    st.depleted_treasure.add(st.area_id)
    st.inventory.extend(lines)
    if lines:
        st.log.append(f"The party takes: {', '.join(lines)}.")
    return lines


def leave(st: State) -> dict:
    """End the delve - the party calls it and heads back to the surface.
    Callable from anywhere with no monsters standing (a one-way chute or
    stairs down can leave a party unable to retrace its steps to area 1 -
    forcing `leave` to happen only there would make that a soft lock, the
    one thing a generated module must never be). Returns a summary of what
    the party has to show for it."""
    if _monsters_blocking(st):
        raise ValueError("cannot leave while monsters are still standing")
    st.finished = True
    st.log.append(f"The party leaves with {st.xp} XP and {len(st.inventory)} items of treasure.")
    return {"xp": st.xp, "inventory": list(st.inventory), "turns": st.turns}
