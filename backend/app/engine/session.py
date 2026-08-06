"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.engine import bestiary
from backend.app.engine.character import Character
from backend.app.engine.dice import Dice, Roll
from backend.app.engine.module import Module
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


def _grant_rewards(state: dict[str, Any], monster: dict[str, Any]) -> None:
    """Award XP and gold to living players when a monster dies."""
    xp_value = monster.get("xp_value", 50)
    gold_value = xp_value // 10
    for player in state["players"]:
        if not player.get("alive", True):
            continue
        player["gold"] = player.get("gold", 0) + gold_value
        player["xp"] = player.get("xp", 0) + xp_value
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


async def new_game(
    session_id: str,
    module: Module,
    character: Character,
    seed: int | None = None,
    turn_timer_seconds: int = 0,
    character_id: str | None = None,
    account_id: int | None = None,
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
        "ranged_damage": _ranged_damage_for_classes(list(character.classes)),
        "color": "#3498db",
        "character_id": character_id,
        "account_id": account_id,
        "xp": getattr(character, "xp", 0),
        "level": getattr(character, "level", 1),
        "gold": getattr(character, "gold", 0),
    }
    players = [player]

    monsters: list[dict[str, Any]] = []
    for spawn in module.monsters:
        template = bestiary.load(spawn.monster)
        monsters.append({
            "id": spawn.id,
            "name": spawn.name,
            "type": "monster",
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
        })

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
        "players": players,
        "active_player_index": 0,
        "player": player,
        "monsters": monsters,
        "log": [await narrator.narrate_opening(random.Random(seed))],
        "rolls": [_roll_to_dict(r) for r in d.log],
        "turn_timer_seconds": max(0, turn_timer_seconds),
        "turn_deadline": _deadline(max(0, turn_timer_seconds)),
    }


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
        "ranged_damage": _ranged_damage_for_classes(list(character.classes)),
        "color": _PLAYER_COLORS[len(state["players"]) % len(_PLAYER_COLORS)],
        "character_id": character_id,
        "account_id": account_id,
        "alive": True,
        "xp": getattr(character, "xp", 0),
        "level": getattr(character, "level", 1),
        "gold": getattr(character, "gold", 0),
    }
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


async def _attack(state: dict[str, Any], attacker: dict[str, Any], target: dict[str, Any], d: Dice) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not _adjacent(attacker, target):
        raise ValueError("target is not adjacent")
    if not target.get("alive", True):
        raise ValueError("target is already dead")

    roll = d.roll("1d20", reason=f"{attacker['name']} attacks {target['name']}", kind="combat").total
    to_hit = attacker.get("to_hit", 0)
    needed = 20 - target["ac"] + to_hit  # descending AC: lower AC needs higher roll
    hit = roll >= needed
    fatal = False
    if hit:
        dmg_roll = d.roll(attacker.get("damage", "1d6"), reason="damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        if target["hp"] <= 0:
            fatal = True
            target["alive"] = False
            if target["type"] == "player":
                state["status"] = STATUS_LOST
            else:
                _grant_rewards(state, target)
                if all(not m.get("alive", True) for m in state["monsters"]):
                    state["status"] = STATUS_WON

    lines = await narrator.narrate_attack(
        attacker, target, hit, fatal,
        random.Random(state["seed"] + state["version"])
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"])))


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
    needed = 20 - target["ac"] + to_hit
    hit = roll >= needed
    fatal = False
    if hit:
        dmg_expr = attacker.get("ranged_damage", "1d6")
        dmg_roll = d.roll(dmg_expr, reason="ranged damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        if target["hp"] <= 0:
            fatal = True
            target["alive"] = False
            if target["type"] == "player":
                state["status"] = STATUS_LOST
            else:
                _grant_rewards(state, target)
                if all(not m.get("alive", True) for m in state["monsters"]):
                    state["status"] = STATUS_WON

    lines = await narrator.narrate_ranged_attack(
        attacker, target, hit, fatal,
        random.Random(state["seed"] + state["version"])
    )
    state["log"].extend(lines)

    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"])))


async def act(state: dict[str, Any], module: Module, action: str, **kwargs: Any) -> dict[str, Any]:
    """Perform one player or DM action and return the updated state."""
    d = Dice(seed=state["seed"] + state["turn"] * 1000 + state["version"])

    if action == "move":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        token = _active_player(state)
        await _move(state, token, int(kwargs["x"]), int(kwargs["y"]), module, d)

    elif action == "attack":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        target_id = kwargs["target_id"]
        target = next((m for m in state["monsters"] if m["id"] == target_id), None)
        if target is None:
            raise ValueError("target not found")
        await _attack(state, _active_player(state), target, d)
        state["phase"] = PHASE_DM
        state["turn_deadline"] = None

    elif action == "ranged":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        target_id = kwargs["target_id"]
        target = next((m for m in state["monsters"] if m["id"] == target_id), None)
        if target is None:
            raise ValueError("target not found")
        await _ranged_attack(state, _active_player(state), target, module, d)
        state["phase"] = PHASE_DM
        state["turn_deadline"] = None

    elif action == "end_turn":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        active = state.get("active_player_index", 0) + 1
        if active >= len(state["players"]):
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None
            state["active_player_index"] = 0
        else:
            state["active_player_index"] = active
        state["player"] = _active_player(state)

    elif action == "dm_turn":
        if state["phase"] != PHASE_DM:
            raise ValueError("not the DM's turn")
        await _run_dm_turn(state, module, d)
        state["turn"] += 1
        state["phase"] = PHASE_PLAYER
        state["active_player_index"] = 0
        state["player"] = _active_player(state)
        state["turn_deadline"] = _deadline(state["turn_timer_seconds"])
        state["log"].append(f"— Turn {state['turn']} —")

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


async def _run_dm_turn(state: dict[str, Any], module: Module, d: Dice) -> None:
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


def view(state: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe view of the state."""
    players = []
    for p in state.get("players", []):
        token = dict(p)
        token.setdefault("xp", 0)
        token.setdefault("level", 1)
        token.setdefault("gold", 0)
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
        "players": players,
        "active_player_index": active_index,
        "player": players[active_index] if players else state.get("player"),
        "monsters": state["monsters"],
        "log": state["log"],
        "turn_timer_seconds": state.get("turn_timer_seconds", 0),
        "turn_deadline": state.get("turn_deadline"),
    }
