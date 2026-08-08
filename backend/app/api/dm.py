"""DM-only session actions."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import SessionRecord, get_db
from backend.app.engine import session as session_engine
from backend.app.socket_manager import socket_manager

# Import access helpers from the sessions router to keep campaign/DM rules consistent.
from backend.app.api.sessions import _can_access_session, _emit_session_events, _is_campaign_dm, _load_session_module

router = APIRouter(tags=["dm"])


async def _load_session_dm_only(
    session_id: str,
    account_id: int,
    db: AsyncSession,
) -> SessionRecord:
    """Return the session if it exists and the caller is the DM."""
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if not await _is_campaign_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the DM can use this action")
    return record


@router.post("/sessions/{session_id}/dm/spawn")
async def dm_spawn(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        scale = data.get("scale")
        if scale is not None:
            scale = float(scale)
        await session_engine.dm_spawn(
            state,
            mod,
            data["name"],
            int(data["x"]),
            int(data["y"]),
            token_id=data.get("token_id"),
            scale=scale,
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/prop")
async def dm_prop(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        await session_engine.dm_prop(
            state,
            mod,
            data["type"],
            int(data["x"]),
            int(data["y"]),
            variant=data.get("variant"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/trap")
async def dm_trap(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        await session_engine.dm_trap(
            state,
            mod,
            int(data["x"]),
            int(data["y"]),
            damage=data.get("damage", "1d6"),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/move")
async def dm_move(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        await session_engine.dm_move(
            state, mod, data["token_id"], int(data["x"]), int(data["y"])
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/damage")
async def dm_damage(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)

    try:
        await session_engine.dm_damage(state, data["token_id"], int(data["amount"]))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/reveal")
async def dm_reveal(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        await session_engine.dm_reveal(
            state, mod, int(data["x"]), int(data["y"]), int(data.get("radius", 4))
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/hide")
async def dm_hide(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    try:
        await session_engine.dm_hide(
            state, mod, int(data["x"]), int(data["y"]), int(data.get("radius", 4))
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/weather")
async def dm_weather(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)

    try:
        await session_engine.dm_weather(state, data.get("weather", "auto"))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}


@router.post("/sessions/{session_id}/dm/lighting")
async def dm_lighting(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    record = await _load_session_dm_only(session_id, account_id, db)
    state = json.loads(record.state)
    prev_state = json.loads(record.state)

    try:
        await session_engine.dm_lighting(state, data.get("lighting", "day"))
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    _emit_session_events(db, prev_state, state, account_id)
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update", {"session": session_view}, room=session_id
        )
    except Exception:
        pass
    return {"session": session_view}
