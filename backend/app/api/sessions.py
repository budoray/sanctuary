"""Session API."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db import get_db
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


@router.post("/sessions")
async def create_session(db: AsyncSession = Depends(get_db)):
    session = new_session()
    store = EventStore(db)
    await store.append(session.id, "session_created", session.to_dict())
    session = await _load_session(db, session.id)
    return {"session_id": session.id, "state": session.to_dict()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await _load_session(db, session_id)
    return {"session_id": session.id, "state": session.to_dict()}


@router.post("/sessions/{session_id}/move")
async def move_token(session_id: str, req: MoveRequest, db: AsyncSession = Depends(get_db)):
    session = await _load_session(db, session_id)
    token = next((t for t in session.map.tokens if t.id == req.token_id), None)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    payload = {"token_id": req.token_id, "x": req.x, "y": req.y}
    session.apply("token_moved", payload)

    store = EventStore(db)
    await store.append(session_id, "token_moved", payload)
    await store.save_snapshot(session_id, session.version, session.to_dict())

    await socket_manager.emit(
        "message",
        {"type": "move", **payload},
        room=session_id,
    )

    return {"session_id": session_id, "state": session.to_dict()}
