"""Arena API: start an arena session for a character."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, SessionRecord, get_db
from backend.app.engine import character as char_engine
from backend.app.engine import module, session as session_engine
from backend.app.socket_manager import socket_manager

router = APIRouter(tags=["arena"])


@router.post("/arena/start")
async def start_arena(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
    module_id: str = Query("arena_pit", description="Arena module to use"),
):
    character_id = data.get("character_id")
    turn_timer_seconds = int(data.get("turn_timer_seconds", 0) or 0)

    result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Character not found")

    char_state = json.loads(record.state)
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

    try:
        mod = module.load(module_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    session_id = str(uuid.uuid4())[:8]
    state = await session_engine.new_game(
        session_id,
        mod,
        char,
        turn_timer_seconds=turn_timer_seconds,
        character_id=character_id,
        account_id=account_id,
        mode="arena",
    )

    session_record = SessionRecord(
        id=session_id,
        account_id=account_id,
        campaign_id=None,
        module_id=module_id,
        character_id=character_id,
        name=f"{char.name} in {mod.name} (Arena)",
        status=state["status"],
        state=json.dumps(state),
    )
    db.add(session_record)
    await db.commit()

    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_engine.view(state)},
            room=session_id,
        )
    except Exception:
        pass

    return {"session": session_engine.view(state)}
