"""Tactical module loader and S3 adventure format.

A module is a YAML file that describes one adventure location:
- id, name, ruleset
- map grid (walls/floors)
- player start position
- monster placements

The S3 adventure format (section 8.1 of the design spec) is a richer,
region/area graph used for campaign-style modules.  It lives alongside the
tactical ``Module`` format; existing sessions continue to use ``Module``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from backend.app.config import SETTINGS


# -----------------------------------------------------------------------------
# Tactical module format (legacy / Phase 1)
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class Map:
    width: int
    height: int
    tile_size: int
    tiles: list[str]
    theme: str | None = None

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
    dungeon_links: dict | None = None


# -----------------------------------------------------------------------------
# S3 adventure format
# -----------------------------------------------------------------------------

class ModuleMeta(BaseModel):
    title: str
    version: str = "1.0"
    party_guidance: dict[str, list[int]] | None = None
    background: str | None = None
    start: str


class RegionCheck(BaseModel):
    chance: str
    every: str


class RegionTableEntry(BaseModel):
    roll: int | str | None = None
    monster: str | None = None
    count: str | None = None


class RegionTable(BaseModel):
    die: str
    entries: list[RegionTableEntry | dict] = Field(default_factory=list)


class Region(BaseModel):
    id: str
    areas: list[str | int]
    check: RegionCheck | None = None
    table: RegionTable | None = None


class Exit(BaseModel):
    to: str | int
    kind: str = "passage"
    hidden: bool = False
    from_x: int | None = None
    from_y: int | None = None
    to_x: int | None = None
    to_y: int | None = None


class DiscoveryTrigger(BaseModel):
    action: str
    scope: str | None = None
    chance: str | None = None
    per: str | None = None


class Discovery(BaseModel):
    what: str
    trigger: DiscoveryTrigger


class Area(BaseModel):
    id: str | int
    name: str
    description: str | None = None
    exits: list[Exit] = Field(default_factory=list)
    contents: list[dict] = Field(default_factory=list)
    monsters: list[dict] = Field(default_factory=list)
    treasure: list[dict] = Field(default_factory=list)
    discoveries: list[Discovery] = Field(default_factory=list)
    # Optional grid data used by the DM Workshop map editor.
    width: int | None = None
    height: int | None = None
    tiles: list[str] | None = None
    start_x: int | None = None
    start_y: int | None = None
    entities: list[dict] = Field(default_factory=list)


class ModuleMonster(BaseModel):
    id: str
    name: str
    frequency: str | None = None
    size: str | None = None
    alignment: str | None = None
    move: str | None = None
    armour_class: int | str | None = None
    hit_dice: str | None = None
    melee_attacks: str | None = None
    senses: str | None = None
    lair_chance: str | None = None
    intelligence: str | None = None
    morale: int | None = None
    loot: str | None = None
    experience: str | None = None
    description: str | None = None
    abilities: list[str] | None = None


class ModuleItem(BaseModel):
    id: str
    name: str
    type: str | None = None
    slot: str | None = None
    effects: dict | None = None
    description: str | None = None


class ModuleMechanic(BaseModel):
    id: str
    name: str
    prose: str
    trigger: dict | None = None


class AdventureData(BaseModel):
    module: ModuleMeta
    regions: list[Region] = Field(default_factory=list)
    areas: list[Area]
    monsters: list[ModuleMonster] = Field(default_factory=list)
    items: list[ModuleItem] = Field(default_factory=list)
    mechanics: list[ModuleMechanic] = Field(default_factory=list)


@dataclass(frozen=True)
class Adventure:
    id: str
    ruleset: str
    data: AdventureData

    @property
    def title(self) -> str:
        return self.data.module.title

    @property
    def description(self) -> str:
        return self.data.module.background or ""


# -----------------------------------------------------------------------------
# Discovery triggers recognised by the engine.
# -----------------------------------------------------------------------------
RECOGNISED_TRIGGER_ACTIONS = {"search", "enter", "rest", "touch", "speak", "time", "leave"}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _module_path(module_id: str) -> Path:
    return SETTINGS.module_root / module_id


def _tactical_path(module_id: str) -> Path:
    return _module_path(module_id) / "module.yaml"


def _adventure_path(module_id: str) -> Path:
    return _module_path(module_id) / "adventure.yaml"


def _to_slug(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "adventure"
    return base


# -----------------------------------------------------------------------------
# Listing / loading
# -----------------------------------------------------------------------------
def list_modules() -> list[dict]:
    """Return metadata for every module under the module root.

    Tactical modules (``module.yaml``) and S3 adventures (``adventure.yaml``)
    are both returned, distinguished by ``format``.
    """
    modules = []
    if not SETTINGS.module_root.exists():
        return modules

    for path in sorted(SETTINGS.module_root.glob("*/module.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        map_doc = doc.get("map", {})
        modules.append({
            "id": doc["id"],
            "name": doc.get("name", doc["id"]),
            "ruleset": doc.get("ruleset", "osric"),
            "description": doc.get("description", ""),
            "format": "tactical",
            "theme": map_doc.get("theme"),
            "width": map_doc.get("width", 0),
            "height": map_doc.get("height", 0),
            "tiles": map_doc.get("tiles", []),
        })

    for path in sorted(SETTINGS.module_root.glob("*/adventure.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = doc.get("module", {})
        modules.append({
            "id": path.parent.name,
            "name": meta.get("title", path.parent.name),
            "ruleset": "osric",
            "description": meta.get("background", "")[:200],
            "format": "s3",
            "theme": None,
            "width": 0,
            "height": 0,
            "tiles": [],
        })

    return modules


def load(module_id: str) -> Module:
    """Load a tactical ``Module`` by id."""
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
        theme=map_doc.get("theme"),
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


def is_adventure(module_id: str) -> bool:
    """True if ``module_id`` resolves to an S3 adventure file."""
    return _adventure_path(module_id).exists()


def load_adventure(module_id: str) -> Adventure:
    """Load an S3 ``Adventure`` by id from the module root."""
    path = _adventure_path(module_id)
    if not path.exists():
        raise KeyError(f"no adventure {module_id!r} at {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = AdventureData.model_validate(doc)
    return Adventure(
        id=module_id,
        ruleset=doc.get("ruleset", "osric"),
        data=data,
    )


def load_module(module_id: str) -> Module | Adventure:
    """Load either a tactical ``Module`` or an S3 ``Adventure``.

    Tactical modules take precedence when both files exist.
    """
    if _tactical_path(module_id).exists():
        return load(module_id)
    if _adventure_path(module_id).exists():
        return load_adventure(module_id)
    raise KeyError(f"no module or adventure {module_id!r}")


def save_adventure(module_id: str, data: dict, check_reachability: bool = True) -> Path:
    """Persist an S3 adventure document under the module root.

    The document is validated before writing.  Returns the written path.
    """
    from backend.app.engine import validate  # avoid circular import at module level

    errors = validate.validate_adventure(data, check_reachability=check_reachability)
    if errors:
        raise ValueError("; ".join(errors))

    path = _adventure_path(module_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def parse_adventure_payload(payload: str | bytes, content_type: str | None = None) -> dict:
    """Parse a YAML or JSON payload into a dict.

    Content type is inspected when available; otherwise the payload is tried
    as YAML first (which also parses JSON).
    """
    if content_type is not None and "json" in content_type.lower():
        return json.loads(payload)
    return yaml.safe_load(payload)
