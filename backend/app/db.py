"""Database setup."""
from datetime import datetime, timezone

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
    module_id = Column(String, nullable=False)
    character_id = Column(String, nullable=False)
    name = Column(String, nullable=False, default="Adventure")
    status = Column(String, default="active")
    state = Column(Text, default="{}")  # full session engine state
    created_at = Column(DateTime, default=_utc_now)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
