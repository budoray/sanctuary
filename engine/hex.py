"""Axial-coordinate hex grid utilities."""
from __future__ import annotations

# Six neighbours in axial (q, r) coordinates.
HEX_DIRECTIONS = [
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
]


def hex_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Cube-coordinate distance using axial (q, r)."""
    aq, ar = a
    bq, br = b
    return (abs(aq - bq) + abs(aq + ar - bq - br) + abs(ar - br)) // 2


def hex_neighbours(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in HEX_DIRECTIONS]


def hex_layout(radius: int) -> list[tuple[int, int]]:
    """All hex coordinates within a given axial radius of (0, 0)."""
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            cells.append((q, r))
    return cells
