"""Server-side validation helpers for session actions and S3 adventures.

These guards run before any state change in ``session.act`` so malformed or
out-of-order client requests raise ``ValueError`` early.
"""
from __future__ import annotations

from collections import deque
from typing import Any

from pydantic import ValidationError

from backend.app.engine import bestiary
from backend.app.engine.module import (
    RECOGNISED_TRIGGER_ACTIONS,
    AdventureData,
    Module,
)


# -----------------------------------------------------------------------------
# S3 adventure validation
# -----------------------------------------------------------------------------
# Tile characters recognised by the DM Workshop grid editor and the tactical map.
VALID_TILE_CHARS = set("01234567")
VALID_ENTITY_TYPES = {"monster", "trap", "treasure", "item", "event"}


def _collect_monster_refs(area: dict) -> set[str]:
    refs: set[str] = set()
    for field in ("monsters", "contents"):
        for entry in area.get(field, []) or []:
            if isinstance(entry, str):
                refs.add(entry)
            elif isinstance(entry, dict):
                if "monster" in entry:
                    refs.add(entry["monster"])
                # treasure or contents may reference a monster as guardian
                for key in ("guardian", "wanders"):
                    if key in entry and isinstance(entry[key], str):
                        refs.add(entry[key])
    for entry in area.get("treasure", []) or []:
        if isinstance(entry, dict) and isinstance(entry.get("guardian"), str):
            refs.add(entry["guardian"])
    return refs


def validate_area_grid(area: dict) -> list[str]:
    """Validate an area's tile grid and placed entities are coherent.

    Returns a list of human-readable errors; an empty list means the area is
    grid-consistent.
    """
    errors: list[str] = []
    aid = area.get("id")
    prefix = f"area {aid}: " if aid else "area: "

    width = area.get("width")
    height = area.get("height")
    tiles = area.get("tiles")

    # Grid is optional in the raw S3 format, but once supplied it must be
    # internally consistent.
    if width is not None or height is not None or tiles is not None:
        if not isinstance(width, int) or not isinstance(height, int):
            errors.append(f"{prefix}width and height must be integers")
            return errors
        if width < 1 or height < 1:
            errors.append(f"{prefix}width and height must be positive")
        if width > 64 or height > 64:
            errors.append(f"{prefix}width and height may not exceed 64")

        if not isinstance(tiles, list):
            errors.append(f"{prefix}tiles must be a list of strings")
            return errors
        if len(tiles) != height:
            errors.append(
                f"{prefix}tile row count ({len(tiles)}) does not match height ({height})"
            )
        for row_idx, row in enumerate(tiles):
            if not isinstance(row, str):
                errors.append(f"{prefix}tile row {row_idx} is not a string")
                continue
            if len(row) != width:
                errors.append(
                    f"{prefix}tile row {row_idx} length ({len(row)}) does not match width ({width})"
                )
            invalid = set(row) - VALID_TILE_CHARS
            if invalid:
                errors.append(
                    f"{prefix}tile row {row_idx} contains invalid characters: {sorted(invalid)}"
                )

    # Entities are optional, but if present they must sit inside the area.
    entities = area.get("entities")
    if entities is not None:
        if not isinstance(entities, list):
            errors.append(f"{prefix}entities must be a list")
        else:
            grid_w = width if isinstance(width, int) else 0
            grid_h = height if isinstance(height, int) else 0
            seen: set[tuple[int, int]] = set()
            for idx, ent in enumerate(entities):
                if not isinstance(ent, dict):
                    errors.append(f"{prefix}entity {idx} is not an object")
                    continue
                ent_type = ent.get("type")
                if ent_type not in VALID_ENTITY_TYPES:
                    errors.append(
                        f"{prefix}entity {idx} has invalid type {ent_type!r}"
                    )
                x = ent.get("x")
                y = ent.get("y")
                if not isinstance(x, int) or not isinstance(y, int):
                    errors.append(f"{prefix}entity {idx} must have integer x and y")
                    continue
                if grid_w and grid_h and not (0 <= x < grid_w and 0 <= y < grid_h):
                    errors.append(
                        f"{prefix}entity {idx} at ({x},{y}) is outside the grid"
                    )
                if (x, y) in seen:
                    errors.append(f"{prefix}entity {idx} overlaps another entity at ({x},{y})")
                else:
                    seen.add((x, y))

    return errors


def _resolve_start_area(doc: dict) -> str | int | None:
    areas = doc.get("areas") or []
    if not areas:
        return None
    area_ids = {a.get("id") for a in areas if isinstance(a, dict)}
    start = doc.get("module", {}).get("start")
    if start in area_ids:
        return start
    # If start is prose, look for an explicit "start" area id, else first area.
    if "start" in area_ids:
        return "start"
    return areas[0].get("id")


def validate_adventure(data: dict, check_reachability: bool = True) -> list[str]:
    """Validate an S3 adventure document.

    Returns a list of human-readable errors; an empty list means the document
    is structurally and semantically valid.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["adventure document must be a mapping"]

    # 1. Structural validation via Pydantic.
    try:
        adventure = AdventureData.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            errors.append(f"{loc}: {err.get('msg', 'invalid value')}")
        return errors

    doc = data
    module_meta = doc.get("module", {})
    areas = doc.get("areas") or []
    area_ids = {str(a.get("id")) for a in areas if isinstance(a, dict)}

    # 2. Required module fields.
    if not module_meta.get("title"):
        errors.append("module.title is required")
    if not module_meta.get("start"):
        errors.append("module.start is required")
    if not areas:
        errors.append("at least one area is required")

    # 3. Exit targets exist and area reachability.
    start_id = _resolve_start_area(doc)
    if start_id is not None and str(start_id) not in area_ids:
        errors.append(f"start area {start_id!r} does not exist")

    for area in areas:
        aid = area.get("id")
        for idx, ex in enumerate(area.get("exits", []) or []):
            target = ex.get("to")
            if target is None:
                errors.append(f"area {aid}: exit {idx} is missing 'to'")
                continue
            if str(target) not in area_ids:
                errors.append(f"area {aid}: exit to {target!r} does not exist")

    if check_reachability and start_id is not None and area_ids:
        reachable = _reachable_area_ids(str(start_id), areas)
        unreachable = area_ids - reachable
        for aid in sorted(unreachable):
            errors.append(f"area {aid} is unreachable from start")

    # 4. Area tile grids and entities are coherent.
    for area in areas:
        errors.extend(validate_area_grid(area))

    # 5. Discovery triggers recognised.
    for area in areas:
        aid = area.get("id")
        for idx, disc in enumerate(area.get("discoveries", []) or []):
            trigger = disc.get("trigger") if isinstance(disc, dict) else None
            if not isinstance(trigger, dict):
                errors.append(f"area {aid}: discovery {idx} is missing trigger")
                continue
            action = trigger.get("action")
            if not action:
                errors.append(f"area {aid}: discovery {idx} trigger is missing action")
            elif action not in RECOGNISED_TRIGGER_ACTIONS:
                errors.append(
                    f"area {aid}: discovery {idx} trigger action {action!r} is not recognised"
                )
            if trigger.get("chance") and not trigger.get("per"):
                errors.append(
                    f"area {aid}: discovery {idx} trigger has chance but no 'per' cadence"
                )

    # 6. Monster references resolve.
    local_monster_ids = {m.get("id") for m in doc.get("monsters", []) or [] if isinstance(m, dict)}
    bestiary_ids = set(bestiary.base_ids())
    known_monsters = local_monster_ids | bestiary_ids

    for area in areas:
        aid = area.get("id")
        for ref in _collect_monster_refs(area):
            if ref not in known_monsters:
                errors.append(f"area {aid}: monster reference {ref!r} not found")

    for region in doc.get("regions", []) or []:
        rid = region.get("id")
        table = region.get("table") or {}
        for idx, entry in enumerate(table.get("entries", []) or []):
            ref = entry.get("monster") if isinstance(entry, dict) else None
            if ref and ref not in known_monsters:
                errors.append(f"region {rid}: table entry {idx} monster {ref!r} not found")

    # 7. Item references resolve (module-local items only; bestiary loot is open-ended).
    local_item_ids = {m.get("id") for m in doc.get("items", []) or [] if isinstance(m, dict)}
    for area in areas:
        aid = area.get("id")
        for entry in area.get("treasure", []) or []:
            if isinstance(entry, dict):
                item_ref = entry.get("item") or entry.get("item_id")
                if item_ref and item_ref not in local_item_ids:
                    errors.append(f"area {aid}: item reference {item_ref!r} not found")

    return errors


def _reachable_area_ids(start_id: str, areas: list[dict]) -> set[str]:
    graph = {str(a.get("id")): a for a in areas if isinstance(a, dict)}
    seen: set[str] = set()
    queue: deque[str] = deque([start_id])
    while queue:
        current = queue.popleft()
        if current in seen or current not in graph:
            continue
        seen.add(current)
        for ex in graph[current].get("exits", []) or []:
            target = str(ex.get("to")) if isinstance(ex, dict) else None
            if target and target not in seen:
                queue.append(target)
    return seen


def _active_token(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("phase") != "player":
        raise ValueError("not the player's turn")
    players = state.get("players", [])
    if not players:
        raise ValueError("no players in session")
    index = state.get("active_player_index", 0)
    if index < 0 or index >= len(players):
        raise ValueError("invalid active player index")
    return players[index]


def validate_actor(state: dict[str, Any]) -> dict[str, Any]:
    """Return the active player token, raising if the actor is invalid/down."""
    token = _active_token(state)
    if not token.get("alive", True):
        raise ValueError("actor is not alive")
    if token.get("down", False):
        raise ValueError("downed players cannot act")
    return token


def validate_move(state: dict[str, Any], module: Module, x: int, y: int) -> None:
    """Verify a move target is adjacent, walkable, and unoccupied."""
    token = validate_actor(state)
    if abs(token["x"] - x) + abs(token["y"] - y) != 1:
        raise ValueError("must move to an adjacent tile")
    if not module.map.walkable(x, y):
        raise ValueError("target tile is blocked")
    for t in state.get("players", []) + state.get("monsters", []):
        if t.get("alive", True) and t["x"] == x and t["y"] == y:
            raise ValueError("target tile is occupied")


def _token_at(state: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for t in state.get("players", []) + state.get("monsters", []):
        if t.get("alive", True) and t["x"] == x and t["y"] == y:
            return t
    return None


def _line_of_sight(state: dict[str, Any], module: Module, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Simple grid ray-cast returning False if any tile between source and target is a wall."""
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


def validate_attack_target(state: dict[str, Any], target_id: str) -> dict[str, Any]:
    """Verify a melee attack target exists and is adjacent to the actor."""
    token = validate_actor(state)
    target = next((m for m in state.get("monsters", []) if m["id"] == target_id), None)
    if target is None:
        raise ValueError("target not found")
    if not target.get("alive", True):
        raise ValueError("target is already dead")
    if abs(token["x"] - target["x"]) + abs(token["y"] - target["y"]) != 1:
        raise ValueError("target is not adjacent")
    return target


def validate_ranged_target(state: dict[str, Any], module: Module, target_id: str, max_range: int = 4) -> dict[str, Any]:
    """Verify a ranged target exists, is in range, and has line of sight."""
    token = validate_actor(state)
    target = next((m for m in state.get("monsters", []) if m["id"] == target_id), None)
    if target is None:
        raise ValueError("target not found")
    if not target.get("alive", True):
        raise ValueError("target is already dead")
    dist = abs(token["x"] - target["x"]) + abs(token["y"] - target["y"])
    if dist > max_range:
        raise ValueError("target is out of range")
    if not _line_of_sight(state, module, token["x"], token["y"], target["x"], target["y"]):
        raise ValueError("no line of sight")
    return target
