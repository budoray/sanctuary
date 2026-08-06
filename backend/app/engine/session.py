"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import random
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


def _roll_hp(monster: dict, d: Dice) -> int:
    total = monster["hp_adjustment"]
    for _ in range(monster["hp_dice_count"]):
        total += d.roll(f"1d{monster['hp_die_faces']}", reason=f"{monster['name']} hp", kind="combat").total
    return max(1, total)


def _deadline(seconds: int) -> str | None:
    """Return an ISO UTC deadline ``seconds`` from now, or ``None`` if disabled."""
    if seconds <= 0:
        return None
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


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
        "color": "#3498db",
        "character_id": character_id,
        "account_id": account_id,
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
            elif all(not m.get("alive", True) for m in state["monsters"]):
                state["status"] = STATUS_WON

    lines = await narrator.narrate_attack(
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
    for monster in state["monsters"]:
        if not monster.get("alive", True):
            continue
        if state["status"] != STATUS_ACTIVE:
            break
        target = _nearest_player(state, monster)
        # If adjacent, attack.
        if _adjacent(monster, target):
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
            line = await narrator.narrate_move(monster, random.Random(state["seed"] + state["version"]))
            if line:
                state["log"].append(line)
            if _adjacent(monster, target):
                await _attack(state, monster, target, d)


def view(state: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe view of the state."""
    players = state.get("players", [])
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
