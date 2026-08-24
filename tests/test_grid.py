"""Tests for square grid utilities."""
from __future__ import annotations

from engine.grid import apply_direction, grid_distance, grid_neighbours, tiles_to_feet


def test_grid_neighbours_count():
    assert len(grid_neighbours(0, 0)) == 4


def test_grid_distance_zero():
    assert grid_distance((0, 0), (0, 0)) == 0


def test_grid_distance_cardinal():
    assert grid_distance((0, 0), (1, 0)) == 1
    assert grid_distance((0, 0), (0, 3)) == 3


def test_apply_direction():
    assert apply_direction(0, 0, 0) == (1, 0)   # East
    assert apply_direction(0, 0, 1) == (0, 1)   # South
    assert apply_direction(0, 0, 2) == (-1, 0)  # West
    assert apply_direction(0, 0, 3) == (0, -1)  # North


def test_tiles_to_feet():
    assert tiles_to_feet(3) == 10.0
