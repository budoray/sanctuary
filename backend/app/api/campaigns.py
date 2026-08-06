"""Campaign API: create, share, and join campaigns."""
import hashlib
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import is_admin, require_account
from backend.app.db import CampaignMemberRecord, CampaignRecord, SessionRecord, get_db

router = APIRouter(tags=["campaigns"])


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _check_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed


async def _require_campaign_manager(
    campaign_id: str,
    request: Request,
    account_id: int = Depends(require_account),
    db: AsyncSession = Depends(get_db),
) -> CampaignRecord:
    """Return the campaign if the caller is the DM or an admin, else 403."""
    result = await db.execute(select(CampaignRecord).where(CampaignRecord.id == campaign_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if record.dm_account_id == account_id:
        return record
    if is_admin(account_id, request.headers.get("cookie", "")):
        return record
    raise HTTPException(status_code=403, detail="Only the DM or an admin can manage this campaign")


async def _require_campaign_member(
    campaign_id: str,
    request: Request,
    account_id: int = Depends(require_account),
    db: AsyncSession = Depends(get_db),
) -> CampaignRecord:
    """Return the campaign if the caller is a member or an admin, else 403."""
    result = await db.execute(select(CampaignRecord).where(CampaignRecord.id == campaign_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if record.dm_account_id == account_id or record.account_id == account_id:
        return record
    if is_admin(account_id, request.headers.get("cookie", "")):
        return record
    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
    )
    if result.scalar_one_or_none():
        return record
    raise HTTPException(status_code=403, detail="Not a member of this campaign")


def _campaign_response(record: CampaignRecord, is_member: bool = False, is_dm: bool = False) -> dict[str, Any]:
    out = {
        "id": record.id,
        "name": record.name,
        "ruleset_id": record.ruleset_id,
        "module_ids": json.loads(record.module_ids),
        "dm_account_id": record.dm_account_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }
    if is_member:
        out["is_member"] = True
    if is_dm:
        out["is_dm"] = True
    return out


@router.post("/campaigns")
async def create_campaign(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    name = data.get("name", "New Campaign")
    ruleset_id = data.get("ruleset_id", "osric")
    module_ids = data.get("module_ids", ["sample_lair"])
    password = data.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="Campaign password is required")

    campaign_id = str(uuid.uuid4())[:8]
    record = CampaignRecord(
        id=campaign_id,
        account_id=account_id,
        name=name,
        ruleset_id=ruleset_id,
        module_ids=json.dumps(module_ids),
        password_hash=_hash_password(password),
        dm_account_id=account_id,
    )
    db.add(record)
    db.add(CampaignMemberRecord(campaign_id=campaign_id, account_id=account_id, role="dm"))
    await db.commit()
    await db.refresh(record)

    return {"campaign": _campaign_response(record, is_member=True, is_dm=True)}


@router.get("/campaigns")
async def list_campaigns(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CampaignRecord)
        .where(CampaignRecord.account_id == account_id)
        .order_by(CampaignRecord.created_at.desc())
    )
    own = result.scalars().all()

    result = await db.execute(
        select(CampaignMemberRecord).where(CampaignMemberRecord.account_id == account_id)
    )
    joined_ids = [m.campaign_id for m in result.scalars().all()]

    joined: list[CampaignRecord] = []
    if joined_ids:
        result = await db.execute(
            select(CampaignRecord).where(CampaignRecord.id.in_(joined_ids))
        )
        joined = result.scalars().all()

    campaigns = []
    seen = set()
    for record in list(own) + list(joined):
        if record.id in seen:
            continue
        seen.add(record.id)
        is_dm = record.dm_account_id == account_id
        campaigns.append(_campaign_response(record, is_member=True, is_dm=is_dm))
    return {"campaigns": campaigns}


@router.get("/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == campaign_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None and record.account_id != account_id:
        # Public metadata only for non-members.
        return {"campaign": _campaign_response(record)}

    is_dm = record.dm_account_id == account_id or (membership is not None and membership.role == "dm")
    return {"campaign": _campaign_response(record, is_member=True, is_dm=is_dm)}


@router.post("/campaigns/{campaign_id}/join")
async def join_campaign(
    campaign_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == campaign_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
    )
    if result.scalar_one_or_none():
        return {"campaign": _campaign_response(record, is_member=True)}

    password = data.get("password", "")
    if not _check_password(password, record.password_hash):
        raise HTTPException(status_code=403, detail="Incorrect password")

    db.add(CampaignMemberRecord(campaign_id=campaign_id, account_id=account_id, role="player"))
    await db.commit()
    await db.refresh(record)
    return {"campaign": _campaign_response(record, is_member=True)}


@router.post("/campaigns/{campaign_id}/members")
async def add_campaign_member(
    campaign_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == campaign_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if record.dm_account_id != account_id:
        raise HTTPException(status_code=403, detail="Only the DM can manage members")

    target_account_id = data.get("account_id")
    role = data.get("role", "player")
    if role not in ("dm", "player"):
        raise HTTPException(status_code=400, detail="role must be dm or player")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == target_account_id,
        )
    )
    if not result.scalar_one_or_none():
        db.add(CampaignMemberRecord(campaign_id=campaign_id, account_id=target_account_id, role=role))
        await db.commit()
    return {"joined": True}


@router.get("/campaigns/{campaign_id}/sessions")
async def list_campaign_sessions(
    campaign_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    result = await db.execute(
        select(CampaignRecord).where(CampaignRecord.id == campaign_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == account_id,
        )
    )
    is_member = result.scalar_one_or_none() is not None
    if not is_member and record.account_id != account_id:
        raise HTTPException(status_code=403, detail="Not a member of this campaign")

    result = await db.execute(
        select(SessionRecord)
        .where(
            SessionRecord.campaign_id == campaign_id,
            SessionRecord.status == "active",
        )
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
            "status": r.status,
            "turn": state.get("turn", 1),
            "phase": state.get("phase", "player"),
            "player_count": len(state.get("players", [])),
        })
    return {"sessions": sessions}


@router.get("/campaigns/{campaign_id}/members")
async def list_campaign_members(
    campaign_id: str,
    request: Request,
    account_id: int = Depends(require_account),
    db: AsyncSession = Depends(get_db),
):
    record = await _require_campaign_member(campaign_id, request, account_id, db)
    result = await db.execute(
        select(CampaignMemberRecord).where(CampaignMemberRecord.campaign_id == campaign_id)
    )
    members = [
        {"account_id": m.account_id, "role": m.role, "joined_at": m.joined_at.isoformat() if m.joined_at else None}
        for m in result.scalars().all()
    ]
    return {"campaign_id": record.id, "members": members}


@router.post("/campaigns/{campaign_id}/transfer_dm")
async def transfer_dm(
    campaign_id: str,
    data: dict[str, Any],
    request: Request,
    record: CampaignRecord = Depends(_require_campaign_manager),
    account_id: int = Depends(require_account),
    db: AsyncSession = Depends(get_db),
):
    target_account_id = data.get("account_id")
    if target_account_id is None:
        raise HTTPException(status_code=400, detail="account_id is required")
    try:
        target_account_id = int(target_account_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="account_id must be an integer")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == target_account_id,
        )
    )
    target_member = result.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=400, detail="Target is not a campaign member")

    # Update the campaign DM and member roles.
    record.dm_account_id = target_account_id
    target_member.role = "dm"

    if target_account_id != account_id:
        result = await db.execute(
            select(CampaignMemberRecord).where(
                CampaignMemberRecord.campaign_id == campaign_id,
                CampaignMemberRecord.account_id == account_id,
            )
        )
        caller_member = result.scalar_one_or_none()
        if caller_member and caller_member.role == "dm":
            caller_member.role = "player"

    await db.commit()
    await db.refresh(record)
    return {"campaign": _campaign_response(record, is_member=True, is_dm=record.dm_account_id == account_id)}


@router.post("/campaigns/{campaign_id}/members/{member_account_id}/role")
async def set_member_role(
    campaign_id: str,
    member_account_id: int,
    data: dict[str, Any],
    request: Request,
    record: CampaignRecord = Depends(_require_campaign_manager),
    db: AsyncSession = Depends(get_db),
):
    role = data.get("role")
    if role not in ("dm", "player", "none"):
        raise HTTPException(status_code=400, detail="role must be dm, player, or none")

    result = await db.execute(
        select(CampaignMemberRecord).where(
            CampaignMemberRecord.campaign_id == campaign_id,
            CampaignMemberRecord.account_id == member_account_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if role == "none":
        await db.execute(
            delete(CampaignMemberRecord).where(
                CampaignMemberRecord.campaign_id == campaign_id,
                CampaignMemberRecord.account_id == member_account_id,
            )
        )
    else:
        member.role = role

    await db.commit()
    return {"account_id": member_account_id, "role": role}
