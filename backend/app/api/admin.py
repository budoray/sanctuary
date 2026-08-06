"""Admin-only API for managing campaigns and sessions."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_admin
from backend.app.db import CampaignMemberRecord, CampaignRecord, SessionRecord, get_db

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
