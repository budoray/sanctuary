"""Room editor API: CRUD for variable-sized dungeon rooms."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import RoomRecord, get_db

router = APIRouter(tags=["rooms"])

MIN_SIZE = 4
MAX_SIZE = 64


def _default_tiles(width: int = 16, height: int = 16) -> list[list[str]]:
    tiles = [["1"] * width for _ in range(height)]
    cx, cy = width // 2, height // 2
    for y in range(cy - 1, cy + 2):
        for x in range(cx - 1, cx + 2):
            if 0 <= y < height and 0 <= x < width:
                tiles[y][x] = "0"
    return tiles


def _validate_tiles(tiles: Any) -> tuple[list[list[str]], int, int]:
    if not isinstance(tiles, list) or not tiles:
        raise HTTPException(status_code=400, detail="tiles must be a non-empty list of rows")
    height = len(tiles)
    width = len(tiles[0]) if height else 0
    if height < MIN_SIZE or width < MIN_SIZE or height > MAX_SIZE or width > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"room must be between {MIN_SIZE}x{MIN_SIZE} and {MAX_SIZE}x{MAX_SIZE}")
    if any(len(row) != width for row in tiles):
        raise HTTPException(status_code=400, detail="all tile rows must have the same width")
    normalized = [[str(cell) for cell in row] for row in tiles]
    return normalized, width, height


def _room_response(record: RoomRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "theme": record.theme or "dungeon",
        "width": record.width or 16,
        "height": record.height or 16,
        "tiles": json.loads(record.tiles or "[]"),
        "entities": json.loads(record.entities or "[]"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


@router.get("/rooms")
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(RoomRecord)
        .where(RoomRecord.account_id == account_id)
        .order_by(RoomRecord.updated_at.desc())
    )
    return {"rooms": [_room_response(r) for r in result.scalars().all()]}


@router.post("/rooms")
async def create_room(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    name = data.get("name", "New Room").strip() or "New Room"
    theme = data.get("theme", "dungeon")
    width = int(data.get("width", 16))
    height = int(data.get("height", 16))
    tiles = data.get("tiles")
    if isinstance(tiles, list) and tiles:
        tiles, width, height = _validate_tiles(tiles)
    else:
        width = max(MIN_SIZE, min(MAX_SIZE, width))
        height = max(MIN_SIZE, min(MAX_SIZE, height))
        tiles = _default_tiles(width, height)
    entities = data.get("entities", [])
    if not isinstance(entities, list):
        entities = []

    record = RoomRecord(
        account_id=account_id,
        name=name,
        theme=theme,
        width=width,
        height=height,
        tiles=json.dumps(tiles),
        entities=json.dumps(entities),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"room": _room_response(record)}


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(select(RoomRecord).where(RoomRecord.id == room_id))
    record = result.scalar_one_or_none()
    if not record or record.account_id != account_id:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"room": _room_response(record)}


@router.put("/rooms/{room_id}")
async def update_room(
    room_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(select(RoomRecord).where(RoomRecord.id == room_id))
    record = result.scalar_one_or_none()
    if not record or record.account_id != account_id:
        raise HTTPException(status_code=404, detail="Room not found")

    if "name" in data:
        record.name = data["name"].strip() or record.name
    if "theme" in data:
        record.theme = data["theme"]
    if "tiles" in data:
        tiles, width, height = _validate_tiles(data["tiles"])
        record.tiles = json.dumps(tiles)
        record.width = width
        record.height = height
    if "width" in data and "height" in data and "tiles" not in data:
        width = max(MIN_SIZE, min(MAX_SIZE, int(data["width"])))
        height = max(MIN_SIZE, min(MAX_SIZE, int(data["height"])))
        record.width = width
        record.height = height
        record.tiles = json.dumps(_default_tiles(width, height))
    if "entities" in data:
        entities = data["entities"]
        if not isinstance(entities, list):
            raise HTTPException(status_code=400, detail="entities must be a list")
        record.entities = json.dumps(entities)

    await db.commit()
    await db.refresh(record)
    return {"room": _room_response(record)}


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(select(RoomRecord).where(RoomRecord.id == room_id))
    record = result.scalar_one_or_none()
    if not record or record.account_id != account_id:
        raise HTTPException(status_code=404, detail="Room not found")
    await db.delete(record)
    await db.commit()
    return {"deleted": True}
