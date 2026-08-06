"""Social features: lightweight friend list and invites."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.db import FriendRecord, get_db
from backend.app.socket_manager import online_accounts

router = APIRouter(tags=["social"])


def _friend_payload(record: FriendRecord, is_online: bool = False) -> dict[str, Any]:
    return {
        "account_id": record.friend_account_id,
        "status": record.status,
        "online": is_online,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


@router.get("/friends")
async def list_friends(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Return accepted friends and incoming friend requests."""
    result = await db.execute(
        select(FriendRecord).where(
            or_(
                FriendRecord.account_id == account_id,
                FriendRecord.friend_account_id == account_id,
            ),
            FriendRecord.status == "accepted",
        )
    )
    accepted = result.scalars().all()

    result = await db.execute(
        select(FriendRecord).where(
            FriendRecord.friend_account_id == account_id,
            FriendRecord.status == "pending",
        )
    )
    pending = result.scalars().all()

    friend_ids = set()
    for r in accepted:
        friend_ids.add(
            r.friend_account_id if r.account_id == account_id else r.account_id
        )

    friends = []
    seen = set()
    for r in accepted:
        fid = r.friend_account_id if r.account_id == account_id else r.account_id
        if fid in seen:
            continue
        seen.add(fid)
        friends.append(
            {
                "account_id": fid,
                "status": "accepted",
                "online": online_accounts.is_online(fid),
            }
        )

    return {
        "friends": friends,
        "pending": [
            {
                "account_id": r.account_id,
                "status": r.status,
                "online": online_accounts.is_online(r.account_id),
            }
            for r in pending
        ],
    }


@router.post("/friends")
async def add_friend(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Send a friend request to another account."""
    try:
        target_id = int(data["account_id"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="account_id is required")

    if target_id == account_id:
        raise HTTPException(status_code=400, detail="cannot friend yourself")

    # If the other person already requested us, accept both directions.
    result = await db.execute(
        select(FriendRecord).where(
            FriendRecord.account_id == target_id,
            FriendRecord.friend_account_id == account_id,
        )
    )
    reverse = result.scalar_one_or_none()
    if reverse is not None:
        reverse.status = "accepted"
        result = await db.execute(
            select(FriendRecord).where(
                FriendRecord.account_id == account_id,
                FriendRecord.friend_account_id == target_id,
            )
        )
        forward = result.scalar_one_or_none()
        if forward is None:
            db.add(
                FriendRecord(
                    account_id=account_id,
                    friend_account_id=target_id,
                    status="accepted",
                )
            )
        else:
            forward.status = "accepted"
        await db.commit()
        return {"status": "accepted"}

    result = await db.execute(
        select(FriendRecord).where(
            FriendRecord.account_id == account_id,
            FriendRecord.friend_account_id == target_id,
        )
    )
    if result.scalar_one_or_none() is not None:
        return {"status": "pending"}

    db.add(
        FriendRecord(
            account_id=account_id,
            friend_account_id=target_id,
            status="pending",
        )
    )
    await db.commit()
    return {"status": "pending"}


@router.post("/friends/{friend_account_id}/accept")
async def accept_friend(
    friend_account_id: int,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Accept an incoming friend request."""
    result = await db.execute(
        select(FriendRecord).where(
            FriendRecord.account_id == friend_account_id,
            FriendRecord.friend_account_id == account_id,
            FriendRecord.status == "pending",
        )
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Friend request not found")

    request.status = "accepted"
    result = await db.execute(
        select(FriendRecord).where(
            FriendRecord.account_id == account_id,
            FriendRecord.friend_account_id == friend_account_id,
        )
    )
    reverse = result.scalar_one_or_none()
    if reverse is None:
        db.add(
            FriendRecord(
                account_id=account_id,
                friend_account_id=friend_account_id,
                status="accepted",
            )
        )
    else:
        reverse.status = "accepted"
    await db.commit()
    return {"status": "accepted"}


@router.post("/friends/{friend_account_id}/decline")
async def decline_friend(
    friend_account_id: int,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Decline an incoming friend request."""
    result = await db.execute(
        delete(FriendRecord).where(
            FriendRecord.account_id == friend_account_id,
            FriendRecord.friend_account_id == account_id,
            FriendRecord.status == "pending",
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Friend request not found")
    await db.commit()
    return {"declined": True}


@router.delete("/friends/{friend_account_id}")
async def remove_friend(
    friend_account_id: int,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Remove a friend (both directions)."""
    await db.execute(
        delete(FriendRecord).where(
            or_(
                (
                    (FriendRecord.account_id == account_id)
                    & (FriendRecord.friend_account_id == friend_account_id)
                ),
                (
                    (FriendRecord.account_id == friend_account_id)
                    & (FriendRecord.friend_account_id == account_id)
                ),
            )
        )
    )
    await db.commit()
    return {"removed": True}
