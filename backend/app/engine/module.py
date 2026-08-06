"""Tactical module loader.

A module is a YAML file that describes one adventure location:
- id, name, ruleset
- map grid (walls/floors)
- player start position
- monster placements
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

from backend.app.config import SETTINGS


@dataclass(frozen=True)
class Map:
    width: int
    height: int
    tile_size: int
    tiles: list[str]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        return self.tiles[y][x] == "0"


@dataclass(frozen=True)
class MonsterSpawn:
    id: str
    name: str
    monster: str
    x: int
    y: int
    color: str


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    ruleset: str
    description: str
    map: Map
    player_start: tuple[int, int]
    monsters: list[MonsterSpawn]


def load(module_id: str) -> Module:
    root = SETTINGS.module_root / module_id
    path = root / "module.yaml"
    if not path.exists():
        raise KeyError(f"no module {module_id!r} at {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    map_doc = doc["map"]
    tiles = map_doc["tiles"]
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    map_ = Map(
        width=map_doc.get("width", width),
        height=map_doc.get("height", height),
        tile_size=map_doc.get("tile_size", 40),
        tiles=tiles,
    )

    player_start = doc.get("player_start", {"x": 1, "y": 1})
    monsters = [
        MonsterSpawn(
            id=m.get("id", f"monster_{i}"),
            name=m["name"],
            monster=m["monster"],
            x=m["x"],
            y=m["y"],
            color=m.get("color", "#e74c3c"),
        )
        for i, m in enumerate(doc.get("monsters", []))
    ]

    return Module(
        id=doc["id"],
        name=doc["name"],
        ruleset=doc.get("ruleset", "osric"),
        description=doc.get("description", ""),
        map=map_,
        player_start=(player_start["x"], player_start["y"]),
        monsters=monsters,
    )
