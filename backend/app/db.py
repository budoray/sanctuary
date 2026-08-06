"""Database setup."""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import SETTINGS

engine = create_async_engine(SETTINGS.database_url, echo=SETTINGS.app_env == "development")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CharacterRecord(Base):
    __tablename__ = "characters"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    ancestry = Column(String, nullable=False)
    class_ = Column("class", String, nullable=False)  # comma-separated class names
    level = Column(Integer, default=1)
    hp = Column(Integer, default=0)
    max_hp = Column(Integer, default=0)
    ac = Column(Integer, default=10)
    abilities = Column(Text, default="{}")  # JSON scores + modifiers
    saves = Column(Text, default="{}")  # JSON saving throws
    seed = Column(Integer, default=0)
    state = Column(Text, default="{}")  # full serialized Character + log
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    campaign_id = Column(String, index=True, nullable=True)
    module_id = Column(String, nullable=False)
    character_id = Column(String, nullable=False)
    name = Column(String, nullable=False, default="Adventure")
    status = Column(String, default="active")
    state = Column(Text, default="{}")  # full session engine state
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class CampaignRecord(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    ruleset_id = Column(String, default="osric")
    module_ids = Column(Text, default="[]")  # JSON list
    password_hash = Column(String, nullable=False)
    dm_account_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class CampaignMemberRecord(Base):
    __tablename__ = "campaign_members"

    campaign_id = Column(String, primary_key=True)
    account_id = Column(Integer, primary_key=True)
    role = Column(String, default="player")  # 'dm' or 'player'
    joined_at = Column(DateTime, default=_utc_now)


class FriendRecord(Base):
    __tablename__ = "friends"

    account_id = Column(Integer, primary_key=True)
    friend_account_id = Column(Integer, primary_key=True)
    status = Column(String, default="pending")  # pending, accepted, declined
    created_at = Column(DateTime, default=_utc_now)


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    account_id = Column(Integer, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)
    event_type = Column(String, index=True, nullable=False)
    payload_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=_utc_now)


def record_event(
    db: AsyncSession,
    event_type: str,
    account_id: int | None = None,
    session_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> EventRecord:
    """Create an analytics event record (callers must commit)."""
    record = EventRecord(
        event_type=event_type,
        account_id=account_id,
        session_id=session_id,
        payload_json=json.dumps(payload or {}),
    )
    db.add(record)
    return record


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
