"""Event-sourced persistence for game sessions.

For the first slice we keep a simple events table plus a latest-snapshot cache.
Replaying all events rebuilds state; snapshots speed it up.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.future import select

from backend.app.db import Base


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    session_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SnapshotRecord(Base):
    __tablename__ = "snapshots"

    session_id = Column(String, primary_key=True)
    version = Column(Integer, nullable=False)
    state = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class EventStore:
    def __init__(self, db_session):
        self.db = db_session

    async def append(self, session_id: str, event_type: str, payload: dict[str, Any]) -> EventRecord:
        record = EventRecord(
            session_id=session_id,
            event_type=event_type,
            payload=json.dumps(payload),
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def events(self, session_id: str):
        result = await self.db.execute(
            select(EventRecord)
            .where(EventRecord.session_id == session_id)
            .order_by(EventRecord.id)
        )
        return result.scalars().all()

    async def snapshot(self, session_id: str) -> SnapshotRecord | None:
        result = await self.db.execute(
            select(SnapshotRecord).where(SnapshotRecord.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def save_snapshot(self, session_id: str, version: int, state: dict[str, Any]):
        record = await self.snapshot(session_id)
        if record:
            record.version = version
            record.state = json.dumps(state)
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = SnapshotRecord(
                session_id=session_id,
                version=version,
                state=json.dumps(state),
            )
            self.db.add(record)
        await self.db.commit()
