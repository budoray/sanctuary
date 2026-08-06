"""Session API: start, view, act in a tactical module."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, SessionRecord, get_db
from backend.app.engine import character as char_engine
from backend.app.engine import module, session as session_engine

router = APIRouter(tags=["sessions"])

DEFAULT_MODULE = "sample_lair"


@router.post("/sessions")
async def create_session(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    character_id = data.get("character_id")
    module_id = data.get("module_id", DEFAULT_MODULE)

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
    )

    mod = module.load(module_id)
    session_id = str(uuid.uuid4())[:8]
    state = session_engine.new_game(session_id, mod, char)

    session_record = SessionRecord(
        id=session_id,
        account_id=account_id,
        module_id=module_id,
        character_id=character_id,
        name=f"{char.name} in {mod.name}",
        status=state["status"],
        state=json.dumps(state),
    )
    db.add(session_record)
    await db.commit()

    return {"session": session_engine.view(state)}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord)
        .where(SessionRecord.account_id == account_id)
        .order_by(SessionRecord.updated_at.desc())
    )
    records = result.scalars().all()
    sessions = []
    for r in records:
        try:
            state = json.loads(r.state)
        except Exception:
            state = {"status": r.status}
        sessions.append({
            "id": r.id,
            "name": r.name,
            "module_id": r.module_id,
            "character_id": r.character_id,
            "status": r.status,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
        })
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(
            SessionRecord.id == session_id,
            SessionRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    state = json.loads(record.state)
    return {"session": session_engine.view(state)}


@router.post("/sessions/{session_id}/act")
async def act_in_session(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(
            SessionRecord.id == session_id,
            SessionRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    state = json.loads(record.state)
    mod = module.load(record.module_id)
    action = data.get("action")
    try:
        state = session_engine.act(
            state,
            mod,
            action,
            **{k: v for k, v in data.items() if k != "action"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    return {"session": session_engine.view(state)}
