"""Square grid utilities.

A 3x3 group of tiles represents a 10ft x 10ft area, so each tile is 10/3 ft
(≈3.33 ft) on a side. Positions are stored as integer tile coordinates (x, y).
"""
from __future__ import annotations

TILES_PER_10FT = 3
FEET_PER_TILE = 10 / TILES_PER_10FT

# Cardinal directions: 0=East, 1=South, 2=West, 3=North
DIRECTION_VECTORS = [
    (1, 0),   # East
    (0, 1),   # South
    (-1, 0),  # West
    (0, -1),  # North
]


def grid_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Manhattan distance in tiles."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def grid_neighbours(x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in DIRECTION_VECTORS]


def apply_direction(x: int, y: int, direction: int) -> tuple[int, int]:
    dx, dy = DIRECTION_VECTORS[direction % len(DIRECTION_VECTORS)]
    return (x + dx, y + dy)


def tiles_to_feet(tiles: int) -> float:
    return tiles * FEET_PER_TILE
