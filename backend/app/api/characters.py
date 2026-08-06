"""Character API."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, get_db
from backend.app.engine import character as char_engine
from backend.app.engine import items

from backend.app.engine.character import ABILITIES, ANCESTRIES, CLASSES, GEN_MODES, arrangeable

router = APIRouter(tags=["characters"])


@router.get("/ruleset/osric/options")
async def osric_options():
    """Player-facing options for the OSRIC ruleset."""
    return {
        "abilities": list(ABILITIES),
        "ancestries": list(ANCESTRIES),
        "classes": list(CLASSES),
        "modes": [
            {"id": m, "roll": "3d6" if "hardest" in m or "difficult" in m else "4d6 drop lowest", "arrange": arrangeable(m)}
            for m in GEN_MODES
        ],
    }


def _serialize(character: char_engine.Character) -> dict[str, Any]:
    return {
        "id": None,
        "name": character.name,
        "ancestry": character.ancestry,
        "classes": list(character.classes),
        "levels": character.levels,
        "scores": character.scores,
        "hit_points": character.hit_points,
        "max_hp": character.hit_points,
        "armour_class": character.armour_class,
        "saves": character.saves,
        "modifiers": character.modifiers,
        "seed": character.seed,
        "log": [
            {
                "index": r.index,
                "expr": r.expr,
                "faces": list(r.faces),
                "kept": list(r.kept),
                "mods": r.mods,
                "total": r.total,
                "reason": r.reason,
                "tags": r.tags,
            }
            for r in character.log
        ],
        "xp": getattr(character, "xp", 0),
        "level": getattr(character, "level", 1),
        "gold": getattr(character, "gold", 0),
    }


def _character_state(character: char_engine.Character, char_id: str) -> dict[str, Any]:
    state = _serialize(character)
    state["id"] = char_id
    state.setdefault("inventory", [])
    state.setdefault("equipment", {})
    return state


@router.post("/characters/preview")
async def preview_character(data: dict[str, Any]):
    """Generate a character without saving it. Used by the creator UI for rolls and previews."""
    mode = data.get("mode", "normal")
    ancestry_name = data.get("ancestry", "human")
    class_names = data.get("classes", ["fighter"])
    name = data.get("name", "Hero")
    arrangement = data.get("arrangement")
    seed = data.get("seed")

    if seed is None:
        import random

        seed = random.randint(1, 1_000_000_000)

    try:
        char = char_engine.generate(
            seed=seed,
            mode=mode,
            ancestry_name=ancestry_name,
            class_names=class_names,
            name=name,
            arrangement=arrangement,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"character": _serialize(char)}


@router.post("/characters")
async def create_character(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    mode = data.get("mode", "normal")
    ancestry_name = data.get("ancestry", "human")
    class_names = data.get("classes", ["fighter"])
    name = data.get("name", "Hero")
    arrangement = data.get("arrangement")
    seed = data.get("seed")

    if seed is None:
        import random

        seed = random.randint(1, 1_000_000_000)

    try:
        char = char_engine.generate(
            seed=seed,
            mode=mode,
            ancestry_name=ancestry_name,
            class_names=class_names,
            name=name,
            arrangement=arrangement,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    char_id = str(uuid.uuid4())[:8]
    state = _character_state(char, char_id)
    record = CharacterRecord(
        id=char_id,
        account_id=account_id,
        name=char.name,
        ancestry=char.ancestry,
        class_=",".join(char.classes),
        level=1,
        hp=char.hit_points,
        max_hp=char.hit_points,
        ac=char.armour_class,
        abilities=json.dumps({"scores": char.scores, "modifiers": char.modifiers}),
        saves=json.dumps(char.saves),
        seed=char.seed,
        state=json.dumps(state),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    return {"character": state}


@router.get("/characters")
async def list_characters(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CharacterRecord)
        .where(CharacterRecord.account_id == account_id)
        .order_by(CharacterRecord.created_at.desc())
    )
    records = result.scalars().all()
    characters = []
    for r in records:
        try:
            state = json.loads(r.state)
        except Exception:
            state = {
                "id": r.id,
                "name": r.name,
                "ancestry": r.ancestry,
                "classes": r.class_.split(","),
                "levels": {c: 1 for c in r.class_.split(",")},
                "hit_points": r.hp,
                "max_hp": r.max_hp,
                "armour_class": r.ac,
            }
        characters.append(state)
    return {"characters": characters}


@router.get("/characters/{character_id}")
async def get_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"character": json.loads(record.state)}


@router.delete("/characters/{character_id}")
async def delete_character(
    character_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Character not found")
    await db.delete(record)
    await db.commit()
    return {"deleted": True}


@router.post("/characters/{character_id}/equip")
async def equip_item_endpoint(
    character_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
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
    char_state.setdefault("inventory", [])
    char_state.setdefault("equipment", {})
    item = items.equip_item(char_state, data.get("instance_id"))
    if not item:
        raise HTTPException(status_code=400, detail="Item not found or cannot be equipped")
    record.state = json.dumps(char_state)
    await db.commit()
    return {"character": char_state}


@router.post("/characters/{character_id}/use")
async def use_item_endpoint(
    character_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
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
    char_state.setdefault("inventory", [])
    restore = items.use_consumable(char_state, data.get("instance_id"))
    if not restore:
        raise HTTPException(status_code=400, detail="Item not found or not usable")
    max_hp = char_state.get("max_hp", char_state.get("hit_points", 1))
    char_state["hit_points"] = min(max_hp, char_state.get("hit_points", 0) + restore)
    record.state = json.dumps(char_state)
    record.hp = char_state["hit_points"]
    await db.commit()
    return {"character": char_state, "restored": restore}
