"""Database setup."""
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.config import SETTINGS

engine = create_async_engine(SETTINGS.database_url, echo=SETTINGS.app_env == "development")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class CharacterRecord(Base):
    __tablename__ = "characters"

    id = Column(String, primary_key=True)
    account_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    race = Column(String, nullable=False)
    class_ = Column("class", String, nullable=False)
    level = Column(Integer, default=1)
    hp = Column(Integer, default=0)
    max_hp = Column(Integer, default=0)
    ac = Column(Integer, default=10)
    abilities = Column(Text, default="{}")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
