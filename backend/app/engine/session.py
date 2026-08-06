"""Tactical session engine: one character vs. a dungeon module.

The state is a plain dict so it serialises cleanly to JSON and the DB.
"""
from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.engine import bestiary, items
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
        "log": [
            await narrator.narrate_opening(random.Random(seed)),
            await narrator.narrate_room(module.name, room_type=None, rng=random.Random(seed + 1)),
        ],
        "rolls": [_roll_to_dict(r) for r in d.log],
        "turn_timer_seconds": max(0, turn_timer_seconds),
        "turn_deadline": _deadline(max(0, turn_timer_seconds)),
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

    state["module_id"] = next_module.id
    state["monsters"] = monsters
    state["turn"] = 1
    state["phase"] = PHASE_PLAYER
    state["active_player_index"] = 0
    state["status"] = STATUS_ACTIVE
    state["campaign_stage"] = state.get("campaign_stage", 0) + 1
    state["version"] += 1
    state["rolls"].extend(_roll_to_dict(r) for r in d.log)
    state["log"].append(f"— The party journeys to {next_module.name} —")
    state["player"] = _active_player(state)
    return state


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


def _check_loss(state: dict[str, Any]) -> None:
    """Set session to lost if every player is dead or downed."""
    if state["status"] != STATUS_ACTIVE:
        return
    players = state.get("players", [])
    if players and all((not p.get("alive", True)) or p.get("down", False) for p in players):
        state["status"] = STATUS_LOST


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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
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
            state["log"].append(f"{token['name']} turns the undead, dealing {damage} damage.")
            if target["hp"] <= 0:
                target["alive"] = False
                target["hp"] = 0
                _grant_rewards(state, target)
                if all(not m.get("alive", True) for m in state["monsters"]):
                    state["status"] = STATUS_WON
                    state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"])))
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
        state["log"].append(f"{token['name']} fires a magic missile for {damage} damage.")
        if target["hp"] <= 0:
            target["alive"] = False
            target["hp"] = 0
            _grant_rewards(state, target)
            if all(not m.get("alive", True) for m in state["monsters"]):
                state["status"] = STATUS_WON
                state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"])))
    else:
        raise ValueError(f"no special ability for class {cls!r}")


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
            if target["hp"] <= 0:
                fatal = True
                target["alive"] = False
                _grant_rewards(state, target)
                if all(not m.get("alive", True) for m in state["monsters"]):
                    state["status"] = STATUS_WON
    state["log"].append(f"{attacker['name']} uses {reason} and {'hits' if hit else 'misses'} {target['name']}{' for ' + str(max(0, attacker.get('damage_bonus', 0) + damage_bonus)) + ' bonus damage' if hit else ''}.")
    if state["status"] == STATUS_WON:
        state["log"].append(await narrator.narrate_victory(random.Random(state["seed"] + state["version"])))


async def act(state: dict[str, Any], module: Module, action: str, **kwargs: Any) -> dict[str, Any]:
    """Perform one player or DM action and return the updated state."""
    d = Dice(seed=state["seed"] + state["turn"] * 1000 + state["version"])

    if action == "dm_turn":
        if state["phase"] != PHASE_DM:
            raise ValueError("not the DM's turn")
        _tick_statuses(state)
        await _run_dm_turn(state, module, d)
        state["turn"] += 1
        state["phase"] = PHASE_PLAYER
        state["active_player_index"] = 0
        state["player"] = _active_player(state)
        _tick_statuses(state)
        state["statuses_tick_index"] = 0
        state["turn_deadline"] = _deadline(state["turn_timer_seconds"])
        state["log"].append(f"— Turn {state['turn']} —")

    else:
        if state["phase"] != PHASE_PLAYER:
            raise ValueError("not the player's turn")
        active_index = state.get("active_player_index", 0)
        if state.get("statuses_tick_index") != active_index:
            _tick_statuses(state)
            state["statuses_tick_index"] = active_index
        token = _active_player(state)

        if action == "move":
            if token.get("down", False):
                raise ValueError("downed players cannot move")
            await _move(state, token, int(kwargs["x"]), int(kwargs["y"]), module, d)

        elif action == "attack":
            if token.get("down", False):
                raise ValueError("downed players cannot attack")
            target_id = kwargs["target_id"]
            target = next((m for m in state["monsters"] if m["id"] == target_id), None)
            if target is None:
                raise ValueError("target not found")
            await _attack(state, token, target, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "ranged":
            if token.get("down", False):
                raise ValueError("downed players cannot attack")
            target_id = kwargs["target_id"]
            target = next((m for m in state["monsters"] if m["id"] == target_id), None)
            if target is None:
                raise ValueError("target not found")
            await _ranged_attack(state, token, target, module, d)
            state["phase"] = PHASE_DM
            state["turn_deadline"] = None

        elif action == "use_potion":
            if token.get("down", False):
                raise ValueError("downed players cannot use potions")
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
            if token.get("down", False):
                raise ValueError("downed players cannot use abilities")
            await _ability(state, token, kwargs["target_id"], module, d)
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
        "players": players,
        "active_player_index": active_index,
        "player": players[active_index] if players else state.get("player"),
        "monsters": state["monsters"],
        "log": state["log"],
        "turn_timer_seconds": state.get("turn_timer_seconds", 0),
        "turn_deadline": state.get("turn_deadline"),
    }
