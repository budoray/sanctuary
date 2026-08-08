"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import secrets
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.engine import bestiary, items, resolve, validate
from backend.app.engine.ai_dm import AIDM, AIDMCallbacks
from backend.app.engine.character import Character, to_hit_target
from backend.app.engine.dice import Dice, Roll
from backend.app.engine.module import Module, MonsterSpawn
from backend.app.engine.narrator import Narrator


narrator = Narrator()


def _roll_to_dict(r: Roll) -> dict[str, Any]:
    return {
        "index": r.index,
        "expr": r.expr,
        "faces": list(r.faces),
        "kept": list(r.kept),
        "mods": r.mods,
        "total": r.total,
        "reason": r.reason,
        "tags": dict(r.tags),
    }


PHASE_PLAYER = "player"
PHASE_DM = "dm"
STATUS_ACTIVE = "active"
STATUS_WON = "won"
STATUS_LOST = "lost"

RANGED_RANGE = 4

TILE_HAZARD_1 = "3"
TILE_HAZARD_2 = "4"
TILE_LAVA = TILE_HAZARD_1
TILE_SPIKES = TILE_HAZARD_2
TILE_EVENT = "5"

# Theme-aware hazard tiles. Most deal damage; ice has a special slip effect.
THEME_HAZARDS: dict[str | None, dict[str, tuple[str, str]]] = {
    "dungeon": {TILE_HAZARD_1: ("ember coals", "1d4"), TILE_HAZARD_2: ("spikes", "1d8")},
    "cave": {TILE_HAZARD_1: ("lava", "1d6"), TILE_HAZARD_2: ("spikes", "1d8")},
    "library": {TILE_HAZARD_1: ("cursed tome", "1d4"), TILE_HAZARD_2: ("falling shelf", "1d6")},
    "ice": {TILE_HAZARD_1: ("ice", "slip"), TILE_HAZARD_2: ("frost", "1d4")},
    "lava": {TILE_HAZARD_1: ("lava", "1d6"), TILE_HAZARD_2: ("magma", "1d8")},
    "forest": {TILE_HAZARD_1: ("brush", "cover"), TILE_HAZARD_2: ("poison thorns", "1d6")},
    "tomb": {TILE_HAZARD_1: ("sarcophagus trap", "1d6"), TILE_HAZARD_2: ("falling stone", "1d8")},
    "sewer": {TILE_HAZARD_1: ("toxic water", "1d6"), TILE_HAZARD_2: ("sewage geyser", "1d8")},
}

ARENA_BASE_WAVE_TEMPLATES = ["goblin", "orc", "skeleton", "ghoul", "zombie"]

MONSTER_XP = {
    "goblin": 50,
    "skeleton": 40,
    "zombie": 60,
    "ghoul": 80,
    "orc": 70,
}


def _xp_value(monster_name: str) -> int:
    return MONSTER_XP.get(monster_name.lower().split()[0], 50)


def _character_for_token(token: dict[str, Any]) -> Character:
    """Reconstruct a minimal Character from a player token for OSRIC helpers."""
    return Character(
        name=token.get("name", ""),
        ancestry=token.get("ancestry", "human"),
        classes=tuple(token.get("classes", [])),
        levels=token.get("levels", {}),
        scores=token.get("scores", {}),
        hit_points=token.get("max_hp", token.get("hp", 1)),
        armour_class=token.get("ac", 10),
        saves=token.get("saves", {}),
        modifiers=token.get("modifiers", {}),
        seed=token.get("seed", 0),
        log=tuple(),
    )


def _player_to_hit_target(token: dict[str, Any], target_ac: int) -> int:
    """Best class to-hit target for a player token, with AC extrapolation.

    OSRIC tables span AC 10 to -10. For absurd test ACs outside that span we
    extrapolate from the nearest table edge so the engine still resolves.
    """
    classes = token.get("classes", [])
    levels = token.get("levels", {})
    if not classes:
        return 20

    def _target_at(ac: int) -> int:
        return min(to_hit_target(c, levels.get(c, 1), ac) for c in classes)

    if target_ac > 10:
        return _target_at(10) - (target_ac - 10)
    if target_ac < -10:
        return _target_at(-10) + (-10 - target_ac)
    return _target_at(target_ac)


def _monster_to_hit_target(token: dict[str, Any], target_ac: int) -> int:
    """HD-based to-hit target for a monster token, with AC extrapolation."""
    hd = token.get("hit_dice", "1")
    if target_ac > 10:
        base = resolve.monster_to_hit_target(hd, 10)
        return base - (target_ac - 10)
    if target_ac < -10:
        base = resolve.monster_to_hit_target(hd, -10)
        return base + (-10 - target_ac)
    return resolve.monster_to_hit_target(hd, target_ac)


def _target_number(attacker: dict[str, Any], target_ac: int) -> int:
    if attacker["type"] == "player":
        return _player_to_hit_target(attacker, target_ac)
    return _monster_to_hit_target(attacker, target_ac)


def _attacker_to_hit_bonus(token: dict[str, Any]) -> int:
    """Sum magic/situational and (for players) Strength to-hit modifiers."""
    bonus = token.get("to_hit", 0)
    if token["type"] == "player":
        bonus += token.get("modifiers", {}).get("hit", 0)
    return bonus


def _attacker_damage_bonus(token: dict[str, Any]) -> int:
    """Sum magic/situational and (for players) Strength damage modifiers."""
    bonus = token.get("damage_bonus", 0)
    if token["type"] == "player":
        bonus += token.get("modifiers", {}).get("damage", 0)
    return bonus


def saving_throw(d: Dice, subject: dict[str, Any], category: str,
                 natural_20_auto_succeeds: bool = False) -> resolve.SaveResult:
    """Resolve a saving throw for a player or monster token."""
    if subject["type"] == "player":
        return resolve.saving_throw(d, _character_for_token(subject), category,
                                    natural_20_auto_succeeds=natural_20_auto_succeeds)
    hd = subject.get("hit_dice", "1")
    return resolve.saving_throw(d, hd, category, natural_20_auto_succeeds=natural_20_auto_succeeds)


def _hd_base(hit_dice: str) -> float:
    """Base hit-dice count for morale calculations."""
    return resolve._hd_base_and_bonus(hit_dice)[0]


async def _check_morale(state: dict[str, Any], monster: dict[str, Any]) -> None:
    """Roll morale when a monster first drops to 50% HP or below."""
    if not monster.get("alive", True):
        return
    max_hp = monster.get("max_hp", max(monster["hp"], 1))
    if max_hp <= 0:
        return
    if monster.get("morale_checked_50"):
        return
    if monster["hp"] > max_hp / 2:
        return
    monster["morale_checked_50"] = True
    d = Dice(seed=state["seed"] + state["version"] + sum(ord(c) for c in monster["id"]))
    result = resolve.morale(d, _hd_base(monster.get("hit_dice", "1")))
    state["log"].append(
        f"{monster['name']} checks morale: {result.outcome} "
        f"(base {result.base}%, rolled {result.roll})."
    )
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)


async def _morale_for_leader_death(state: dict[str, Any], leader: dict[str, Any]) -> None:
    """Roll morale for surviving monsters when a boss/leader dies."""
    if not leader.get("boss"):
        return
    for monster in state["monsters"]:
        if monster is leader or not monster.get("alive", True):
            continue
        d = Dice(seed=state["seed"] + state["version"] + sum(ord(c) for c in monster["id"]))
        result = resolve.morale(d, _hd_base(monster.get("hit_dice", "1")))
        state["log"].append(
            f"{monster['name']} sees {leader['name']} fall and checks morale: "
            f"{result.outcome} (base {result.base}%, rolled {result.roll})."
        )
        state["rolls"].extend(_roll_to_dict(r) for r in d.log)


def _hit_die_for_class(class_name: str) -> str:
    cls = class_name.lower()
    if cls == "fighter":
        return "1d10"
    if cls in ("cleric", "thief"):
        return "1d8"
    if cls in ("magic-user", "illusionist"):
        return "1d4"
    return "1d6"


def _roll_hp(monster: dict, d: Dice) -> int:
    total = monster["hp_adjustment"]
    for _ in range(monster["hp_dice_count"]):
        total += d.roll(f"1d{monster['hp_die_faces']}", reason=f"{monster['name']} hp", kind="combat").total
    return max(1, total)


def _spawn_token(spawn, state: dict[str, Any], d: Dice,
                 monsters_dir: Path | None = None) -> dict[str, Any]:
    """Create a live monster token from a MonsterSpawn."""
    if monsters_dir is None:
        md = state.get("monsters_dir")
        if md:
            monsters_dir = Path(md)
    template = bestiary.load(spawn.monster, monsters_dir=monsters_dir)
    token = {
        "id": spawn.id,
        "name": spawn.name,
        "type": "monster",
        "monster": spawn.monster,
        "x": spawn.x,
        "y": spawn.y,
        "hp": _roll_hp(template, d),
        "max_hp": _roll_hp(template, d),
        "ac": template["ac"],
        "damage": template["damage"],
        "hit_dice": template.get("hit_dice", "1"),
        "to_hit": 0,
        "color": spawn.color,
        "alive": True,
        "xp_value": _xp_value(spawn.name),
    }
    if spawn.boss:
        token["boss"] = True
        token["phases"] = list(spawn.phases)
        token["phases_triggered"] = []
    return token


def _grant_rewards(state: dict[str, Any], monster: dict[str, Any]) -> None:
    """Award XP, gold, and possibly loot to living players when a monster dies."""
    xp_value = monster.get("xp_value", 50)
    gold_value = xp_value // 10
    for player in state["players"]:
        if not player.get("alive", True):
            continue
        player["gold"] = player.get("gold", 0) + gold_value
        player["xp"] = player.get("xp", 0) + xp_value

        # Chance for a loot drop, higher for boss monsters.
        drop_chance = 0.10
        if monster.get("boss"):
            drop_chance = 0.75
        d = Dice(seed=state["seed"] + state["version"] + sum(ord(c) for c in player["id"]))
        drop_roll = d.roll("1d100", reason=f"{player['name']} loot drop", kind="loot").total
        if drop_roll <= int(drop_chance * 100):
            loot = items.generate_loot(level=player.get("level", 1), d=d)
            player.setdefault("session_loot", []).append(loot)
            state["log"].append(f"{player['name']} loots {loot['name']} from {monster['name']}.")
        state["rolls"].extend(_roll_to_dict(r) for r in d.log)

        while player["xp"] >= player.get("level", 1) * 100:
            player["level"] = player.get("level", 1) + 1
            cls = player["classes"][0] if player.get("classes") else ""
            if cls and "levels" in player:
                player["levels"][cls] = player["levels"].get(cls, 1) + 1
            die = _hit_die_for_class(cls)
            id_seed = sum(ord(c) for c in player["id"])
            level_d = Dice(seed=state["seed"] + state["version"] + id_seed)
            roll = level_d.roll(
                die, reason=f"{player['name']} level-up hp", kind="progression"
            )
            hp_gain = max(1, roll.total)
            player["hp"] = player.get("hp", 0) + hp_gain
            player["max_hp"] = player.get("max_hp", player["hp"]) + hp_gain
            state["log"].append(f"{player['name']} reaches level {player['level']}! (+{hp_gain} HP)")
            state["rolls"].extend(_roll_to_dict(r) for r in level_d.log)


def _deadline(seconds: int) -> str | None:
    """Return an ISO UTC deadline ``seconds`` from now, or ``None`` if disabled."""
    if seconds <= 0:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _ranged_damage_for_classes(classes: list[str]) -> str:
    """Default missile damage for a player based on their first class."""
    if not classes:
        return "1d6"
    cls = classes[0].lower()
    if cls in ("magic-user", "illusionist"):
        return "1d4"
    # fighter, thief, cleric, druid and everything else default to 1d6
    return "1d6"


def _melee_damage_for_classes(classes: list[str]) -> str:
    """Default melee damage for a player based on their first class."""
    if not classes:
        return "1d6"
    cls = classes[0].lower()
    if cls == "fighter":
        return "1d8"
    if cls in ("magic-user", "illusionist"):
        return "1d4"
    # cleric, thief, druid and everything else default to 1d6
    return "1d6"


async def new_game(
    session_id: str,
    module: Module,
    character: Character,
    seed: int | None = None,
    turn_timer_seconds: int = 0,
    character_id: str | None = None,
    account_id: int | None = None,
    mode: str = "campaign",
    dungeon_links: dict[str, Any] | None = None,
    monsters_dir: Path | None = None,
) -> dict[str, Any]:
    """Create a fresh session state."""
    if seed is None:
        seed_d = Dice(seed=secrets.randbelow(1_000_000_000) + 1)
        seed = seed_d.randint(1, 1_000_000_000)
    d = Dice(seed=seed)

    px, py = module.player_start
    player = {
        "id": "player",
        "name": character.name,
        "type": "player",
        "classes": list(character.classes),
        "levels": dict(character.levels),
        "scores": dict(character.scores),
        "modifiers": dict(character.modifiers),
        "saves": dict(character.saves),
        "ancestry": character.ancestry,
        "seed": character.seed,
        "x": px,
        "y": py,
        "hp": character.hit_points,
        "max_hp": character.hit_points,
        "ac": character.armour_class,
        "damage": _melee_damage_for_classes(list(character.classes)),
        "ranged_damage": _ranged_damage_for_classes(list(character.classes)),
        "color": "#3498db",
        "character_id": character_id,
        "account_id": account_id,
        "xp": getattr(character, "xp", 0),
        "level": getattr(character, "level", 1),
        "gold": getattr(character, "gold", 0),
        "session_loot": [],
        "ai_controlled": False,
    }
    items.apply_gear(
        {"equipment": getattr(character, "equipment", {}), "inventory": list(getattr(character, "inventory", ()))},
        player,
    )
    player.setdefault("alive", True)
    player["down"] = False
    player["statuses"] = []
    player["inventory"] = _potion_inventory(
        {"equipment": getattr(character, "equipment", {}), "inventory": list(getattr(character, "inventory", ()))}
    )
    players = [player]

    monsters: list[dict[str, Any]] = []
    for spawn in module.monsters:
        monsters.append(_spawn_token(spawn, {}, d, monsters_dir=monsters_dir))

    nd = Dice(seed=seed)
    log = [
        await narrator.narrate_opening(nd, module=module.name, mode=mode),
        await narrator.narrate_room(module.name, room_type=None, rng=nd),
    ]
    if mode == "arena":
        log.append(await narrator.narrate_banter("arena", rng=nd))

    state = {
        "id": session_id,
        "module_id": module.id,
        "account_id": account_id,
        "character_id": character_id,
        "version": 0,
        "turn": 1,
        "phase": PHASE_PLAYER,
        "status": STATUS_ACTIVE,
        "seed": seed,
        "mode": mode,
        "wave": 1,
        "players": players,
        "active_player_index": 0,
        "player": player,
        "monsters": monsters,
        "log": log,
        "rolls": [_roll_to_dict(r) for r in d.log] + [_roll_to_dict(r) for r in nd.log],
        "turn_timer_seconds": max(0, turn_timer_seconds),
        "turn_deadline": _deadline(max(0, turn_timer_seconds)),
        "dm_acted_this_round": False,
        "ai_dm_enabled": True,
        "monsters_dir": str(monsters_dir) if monsters_dir else None,
        "props": [],
        "traps": [],
    }
    if dungeon_links:
        state["dungeon_links"] = dungeon_links
    return state


async def advance_module(
    state: dict[str, Any],
    next_module: Module,
    monsters_dir: Path | None = None,
) -> dict[str, Any]:
    """Advance a won campaign session to the next module.

    Player tokens keep their HP, progression, inventory, and statuses.
    Monsters, turn count, phase, and active player are reset.
    """
    if state["status"] != STATUS_WON:
        raise ValueError("session must be won to advance")

    d = Dice(seed=state["seed"] + state["version"])
    px, py = next_module.player_start

    for player in state["players"]:
        player["x"] = px
        player["y"] = py

    monsters: list[dict[str, Any]] = []
    for spawn in next_module.monsters:
        monsters.append(_spawn_token(spawn, state, d, monsters_dir=monsters_dir))

    state["module_id"] = next_module.id
    state["monsters"] = monsters
    state["turn"] = 1
    state["phase"] = PHASE_PLAYER
    state["active_player_index"] = 0
    state["dm_acted_this_round"] = False
    state["status"] = STATUS_ACTIVE
    state["campaign_stage"] = state.get("campaign_stage", 0) + 1
    state["version"] += 1
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    state["log"].append(f"— The party journeys to {next_module.name} —")
    state["props"] = []
    state["traps"] = []
    state["player"] = _active_player(state)
    return state


def _unique_monster_id(state: dict[str, Any], base_id: str) -> str:
    existing = {m["id"] for m in state.get("monsters", [])}
    if base_id not in existing:
        return base_id
    suffix = 1
    while f"{base_id}_{suffix}" in existing:
        suffix += 1
    return f"{base_id}_{suffix}"


async def dm_spawn(
    state: dict[str, Any],
    module: Module,
    monster_name: str,
    x: int,
    y: int,
    token_id: str | None = None,
    monsters_dir: Path | None = None,
    scale: float | None = None,
) -> dict[str, Any]:
    """Spawn a named monster at x, y."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not module.map.in_bounds(x, y):
        raise ValueError("target is out of bounds")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")
    if _token_at(state, x, y) is not None:
        raise ValueError("target tile is occupied")

    template = bestiary.load(monster_name, monsters_dir=monsters_dir)
    if token_id is None:
        token_id = _unique_monster_id(state, f"dm_{template['id']}")
    else:
        token_id = _unique_monster_id(state, token_id)

    spawn = MonsterSpawn(
        id=token_id,
        name=template["name"],
        monster=monster_name,
        x=x,
        y=y,
        color="#e74c3c",
    )
    d = Dice(seed=state["seed"] + state["version"])
    token = _spawn_token(spawn, state, d, monsters_dir=monsters_dir)
    scale_factor = float(scale) if scale else 1.0
    if scale_factor != 1.0:
        token["max_hp"] = max(1, round(token["max_hp"] * scale_factor))
        token["hp"] = max(1, min(token["hp"], token["max_hp"]) if token["hp"] > token["max_hp"] else round(token["hp"] * scale_factor))
        token["damage_bonus"] = token.get("damage_bonus", 0) + round((scale_factor - 1) * 2)
        token["name"] = f"{token['name']} (x{scale_factor:g})"
    state["monsters"].append(token)
    state["version"] += 1
    state["log"].append(f"The DM spawns {token['name']} at ({x}, {y}).")
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    return token


async def dm_move(
    state: dict[str, Any], module: Module, token_id: str, x: int, y: int
) -> dict[str, Any]:
    """Move any monster to x, y."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    token = next(
        (m for m in state.get("monsters", []) if m["id"] == token_id and m.get("alive", True)),
        None,
    )
    if token is None:
        raise ValueError("monster not found")
    if not module.map.in_bounds(x, y):
        raise ValueError("target is out of bounds")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")
    if _token_at(state, x, y) is not None:
        raise ValueError("target tile is occupied")
    token["x"] = x
    token["y"] = y
    state["version"] += 1
    state["log"].append(f"The DM moves {token['name']} to ({x}, {y}).")
    return token


async def dm_damage(
    state: dict[str, Any], token_id: str, amount: int
) -> dict[str, Any]:
    """Apply damage to a monster or player."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    token = next(
        (t for t in _tokens(state) if t["id"] == token_id and t.get("alive", True)),
        None,
    )
    if token is None:
        raise ValueError("token not found")
    amount = int(amount)
    if amount <= 0:
        raise ValueError("damage amount must be positive")

    token["hp"] -= amount
    state["log"].append(f"The DM deals {amount} damage to {token['name']}.")
    if token["type"] == "player":
        if token["hp"] <= -11:
            token["alive"] = False
            token["down"] = True
            token["hp"] = 0
            _check_loss(state)
        elif token["hp"] <= 0:
            token["hp"] = 0
            token["down"] = True
    else:
        if token["hp"] <= 0:
            token["alive"] = False
            token["hp"] = 0
            _grant_rewards(state, token)
            _check_victory(state)
    state["version"] += 1
    return token


async def dm_reveal(
    state: dict[str, Any], module: Module, x: int, y: int, radius: int
) -> None:
    """Reveal a radius of fog for all players."""
    radius = int(radius)
    if radius < 0 or radius > 20:
        raise ValueError("radius must be between 0 and 20")
    revealed = state.setdefault("dm_revealed", set())
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if abs(dx) + abs(dy) <= radius:
                tx, ty = x + dx, y + dy
                if module.map.in_bounds(tx, ty):
                    revealed.add(f"{tx},{ty}")
    state["version"] += 1
    state["log"].append(f"The DM reveals the fog around ({x}, {y}).")


_PROP_TYPES = {"barrel", "rubble", "torch"}


async def dm_prop(
    state: dict[str, Any],
    module: Module,
    prop_type: str,
    x: int,
    y: int,
    variant: str | None = None,
) -> dict[str, Any]:
    """Place or remove a decorative environment prop."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not module.map.in_bounds(x, y):
        raise ValueError("target is out of bounds")

    props = state.setdefault("props", [])

    if prop_type == "clear":
        before = len(props)
        props[:] = [p for p in props if not (p.get("x") == x and p.get("y") == y)]
        if len(props) == before:
            raise ValueError("no prop at target tile")
        state["version"] += 1
        state["log"].append(f"The DM clears props at ({x}, {y}).")
        return {"cleared": True, "x": x, "y": y}

    if prop_type not in _PROP_TYPES:
        raise ValueError(f"unknown prop type: {prop_type}")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")

    prop_id = f"prop_{len(props)}_{x}_{y}"
    prop = {
        "id": prop_id,
        "type": prop_type,
        "x": int(x),
        "y": int(y),
        "variant": variant or "",
    }
    props.append(prop)
    state["version"] += 1
    state["log"].append(f"The DM places a {prop_type} at ({x}, {y}).")
    return prop


async def dm_trap(
    state: dict[str, Any],
    module: Module,
    x: int,
    y: int,
    damage: str = "1d6",
) -> dict[str, Any]:
    """Place a hidden DM trap at x, y."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not module.map.in_bounds(x, y):
        raise ValueError("target is out of bounds")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")

    traps = state.setdefault("traps", [])
    trap_id = f"trap_{len(traps)}_{x}_{y}"
    trap = {
        "id": trap_id,
        "x": int(x),
        "y": int(y),
        "damage": damage,
        "triggered": False,
    }
    traps.append(trap)
    state["version"] += 1
    state["log"].append(f"The DM hides a trap at ({x}, {y}).")
    return trap


def _tokens(state: dict[str, Any]) -> list[dict[str, Any]]:
    out = list(state["players"])
    out.extend(state["monsters"])
    return out


def _ai_dm_enabled(state: dict[str, Any]) -> bool:
    """True when the AI DM should resolve monster turns automatically.

    When a human DM is assigned, the AI is disabled so the human DM can
    control monster turns.  The flag is still toggled independently and
    applies when no human DM is present.
    """
    if state.get("dm_account_id") is not None:
        return False
    return state.get("ai_dm_enabled", True)


class _AIDMCallbacks:
    """Bridge the AI policy to the session engine's action helpers."""

    def __init__(self, state: dict[str, Any], module: Module, d: Dice, nd: Dice):
        self.state = state
        self.module = module
        self.d = d
        self.nd = nd

    async def attack(self, attacker: dict[str, Any], target: dict[str, Any]) -> None:
        await _attack(self.state, attacker, target, self.d)

    async def ranged_attack(self, attacker: dict[str, Any], target: dict[str, Any]) -> None:
        await _ranged_attack(self.state, attacker, target, self.module, self.d)

    async def move(self, token: dict[str, Any], x: int, y: int) -> None:
        await _move(self.state, token, x, y, self.module, self.d)

    def line_of_sight(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        return _line_of_sight(self.state, self.module, x0, y0, x1, y1)

    def has_cover(self, target: dict[str, Any]) -> bool:
        return _has_cover(self.state, self.module, target)

    def is_flanking(self, attacker: dict[str, Any], target: dict[str, Any]) -> bool:
        return _is_flanking(self.state, attacker, target)

    def token_at(self, x: int, y: int) -> dict[str, Any] | None:
        return _token_at(self.state, x, y)


def _active_player(state: dict[str, Any]) -> dict[str, Any]:
    return state["players"][state.get("active_player_index", 0)]


_PLAYER_COLORS = [
    "#3498db",
    "#e74c3c",
    "#2ecc71",
    "#f1c40f",
    "#9b59b6",
    "#e67e22",
    "#1abc9c",
    "#34495e",
]


def _find_spawn_tile(state: dict[str, Any], module: Module) -> tuple[int, int]:
    """Return a free walkable tile near the module start or existing players."""
    start_x, start_y = module.player_start
    occupied = {(t["x"], t["y"]) for t in _tokens(state)}
    if module.map.walkable(start_x, start_y) and (start_x, start_y) not in occupied:
        return start_x, start_y

    # Prefer spreading around existing players if any are already on the map.
    seeds = [(p["x"], p["y"]) for p in state["players"]]
    if not seeds:
        seeds = [(start_x, start_y)]

    for sx, sy in seeds:
        queue: deque[tuple[int, int]] = deque([(sx, sy)])
        seen = {(sx, sy)}
        while queue:
            x, y = queue.popleft()
            if module.map.walkable(x, y) and (x, y) not in occupied:
                return x, y
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if module.map.in_bounds(nx, ny) and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    queue.append((nx, ny))

    # Fallback to the module start even if occupied; the caller must decide.
    return start_x, start_y


async def add_player(
    state: dict[str, Any],
    module: Module,
    character: Character,
    character_id: str,
    account_id: int,
) -> dict[str, Any]:
    """Add a new party member to an existing session."""
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("session is not active")

    player_id = f"player_{len(state['players'])}"
    x, y = _find_spawn_tile(state, module)
    token = {
        "id": player_id,
        "name": character.name,
        "type": "player",
        "classes": list(character.classes),
        "levels": dict(character.levels),
        "scores": dict(character.scores),
        "modifiers": dict(character.modifiers),
        "saves": dict(character.saves),
        "ancestry": character.ancestry,
        "seed": character.seed,
        "x": x,
        "y": y,
        "hp": character.hit_points,
        "max_hp": character.hit_points,
        "ac": character.armour_class,
        "damage": _melee_damage_for_classes(list(character.classes)),
        "ranged_damage": _ranged_damage_for_classes(list(character.classes)),
        "color": _PLAYER_COLORS[len(state["players"]) % len(_PLAYER_COLORS)],
        "character_id": character_id,
        "account_id": account_id,
        "alive": True,
        "xp": getattr(character, "xp", 0),
        "level": getattr(character, "level", 1),
        "gold": getattr(character, "gold", 0),
        "session_loot": [],
        "ai_controlled": False,
    }
    items.apply_gear(
        {"equipment": getattr(character, "equipment", {}), "inventory": list(getattr(character, "inventory", ()))},
        token,
    )
    token.setdefault("alive", True)
    token["down"] = False
    token["statuses"] = []
    token["inventory"] = _potion_inventory(
        {"equipment": getattr(character, "equipment", {}), "inventory": list(getattr(character, "inventory", ()))}
    )
    state["players"].append(token)
    state["version"] += 1
    state["log"].append(f"{character.name} joins the party.")
    return token


def _token_at(state: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for t in _tokens(state):
        if t.get("alive", True) and t["x"] == x and t["y"] == y:
            return t
    return None


def _adjacent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) == 1


async def _move(state: dict[str, Any], token: dict[str, Any], x: int, y: int, module: Module, d: Dice) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")
    if _token_at(state, x, y) is not None:
        raise ValueError("target tile is occupied")
    if not _adjacent(token, {"x": x, "y": y}):
        raise ValueError("must move to an adjacent tile")
    token["x"] = x
    token["y"] = y
    nd = Dice(seed=state["seed"] + state["version"])
    line = await narrator.narrate_move(token, nd)
    if line:
        state["log"].append(line)

    # Traps are marked with tile '2'. Trigger on a 1 in 6.
    if module.map.in_bounds(x, y) and module.map.tiles[y][x] == "2":
        trigger_roll = d.roll("1d6", reason="trap trigger", kind="trap").total
        if trigger_roll == 1:
            damage_roll = d.roll("1d6", reason="trap damage", kind="trap")
            damage = max(1, damage_roll.total)
            # Physical traps allow a save vs. aimed magic items for half damage.
            save = saving_throw(d, token, "aimed_magic_items")
            if save.success:
                damage = max(1, damage // 2)
                save_msg = f" {token['name']} saves for half damage."
            else:
                save_msg = ""
            token["hp"] -= damage
            if token["type"] == "player":
                if token["hp"] <= -11:
                    token["alive"] = False
                    token["down"] = True
                    token["hp"] = 0
                    _check_loss(state)
                elif token["hp"] <= 0:
                    token["hp"] = 0
                    token["down"] = True
            trap_line = await narrator.narrate_trap(
                "a hidden trap",
                triggered=True,
                rng=nd,
            )
            state["log"].append(f"{trap_line} {token['name']} suffers {damage} damage.{save_msg}")

    # DM-placed traps trigger on entry (always, once).
    for trap in state.get("traps", []):
        if trap.get("triggered") or trap["x"] != x or trap["y"] != y:
            continue
        trap["triggered"] = True
        dmg_roll = d.roll(trap.get("damage", "1d6"), reason="trap damage", kind="trap")
        damage = max(1, dmg_roll.total)
        save = saving_throw(d, token, "aimed_magic_items")
        save_msg = ""
        if save.success:
            damage = max(1, damage // 2)
            save_msg = f" {token['name']} saves for half damage."
        token["hp"] -= damage
        if token["type"] == "player":
            if token["hp"] <= -11:
                token["alive"] = False
                token["down"] = True
                token["hp"] = 0
                _check_loss(state)
            elif token["hp"] <= 0:
                token["hp"] = 0
                token["down"] = True
        state["log"].append(f"{token['name']} trips a hidden trap and suffers {damage} damage.{save_msg}")
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)

    # Theme-aware hazard tiles: 3 and 4.
    tile = module.map.tiles[y][x] if module.map.in_bounds(x, y) else "0"
    hazards = THEME_HAZARDS.get(module.map.theme, THEME_HAZARDS["dungeon"])
    if tile in hazards:
        await _apply_hazard(state, token, tile, module.map.theme, d, module)

    # Event/branch tile: 5.
    if tile == TILE_EVENT:
        _trigger_event(state, module, x, y)

    # Dungeon room transitions (user-built dungeons).
    links = state.get("dungeon_links") or getattr(module, "dungeon_links", None)
    if links:
        transition = links.get(f"{x},{y}")
        if transition:
            token["x"] = transition["x"]
            token["y"] = transition["y"]
            kind = transition.get("kind", "passage")
            state["log"].append(
                f"{token['name']} takes the {kind} to another area."
            )


async def _apply_hazard(state: dict[str, Any], token: dict[str, Any], tile: str, theme: str | None, d: Dice, module: Module | None = None) -> None:
    """Apply theme-aware hazard damage or effects to a token on a hazard tile."""
    hazards = THEME_HAZARDS.get(theme, THEME_HAZARDS["dungeon"])
    name, expr = hazards[tile]
    nd = Dice(seed=state["seed"] + state["version"])

    if expr == "slip":
        # Ice: chance to slide one tile in a random direction.
        slip_roll = d.roll("1d6", reason="ice slip", kind="hazard").total
        if slip_roll <= 2 and module is not None:
            dx = d.choice([-1, 0, 1], reason="ice slip dx", kind="hazard")
            dy = d.choice([-1, 0, 1], reason="ice slip dy", kind="hazard")
            nx, ny = token["x"] + dx, token["y"] + dy
            if module.map.in_bounds(nx, ny) and module.map.walkable(nx, ny) and _token_at(state, nx, ny) is None:
                token["x"] = nx
                token["y"] = ny
                state["log"].append(f"{token['name']} slips on the ice and slides.")
            else:
                state["log"].append(f"{token['name']} slips on the ice but catches themself.")
        state["rolls"].extend(_roll_to_dict(r) for r in nd.log)
        return

    if expr == "cover":
        # Forest brush: grant temporary cover status.
        token.setdefault("statuses", []).append({"type": "cover", "duration": 1})
        state["log"].append(f"{token['name']} takes cover in the brush.")
        state["rolls"].extend(_roll_to_dict(r) for r in nd.log)
        return

    damage_roll = d.roll(expr, reason=f"{name} damage", kind="hazard")
    damage = max(1, damage_roll.total)
    token["hp"] -= damage
    hazard_line = await narrator.narrate_hazard(
        name, token.get("name", "someone"), rng=nd
    )
    state["log"].append(f"{hazard_line} {token['name']} suffers {damage} damage.")
    if token["type"] == "player":
        if token["hp"] <= -11:
            token["alive"] = False
            token["down"] = True
            token["hp"] = 0
            _check_loss(state)
        elif token["hp"] <= 0:
            token["hp"] = 0
            token["down"] = True
    else:
        if token["hp"] <= 0:
            token["alive"] = False
            token["hp"] = 0
            _grant_rewards(state, token)
            _check_victory(state)
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


def _trigger_event(state: dict[str, Any], module: Module, x: int, y: int) -> None:
    """Fire a map event when a player steps on an event tile."""
    for event in module.events:
        if event.x == x and event.y == y:
            state["pending_branch"] = event.id
            state["log"].append(event.message)
            choices = " ".join(f"[{k}: {v}]" for k, v in event.choices.items())
            state["log"].append(f"Choose a path: {choices}")
            return


def _spawn_branch(state: dict[str, Any], module: Module, branch_id: str, d: Dice) -> None:
    """Spawn the monsters for a chosen branch."""
    branch = next((b for b in module.branches if b.id == branch_id), None)
    if branch is None:
        raise ValueError(f"unknown branch: {branch_id!r}")
    for spawn in branch.monsters:
        state["monsters"].append(_spawn_token(spawn, state, d))
    state["log"].append(f"The {branch_id} branch reveals its guardians.")
    state.pop("pending_branch", None)


async def _check_boss_phase(state: dict[str, Any], monster: dict[str, Any]) -> None:
    """Trigger boss phase transitions when HP crosses configured thresholds."""
    if not monster.get("boss") or not monster.get("alive", True):
        return
    phases = monster.get("phases", [])
    triggered = set(monster.get("phases_triggered", []))
    max_hp = monster.get("max_hp", max(monster["hp"], 1))
    ratio = monster["hp"] / max_hp
    for i, phase in enumerate(phases):
        if i in triggered:
            continue
        threshold = phase.get("hp_threshold", 0)
        if ratio <= threshold:
            triggered.add(i)
            monster["damage_bonus"] = monster.get("damage_bonus", 0) + phase.get("damage_bonus", 0)
            monster["to_hit"] = monster.get("to_hit", 0) + phase.get("to_hit_bonus", 0)
            for spawn in phase.get("spawn", []):
                ms = MonsterSpawn(
                    id=spawn["id"],
                    name=spawn["name"],
                    monster=spawn["monster"],
                    x=spawn["x"],
                    y=spawn["y"],
                    color=spawn.get("color", "#e74c3c"),
                )
                d = Dice(seed=state["seed"] + state["version"] + len(state["monsters"]))
                state["monsters"].append(_spawn_token(ms, state, d))
            state["log"].append(
                await narrator.narrate_phase_transition(monster["name"], phase)
            )
    monster["phases_triggered"] = list(triggered)


def _line_of_sight(state: dict[str, Any], module: Module, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Simple grid ray-cast (Bresenham) returning False if any tile between
    source and target (inclusive of target, exclusive of source) is a wall.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while (x, y) != (x1, y1):
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
        if (x, y) != (x0, y0) and not module.map.walkable(x, y):
            return False
    return True


def _ranged_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])


def _potion_inventory(character_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only potion/consumable items from a character's inventory."""
    out = []
    for item in character_state.get("inventory", ()):
        if item.get("slot") == "consumable" or item.get("type") == "potion":
            out.append(dict(item))
    return out


def _is_undead(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in ("skeleton", "zombie", "ghoul", "wraith", "spectre", "vampire"))


def _has_cover(state: dict[str, Any], module: Module, target: dict[str, Any]) -> bool:
    """True if the target is adjacent to a wall or standing in forest brush."""
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        x, y = target["x"] + dx, target["y"] + dy
        if module.map.in_bounds(x, y) and module.map.tiles[y][x] == "1":
            return True
    # Forest brush tiles grant cover.
    if module.map.theme == "forest":
        tile = module.map.tiles[target["y"]][target["x"]]
        if tile == TILE_HAZARD_1:
            return True
    return False


def _is_flanking(state: dict[str, Any], attacker: dict[str, Any], target: dict[str, Any]) -> bool:
    """True if a living ally of the attacker is on the opposite side of the target."""
    dx = attacker["x"] - target["x"]
    dy = attacker["y"] - target["y"]
    if abs(dx) + abs(dy) != 1:
        return False
    opposite_x = target["x"] - dx
    opposite_y = target["y"] - dy
    allies = state["monsters"] if attacker["type"] == "monster" else state["players"]
    for token in allies:
        if (
            token.get("alive", True)
            and not token.get("down", False)
            and token["id"] != attacker["id"]
            and token["x"] == opposite_x
            and token["y"] == opposite_y
        ):
            return True
    return False


def _check_loss(state: dict[str, Any]) -> None:
    """Set session to lost if every player is dead or downed."""
    if state["status"] != STATUS_ACTIVE:
        return
    players = state.get("players", [])
    if players and all((not p.get("alive", True)) or p.get("down", False) for p in players):
        state["status"] = STATUS_LOST


def _check_victory(state: dict[str, Any]) -> None:
    """Set session to won if all monsters are dead.

    In arena mode the fight continues until the player falls, so victories
    are handled by wave spawning instead.
    """
    if state["status"] != STATUS_ACTIVE:
        return
    if state.get("mode") == "arena":
        return
    if all(not m.get("alive", True) for m in state["monsters"]):
        state["status"] = STATUS_WON


def _tick_statuses(state: dict[str, Any]) -> None:
    """Apply status effects and decrement durations at the start of a turn."""
    for token in _tokens(state):
        if not token.get("alive", True):
            continue
        statuses = token.get("statuses", [])
        if not statuses:
            continue
        remaining: list[dict[str, Any]] = []
        for status in statuses:
            duration = status.get("duration", 1)
            if status.get("type") == "poisoned" and "damage" in status:
                token["hp"] -= status["damage"]
                state["log"].append(f"{token['name']} suffers {status['damage']} poison damage.")
                if token["type"] == "player" and token["hp"] <= -11:
                    token["alive"] = False
                    token["down"] = True
                    token["hp"] = 0
                elif token["type"] == "player" and token["hp"] <= 0:
                    token["hp"] = 0
                    token["down"] = True
                elif token["type"] != "player" and token["hp"] <= 0:
                    token["alive"] = False
                    token["hp"] = 0
            duration -= 1
            if duration > 0:
                remaining.append({**status, "duration": duration})
        token["statuses"] = remaining
    _check_loss(state)


async def _attack(state: dict[str, Any], attacker: dict[str, Any], target: dict[str, Any], d: Dice) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not _adjacent(attacker, target):
        raise ValueError("target is not adjacent")
    if not target.get("alive", True):
        raise ValueError("target is already dead")

    to_hit = _attacker_to_hit_bonus(attacker)
    if attacker["type"] == "player" and _is_flanking(state, attacker, target):
        to_hit += 2
    needed = _target_number(attacker, target["ac"])
    roll_obj = d.roll("1d20", reason=f"{attacker['name']} attacks {target['name']}", kind="combat")
    roll = roll_obj.total + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        damage_expr = attacker.get("damage", "1d6")
        damage_bonus = _attacker_damage_bonus(attacker)
        dmg_roll = d.roll(damage_expr, mods=damage_bonus, reason="damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        if target["type"] == "monster":
            target["last_wounded_by"] = attacker["id"]
        if target["type"] == "player":
            if target["hp"] <= -11:  # below -10
                fatal = True
                target["alive"] = False
                target["down"] = True
                target["hp"] = 0
                _check_loss(state)
            elif target["hp"] <= 0:
                target["hp"] = 0
                target["down"] = True
        else:
            await _check_boss_phase(state, target)
            await _check_morale(state, target)
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)
                if target.get("boss"):
                    await _morale_for_leader_death(state, target)

    nd = Dice(seed=state["seed"] + state["version"])
    lines = await narrator.narrate_attack(
        attacker, target, hit, fatal, nd
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


async def _ranged_attack(
    state: dict[str, Any],
    attacker: dict[str, Any],
    target: dict[str, Any],
    module: Module,
    d: Dice,
) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not target.get("alive", True):
        raise ValueError("target is already dead")
    dist = _ranged_distance(attacker, target)
    if dist > RANGED_RANGE:
        raise ValueError("target is out of range")
    if not _line_of_sight(state, module, attacker["x"], attacker["y"], target["x"], target["y"]):
        raise ValueError("no line of sight")

    to_hit = _attacker_to_hit_bonus(attacker)
    if _has_cover(state, module, target):
        to_hit -= 2  # descending AC: cover is harder to hit
    needed = _target_number(attacker, target["ac"])
    roll_obj = d.roll("1d20", reason=f"{attacker['name']} shoots {target['name']}", kind="combat")
    roll = roll_obj.total + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        dmg_expr = attacker.get("ranged_damage", "1d6")
        damage_bonus = _attacker_damage_bonus(attacker)
        dmg_roll = d.roll(dmg_expr, mods=damage_bonus, reason="ranged damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        if target["type"] == "monster":
            target["last_wounded_by"] = attacker["id"]
        if target["type"] == "player":
            if target["hp"] <= -11:
                fatal = True
                target["alive"] = False
                target["down"] = True
                target["hp"] = 0
                _check_loss(state)
            elif target["hp"] <= 0:
                target["hp"] = 0
                target["down"] = True
        else:
            await _check_boss_phase(state, target)
            await _check_morale(state, target)
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)
                if target.get("boss"):
                    await _morale_for_leader_death(state, target)

    nd = Dice(seed=state["seed"] + state["version"])
    lines = await narrator.narrate_ranged_attack(
        attacker, target, hit, fatal, nd
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


async def _use_potion(state: dict[str, Any], token: dict[str, Any], d: Dice, instance_id: str | None = None) -> None:
    inventory = token.get("inventory", [])
    if instance_id is not None:
        potion_index = next((i for i, item in enumerate(inventory) if item.get("instance_id") == instance_id), None)
    else:
        potion_index = next((i for i, item in enumerate(inventory) if item.get("slot") == "consumable" or item.get("type") == "potion"), None)
    if potion_index is None:
        raise ValueError("no potion available")
    potion = inventory[potion_index]
    restore = potion.get("effects", {}).get("hp_restore", 0)
    if restore <= 0:
        raise ValueError("no potion available")
    inventory.pop(potion_index)
    before = token["hp"]
    token["hp"] = min(token.get("max_hp", token["hp"]), token["hp"] + restore)
    healed = token["hp"] - before
    state["log"].append(f"{token['name']} quaffs {potion.get('name', 'a potion')} and recovers {healed} HP.")


async def _stabilize(state: dict[str, Any], token: dict[str, Any], target_id: str) -> None:
    if token.get("down", False):
        raise ValueError("you are downed")
    target = next((p for p in state["players"] if p["id"] == target_id), None)
    if target is None:
        raise ValueError("target not found")
    if not target.get("down", False):
        raise ValueError("target is not downed")
    if not _adjacent(token, target):
        raise ValueError("must be adjacent to stabilize")
    target["down"] = False
    target["hp"] = 1
    state["log"].append(f"{token['name']} stabilizes {target['name']}; they stir with 1 HP.")


async def _ability(state: dict[str, Any], token: dict[str, Any], target_id: str, module: Module, d: Dice) -> None:
    cls = token.get("classes", [""])[0].lower()
    target = next((m for m in state["monsters"] if m["id"] == target_id), None)
    if target is None:
        raise ValueError("target not found")
    if not target.get("alive", True):
        raise ValueError("target is already dead")
    nd = Dice(seed=state["seed"] + state["version"])

    if cls == "fighter":
        if not _adjacent(token, target):
            raise ValueError("target is not adjacent")
        await _attack_with_bonuses(state, token, target, d, to_hit_bonus=0, damage_bonus=2, reason="Heavy Strike")
    elif cls == "thief":
        if not _adjacent(token, target):
            raise ValueError("target is not adjacent")
        await _attack_with_bonuses(state, token, target, d, to_hit_bonus=4, damage_bonus=2, reason="Backstab")
    elif cls == "cleric":
        if not _is_undead(target["name"]):
            raise ValueError("Turn Undead only affects undead")
        dist = _ranged_distance(token, target)
        if dist > 4:
            raise ValueError("target is out of range")
        if not _line_of_sight(state, module, token["x"], token["y"], target["x"], target["y"]):
            raise ValueError("no line of sight")
        roll = d.roll("1d20", reason=f"{token['name']} turns {target['name']}", kind="combat").total
        if roll >= 10:
            dmg_roll = d.roll("1d6", reason="Turn Undead damage", kind="combat")
            damage = max(1, dmg_roll.total)
            target["hp"] -= damage
            await _check_boss_phase(state, target)
            state["log"].append(f"{token['name']} turns the undead, dealing {damage} damage.")
            if target["hp"] <= 0:
                target["alive"] = False
                target["hp"] = 0
                _grant_rewards(state, target)
                _check_victory(state)
                if state["status"] == STATUS_WON:
                    state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
        else:
            state["log"].append(f"{token['name']} attempts to turn the undead, but it holds fast.")
    elif cls in ("magic-user", "illusionist"):
        dist = _ranged_distance(token, target)
        if dist > 6:
            raise ValueError("target is out of range")
        if not _line_of_sight(state, module, token["x"], token["y"], target["x"], target["y"]):
            raise ValueError("no line of sight")
        dmg_roll = d.roll("1d4+1", reason="Magic Missile damage", kind="combat")
        damage = max(2, dmg_roll.total)
        target["hp"] -= damage
        await _check_boss_phase(state, target)
        state["log"].append(f"{token['name']} fires a magic missile for {damage} damage.")
        if target["hp"] <= 0:
            target["alive"] = False
            target["hp"] = 0
            _grant_rewards(state, target)
            _check_victory(state)
            if state["status"] == STATUS_WON:
                state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
    else:
        raise ValueError(f"no special ability for class {cls!r}")
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


async def _resolve_aoe(
    state: dict[str, Any],
    token: dict[str, Any],
    center_x: int,
    center_y: int,
    module: Module,
    d: Dice,
) -> None:
    """Area-of-effect burst for magic-user/illusionist/cleric."""
    cls = token.get("classes", [""])[0].lower()
    if cls not in ("magic-user", "illusionist", "cleric"):
        raise ValueError("this class cannot use area abilities")
    nd = Dice(seed=state["seed"] + state["version"])
    dist = _ranged_distance(token, {"x": center_x, "y": center_y})
    if dist > 6:
        raise ValueError("center is out of range")
    if not _line_of_sight(state, module, token["x"], token["y"], center_x, center_y):
        raise ValueError("no line of sight to center")

    if cls == "cleric":
        damage_expr = "1d6"
        reason = "Holy Burst damage"
    else:
        damage_expr = "1d4+1"
        reason = "Fireball damage"

    total_damage = 0
    for monster in state["monsters"]:
        if not monster.get("alive", True):
            continue
        if max(abs(monster["x"] - center_x), abs(monster["y"] - center_y)) > 2:
            continue
        if not _line_of_sight(state, module, center_x, center_y, monster["x"], monster["y"]):
            continue
        dmg_roll = d.roll(damage_expr, reason=reason, kind="combat")
        damage = max(1, dmg_roll.total)
        monster["hp"] -= damage
        total_damage += damage
        await _check_boss_phase(state, monster)
        if monster["hp"] <= 0:
            monster["alive"] = False
            monster["hp"] = 0
            _grant_rewards(state, monster)
            _check_victory(state)
    state["log"].append(f"{token['name']} unleashes an area burst for {total_damage} total damage.")
    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


async def _attack_with_bonuses(
    state: dict[str, Any],
    attacker: dict[str, Any],
    target: dict[str, Any],
    d: Dice,
    to_hit_bonus: int,
    damage_bonus: int,
    reason: str,
) -> None:
    nd = Dice(seed=state["seed"] + state["version"])
    to_hit = _attacker_to_hit_bonus(attacker) + to_hit_bonus
    if attacker["type"] == "player" and _is_flanking(state, attacker, target):
        to_hit += 2
    needed = _target_number(attacker, target["ac"])
    roll_obj = d.roll("1d20", reason=f"{attacker['name']} {reason} {target['name']}", kind="combat")
    roll = roll_obj.total + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        damage_expr = attacker.get("damage", "1d6")
        total_bonus = _attacker_damage_bonus(attacker) + damage_bonus
        dmg_roll = d.roll(damage_expr, mods=total_bonus, reason=f"{reason} damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        if target["type"] == "monster":
            target["last_wounded_by"] = attacker["id"]
        if target["type"] == "player":
            if target["hp"] <= -11:
                fatal = True
                target["alive"] = False
                target["down"] = True
                target["hp"] = 0
                _check_loss(state)
            elif target["hp"] <= 0:
                target["hp"] = 0
                target["down"] = True
        else:
            await _check_boss_phase(state, target)
            await _check_morale(state, target)
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)
                if target.get("boss"):
                    await _morale_for_leader_death(state, target)
    state["log"].append(f"{attacker['name']} uses {reason} and {'hits' if hit else 'misses'} {target['name']}{' for ' + str(max(0, attacker.get('damage_bonus', 0) + damage_bonus)) + ' bonus damage' if hit else ''}.")
    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(nd, module=state.get("module_id")))
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)


async def _start_round(state: dict[str, Any], module: Module, d: Dice) -> None:
    """Advance the turn counter and roll initiative for the new round.

    If the DM wins initiative, the DM acts immediately before control returns
    to the players. Otherwise the players act first.
    """
    _check_loss(state)
    if state["status"] != STATUS_ACTIVE:
        state["phase"] = PHASE_DM
        state["turn_deadline"] = None
        return

    player_init = d.roll("1d6", reason="player initiative", kind="initiative").total
    dm_init = d.roll("1d6", reason="DM initiative", kind="initiative").total
    state["turn"] += 1
    state["phase"] = PHASE_PLAYER
    state["active_player_index"] = 0
    state["dm_acted_this_round"] = False
    state["player"] = _active_player(state)
    _tick_statuses(state)
    state["statuses_tick_index"] = 0
    state["turn_deadline"] = _deadline(state["turn_timer_seconds"])
    state["log"].append(f"— Turn {state['turn']} —")
    if dm_init > player_init:
        state["log"].append("The DM seizes the initiative!")
        await _run_dm_turn(state, module, d)
        _check_loss(state)
        state["dm_acted_this_round"] = True
    else:
        state["log"].append("The players act first!")


def _step_toward(
    state: dict[str, Any],
    module: Module,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> tuple[int, int] | None:
    """Return one deterministic step from ``start`` toward ``goal``.

    Prefers closing the larger axis first, then falls back to the other
    axis and finally to any free adjacent tile.
    """
    sx, sy = start
    gx, gy = goal
    dx = gx - sx
    dy = gy - sy
    candidates: list[tuple[int, int]] = []
    if dx > 0:
        candidates.append((1, 0))
    elif dx < 0:
        candidates.append((-1, 0))
    if dy > 0:
        candidates.append((0, 1))
    elif dy < 0:
        candidates.append((0, -1))
    for cdx, cdy in candidates:
        nx, ny = sx + cdx, sy + cdy
        if (
            module.map.in_bounds(nx, ny)
            and module.map.walkable(nx, ny)
            and _token_at(state, nx, ny) is None
        ):
            return nx, ny
    for cdx, cdy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        if (cdx, cdy) in candidates:
            continue
        nx, ny = sx + cdx, sy + cdy
        if (
            module.map.in_bounds(nx, ny)
            and module.map.walkable(nx, ny)
            and _token_at(state, nx, ny) is None
        ):
            return nx, ny
    return None


async def _advance_active_player(
    state: dict[str, Any], module: Module, d: Dice
) -> None:
    """Move the active-player pointer forward, running the DM turn when needed."""
    active = state.get("active_player_index", 0) + 1
    if active >= len(state["players"]):
        state["phase"] = PHASE_DM
        state["turn_deadline"] = None
        state["active_player_index"] = 0
        if _ai_dm_enabled(state):
            _tick_statuses(state)
            if not state.get("dm_acted_this_round", False):
                await _run_dm_turn(state, module, d)
            await _start_round(state, module, d)
    else:
        state["active_player_index"] = active
    if state["players"]:
        state["player"] = _active_player(state)


async def _ai_player_turn(
    state: dict[str, Any], module: Module, d: Dice
) -> None:
    """Resolve one AI-controlled player turn automatically."""
    player = _active_player(state)
    state["version"] += 1

    if not player.get("alive", True) or player.get("down", False):
        state["log"].append(f"{player['name']} is unable to act.")
        await _advance_active_player(state, module, d)
        return

    # Use a potion when badly wounded.
    max_hp = player.get("max_hp", player.get("hp", 1))
    if max_hp and player.get("hp", max_hp) <= max_hp * 0.25:
        inventory = player.get("inventory", [])
        has_potion = any(
            i.get("slot") == "consumable" or i.get("type") == "potion"
            for i in inventory
        )
        if has_potion:
            await _use_potion(state, player, d)
            await _advance_active_player(state, module, d)
            return

    # Find the nearest living monster.
    targets = [m for m in state.get("monsters", []) if m.get("alive", True)]
    if not targets:
        state["log"].append(f"{player['name']} waits; no enemies in sight.")
        await _advance_active_player(state, module, d)
        return

    target = min(
        targets,
        key=lambda m: abs(m["x"] - player["x"]) + abs(m["y"] - player["y"]),
    )

    if _adjacent(player, target):
        await _attack(state, player, target, d)
        await _advance_active_player(state, module, d)
        return

    if (
        _ranged_distance(player, target) <= RANGED_RANGE
        and _line_of_sight(state, module, player["x"], player["y"], target["x"], target["y"])
    ):
        await _ranged_attack(state, player, target, module, d)
        await _advance_active_player(state, module, d)
        return

    step = _step_toward(state, module, (player["x"], player["y"]), (target["x"], target["y"]))
    if step:
        await _move(state, player, step[0], step[1], module, d)
    else:
        state["log"].append(f"{player['name']} is blocked and holds.")
    await _advance_active_player(state, module, d)


async def _auto_resolve_ai_players(
    state: dict[str, Any], module: Module, d: Dice
) -> None:
    """Act for every AI-controlled player until a human player's turn arrives."""
    while (
        state["phase"] == PHASE_PLAYER
        and state["status"] == STATUS_ACTIVE
        and state["players"]
    ):
        player = _active_player(state)
        if not player.get("ai_controlled"):
            break
        await _ai_player_turn(state, module, d)


async def run_ai_players(
    state: dict[str, Any], module: Module
) -> dict[str, Any]:
    """Public helper to resolve any pending AI player turns outside ``act``."""
    d = Dice(seed=state["seed"] + state["turn"] * 1000 + state["version"])
    await _auto_resolve_ai_players(state, module, d)
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    return state


async def act(state: dict[str, Any], module: Module, action: str, **kwargs: Any) -> dict[str, Any]:
    """Perform one player or DM action and return the updated state."""
    d = Dice(seed=state["seed"] + state["turn"] * 1000 + state["version"])

    if action == "dm_turn":
        if state["phase"] != PHASE_DM:
            raise ValueError("not the DM's turn")
        _tick_statuses(state)
        if not state.get("dm_acted_this_round", False):
            await _run_dm_turn(state, module, d)
        await _start_round(state, module, d)
        await _auto_resolve_ai_players(state, module, d)

    else:
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        active_index = state.get("active_player_index", 0)
        if state.get("statuses_tick_index") != active_index:
            _tick_statuses(state)
            state["statuses_tick_index"] = active_index
        token = _active_player(state)

        # Server-side anti-cheat validation: actor and target must be legal.
        if action == "move":
            validate.validate_move(state, module, int(kwargs["x"]), int(kwargs["y"]))
        elif action in ("attack", "ability"):
            validate.validate_attack_target(state, kwargs["target_id"])
        elif action == "ranged":
            validate.validate_ranged_target(state, module, kwargs["target_id"], max_range=RANGED_RANGE)
        elif action == "aoe":
            validate.validate_actor(state)
        elif action in ("use_potion", "use_item", "end_turn"):
            validate.validate_actor(state)

        if action == "move":
            await _move(state, token, int(kwargs["x"]), int(kwargs["y"]), module, d)

        elif action == "attack":
            target_id = kwargs["target_id"]
            target = next((m for m in state["monsters"] if m["id"] == target_id), None)
            await _attack(state, token, target, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "ranged":
            target_id = kwargs["target_id"]
            target = next((m for m in state["monsters"] if m["id"] == target_id), None)
            await _ranged_attack(state, token, target, module, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "use_potion":
            await _use_potion(state, token, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "use_item":
            await _use_potion(state, token, d, instance_id=kwargs.get("instance_id"))
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "stabilize":
            if token.get("down", False):
                raise ValueError("downed players cannot stabilize")
            await _stabilize(state, token, kwargs["target_id"])
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "ability":
            target_id = kwargs["target_id"]
            target = next((m for m in state["monsters"] if m["id"] == target_id), None)
            await _ability(state, token, target_id, module, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "aoe":
            await _resolve_aoe(state, token, int(kwargs["center_x"]), int(kwargs["center_y"]), module, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "choose_path":
            branch_id = kwargs.get("branch_id")
            if not branch_id:
                raise ValueError("branch_id is required")
            _spawn_branch(state, module, branch_id, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "end_turn":
            await _advance_active_player(state, module, d)
            await _auto_resolve_ai_players(state, module, d)

        elif action == "toggle_ai_dm":
            account_id = kwargs.get("account_id")
            if account_id is None:
                raise ValueError("account_id is required")
            if account_id != state.get("account_id") and account_id != state.get("dm_account_id"):
                raise ValueError("not authorized")
            enabled = not state.get("ai_dm_enabled", True)
            state["ai_dm_enabled"] = enabled
            state["log"].append(f"AI DM {'enabled' if enabled else 'disabled'}.")

        else:
            raise ValueError(f"unknown action: {action!r}")

    state["version"] += 1
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    return state


def _nearest_player(state: dict[str, Any], monster: dict[str, Any]) -> dict[str, Any]:
    alive = [p for p in state["players"] if p.get("alive", True)]
    if not alive:
        return state["players"][0]
    return min(alive, key=lambda p: abs(p["x"] - monster["x"]) + abs(p["y"] - monster["y"]))


async def _spawn_arena_wave(
    state: dict[str, Any], module: Module, d: Dice, monsters_dir: Path | None = None
) -> None:
    """Spawn a scaled arena wave."""
    if monsters_dir is None:
        md = state.get("monsters_dir")
        if md:
            monsters_dir = Path(md)
    wave = state.get("wave", 1)
    wave_d = Dice(seed=state["seed"] + wave)
    player_level = max(p.get("level", 1) for p in state["players"])
    count = min(2 + wave, 6)
    template_name = wave_d.choice(ARENA_BASE_WAVE_TEMPLATES, reason="arena wave template", kind="arena")

    # Scale up monster HP and damage for later waves.
    hp_bonus = wave - 1
    damage_bonus = wave // 3
    to_hit_bonus = wave // 4

    spawned = 0
    for _ in range(count * 2):
        if spawned >= count:
            break
        sx = wave_d.randint(1, module.map.width - 2, reason="arena spawn x", kind="arena")
        sy = wave_d.randint(1, module.map.height - 2, reason="arena spawn y", kind="arena")
        if not module.map.walkable(sx, sy) or _token_at(state, sx, sy) is not None:
            continue
        template = bestiary.load(template_name, monsters_dir=monsters_dir)
        monster = {
            "id": f"arena_w{wave}_{spawned}",
            "name": template["name"],
            "type": "monster",
            "x": sx,
            "y": sy,
            "hp": max(1, _roll_hp(template, d) + hp_bonus),
            "max_hp": max(1, _roll_hp(template, d) + hp_bonus),
            "ac": max(0, template["ac"] - wave // 5),
            "damage": template["damage"],
            "hit_dice": template.get("hit_dice", "1"),
            "to_hit": to_hit_bonus,
            "color": "#e74c3c",
            "alive": True,
            "xp_value": _xp_value(template["name"]),
        }
        if damage_bonus:
            monster["damage_bonus"] = damage_bonus
        state["monsters"].append(monster)
        spawned += 1

    state["log"].append(f"Wave {wave} enters the arena!")
    banter = await narrator.narrate_banter("arena", rng=wave_d)
    if banter:
        state["log"].append(banter)
    state["rolls"].extend(_roll_to_dict(r) for r in wave_d.log)


async def _run_dm_turn(state: dict[str, Any], module: Module, d: Dice) -> None:
    nd = Dice(seed=state["seed"] + state["version"])
    # Hazard tiles damage tokens that end their turn standing on them.
    hazards = THEME_HAZARDS.get(module.map.theme, THEME_HAZARDS["dungeon"])
    for token in _tokens(state):
        if not token.get("alive", True):
            continue
        tile = module.map.tiles[token["y"]][token["x"]]
        if tile in hazards:
            await _apply_hazard(state, token, tile, module.map.theme, d, module)

    callbacks = _AIDMCallbacks(state, module, d, nd)
    ai = AIDM(state, module, d, callbacks)
    events = await ai.take_turn()

    if events:
        summary = await narrator.narrate_dm_turn(events, nd)
        if summary:
            state["log"].append(summary)

    _check_loss(state)
    state["rolls"].extend(_roll_to_dict(r) for r in nd.log)

    # In arena mode, spawn the next wave if all monsters are dead.
    if state.get("mode") == "arena" and state["status"] == STATUS_ACTIVE:
        if all(not m.get("alive", True) for m in state["monsters"]):
            state["wave"] = state.get("wave", 1) + 1
            await _spawn_arena_wave(state, module, d)


def view(state: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe view of the state."""
    players = []
    for p in state.get("players", []):
        token = dict(p)
        token.setdefault("xp", 0)
        token.setdefault("level", 1)
        token.setdefault("gold", 0)
        token.setdefault("alive", True)
        token.setdefault("down", False)
        token.setdefault("statuses", [])
        token.setdefault("inventory", [])
        players.append(token)
    active_index = state.get("active_player_index", 0)
    return {
        "id": state["id"],
        "module_id": state["module_id"],
        "dungeon_id": state.get("dungeon_id"),
        "account_id": state.get("account_id"),
        "character_id": state.get("character_id"),
        "campaign_id": state.get("campaign_id"),
        "dm_account_id": state.get("dm_account_id"),
        "turn": state["turn"],
        "phase": state["phase"],
        "status": state["status"],
        "mode": state.get("mode", "campaign"),
        "wave": state.get("wave", 1),
        "players": players,
        "active_player_index": active_index,
        "player": players[active_index] if players else state.get("player"),
        "monsters": state["monsters"],
        "log": state["log"],
        "turn_timer_seconds": state.get("turn_timer_seconds", 0),
        "turn_deadline": state.get("turn_deadline"),
        "dm_revealed": list(state.get("dm_revealed", [])),
        "ai_dm_enabled": _ai_dm_enabled(state),
        "props": state.get("props", []),
        "traps": state.get("traps", []),
    }
