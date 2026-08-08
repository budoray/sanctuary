"""Database setup."""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
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
    ruleset_id = Column(String, default="osric")
    state = Column(Text, default="{}")  # full serialized Character + log
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class SessionRecord(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)  # instance owner
    campaign_id = Column(String, index=True, nullable=True)
    dungeon_id = Column(String, index=True, nullable=True)
    module_id = Column(String, nullable=False)
    adventure_id = Column(String, index=True, nullable=True)  # S3 adventure id if applicable
    character_id = Column(String, nullable=False)
    name = Column(String, nullable=False, default="Adventure")
    status = Column(String, default="active")  # active, paused, won, lost
    visibility = Column(String, default="solo")  # solo, co-op, friends, public, private, invite
    invite_code = Column(String, nullable=True, index=True)
    ruleset_id = Column(String, default="osric")
    dm_account_id = Column(Integer, index=True, nullable=True)  # human DM, null = AI DM
    ai_dm_enabled = Column(Boolean, default=True, nullable=False)
    state = Column(Text, default="{}")  # full session engine state
    state_version = Column(Integer, default=0, nullable=False)  # optimistic locking
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    last_active_at = Column(DateTime, nullable=True)
    saved_at = Column(DateTime, nullable=True)

    __mapper_args__ = {"version_id_col": state_version, "version_id_generator": False}


class RoomRecord(Base):
    __tablename__ = "rooms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    theme = Column(String, default="dungeon")
    width = Column(Integer, default=16)
    height = Column(Integer, default=16)
    tiles = Column(Text, default="[]")  # JSON grid
    entities = Column(Text, default="[]")  # JSON list of placed entities
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class DungeonRecord(Base):
    __tablename__ = "dungeons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    ruleset_id = Column(String, default="osric")
    public = Column(Integer, default=0)  # 0 private, 1 public
    room_order = Column(Text, default="[]")  # JSON list of room ids
    links = Column(Text, default="[]")  # JSON list of transitions
    start_room_id = Column(String, nullable=True)
    start_x = Column(Integer, default=1)
    start_y = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class CampaignRecord(Base):
    __tablename__ = "campaigns"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    ruleset_id = Column(String, default="osric")
    module_ids = Column(Text, default="[]")  # JSON list
    cleared_module_ids = Column(Text, default="[]")  # JSON list
    current_module_index = Column(Integer, default=0)
    quests = Column(Text, default="[]")  # JSON list
    reputation = Column(Text, default="{}")  # JSON object
    journey_notes = Column(Text, default="")
    password_hash = Column(String, nullable=False)
    dm_account_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class AdventureRecord(Base):
    __tablename__ = "adventures"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    ruleset_id = Column(String, default="osric")
    data_json = Column(Text, default="{}")  # full S3 adventure document
    status = Column(String, default="draft")  # draft, published, archived
    visibility = Column(String, default="private")  # private, public, unlisted
    rating_sum = Column(Integer, default=0)
    rating_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    tags = Column(Text, default="[]")  # JSON list
    parent_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


class CustomRulesetRecord(Base):
    __tablename__ = "rulesets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    account_id = Column(Integer, index=True, nullable=False)
    base_ruleset_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    overrides_json = Column(Text, default="{}")  # JSON overrides merged onto base manifest
    status = Column(String, default="draft")  # draft, published, archived
    visibility = Column(String, default="private")  # private, public, unlisted
    rating_sum = Column(Integer, default=0)
    rating_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    tags = Column(Text, default="[]")  # JSON list
    parent_id = Column(String, nullable=True, index=True)
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
