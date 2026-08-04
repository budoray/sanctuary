"""Session API."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import uuid

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, get_db
from backend.app.engine.character import make_character
from backend.app.engine.dm import DMController
from backend.app.engine.session import GameSession, new_session
from backend.app.engine.store import EventStore
from backend.app.socket_manager import socket_manager

router = APIRouter(tags=["sessions"])


class MoveRequest(BaseModel):
    token_id: str
    x: int
    y: int


async def _load_session(db: AsyncSession, session_id: str) -> GameSession:
    store = EventStore(db)
    snapshot = await store.snapshot(session_id)
    events = await store.events(session_id)

    if not snapshot and not events:
        raise HTTPException(status_code=404, detail="Session not found")

    session = None
    start_from = 0
    if snapshot:
        session = GameSession.from_dict(json.loads(snapshot.state))
        start_from = snapshot.version

    for ev in events:
        if ev.id <= start_from:
            continue
        payload = json.loads(ev.payload)
        if session is None and ev.event_type == "session_created":
            session = GameSession.from_dict(payload)
        elif session:
            session.apply(ev.event_type, payload)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    # Version is the count of events that have been applied.
    session.version = len(events)
    return session


async def _get_or_create_character(db: AsyncSession, account_id: int) -> CharacterRecord:
    from sqlalchemy.future import select

    result = await db.execute(
        select(CharacterRecord).where(CharacterRecord.account_id == account_id).limit(1)
    )
    record = result.scalar_one_or_none()
    if record:
        return record

    char = make_character(account_id=account_id, name="Hero", race="Human", class_="Fighter")
    char.id = str(uuid.uuid4())[:8]
    record = CharacterRecord(
        id=char.id,
        account_id=char.account_id,
        name=char.name,
        race=char.race,
        class_=char.class_,
        level=char.level,
        hp=char.hp,
        max_hp=char.max_hp,
        ac=char.ac,
        abilities=json.dumps(char.abilities),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.post("/sessions")
async def create_session(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    char = await _get_or_create_character(db, account_id)
    session = new_session(account_id=account_id)
    # Name the player token after the character.
    hero = next((t for t in session.map.tokens if t.owner == "player"), None)
    if hero:
        hero.name = char.name
    store = EventStore(db)
    await store.append(session.id, "session_created", session.to_dict())
    session = await _load_session(db, session.id)
    return {"session_id": session.id, "state": session.to_dict()}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    session = await _load_session(db, session_id)
    if session.account_id != account_id:
        raise HTTPException(status_code=403, detail="Not your session")
    return {"session_id": session.id, "state": session.to_dict()}


@router.post("/sessions/{session_id}/move")
async def move_token(
    session_id: str,
    req: MoveRequest,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    session = await _load_session(db, session_id)
    if session.account_id != account_id:
        raise HTTPException(status_code=403, detail="Not your session")

    token = next((t for t in session.map.tokens if t.id == req.token_id), None)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    payload = {"token_id": req.token_id, "x": req.x, "y": req.y}
    session.apply("token_moved", payload)
    session.end_player_turn()

    store = EventStore(db)
    await store.append(session_id, "token_moved", payload)

    # AI DM turn
    dm = DMController()
    dm_result = await dm.take_turn(session)
    dm_payload = {"turn": session.turn + 1}
    if "token_id" in dm_result:
        session.apply("token_moved", {
            "token_id": dm_result["token_id"],
            "x": dm_result["x"],
            "y": dm_result["y"],
        })
        await store.append(session_id, "token_moved", {
            "token_id": dm_result["token_id"],
            "x": dm_result["x"],
            "y": dm_result["y"],
        })
        dm_payload["move"] = {
            "token_id": dm_result["token_id"],
            "x": dm_result["x"],
            "y": dm_result["y"],
        }
    entry = {"turn": session.turn, "text": dm_result.get("narration", "The DM acts.")}
    dm_payload["entry"] = entry
    session.apply("dm_turn", dm_payload)
    await store.append(session_id, "dm_turn", dm_payload)
    await store.save_snapshot(session_id, session.version, session.to_dict())

    await socket_manager.emit(
        "message",
        {"type": "move", **payload},
        room=session_id,
    )
    if "move" in dm_payload:
        await socket_manager.emit(
            "message",
            {"type": "move", **dm_payload["move"]},
            room=session_id,
        )
    await socket_manager.emit(
        "message",
        {"type": "dm_turn", "entry": entry},
        room=session_id,
    )

    return {"session_id": session_id, "state": session.to_dict()}
