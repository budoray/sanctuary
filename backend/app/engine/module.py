"""Tactical module loader.

A module is a YAML file that describes one adventure location:
- id, name, ruleset
- map grid (walls/floors)
- player start position
- monster placements
"""
from dataclasses import dataclass, field
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
        return self.tiles[y][x] in ("0", "2", "3", "4", "5")


@dataclass(frozen=True)
class MonsterSpawn:
    id: str
    name: str
    monster: str
    x: int
    y: int
    color: str
    boss: bool = False
    phases: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class Event:
    id: str
    x: int
    y: int
    message: str
    choices: dict[str, str]


@dataclass(frozen=True)
class Branch:
    id: str
    monsters: list[MonsterSpawn]


@dataclass(frozen=True)
class Module:
    id: str
    name: str
    ruleset: str
    description: str
    map: Map
    player_start: tuple[int, int]
    monsters: list[MonsterSpawn]
    events: list[Event]
    branches: list[Branch]


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

    def _parse_spawn(m: dict, suffix: str = "") -> MonsterSpawn:
        return MonsterSpawn(
            id=m.get("id", f"monster_{suffix}"),
            name=m["name"],
            monster=m["monster"],
            x=m["x"],
            y=m["y"],
            color=m.get("color", "#e74c3c"),
            boss=m.get("boss", False),
            phases=m.get("phases", []),
        )

    monsters = [_parse_spawn(m, str(i)) for i, m in enumerate(doc.get("monsters", []))]

    events = [
        Event(
            id=e.get("id", f"event_{i}"),
            x=e["x"],
            y=e["y"],
            message=e["message"],
            choices=e.get("choices", {}),
        )
        for i, e in enumerate(doc.get("events", []))
    ]

    branches = [
        Branch(
            id=branch_id,
            monsters=[_parse_spawn(m, f"{branch_id}_{i}") for i, m in enumerate(spawns)],
        )
        for branch_id, spawns in doc.get("branches", {}).items()
    ]

    return Module(
        id=doc["id"],
        name=doc["name"],
        ruleset=doc.get("ruleset", "osric"),
        description=doc.get("description", ""),
        map=map_,
        player_start=(player_start["x"], player_start["y"]),
        monsters=monsters,
        events=events,
        branches=branches,
    )
