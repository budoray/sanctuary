"""Compile an S3 Adventure into a tactical Module for play.

The workshop stores each area as a small grid.  This compiler lays the areas
out horizontally (with a one-tile wall separator), converts placed entities to
monsters/events, and turns area exits into dungeon-style transition links.
"""
from __future__ import annotations

from backend.app.db import AdventureRecord
from backend.app.engine import items
from backend.app.engine.module import Adventure, Area, Event, Map, Module, MonsterSpawn

SEPARATOR = 1
DEFAULT_SIZE = 8


def _area_size(area: Area) -> tuple[int, int]:
    tiles = area.tiles or []
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    if width == 0 or height == 0:
        width = area.width or DEFAULT_SIZE
        height = area.height or DEFAULT_SIZE
        tiles = None
    # If declared size differs from tile data, trust the tile data.
    return width, height, tiles


def _default_tiles(width: int, height: int) -> list[str]:
    return ["0" * width for _ in range(height)]


def _ensure_tiles(area: Area) -> tuple[int, int, list[str]]:
    width, height, tiles = _area_size(area)
    if tiles is None or len(tiles) != height or any(len(row) != width for row in tiles):
        tiles = _default_tiles(width, height)
    return width, height, tiles


def compile(adventure: Adventure) -> Module:
    """Build a tactical ``Module`` from an S3 ``Adventure``."""
    data = adventure.data
    areas = data.areas
    if not areas:
        raise ValueError("adventure has no areas")

    area_by_id: dict[str | int, Area] = {}
    for area in areas:
        area_by_id[area.id] = area

    start_id = data.module.start
    start_area = area_by_id.get(start_id)
    if start_area is None:
        start_area = areas[0]
        start_id = start_area.id

    sizes: list[tuple[int, int, list[str]]] = []
    for area in areas:
        sizes.append(_ensure_tiles(area))

    total_width = sum(w for w, _, _ in sizes) + (len(areas) - 1) * SEPARATOR
    total_height = max(h for _, h, _ in sizes)
    tiles = [["1"] * total_width for _ in range(total_height)]

    offsets: dict[str | int, tuple[int, int]] = {}
    x_offset = 0
    for idx, area in enumerate(areas):
        w, h, area_tiles = sizes[idx]
        ox, oy = x_offset, 0
        offsets[area.id] = (ox, oy)
        for y in range(h):
            for x in range(w):
                tiles[oy + y][ox + x] = area_tiles[y][x]
        x_offset += w + SEPARATOR

    # Convert placed entities to global spawns/events.
    monsters: list[MonsterSpawn] = []
    events: list[Event] = []
    entity_index = 0
    for area in areas:
        ox, oy = offsets[area.id]
        w, h, _ = sizes[areas.index(area)]
        for ent in area.entities or []:
            ent_type = ent.get("type")
            ex = int(ent.get("x", 0))
            ey = int(ent.get("y", 0))
            if ex < 0 or ex >= w or ey < 0 or ey >= h:
                continue
            gx, gy = ox + ex, oy + ey
            entity_index += 1
            if ent_type == "monster":
                key = ent.get("key") or ent.get("monster") or "goblin"
                for i in range(ent.get("count", 1)):
                    monsters.append(
                        MonsterSpawn(
                            id=f"{area.id}_m{entity_index}_{i}",
                            name=ent.get("name") or key.capitalize(),
                            monster=key,
                            x=gx,
                            y=gy,
                            color=ent.get("color", "#e74c3c"),
                        )
                    )
            elif ent_type == "trap":
                events.append(
                    Event(
                        id=f"{area.id}_t{entity_index}",
                        x=gx,
                        y=gy,
                        message=ent.get("message") or f"A {ent.get('key', 'trap')} triggers!",
                        choices={"ok": f"trap:{ent.get('damage', '1d6')}"},
                    )
                )
            elif ent_type == "treasure":
                events.append(
                    Event(
                        id=f"{area.id}_tr{entity_index}",
                        x=gx,
                        y=gy,
                        message=ent.get("message") or "You find treasure.",
                        choices={
                            "take": f"gold:{ent.get('value', 0)}",
                            "item": ent.get("item_id", ""),
                        },
                    )
                )
            elif ent_type == "item":
                item_id = ent.get("item_id") or "healing_potion"
                template = items.LOOT_TABLE.get(item_id, items.LOOT_TABLE["healing_potion"])
                events.append(
                    Event(
                        id=f"{area.id}_i{entity_index}",
                        x=gx,
                        y=gy,
                        message=f"You find {template['name']}.",
                        choices={"take": f"item:{item_id}"},
                    )
                )
            elif ent_type == "event":
                events.append(
                    Event(
                        id=f"{area.id}_e{entity_index}",
                        x=gx,
                        y=gy,
                        message=ent.get("message") or "Something happens.",
                        choices=ent.get("choices", {"ok": "none"}),
                    )
                )

    # Build transition links from area exits.
    link_lookup: dict[str, dict] = {}
    for area in areas:
        ox, oy = offsets[area.id]
        w, h, _ = sizes[areas.index(area)]
        for ex in area.exits:
            target = area_by_id.get(ex.to)
            if target is None:
                continue
            tox, toy = offsets[target.id]
            sx = ox + (ex.from_x if ex.from_x is not None else (area.start_x or w // 2))
            sy = oy + (ex.from_y if ex.from_y is not None else (area.start_y or h // 2))
            tx = tox + (ex.to_x if ex.to_x is not None else (target.start_x or (sizes[areas.index(target)][0] // 2)))
            ty = toy + (ex.to_y if ex.to_y is not None else (target.start_y or (sizes[areas.index(target)][1] // 2)))
            link_lookup[f"{sx},{sy}"] = {
                "x": tx,
                "y": ty,
                "kind": ex.kind,
                "hidden": ex.hidden,
            }

    # Player start position.
    start_w, start_h, _ = sizes[areas.index(start_area)]
    px = offsets[start_id][0] + (start_area.start_x or start_w // 2)
    py = offsets[start_id][1] + (start_area.start_y or start_h // 2)

    map_ = Map(
        width=total_width,
        height=total_height,
        tile_size=64,
        tiles=["".join(row) for row in tiles],
        theme="dungeon",
    )

    mod = Module(
        id=adventure.id,
        name=data.module.title,
        ruleset=adventure.ruleset,
        description=data.module.background or "",
        map=map_,
        player_start=(px, py),
        monsters=monsters,
        events=events,
        branches=[],
        dungeon_links=link_lookup,
    )
    return mod


def compile_record(record: AdventureRecord) -> Module:
    """Compile an ``AdventureRecord`` without loading it through ``module.load_adventure``."""
    import json
    from backend.app.engine.module import AdventureData

    data = AdventureData.model_validate(json.loads(record.data_json))
    adventure = Adventure(id=record.id, ruleset=record.ruleset_id or "osric", data=data)
    return compile(adventure)
