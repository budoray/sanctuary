"""Compile a DungeonRecord + RoomRecords into a Module the engine can play."""
from __future__ import annotations

import json
import uuid
from typing import Any

from backend.app.db import DungeonRecord, RoomRecord
from backend.app.engine import items
from backend.app.engine.module import Event, Map, Module, MonsterSpawn

ROOM_SIZE = 16
SEPARATOR = 1  # wall column between rooms


def generate_id() -> str:
    return str(uuid.uuid4())[:8]


def _room_offset(room_index: int) -> tuple[int, int]:
    x = room_index * (ROOM_SIZE + SEPARATOR)
    return x, 0


def compile(record: DungeonRecord, rooms: list[RoomRecord]) -> Module:
    """Build a Module from a dungeon definition."""
    order = json.loads(record.room_order or "[]")
    if not order:
        order = [r.id for r in rooms]
    room_by_id = {r.id: r for r in rooms}
    ordered = [room_by_id[r_id] for r_id in order if r_id in room_by_id]
    if not ordered:
        raise ValueError("dungeon has no valid rooms")

    room_count = len(ordered)
    width = room_count * ROOM_SIZE + (room_count - 1) * SEPARATOR
    height = ROOM_SIZE
    tiles = [["1"] * width for _ in range(height)]

    offsets: dict[str, tuple[int, int]] = {}
    for idx, room in enumerate(ordered):
        ox, oy = _room_offset(idx)
        offsets[room.id] = (ox, oy)
        room_tiles = json.loads(room.tiles or "[]")
        if len(room_tiles) != ROOM_SIZE or any(len(row) != ROOM_SIZE for row in room_tiles):
            room_tiles = [["1"] * ROOM_SIZE for _ in range(ROOM_SIZE)]
        for y in range(ROOM_SIZE):
            for x in range(ROOM_SIZE):
                tiles[oy + y][ox + x] = room_tiles[y][x]

    links = json.loads(record.links or "[]")

    # Convert room entities to global spawns/events.
    monsters: list[MonsterSpawn] = []
    events: list[Event] = []
    entity_index = 0
    for room in ordered:
        ox, oy = offsets[room.id]
        room_entities = json.loads(room.entities or "[]")
        for ent in room_entities:
            ent_type = ent.get("type")
            ex = int(ent.get("x", 0))
            ey = int(ent.get("y", 0))
            gx, gy = ox + ex, oy + ey
            entity_index += 1
            if ent_type == "monster":
                for i in range(ent.get("count", 1)):
                    monsters.append(
                        MonsterSpawn(
                            id=f"{room.id}_m{entity_index}_{i}",
                            name=ent.get("name") or ent.get("key", "monster").capitalize(),
                            monster=ent.get("key", "goblin"),
                            x=gx,
                            y=gy,
                            color=ent.get("color", "#e74c3c"),
                        )
                    )
            elif ent_type == "trap":
                events.append(
                    Event(
                        id=f"{room.id}_t{entity_index}",
                        x=gx,
                        y=gy,
                        message=ent.get("message") or f"A {ent.get('key', 'trap')} triggers!",
                        choices={"ok": f"trap:{ent.get('damage', '1d6')}"},
                    )
                )
            elif ent_type == "treasure":
                events.append(
                    Event(
                        id=f"{room.id}_tr{entity_index}",
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
                item_id = ent.get("item_id", "healing_potion")
                template = items.LOOT_TABLE.get(item_id, items.LOOT_TABLE["healing_potion"])
                events.append(
                    Event(
                        id=f"{room.id}_i{entity_index}",
                        x=gx,
                        y=gy,
                        message=f"You find {template['name']}.",
                        choices={"take": f"item:{item_id}"},
                    )
                )
            elif ent_type == "event":
                events.append(
                    Event(
                        id=f"{room.id}_e{entity_index}",
                        x=gx,
                        y=gy,
                        message=ent.get("message") or "Something happens.",
                        choices=ent.get("choices", {"ok": "none"}),
                    )
                )

    # Build link lookup for the session engine.
    link_lookup: dict[str, dict[str, Any]] = {}
    for link in links:
        room_id = link.get("from_room_id")
        lx = link.get("from_x")
        ly = link.get("from_y")
        to_room = link.get("to_room_id")
        tx = link.get("to_x")
        ty = link.get("to_y")
        if room_id not in offsets or to_room not in offsets:
            continue
        ox, oy = offsets[room_id]
        tox, toy = offsets[to_room]
        gx, gy = ox + int(lx), oy + int(ly)
        tgx, tgy = tox + int(tx), toy + int(ty)
        link_lookup[f"{gx},{gy}"] = {
            "x": tgx,
            "y": tgy,
            "room_id": to_room,
            "kind": link.get("kind", "passage"),
        }

    start_room = record.start_room_id or ordered[0].id
    start_x = (record.start_x or 1)
    start_y = (record.start_y or 1)
    if start_room not in offsets:
        start_room = ordered[0].id
    sox, soy = offsets[start_room]
    player_start = (sox + start_x, soy + start_y)

    map_ = Map(
        width=width,
        height=height,
        tile_size=64,
        tiles=["".join(row) for row in tiles],
        theme=ordered[0].theme or "dungeon",
    )

    mod = Module(
        id=f"dungeon:{record.id}",
        name=record.name,
        ruleset=record.ruleset_id or "osric",
        description=f"A custom dungeon built by the DM.",
        map=map_,
        player_start=player_start,
        monsters=monsters,
        events=events,
        branches=[],
    )
    return mod, link_lookup
