"""Character progression persistence API.

Allows players to save the current session state back to their character record
mid-session or after a loss, preserving XP, gold, HP, max HP, level, and loot.
"""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CharacterRecord, SessionRecord, get_db
from backend.app.engine import items
from backend.app.api.sessions import _can_access_session

router = APIRouter(tags=["progression"])


@router.post("/sessions/{session_id}/save")
async def save_progression(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")

    if record.status not in ("active", "lost"):
        raise HTTPException(
            status_code=400,
            detail="Progress can only be saved from an active or lost session",
        )

    state = json.loads(record.state)
    updated_character_ids: list[str] = []

    for player in state.get("players", []):
        char_id = player.get("character_id")
        if not char_id:
            continue

        char_result = await db.execute(
            select(CharacterRecord).where(CharacterRecord.id == char_id)
        )
        char_record = char_result.scalar_one_or_none()
        if not char_record:
            continue

        char_state = json.loads(char_record.state)
        char_state["level"] = player.get("level", char_state.get("level", 1))
        char_state["xp"] = player.get("xp", char_state.get("xp", 0))
        char_state["gold"] = player.get("gold", char_state.get("gold", 0))
        char_state["hit_points"] = player.get("hp", char_state.get("hit_points", 0))
        char_state["max_hp"] = player.get("max_hp", char_state.get("max_hp", char_state["hit_points"]))
        char_state.setdefault("inventory", [])
        char_state.setdefault("equipment", {})

        for loot in player.get("session_loot", []):
            items.add_item(char_state, loot)
            state["log"].append(f"{player['name']} stashes {loot['name']}.")
        player["session_loot"] = []

        char_record.state = json.dumps(char_state)
        char_record.level = char_state["level"]
        char_record.hp = char_state["hit_points"]
        char_record.max_hp = char_state["max_hp"]
        updated_character_ids.append(char_id)

    record.state = json.dumps(state)
    await db.commit()

    return {"saved": True, "character_ids": updated_character_ids}
