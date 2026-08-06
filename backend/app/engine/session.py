"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.engine import bestiary, items, validate
from backend.app.engine.character import Character
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

TILE_LAVA = "3"
TILE_SPIKES = "4"
TILE_EVENT = "5"

HAZARD_DAMAGE = {
    TILE_LAVA: ("lava", "1d6"),
    TILE_SPIKES: ("spikes", "1d8"),
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


def _spawn_token(spawn, state: dict[str, Any], d: Dice) -> dict[str, Any]:
    """Create a live monster token from a MonsterSpawn."""
    template = bestiary.load(spawn.monster)
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
        rng = random.Random(state["seed"] + state["version"] + sum(ord(c) for c in player["id"]))
        if rng.random() < drop_chance:
            loot = items.generate_loot(level=player.get("level", 1), rng=rng)
            player.setdefault("session_loot", []).append(loot)
            state["log"].append(f"{player['name']} loots {loot['name']} from {monster['name']}.")

        while player["xp"] >= player.get("level", 1) * 100:
            player["level"] = player.get("level", 1) + 1
            cls = player["classes"][0] if player.get("classes") else ""
            die = _hit_die_for_class(cls)
            id_seed = sum(ord(c) for c in player["id"])
            roll = Dice(seed=state["seed"] + state["version"] + id_seed).roll(
                die, reason=f"{player['name']} level-up hp", kind="progression"
            )
            hp_gain = max(1, roll.total)
            player["hp"] = player.get("hp", 0) + hp_gain
            player["max_hp"] = player.get("max_hp", player["hp"]) + hp_gain
            state["log"].append(f"{player['name']} reaches level {player['level']}! (+{hp_gain} HP)")


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
) -> dict[str, Any]:
    """Create a fresh session state."""
    if seed is None:
        seed = random.randint(1, 1_000_000_000)
    d = Dice(seed=seed)

    px, py = module.player_start
    player = {
        "id": "player",
        "name": character.name,
        "type": "player",
        "classes": list(character.classes),
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
        monsters.append(_spawn_token(spawn, {}, d))

    log = [
        await narrator.narrate_opening(random.Random(seed), module=module.name, mode=mode),
        await narrator.narrate_room(module.name, room_type=None, rng=random.Random(seed + 1)),
    ]
    if mode == "arena":
        log.append(await narrator.narrate_banter("arena", rng=random.Random(seed + 2)))

    return {
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
        "rolls": [_roll_to_dict(r) for r in d.log],
        "turn_timer_seconds": max(0, turn_timer_seconds),
        "turn_deadline": _deadline(max(0, turn_timer_seconds)),
        "dm_acted_this_round": False,
    }


async def advance_module(state: dict[str, Any], next_module: Module) -> dict[str, Any]:
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
        monsters.append(_spawn_token(spawn, state, d))

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

    template = bestiary.load(monster_name)
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
    token = _spawn_token(spawn, state, d)
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


def _tokens(state: dict[str, Any]) -> list[dict[str, Any]]:
    out = list(state["players"])
    out.extend(state["monsters"])
    return out


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
    line = await narrator.narrate_move(token, random.Random(state["seed"] + state["version"]))
    if line:
        state["log"].append(line)

    # Traps are marked with tile '2'. Trigger on a 1 in 6.
    if module.map.in_bounds(x, y) and module.map.tiles[y][x] == "2":
        trigger_roll = d.roll("1d6", reason="trap trigger", kind="trap").total
        if trigger_roll == 1:
            damage_roll = d.roll("1d6", reason="trap damage", kind="trap")
            damage = max(1, damage_roll.total)
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
                rng=random.Random(state["seed"] + state["version"]),
            )
            state["log"].append(f"{trap_line} {token['name']} suffers {damage} damage.")

    # Hazard tiles: 3 = lava, 4 = spikes.
    tile = module.map.tiles[y][x] if module.map.in_bounds(x, y) else "0"
    if tile in HAZARD_DAMAGE:
        await _apply_hazard(state, token, tile, d)

    # Event/branch tile: 5.
    if tile == TILE_EVENT:
        _trigger_event(state, module, x, y)


async def _apply_hazard(state: dict[str, Any], token: dict[str, Any], tile: str, d: Dice) -> None:
    """Apply hazard damage to a token that enters or starts its turn on a hazard tile."""
    name, expr = HAZARD_DAMAGE[tile]
    damage_roll = d.roll(expr, reason=f"{name} damage", kind="hazard")
    damage = max(1, damage_roll.total)
    token["hp"] -= damage
    hazard_line = await narrator.narrate_hazard(
        name, token.get("name", "someone"), rng=random.Random(state["seed"] + state["version"])
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
    """True if the target is adjacent to a wall tile and gains +2 AC cover."""
    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        x, y = target["x"] + dx, target["y"] + dy
        if module.map.in_bounds(x, y) and module.map.tiles[y][x] == "1":
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
    for token in state["players"]:
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

    roll = d.roll("1d20", reason=f"{attacker['name']} attacks {target['name']}", kind="combat").total
    to_hit = attacker.get("to_hit", 0)
    if attacker["type"] == "player" and _is_flanking(state, attacker, target):
        to_hit += 2
    needed = 20 - target["ac"] + to_hit  # descending AC: lower AC needs higher roll
    hit = roll >= needed
    fatal = False
    if hit:
        damage_expr = attacker.get("damage", "1d6")
        damage_bonus = attacker.get("damage_bonus", 0)
        if damage_bonus:
            damage_expr = f"{damage_expr}+{damage_bonus}"
        dmg_roll = d.roll(damage_expr, reason="damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)

    lines = await narrator.narrate_attack(
        attacker, target, hit, fatal,
        random.Random(state["seed"] + state["version"])
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))


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

    roll = d.roll("1d20", reason=f"{attacker['name']} shoots {target['name']}", kind="combat").total
    to_hit = attacker.get("to_hit", 0)
    effective_ac = target["ac"]
    if _has_cover(state, module, target):
        effective_ac -= 2  # descending AC: lower is better
    needed = 20 - effective_ac + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        dmg_expr = attacker.get("ranged_damage", "1d6")
        damage_bonus = attacker.get("damage_bonus", 0)
        if damage_bonus:
            dmg_expr = f"{dmg_expr}+{damage_bonus}"
        dmg_roll = d.roll(dmg_expr, reason="ranged damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)

    lines = await narrator.narrate_ranged_attack(
        attacker, target, hit, fatal,
        random.Random(state["seed"] + state["version"])
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))


async def _use_potion(state: dict[str, Any], token: dict[str, Any], d: Dice) -> None:
    inventory = token.get("inventory", [])
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
                    state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))
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
                state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))
    else:
        raise ValueError(f"no special ability for class {cls!r}")


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
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))


async def _attack_with_bonuses(
    state: dict[str, Any],
    attacker: dict[str, Any],
    target: dict[str, Any],
    d: Dice,
    to_hit_bonus: int,
    damage_bonus: int,
    reason: str,
) -> None:
    roll = d.roll("1d20", reason=f"{attacker['name']} {reason} {target['name']}", kind="combat").total
    to_hit = attacker.get("to_hit", 0) + to_hit_bonus
    if attacker["type"] == "player" and _is_flanking(state, attacker, target):
        to_hit += 2
    needed = 20 - target["ac"] + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        damage_expr = attacker.get("damage", "1d6")
        base_bonus = attacker.get("damage_bonus", 0)
        total_bonus = base_bonus + damage_bonus
        if total_bonus:
            damage_expr = f"{damage_expr}+{total_bonus}"
        dmg_roll = d.roll(damage_expr, reason=f"{reason} damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                _check_victory(state)
    state["log"].append(f"{attacker['name']} uses {reason} and {'hits' if hit else 'misses'} {target['name']}{' for ' + str(max(0, attacker.get('damage_bonus', 0) + damage_bonus)) + ' bonus damage' if hit else ''}.")
    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"]), module=state.get("module_id")))


async def _start_round(state: dict[str, Any], module: Module, d: Dice) -> None:
    """Advance the turn counter and roll initiative for the new round.

    If the DM wins initiative, the DM acts immediately before control returns
    to the players. Otherwise the players act first.
    """
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
        state["dm_acted_this_round"] = True
    else:
        state["log"].append("The players act first!")


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
        elif action in ("use_potion", "end_turn"):
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
            active = active_index + 1
            if active >= len(state["players"]):
                state["phase"] = PHASE_DM
                state["turn_deadline"] = None
                state["active_player_index"] = 0
            else:
                state["active_player_index"] = active
            state["player"] = _active_player(state)

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


async def _spawn_arena_wave(state: dict[str, Any], module: Module, d: Dice) -> None:
    """Spawn a scaled arena wave."""
    wave = state.get("wave", 1)
    rng = random.Random(state["seed"] + wave)
    player_level = max(p.get("level", 1) for p in state["players"])
    count = min(2 + wave, 6)
    template_name = rng.choice(ARENA_BASE_WAVE_TEMPLATES)

    # Scale up monster HP and damage for later waves.
    hp_bonus = wave - 1
    damage_bonus = wave // 3
    to_hit_bonus = wave // 4

    spawned = 0
    for _ in range(count * 2):
        if spawned >= count:
            break
        sx = rng.randint(1, module.map.width - 2)
        sy = rng.randint(1, module.map.height - 2)
        if not module.map.walkable(sx, sy) or _token_at(state, sx, sy) is not None:
            continue
        template = bestiary.load(template_name)
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
    banter = await narrator.narrate_banter("arena", rng=rng)
    if banter:
        state["log"].append(banter)


async def _run_dm_turn(state: dict[str, Any], module: Module, d: Dice) -> None:
    # Lava damages any token that ends its turn standing on it.
    for token in _tokens(state):
        if not token.get("alive", True):
            continue
        tile = module.map.tiles[token["y"]][token["x"]]
        if tile == TILE_LAVA:
            await _apply_hazard(state, token, tile, d)

    events: list[str] = []
    for monster in state["monsters"]:
        if not monster.get("alive", True):
            continue
        if state["status"] != STATUS_ACTIVE:
            break
        target = _nearest_player(state, monster)
        # If adjacent, attack.
        if _adjacent(monster, target):
            events.append(f"{monster['name']} attacks {target['name']}.")
            await _attack(state, monster, target, d)
            continue
        # Move one tile toward the target.
        dx = 0
        if target["x"] > monster["x"]:
            dx = 1
        elif target["x"] < monster["x"]:
            dx = -1
        dy = 0
        if target["y"] > monster["y"]:
            dy = 1
        elif target["y"] < monster["y"]:
            dy = -1

        # Try primary direction, then secondary.
        moved = False
        for tx, ty in [(monster["x"] + dx, monster["y"] + dy), (monster["x"] + dx, monster["y"]), (monster["x"], monster["y"] + dy)]:
            if module.map.walkable(tx, ty) and _token_at(state, tx, ty) is None:
                monster["x"] = tx
                monster["y"] = ty
                moved = True
                break
        if moved:
            events.append(f"{monster['name']} moves toward {target['name']}.")
            line = await narrator.narrate_move(monster, random.Random(state["seed"] + state["version"]))
            if line:
                state["log"].append(line)
            if _adjacent(monster, target):
                await _attack(state, monster, target, d)

    if events:
        summary = await narrator.narrate_dm_turn(
            events, random.Random(state["seed"] + state["version"])
        )
        if summary:
            state["log"].append(summary)

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
    }
