"""Module API: load module metadata, including compiled dungeons."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import DungeonRecord, RoomRecord, get_db
from backend.app.engine import bestiary, dungeon_compiler, items, module

router = APIRouter(tags=["modules"])


def _module_response(mod: module.Module) -> dict:
    return {
        "module": {
            "id": mod.id,
            "name": mod.name,
            "ruleset": mod.ruleset,
            "description": mod.description,
            "map": {
                "width": mod.map.width,
                "height": mod.map.height,
                "tile_size": mod.map.tile_size,
                "tiles": mod.map.tiles,
                "theme": mod.map.theme,
            },
        }
    }


@router.get("/modules")
async def list_all_modules():
    return {"modules": module.list_modules()}


@router.get("/modules/{module_id}")
async def get_module(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    if module_id.startswith("dungeon:"):
        dungeon_id = module_id.split(":", 1)[1]
        result = await db.execute(select(DungeonRecord).where(DungeonRecord.id == dungeon_id))
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Dungeon not found")
        if record.account_id != account_id and not record.public:
            raise HTTPException(status_code=403, detail="Not allowed to view this dungeon")
        order = list(dict.fromkeys(json.loads(record.room_order or "[]")))
        result = await db.execute(select(RoomRecord).where(RoomRecord.id.in_(order)))
        rooms = {r.id: r for r in result.scalars().all()}
        ordered = [rooms[r_id] for r_id in order if r_id in rooms]
        if not ordered:
            raise HTTPException(status_code=400, detail="Dungeon has no rooms")
        mod, _links = dungeon_compiler.compile(record, ordered)
        return _module_response(mod)

    try:
        mod = module.load(module_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _module_response(mod)


@router.get("/bestiary")
async def list_bestiary():
    """Return the slugs of all available monster templates."""
    return {"monsters": bestiary.base_ids()}


@router.get("/items")
async def list_items():
    """Return the available treasure/item templates."""
    return {
        "items": [
            {"id": k, "name": v["name"], "type": v["type"], "slot": v.get("slot")}
            for k, v in items.LOOT_TABLE.items()
        ]
    }
