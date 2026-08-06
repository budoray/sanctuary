"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import random
from typing import Any

from backend.app.engine import bestiary
from backend.app.engine.character import Character
from backend.app.engine.dice import Dice, Roll
from backend.app.engine.module import Module


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


def new_game(session_id: str, module: Module, character: Character, seed: int | None = None) -> dict[str, Any]:
    """Create a fresh session state."""
    if seed is None:
        seed = random.randint(1, 1_000_000_000)
    d = Dice(seed=seed)

    px, py = module.player_start
    player = {
        "id": "player",
        "name": character.name,
        "type": "player",
        "x": px,
        "y": py,
        "hp": character.hit_points,
        "max_hp": character.hit_points,
        "ac": character.armour_class,
        "color": "#3498db",
        "character_id": None,
    }

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
        "version": 0,
        "turn": 1,
        "phase": PHASE_PLAYER,
        "status": STATUS_ACTIVE,
        "seed": seed,
        "player": player,
        "monsters": monsters,
        "log": ["The dungeon is silent, save for dripping water."],
        "rolls": [_roll_to_dict(r) for r in d.log],
    }


def _tokens(state: dict[str, Any]) -> list[dict[str, Any]]:
    out = [state["player"]]
    out.extend(state["monsters"])
    return out


def _token_at(state: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for t in _tokens(state):
        if t.get("alive", True) and t["x"] == x and t["y"] == y:
            return t
    return None


def _adjacent(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) == 1


def _move(state: dict[str, Any], token: dict[str, Any], x: int, y: int, module: Module, d: Dice) -> None:
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


def _attack(state: dict[str, Any], attacker: dict[str, Any], target: dict[str, Any], d: Dice) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValueError("game is over")
    if not _adjacent(attacker, target):
        raise ValueError("target is not adjacent")
    if not target.get("alive", True):
        raise ValueError("target is already dead")

    roll = d.roll("1d20", reason=f"{attacker['name']} attacks {target['name']}", kind="combat").total
    to_hit = attacker.get("to_hit", 0)
    needed = 20 - target["ac"] + to_hit  # descending AC: lower AC needs higher roll
    if roll >= needed:
        dmg_roll = d.roll(attacker.get("damage", "1d6"), reason="damage", kind="combat")
        damage = max(1, dmg_roll.total)
        target["hp"] -= damage
        state["log"].append(f"{attacker['name']} hits {target['name']} for {damage} damage.")
        if target["hp"] <= 0:
            target["alive"] = False
            state["log"].append(f"{target['name']} falls.")
            if target["type"] == "player":
                state["status"] = STATUS_LOST
            elif all(not m.get("alive", True) for m in state["monsters"]):
                state["status"] = STATUS_WON
    else:
        state["log"].append(f"{attacker['name']} misses {target['name']}.")


def act(state: dict[str, Any], module: Module, action: str, **kwargs: Any) -> dict[str, Any]:
    """Perform one player or DM action and return the updated state."""
    d = Dice(seed=state["seed"] + state["turn"] * 1000 + state["version"])

    if action == "move":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        token = state["player"]
        _move(state, token, int(kwargs["x"]), int(kwargs["y"]), module, d)

    elif action == "attack":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        target_id = kwargs["target_id"]
        target = next((m for m in state["monsters"] if m["id"] == target_id), None)
        if target is None:
            raise ValueError("target not found")
        _attack(state, state["player"], target, d)
        state["phase"] = PHASE_DM

    elif action == "end_turn":
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        state["phase"] = PHASE_DM

    elif action == "dm_turn":
        if state["phase"] != PHASE_DM:
            raise ValueError("not the DM's turn")
        _run_dm_turn(state, module, d)
        state["turn"] += 1
        state["phase"] = PHASE_PLAYER

    else:
        raise ValueError(f"unknown action: {action!r}")

    state["version"] += 1
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    return state


def _run_dm_turn(state: dict[str, Any], module: Module, d: Dice) -> None:
    player = state["player"]
    for monster in state["monsters"]:
        if not monster.get("alive", True):
            continue
        if state["status"] != STATUS_ACTIVE:
            break
        # If adjacent, attack.
        if _adjacent(monster, player):
            _attack(state, monster, player, d)
            continue
        # Move one tile toward the player.
        dx = 0
        if player["x"] > monster["x"]:
            dx = 1
        elif player["x"] < monster["x"]:
            dx = -1
        dy = 0
        if player["y"] > monster["y"]:
            dy = 1
        elif player["y"] < monster["y"]:
            dy = -1

        # Try primary direction, then secondary.
        moved = False
        for tx, ty in [(monster["x"] + dx, monster["y"] + dy), (monster["x"] + dx, monster["y"]), (monster["x"], monster["y"] + dy)]:
            if module.map.walkable(tx, ty) and _token_at(state, tx, ty) is None:
                monster["x"] = tx
                monster["y"] = ty
                moved = True
                break
        if moved and _adjacent(monster, player):
            _attack(state, monster, player, d)


def view(state: dict[str, Any]) -> dict[str, Any]:
    """Return a client-safe view of the state."""
    return {
        "id": state["id"],
        "module_id": state["module_id"],
        "turn": state["turn"],
        "phase": state["phase"],
        "status": state["status"],
        "player": state["player"],
        "monsters": state["monsters"],
        "log": state["log"],
    }
