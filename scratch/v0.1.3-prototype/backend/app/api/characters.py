"""Character API."""
import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, get_db
from backend.app.engine.character import Character, make_character

router = APIRouter(tags=["characters"])


def _to_dict(record: CharacterRecord) -> dict:
    return {
        "id": record.id,
        "account_id": record.account_id,
        "name": record.name,
        "race": record.race,
        "class": record.class_,
        "level": record.level,
        "hp": record.hp,
        "max_hp": record.max_hp,
        "ac": record.ac,
        "abilities": json.loads(record.abilities or "{}"),
    }


@router.get("/characters")
async def list_characters(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CharacterRecord).where(CharacterRecord.account_id == account_id)
    )
    return {"characters": [_to_dict(r) for r in result.scalars().all()]}


@router.post("/characters")
async def create_character(
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    char = make_character(
        account_id=account_id,
        name=data.get("name", "Hero"),
        race=data.get("race", "Human"),
        class_=data.get("class", "Fighter"),
    )
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
    return {"character": _to_dict(record)}
