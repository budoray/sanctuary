"""Session API: start, view, act in a tactical module."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import CampaignMemberRecord, CampaignRecord, CharacterRecord, SessionRecord, get_db
import random

from backend.app.engine import character as char_engine
from backend.app.engine import items, module, session as session_engine
from backend.app.socket_manager import socket_manager

router = APIRouter(tags=["sessions"])

DEFAULT_MODULE = "sample_lair"


async def _can_access_session(
    record: SessionRecord, account_id: int, db: AsyncSession
) -> bool:
    if record.account_id == account_id:
        return True
    if not record.campaign_id:
        return False
    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == record.campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def _is_campaign_dm(
    record: SessionRecord, account_id: int, db: AsyncSession
) -> bool:
    if not record.campaign_id:
        return False
    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == record.campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if campaign and campaign.dm_account_id == account_id:
        return True
    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == record.campaign_id,
            CampaignMemberRecord.account_id == account_id,
            CampaignMemberRecord.role == "dm",
        )
    )
    return result.scalar_one_or_none() is not None


@router.post("/sessions")
async def create_session(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    character_id = data.get("character_id")
    module_id = data.get("module_id", DEFAULT_MODULE)
    campaign_id = data.get("campaign_id")
    turn_timer_seconds = int(data.get("turn_timer_seconds", 0) or 0)

    result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Character not found")

    if campaign_id:
        result = await db.execute(
            select(CampaignRecord).where(CampaignRecord.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        result = await db.execute(
            select(CampaignMemberRecord).where(
                CampaignMemberRecord.campaign_id == campaign_id,
                CampaignMemberRecord.account_id == account_id,
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this campaign")
        if module_id == DEFAULT_MODULE and campaign.module_ids:
            module_id = json.loads(campaign.module_ids)[0]

    char_state = json.loads(record.state)
    char = char_engine.Character(
        name=char_state["name"],
        ancestry=char_state["ancestry"],
        classes=tuple(char_state["classes"]),
        levels=char_state["levels"],
        scores=char_state["scores"],
        hit_points=char_state["hit_points"],
        armour_class=char_state["armour_class"],
        saves=char_state["saves"],
        modifiers=char_state["modifiers"],
        seed=char_state["seed"],
        log=tuple(),
        xp=char_state.get("xp", 0),
        level=char_state.get("level", 1),
        gold=char_state.get("gold", 0),
        inventory=tuple(char_state.get("inventory", [])),
        equipment=char_state.get("equipment", {}),
    )

    mod = module.load(module_id)
    session_id = str(uuid.uuid4())[:8]
    state = await session_engine.new_game(
        session_id, mod, char, turn_timer_seconds=turn_timer_seconds, character_id=character_id, account_id=account_id
    )
    if campaign_id:
        state["campaign_id"] = campaign_id
        state["dm_account_id"] = campaign.dm_account_id

    session_record = SessionRecord(
        id=session_id,
        account_id=account_id,
        campaign_id=campaign_id,
        module_id=module_id,
        character_id=character_id,
        name=f"{char.name} in {mod.name}",
        status=state["status"],
        state=json.dumps(state),
    )
    db.add(session_record)
    await db.commit()

    return {"session": session_engine.view(state)}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    member_of_campaign = (
        select(CampaignMemberRecord)
        .where(
            CampaignMemberRecord.campaign_id == SessionRecord.campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
        .exists()
    )
    result = await db.execute(
        select(SessionRecord)
        .where(
            or_(
                SessionRecord.account_id == account_id,
                member_of_campaign,
            )
        )
        .order_by(SessionRecord.updated_at.desc())
    )
    records = result.scalars().all()
    sessions = []
    for r in records:
        try:
            state = json.loads(r.state)
        except Exception:
            state = {"status": r.status}
        sessions.append({
            "id": r.id,
            "name": r.name,
            "module_id": r.module_id,
            "character_id": r.character_id,
            "status": r.status,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
        })
    return {"sessions": sessions}


@router.get("/sessions/active")
async def get_active_session(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord)
        .where(
            SessionRecord.account_id == account_id,
            SessionRecord.status == "active",
        )
        .order_by(SessionRecord.updated_at.desc())
        .limit(1)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="No active session")
    state = json.loads(record.state)
    return {"session": session_engine.view(state)}


@router.get("/sessions/{session_id}")
async def get_session(
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
    state = json.loads(record.state)
    return {"session": session_engine.view(state)}


@router.post("/sessions/{session_id}/act")
async def act_in_session(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")

    state = json.loads(record.state)
    mod = module.load(record.module_id)

    action = data.get("action")
    if action == "dm_turn" and record.campaign_id and not await _is_campaign_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the DM can run the DM turn")
    if action in ("move", "attack", "ranged", "end_turn", "use_potion", "stabilize", "ability"):
        if record.campaign_id:
            active_index = state.get("active_player_index", 0)
            active_players = state.get("players", [])
            active = active_players[active_index] if active_players else {}
            if active.get("account_id") != account_id:
                raise HTTPException(status_code=403, detail="Not your turn")
        elif record.account_id != account_id:
            raise HTTPException(status_code=403, detail="Only the session owner can control the hero")
    try:
        state = await session_engine.act(
            state,
            mod,
            action,
            **{k: v for k, v in data.items() if k != "action"},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    if state["status"] == "won":
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
            if player.get("alive", True):
                rng = random.Random(state.get("seed", 0) + state.get("version", 0) + sum(ord(c) for c in player.get("id", "")))
                loot = items.generate_loot(rng)
                items.add_item(char_state, loot)
                state["log"].append(f"{player['name']} finds {loot['name']}.")
            char_record.state = json.dumps(char_state)
            char_record.level = char_state["level"]
            char_record.hp = char_state["hit_points"]
            char_record.max_hp = char_state["max_hp"]
        await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_view},
            room=session_id,
        )
    except Exception:
        pass

    return {"session": session_view}


@router.post("/sessions/{session_id}/advance")
async def advance_session(
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
    if record.account_id != account_id and not await _is_campaign_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the session owner or DM can advance")
    if not record.campaign_id:
        raise HTTPException(status_code=400, detail="Only campaign sessions can be advanced")

    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == record.campaign_id)
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    module_ids = json.loads(campaign.module_ids)
    if not module_ids:
        raise HTTPException(status_code=400, detail="Campaign has no modules")

    try:
        current_index = module_ids.index(record.module_id)
    except ValueError:
        current_index = -1
    next_index = (current_index + 1) % len(module_ids)
    next_module_id = module_ids[next_index]

    state = json.loads(record.state)
    next_module = module.load(next_module_id)
    state = await session_engine.advance_module(state, next_module)

    record.module_id = next_module_id
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_view},
            room=session_id,
        )
    except Exception:
        pass

    return {"session": session_view}


@router.post("/sessions/{session_id}/rest")
async def rest_in_session(
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

    state = json.loads(record.state)
    players = state.get("players", [])
    if record.campaign_id:
        if account_id not in {p.get("account_id") for p in players if p.get("account_id")}:
            raise HTTPException(status_code=403, detail="Not a player in this session")
    elif record.account_id != account_id:
        raise HTTPException(status_code=403, detail="Only the session owner can rest")

    active_index = state.get("active_player_index", 0)
    if active_index >= len(players):
        raise HTTPException(status_code=400, detail="No active player")
    active_player = players[active_index]

    if active_player.get("gold", 0) < 10:
        raise HTTPException(status_code=400, detail="Not enough gold")

    active_player["gold"] = active_player.get("gold", 0) - 10
    active_player["hp"] = active_player.get("max_hp", active_player["hp"])
    active_player["down"] = False
    state["version"] += 1
    state["log"].append(
        f"{active_player['name']} rests at the campsite and recovers to full HP."
    )

    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_view},
            room=session_id,
        )
    except Exception:
        pass

    return {"session": session_view}


@router.post("/sessions/{session_id}/join")
async def join_session(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if not record.campaign_id:
        raise HTTPException(status_code=400, detail="Only campaign sessions can be joined")

    character_id = data.get("character_id")
    result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    char_record = result.scalar_one_or_none()
    if not char_record:
        raise HTTPException(status_code=404, detail="Character not found")

    char_state = json.loads(char_record.state)
    char = char_engine.Character(
        name=char_state["name"],
        ancestry=char_state["ancestry"],
        classes=tuple(char_state["classes"]),
        levels=char_state["levels"],
        scores=char_state["scores"],
        hit_points=char_state["hit_points"],
        armour_class=char_state["armour_class"],
        saves=char_state["saves"],
        modifiers=char_state["modifiers"],
        seed=char_state["seed"],
        log=tuple(),
        xp=char_state.get("xp", 0),
        level=char_state.get("level", 1),
        gold=char_state.get("gold", 0),
        inventory=tuple(char_state.get("inventory", [])),
        equipment=char_state.get("equipment", {}),
    )

    state = json.loads(record.state)
    mod = module.load(record.module_id)
    try:
        await session_engine.add_player(state, mod, char, character_id, account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    state["version"] += 1
    record.state = json.dumps(state)
    record.status = state["status"]
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_view},
            room=session_id,
        )
    except Exception:
        pass

    return {"session": session_view}
