"""Session API: start, view, act in a tactical module."""
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import (
    CampaignMemberRecord,
    CampaignRecord,
    CharacterRecord,
    DungeonRecord,
    FriendRecord,
    RoomRecord,
    SessionRecord,
    _utc_now,
    get_db,
    record_event,
)
from backend.app.dependencies import limit_actions

from backend.app.engine import adventure_compiler, character as char_engine
from backend.app.engine import dungeon_compiler, items, module, session as session_engine
from backend.app.engine.dice import Dice
from backend.app.api.rulesets import resolve_ruleset
from backend.app.socket_manager import presence_tracker, socket_manager

router = APIRouter(tags=["sessions"])

DEFAULT_MODULE = "sample_lair"


def _character_from_state(char_state: dict[str, Any]) -> char_engine.Character:
    """Build a Character from persisted state, backfilling old records."""
    classes = tuple(char_state.get("classes", []))
    level = char_state.get("level", 1)
    levels = char_state.get("levels") or {c: level for c in classes}
    scores = char_state.get("scores") or {a: 10 for a in char_engine.ABILITIES}
    modifiers = char_state.get("modifiers") or char_engine.ability_modifiers(scores)
    saves = char_state.get("saves") or char_engine._multiclass_saves(classes, level)
    return char_engine.Character(
        name=char_state.get("name", "Hero"),
        ancestry=char_state.get("ancestry", "human"),
        classes=classes,
        levels=levels,
        scores=scores,
        hit_points=char_state.get("hit_points", 1),
        armour_class=char_state.get("armour_class", 10),
        saves=saves,
        modifiers=modifiers,
        seed=char_state.get("seed", 0),
        log=tuple(),
        xp=char_state.get("xp", 0),
        level=level,
        gold=char_state.get("gold", 0),
        inventory=tuple(char_state.get("inventory", [])),
        equipment=char_state.get("equipment", {}),
    )


async def _load_session_module(record: SessionRecord, db: AsyncSession) -> module.Module:
    """Load a Module for a session, handling built-in, S3 adventures, and compiled dungeons."""
    if record.module_id.startswith("dungeon:"):
        from backend.app.db import DungeonRecord, RoomRecord

        dungeon_id = record.module_id.split(":", 1)[1]
        result = await db.execute(select(DungeonRecord).where(DungeonRecord.id == dungeon_id))
        dungeon = result.scalar_one_or_none()
        if not dungeon:
            raise HTTPException(status_code=404, detail="Dungeon not found")
        order = list(dict.fromkeys(json.loads(dungeon.room_order or "[]")))
        result = await db.execute(select(RoomRecord).where(RoomRecord.id.in_(order)))
        rooms = {r.id: r for r in result.scalars().all()}
        ordered = [rooms[r_id] for r_id in order if r_id in rooms]
        if not ordered:
            raise HTTPException(status_code=400, detail="Dungeon has no rooms")
        mod, _links = dungeon_compiler.compile(dungeon, ordered)
        return mod
    loaded = module.load(record.module_id)
    if isinstance(loaded, module.Adventure):
        return adventure_compiler.compile(loaded)
    return loaded


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


async def _is_owner_or_dm(
    record: SessionRecord, account_id: int, db: AsyncSession
) -> bool:
    if record.account_id == account_id:
        return True
    return await _is_campaign_dm(record, account_id, db)


async def _can_view_session(
    record: SessionRecord, account_id: int, db: AsyncSession
) -> bool:
    if record.account_id == account_id:
        return True
    if record.campaign_id:
        result = await db.execute(
            select(CampaignMemberRecord).where(
                CampaignMemberRecord.campaign_id == record.campaign_id,
                CampaignMemberRecord.account_id == account_id,
            )
        )
        if result.scalar_one_or_none():
            return True
    if record.visibility == "public":
        return True
    if record.visibility in ("friends", "co-op"):
        friend = await db.execute(
            select(FriendRecord).where(
                or_(
                    and_(
                        FriendRecord.account_id == account_id,
                        FriendRecord.friend_account_id == record.account_id,
                        FriendRecord.status == "accepted",
                    ),
                    and_(
                        FriendRecord.account_id == record.account_id,
                        FriendRecord.friend_account_id == account_id,
                        FriendRecord.status == "accepted",
                    ),
                )
            )
        )
        return friend.scalar_one_or_none() is not None
    return False


def _persist_character_state(
    char_state: dict[str, Any], player: dict[str, Any], state: dict[str, Any] | None = None
) -> None:
    """Write a player token's persistent fields back into a CharacterRecord state dict."""
    char_state["level"] = player.get("level", char_state.get("level", 1))
    char_state["xp"] = player.get("xp", char_state.get("xp", 0))
    char_state["gold"] = player.get("gold", char_state.get("gold", 0))
    char_state["hit_points"] = player.get("hp", char_state.get("hit_points", 0))
    char_state["max_hp"] = player.get("max_hp", char_state.get("max_hp", char_state["hit_points"]))
    char_state.setdefault("inventory", [])
    char_state.setdefault("equipment", {})
    for loot in player.get("session_loot", []):
        items.add_item(char_state, loot)
        if state is not None:
            state["log"].append(f"{player['name']} stashes {loot['name']}.")
    player["session_loot"] = []


def _persist_instance_state(
    record: SessionRecord, state: dict[str, Any], *, saved: bool = False
) -> None:
    """Persist an instance state with optimistic locking and activity timestamps."""
    record.state = json.dumps(state)
    record.status = state.get("status", record.status)
    record.state_version = (record.state_version or 0) + 1
    record.last_active_at = _utc_now()
    if saved:
        record.saved_at = _utc_now()


def _emit_session_events(
    db: AsyncSession,
    prev_state: dict[str, Any],
    state: dict[str, Any],
    actor_account_id: int,
) -> None:
    """Record analytics events based on state changes after an action."""
    session_id = state.get("id")
    prev_status = prev_state.get("status")
    new_status = state.get("status")

    if prev_status == "active" and new_status == "won":
        record_event(
            db,
            "session_end_won",
            account_id=actor_account_id,
            session_id=session_id,
        )
    if prev_status == "active" and new_status == "lost":
        record_event(
            db,
            "session_end_lost",
            account_id=actor_account_id,
            session_id=session_id,
        )

    prev_players = {p["id"]: p for p in prev_state.get("players", [])}
    for player in state.get("players", []):
        prev_player = prev_players.get(player["id"])
        if prev_player is None:
            continue
        if prev_player.get("alive", True) and not player.get("alive", True):
            record_event(
                db,
                "player_death",
                account_id=player.get("account_id", actor_account_id),
                session_id=session_id,
                payload={"name": player["name"], "character_id": player.get("character_id")},
            )
        if player.get("level", 1) > prev_player.get("level", 1):
            record_event(
                db,
                "level_up",
                account_id=player.get("account_id", actor_account_id),
                session_id=session_id,
                payload={"name": player["name"], "level": player.get("level", 1)},
            )

    prev_monsters = {
        m["id"]: m
        for m in prev_state.get("monsters", [])
        if m.get("alive", True) and m.get("boss")
    }
    for monster in state.get("monsters", []):
        if monster["id"] in prev_monsters and not monster.get("alive", True):
            record_event(
                db,
                "boss_kill",
                account_id=actor_account_id,
                session_id=session_id,
                payload={"name": monster["name"]},
            )


@router.post("/sessions")
async def create_session(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    character_id = data.get("character_id")
    module_id = data.get("module_id", DEFAULT_MODULE)
    adventure_id = data.get("adventure_id") or module_id
    campaign_id = data.get("campaign_id")
    campaign = None
    turn_timer_seconds = int(data.get("turn_timer_seconds", 0) or 0)
    visibility = data.get("visibility", "solo")
    if visibility not in ("solo", "co-op", "friends", "public", "private", "invite"):
        visibility = "solo"
    name = data.get("name", "").strip()
    invite_code = None
    if visibility in ("invite", "public", "friends", "co-op", "private"):
        invite_code = str(uuid.uuid4())[:6].upper()
    ai_dm_enabled = bool(data.get("ai_dm_enabled", True))

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
            module_ids = json.loads(campaign.module_ids)
            index = campaign.current_module_index or 0
            module_id = module_ids[index % len(module_ids)]

    char_state = json.loads(record.state)
    char = _character_from_state(char_state)

    if module_id.startswith("dungeon:"):
        dungeon_id = module_id.split(":", 1)[1]
        result = await db.execute(select(DungeonRecord).where(DungeonRecord.id == dungeon_id))
        dungeon = result.scalar_one_or_none()
        if not dungeon:
            raise HTTPException(status_code=404, detail="Dungeon not found")
        order = list(dict.fromkeys(json.loads(dungeon.room_order or "[]")))
        result = await db.execute(select(RoomRecord).where(RoomRecord.id.in_(order)))
        rooms = {r.id: r for r in result.scalars().all()}
        ordered = [rooms[r_id] for r_id in order if r_id in rooms]
        if not ordered:
            raise HTTPException(status_code=400, detail="Dungeon has no rooms")
        mod, dungeon_links = dungeon_compiler.compile(dungeon, ordered)
        ruleset_id = dungeon.ruleset_id or "osric"
    else:
        loaded = module.load(module_id)
        if isinstance(loaded, module.Adventure):
            mod = adventure_compiler.compile(loaded)
        else:
            mod = loaded
        dungeon_links = mod.dungeon_links
        ruleset_id = mod.ruleset

    if campaign_id:
        ruleset_id = campaign.ruleset_id or ruleset_id

    ruleset = await resolve_ruleset(ruleset_id, account_id=account_id, db=db)
    monsters_dir = ruleset.content_path("monsters")

    session_id = str(uuid.uuid4())[:8]
    state = await session_engine.new_game(
        session_id,
        mod,
        char,
        turn_timer_seconds=turn_timer_seconds,
        character_id=character_id,
        account_id=account_id,
        dungeon_links=dungeon_links,
        monsters_dir=monsters_dir,
    )
    if campaign_id:
        state["campaign_id"] = campaign_id
        state["dm_account_id"] = campaign.dm_account_id

    session_record = SessionRecord(
        id=session_id,
        account_id=account_id,
        campaign_id=campaign_id,
        module_id=module_id,
        adventure_id=adventure_id,
        character_id=character_id,
        name=name or f"{char.name} in {mod.name}",
        status=state["status"],
        visibility=visibility,
        invite_code=invite_code,
        ruleset_id=ruleset_id,
        dm_account_id=campaign.dm_account_id if campaign else data.get("dm_account_id"),
        ai_dm_enabled=ai_dm_enabled,
        state=json.dumps(state),
        state_version=0,
        last_active_at=_utc_now(),
    )
    db.add(session_record)
    record_event(
        db,
        "session_start",
        account_id=account_id,
        session_id=session_id,
        payload={"module_id": module_id, "campaign_id": campaign_id},
    )
    await db.commit()

    return {"session": session_engine.view(state)}


@router.delete("/sessions")
async def delete_all_sessions(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord)
        .where(
            or_(
                SessionRecord.account_id == account_id,
                SessionRecord.campaign_id.in_(
                    select(CampaignRecord.id).where(CampaignRecord.dm_account_id == account_id)
                ),
            )
        )
    )
    records = result.scalars().all()
    for record in records:
        if record.account_id == account_id or await _is_campaign_dm(record, account_id, db):
            await db.delete(record)
    await db.commit()
    return {"deleted": len(records)}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """List instances the account can see: own, campaign, public, and friend sessions."""
    member_of_campaign = (
        select(CampaignMemberRecord)
        .where(
            CampaignMemberRecord.campaign_id == SessionRecord.campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
        .exists()
    )
    accepted_friend_ids = (
        select(FriendRecord.friend_account_id.label("fid"))
        .where(
            FriendRecord.account_id == account_id,
            FriendRecord.status == "accepted",
        )
        .union(
            select(FriendRecord.account_id.label("fid")).where(
                FriendRecord.friend_account_id == account_id,
                FriendRecord.status == "accepted",
            )
        )
        .scalar_subquery()
    )
    result = await db.execute(
        select(SessionRecord)
        .where(
            or_(
                SessionRecord.account_id == account_id,
                member_of_campaign,
                SessionRecord.visibility == "public",
                and_(
                    SessionRecord.visibility.in_(["friends", "co-op"]),
                    SessionRecord.account_id.in_(accepted_friend_ids),
                ),
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
            "adventure_id": r.adventure_id,
            "character_id": r.character_id,
            "account_id": r.account_id,
            "status": r.status,
            "visibility": r.visibility,
            "invite_code": r.invite_code,
            "ai_dm_enabled": r.ai_dm_enabled,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
        })
    return {"sessions": sessions}


@router.get("/sessions/joinable")
async def list_joinable_sessions(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Return public sessions and friend-only sessions owned by accepted friends."""
    friend_ids = (
        select(
            FriendRecord.friend_account_id.label("fid")
        )
        .where(
            FriendRecord.account_id == account_id,
            FriendRecord.status == "accepted",
        )
        .union(
            select(FriendRecord.account_id.label("fid")).where(
                FriendRecord.friend_account_id == account_id,
                FriendRecord.status == "accepted",
            )
        )
        .scalar_subquery()
    )
    result = await db.execute(
        select(SessionRecord)
        .where(
            SessionRecord.status == "active",
            SessionRecord.account_id != account_id,
            or_(
                SessionRecord.visibility == "public",
                and_(
                    SessionRecord.visibility == "friends",
                    SessionRecord.account_id.in_(friend_ids),
                ),
            ),
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
            "account_id": r.account_id,
            "status": r.status,
            "visibility": r.visibility,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
        })
    return {"sessions": sessions}


@router.post("/sessions/join-by-code")
async def join_session_by_code(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    code = (data.get("code") or "").upper().strip()
    character_id = data.get("character_id")
    if not code:
        raise HTTPException(status_code=400, detail="Invite code required")
    result = await db.execute(
        select(SessionRecord).where(
            SessionRecord.invite_code == code,
            SessionRecord.status == "active",
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Adventure not found")
    if record.visibility == "friends":
        friend = await db.execute(
            select(FriendRecord).where(
                or_(
                    and_(
                        FriendRecord.account_id == account_id,
                        FriendRecord.friend_account_id == record.account_id,
                        FriendRecord.status == "accepted",
                    ),
                    and_(
                        FriendRecord.account_id == record.account_id,
                        FriendRecord.friend_account_id == account_id,
                        FriendRecord.status == "accepted",
                    ),
                )
            )
        )
        if not friend.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Adventure is friends-only")
    return await _join_existing_session(record, character_id, account_id, db)


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
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    state = json.loads(record.state)
    return {"session": session_engine.view(state)}


@router.get("/sessions/{session_id}/presence")
async def get_session_presence(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "present": presence_tracker.get(session_id)}


@router.post("/sessions/{session_id}/act")
async def act_in_session(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
    _rate_limited: None = Depends(limit_actions),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if record.status not in ("active",):
        raise HTTPException(status_code=400, detail="Instance is not active")

    state = json.loads(record.state)
    prev_state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    action = data.get("action")
    if action == "dm_turn" and record.campaign_id and not await _is_campaign_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the DM can run the DM turn")
    if action in ("move", "attack", "ranged", "end_turn", "use_potion", "stabilize", "ability", "interact_prop"):
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

    _emit_session_events(db, prev_state, state, account_id)

    _persist_instance_state(record, state)
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
            _persist_character_state(char_state, player, state)
            if player.get("alive", True):
                d = Dice(seed=state.get("seed", 0) + state.get("version", 0) + sum(ord(c) for c in player.get("id", "")))
                loot = items.generate_loot(level=player.get("level", 1), d=d)
                items.add_item(char_state, loot)
                state["log"].append(f"{player['name']} finds {loot['name']}.")
                state["rolls"].extend(session_engine._roll_to_dict(r) for r in d.log)
            char_record.state = json.dumps(char_state)
            char_record.level = char_state["level"]
            char_record.hp = char_state["hit_points"]
            char_record.max_hp = char_state["max_hp"]
        _persist_instance_state(record, state, saved=True)
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
    current_module_id = module_ids[current_index]
    next_index = (current_index + 1) % len(module_ids)
    next_module_id = module_ids[next_index]

    state = json.loads(record.state)
    next_module = module.load(next_module_id)
    ruleset_id = campaign.ruleset_id or next_module.ruleset or "osric"
    ruleset = await resolve_ruleset(ruleset_id, account_id=account_id, db=db)
    monsters_dir = ruleset.content_path("monsters")
    state = await session_engine.advance_module(state, next_module, monsters_dir=monsters_dir)

    # Update campaign progress: mark current module cleared and move index forward.
    cleared = json.loads(campaign.cleared_module_ids or "[]")
    if current_module_id not in cleared:
        cleared.append(current_module_id)
    campaign.cleared_module_ids = json.dumps(cleared)
    campaign.current_module_index = next_index

    record.module_id = next_module_id
    _persist_instance_state(record, state)
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

    _persist_instance_state(record, state)
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


async def _join_existing_session(
    record: SessionRecord,
    character_id: Any,
    account_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Add a player's character to an existing session."""
    char_result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    char_record = char_result.scalar_one_or_none()
    if not char_record:
        raise HTTPException(status_code=404, detail="Character not found")

    char_state = json.loads(char_record.state)
    char = _character_from_state(char_state)

    state = json.loads(record.state)
    mod = await _load_session_module(record, db)

    # If this account already has a player token in the instance (e.g. they
    # disconnected and became AI-controlled), resume human control instead of
    # adding a duplicate character.
    existing = next(
        (p for p in state.get("players", []) if p.get("account_id") == account_id),
        None,
    )
    if existing is not None:
        existing["ai_controlled"] = False
        state["version"] += 1
        _persist_instance_state(record, state)
        await db.commit()
        session_view = session_engine.view(state)
        try:
            await socket_manager.emit(
                "session_update",
                {"session": session_view},
                room=record.id,
            )
        except Exception:
            pass
        return {"session": session_view}

    try:
        await session_engine.add_player(state, mod, char, character_id, account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Snapshot the character's persistent state on entry so leave/end can diff or revert.
    player = state["players"][-1]
    player["_entry_snapshot"] = {
        "hp": char.hit_points,
        "max_hp": char.hit_points,
        "xp": getattr(char, "xp", 0),
        "level": getattr(char, "level", 1),
        "gold": getattr(char, "gold", 0),
        "inventory": list(getattr(char, "inventory", ())),
    }

    state["version"] += 1
    _persist_instance_state(record, state)
    await db.commit()

    session_view = session_engine.view(state)
    try:
        await socket_manager.emit(
            "session_update",
            {"session": session_view},
            room=record.id,
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
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    if record.status != "active":
        raise HTTPException(status_code=400, detail="Session is not active")
    if record.account_id == account_id:
        raise HTTPException(status_code=400, detail="You own this session")
    if record.campaign_id and not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if not record.campaign_id and record.visibility not in ("public", "friends", "co-op", "private", "invite"):
        raise HTTPException(status_code=400, detail="Session is not joinable")
    return await _join_existing_session(record, data.get("character_id"), account_id, db)


@router.post("/sessions/{session_id}/leave")
async def leave_session(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Mark a player's character as AI-controlled and persist their state."""
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if record.status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Instance is already finished")

    state = json.loads(record.state)
    character_id = data.get("character_id")
    player_index = next(
        (
            i
            for i, p in enumerate(state.get("players", []))
            if p.get("character_id") == character_id and p.get("account_id") == account_id
        ),
        None,
    )
    if player_index is None:
        raise HTTPException(status_code=404, detail="Character not in this instance")

    player = state["players"][player_index]
    player["ai_controlled"] = True

    char_result = await db.execute(
        select(CharacterRecord).where(
            CharacterRecord.id == character_id,
            CharacterRecord.account_id == account_id,
        )
    )
    char_record = char_result.scalar_one_or_none()
    if char_record:
        char_state = json.loads(char_record.state)
        _persist_character_state(char_state, player, state)
        char_record.state = json.dumps(char_state)
        char_record.level = char_state["level"]
        char_record.hp = char_state["hit_points"]
        char_record.max_hp = char_state["max_hp"]

    state["version"] += 1

    # If it is this player's turn, let the AI take over immediately so the
    # party is not stalled waiting for a disconnected player.
    active_index = state.get("active_player_index", 0)
    if active_index == player_index and state.get("phase") == "player":
        mod = await _load_session_module(record, db)
        state = await session_engine.run_ai_players(state, mod)

    _persist_instance_state(record, state, saved=True)
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

    return {"left": True, "session": session_view}


@router.post("/sessions/{session_id}/take-control")
async def take_control(
    session_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Resume human control of a player token that was AI-controlled."""
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if record.status not in ("active", "paused"):
        raise HTTPException(status_code=400, detail="Instance is already finished")

    state = json.loads(record.state)
    character_id = data.get("character_id")
    player = next(
        (
            p
            for p in state.get("players", [])
            if p.get("character_id") == character_id
            and p.get("account_id") == account_id
        ),
        None,
    )
    if player is None:
        raise HTTPException(status_code=404, detail="Character not in this instance")

    player["ai_controlled"] = False
    state["version"] += 1
    _persist_instance_state(record, state)
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

    return {"control": True, "session": session_view}


@router.post("/sessions/{session_id}/pause")
async def pause_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if not await _is_owner_or_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the owner or DM can pause")
    if record.status != "active":
        raise HTTPException(status_code=400, detail="Instance is not active")

    state = json.loads(record.state)
    state["status"] = "paused"
    record.ai_dm_enabled = False
    _persist_instance_state(record, state)
    await db.commit()
    return {"paused": True, "session": session_engine.view(state)}


@router.post("/sessions/{session_id}/resume")
async def resume_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(SessionRecord).where(SessionRecord.id == session_id)
    )
    record = result.scalar_one_or_none()
    if not record or not await _can_view_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if not await _is_owner_or_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the owner or DM can resume")
    if record.status != "paused":
        raise HTTPException(status_code=400, detail="Instance is not paused")

    state = json.loads(record.state)
    state["status"] = "active"
    record.ai_dm_enabled = True
    _persist_instance_state(record, state)
    await db.commit()
    return {"resumed": True, "session": session_engine.view(state)}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(select(SessionRecord).where(SessionRecord.id == session_id))
    record = result.scalar_one_or_none()
    if not record or not await _can_access_session(record, account_id, db):
        raise HTTPException(status_code=404, detail="Session not found")
    if record.account_id != account_id and not await _is_campaign_dm(record, account_id, db):
        raise HTTPException(status_code=403, detail="Only the session owner or DM can delete")
    await db.delete(record)
    await db.commit()
    return {"deleted": True}


@router.get("/account/progress")
async def account_progress(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Aggregate account-wide progression stats from analytics events."""
    from sqlalchemy import func
    from backend.app.db import EventRecord

    result = await db.execute(
        select(EventRecord.event_type, func.count())
        .where(EventRecord.account_id == account_id)
        .group_by(EventRecord.event_type)
    )
    counts = {event_type: count for event_type, count in result.all()}

    # Modules cleared across all campaigns the account owns or belongs to.
    member_campaign_ids = (
        select(CampaignMemberRecord.campaign_id)
        .where(CampaignMemberRecord.account_id == account_id)
        .scalar_subquery()
    )
    cleared_result = await db.execute(
        select(CampaignRecord.cleared_module_ids)
        .where(
            or_(
                CampaignRecord.account_id == account_id,
                CampaignRecord.id.in_(member_campaign_ids),
            )
        )
    )
    modules_cleared = set()
    for (cleared_json,) in cleared_result.all():
        try:
            modules_cleared.update(json.loads(cleared_json or "[]"))
        except Exception:
            pass

    return {
        "wins": counts.get("session_end_won", 0),
        "losses": counts.get("session_end_lost", 0),
        "deaths": counts.get("player_death", 0),
        "level_ups": counts.get("level_up", 0),
        "boss_kills": counts.get("boss_kill", 0),
        "sessions": counts.get("session_start", 0),
        "modules_cleared": len(modules_cleared),
    }
