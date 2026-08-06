"""Server-side validation helpers for session actions.

These guards run before any state change in ``session.act`` so malformed or
out-of-order client requests raise ``ValueError`` early.
"""
from __future__ import annotations

from typing import Any

from backend.app.engine.module import Module


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
