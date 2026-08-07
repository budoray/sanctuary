"""Room editor API: CRUD for 16x16 dungeon rooms."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import RoomRecord, get_db

router = APIRouter(tags=["rooms"])

DEFAULT_TILES = [["1"] * 16 for _ in range(16)]
# carve a small starting chamber
for y in range(6, 10):
    for x in range(6, 10):
        DEFAULT_TILES[y][x] = "0"


def _room_response(record: RoomRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "theme": record.theme or "dungeon",
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
    tiles = data.get("tiles")
    if not isinstance(tiles, list) or len(tiles) != 16 or any(len(row) != 16 for row in tiles):
        tiles = DEFAULT_TILES
    entities = data.get("entities", [])
    if not isinstance(entities, list):
        entities = []

    record = RoomRecord(
        account_id=account_id,
        name=name,
        theme=theme,
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
        tiles = data["tiles"]
        if isinstance(tiles, list) and len(tiles) == 16 and all(len(row) == 16 for row in tiles):
            record.tiles = json.dumps(tiles)
        else:
            raise HTTPException(status_code=400, detail="tiles must be a 16x16 grid")
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
