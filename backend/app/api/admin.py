"""Admin-only API for managing campaigns and sessions."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_admin
from backend.app.db import CampaignMemberRecord, CampaignRecord, EventRecord, SessionRecord, get_db
from backend.app.api.campaigns import create_campaign as create_campaign_logic

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/campaigns")
async def admin_list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CampaignRecord).order_by(CampaignRecord.created_at.desc()))
    campaigns = result.scalars().all()

    out = []
    for c in campaigns:
        member_result = await db.execute(
            select(CampaignMemberRecord).where(CampaignMemberRecord.campaign_id == c.id)
        )
        member_count = len(member_result.scalars().all())
        out.append({
            "id": c.id,
            "name": c.name,
            "ruleset_id": c.ruleset_id,
            "module_ids": json.loads(c.module_ids),
            "dm_account_id": c.dm_account_id,
            "member_count": member_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"campaigns": out}


@router.delete("/campaigns/{campaign_id}")
async def admin_delete_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CampaignRecord).where(CampaignRecord.id == campaign_id))
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    await db.execute(
        delete(CampaignMemberRecord).where(CampaignMemberRecord.campaign_id == campaign_id)
    )
    await db.execute(
        delete(SessionRecord).where(SessionRecord.campaign_id == campaign_id)
    )
    await db.delete(campaign)
    await db.commit()
    return {"deleted": True}


@router.get("/sessions")
async def admin_list_active_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SessionRecord)
        .where(SessionRecord.status == "active")
        .order_by(SessionRecord.updated_at.desc())
    )
    sessions = []
    for r in result.scalars().all():
        try:
            state = json.loads(r.state)
        except Exception:
            state = {}
        sessions.append({
            "id": r.id,
            "name": r.name,
            "module_id": r.module_id,
            "campaign_id": r.campaign_id,
            "status": r.status,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
            "player_count": len(state.get("players", [])),
        })
    return {"sessions": sessions}


@router.delete("/sessions/{session_id}")
async def admin_delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SessionRecord).where(SessionRecord.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
    return {"deleted": True}


@router.post("/campaigns")
async def admin_create_campaign(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_admin),
):
    """Create a campaign on behalf of the admin, reusing the standard creation logic."""
    return await create_campaign_logic(data=data, db=db, account_id=account_id)


@router.get("/analytics")
async def analytics_summary(db: AsyncSession = Depends(get_db)):
    """Return aggregated counts for key event types."""
    event_types = [
        "session_start",
        "session_end_won",
        "session_end_lost",
        "level_up",
        "player_death",
        "boss_kill",
    ]
    counts: dict[str, int] = {}
    for event_type in event_types:
        result = await db.execute(
            select(func.count(EventRecord.id)).where(EventRecord.event_type == event_type)
        )
        counts[event_type] = result.scalar() or 0

    return {
        "sessions": counts["session_start"],
        "wins": counts["session_end_won"],
        "losses": counts["session_end_lost"],
        "level_ups": counts["level_up"],
        "deaths": counts["player_death"],
        "boss_kills": counts["boss_kill"],
    }


@router.get("/analytics/events")
async def analytics_events(
    type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return raw analytics events, optionally filtered by type."""
    query = select(EventRecord).order_by(EventRecord.created_at.desc()).limit(500)
    if type:
        query = query.where(EventRecord.event_type == type)
    result = await db.execute(query)
    events = []
    for r in result.scalars().all():
        try:
            payload = json.loads(r.payload_json)
        except Exception:
            payload = {}
        events.append({
            "id": r.id,
            "account_id": r.account_id,
            "session_id": r.session_id,
            "event_type": r.event_type,
            "payload": payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"events": events}
