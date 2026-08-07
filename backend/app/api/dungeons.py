"""Dungeon editor API: collections of linked rooms."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, DungeonRecord, RoomRecord, SessionRecord, get_db, record_event
from backend.app.engine import character as char_engine
from backend.app.engine import dungeon_compiler, session as session_engine
from backend.app.api.rulesets import resolve_ruleset
from backend.app.socket_manager import socket_manager

router = APIRouter(tags=["dungeons"])


def _dungeon_response(record: DungeonRecord, rooms: list[RoomRecord] | None = None) -> dict[str, Any]:
    out = {
        "id": record.id,
        "account_id": record.account_id,
        "name": record.name,
        "ruleset_id": record.ruleset_id or "osric",
        "public": bool(record.public),
        "room_order": json.loads(record.room_order or "[]"),
        "links": json.loads(record.links or "[]"),
        "start_room_id": record.start_room_id,
        "start_x": record.start_x or 1,
        "start_y": record.start_y or 1,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if rooms is not None:
        out["rooms"] = [
            {
                "id": r.id,
                "name": r.name,
                "theme": r.theme or "dungeon",
                "tiles": json.loads(r.tiles or "[]"),
                "entities": json.loads(r.entities or "[]"),
            }
            for r in rooms
        ]
    return out


@router.get("/dungeons")
async def list_dungeons(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(DungeonRecord).where(
            (DungeonRecord.account_id == account_id) | (DungeonRecord.public == 1)
        ).order_by(DungeonRecord.updated_at.desc())
    )
    return {"dungeons": [_dungeon_response(r) for r in result.scalars().all()]}


@router.post("/dungeons")
async def create_dungeon(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    name = data.get("name", "New Dungeon").strip() or "New Dungeon"
    record = DungeonRecord(
        account_id=account_id,
        name=name,
        ruleset_id=data.get("ruleset_id", "osric"),
        public=1 if data.get("public") else 0,
        room_order=json.dumps(data.get("room_order", [])),
        links=json.dumps(data.get("links", [])),
        start_room_id=data.get("start_room_id"),
        start_x=int(data.get("start_x", 1)),
        start_y=int(data.get("start_y", 1)),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"dungeon": _dungeon_response(record)}


async def _load_dungeon(
    dungeon_id: str,
    account_id: int,
    db: AsyncSession,
) -> tuple[DungeonRecord, list[RoomRecord]]:
    result = await db.execute(select(DungeonRecord).where(DungeonRecord.id == dungeon_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Dungeon not found")
    if record.account_id != account_id and not record.public:
        raise HTTPException(status_code=403, detail="Not allowed to view this dungeon")

    order = json.loads(record.room_order or "[]")
    if not order:
        return record, []
    result = await db.execute(select(RoomRecord).where(RoomRecord.id.in_(order)))
    rooms = {r.id: r for r in result.scalars().all()}
    ordered = [rooms[r_id] for r_id in order if r_id in rooms]
    return record, ordered


@router.get("/dungeons/{dungeon_id}")
async def get_dungeon(
    dungeon_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record, rooms = await _load_dungeon(dungeon_id, account_id, db)
    return {"dungeon": _dungeon_response(record, rooms)}


@router.put("/dungeons/{dungeon_id}")
async def update_dungeon(
    dungeon_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(DungeonRecord).where(
            DungeonRecord.id == dungeon_id,
            DungeonRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Dungeon not found")

    if "name" in data:
        record.name = data["name"].strip() or record.name
    if "ruleset_id" in data:
        record.ruleset_id = data["ruleset_id"]
    if "public" in data:
        record.public = 1 if data["public"] else 0
    if "room_order" in data:
        record.room_order = json.dumps(data["room_order"])
    if "links" in data:
        record.links = json.dumps(data["links"])
    if "start_room_id" in data:
        record.start_room_id = data["start_room_id"]
    if "start_x" in data:
        record.start_x = int(data["start_x"])
    if "start_y" in data:
        record.start_y = int(data["start_y"])

    await db.commit()
    await db.refresh(record)
    _, rooms = await _load_dungeon(dungeon_id, account_id, db)
    return {"dungeon": _dungeon_response(record, rooms)}


@router.delete("/dungeons/{dungeon_id}")
async def delete_dungeon(
    dungeon_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(DungeonRecord).where(
            DungeonRecord.id == dungeon_id,
            DungeonRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Dungeon not found")
    await db.delete(record)
    await db.commit()
    return {"deleted": True}


@router.post("/dungeons/{dungeon_id}/play")
async def play_dungeon(
    dungeon_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Create a session using a compiled dungeon."""
    character_id = data.get("character_id")
    campaign_id = data.get("campaign_id")
    turn_timer_seconds = int(data.get("turn_timer_seconds", 0) or 0)

    record, rooms = await _load_dungeon(dungeon_id, account_id, db)
    if not rooms:
        raise HTTPException(status_code=400, detail="Dungeon has no rooms")

    char_result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    char_record = char_result.scalar_one_or_none()
    if not char_record:
        raise HTTPException(status_code=404, detail="Character not found")

    char_state = json.loads(char_record.state)
    char = char_engine.Character(
        name=char_state["name"],
        ancestry=char_state["ancestry"],
        classes=tuple(char_state["classes"]),
        levels=char_state["levels"],
        scores=char_state["scores"],
        hit_points=char_state["hit_points"],
        armour_class=char_state["armour_class"],
        saves=char_state["saves"],
        modifiers=char_state["modifiers"],
        seed=char_state["seed"],
        log=tuple(),
        xp=char_state.get("xp", 0),
        level=char_state.get("level", 1),
        gold=char_state.get("gold", 0),
        inventory=tuple(char_state.get("inventory", [])),
        equipment=char_state.get("equipment", {}),
    )

    mod, links = dungeon_compiler.compile(record, rooms)
    ruleset_id = record.ruleset_id or "osric"
    ruleset = await resolve_ruleset(ruleset_id, account_id=account_id, db=db)
    monsters_dir = ruleset.content_path("monsters")
    session_id = dungeon_compiler.generate_id()
    state = await session_engine.new_game(
        session_id,
        mod,
        char,
        turn_timer_seconds=turn_timer_seconds,
        character_id=character_id,
        account_id=account_id,
        mode="dungeon",
        dungeon_links=links,
        monsters_dir=monsters_dir,
    )
    state["dungeon_id"] = dungeon_id
    if campaign_id:
        state["campaign_id"] = campaign_id

    session_record = SessionRecord(
        id=session_id,
        account_id=account_id,
        campaign_id=campaign_id,
        dungeon_id=dungeon_id,
        module_id=f"dungeon:{dungeon_id}",
        character_id=character_id,
        name=f"{char.name} in {record.name}",
        status=state["status"],
        ruleset_id=ruleset_id,
        state=json.dumps(state),
    )
    db.add(session_record)
    record_event(
        db,
        "session_start",
        account_id=account_id,
        session_id=session_id,
        payload={"dungeon_id": dungeon_id, "campaign_id": campaign_id},
    )
    await db.commit()

    return {"session": session_engine.view(state)}
