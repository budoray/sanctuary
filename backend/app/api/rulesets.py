"""Ruleset API: list built-ins, fork/customize, and resolve rulesets."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.config import SETTINGS
from backend.app.db import CustomRulesetRecord, get_db
from backend.app.rulesets.loader import load_ruleset
from backend.app.rulesets.base import Ruleset

router = APIRouter(tags=["rulesets"])


BUILTIN_RULESETS = {"osric"}


def _ruleset_manifest(ruleset_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load a ruleset manifest, optionally merging overrides."""
    rs = load_ruleset(ruleset_id, overrides=overrides)
    manifest = dict(rs.manifest)
    manifest["is_builtin"] = ruleset_id in BUILTIN_RULESETS
    manifest["monster_ids"] = rs.list_monsters()
    return manifest


def _custom_response(record: CustomRulesetRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "account_id": record.account_id,
        "base_ruleset_id": record.base_ruleset_id,
        "name": record.name,
        "description": record.description or "",
        "overrides": json.loads(record.overrides_json or "{}"),
        "status": record.status or "draft",
        "visibility": record.visibility or "private",
        "rating_sum": record.rating_sum or 0,
        "rating_count": record.rating_count or 0,
        "download_count": record.download_count or 0,
        "tags": json.loads(record.tags or "[]"),
        "parent_id": record.parent_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _average_ruleset_rating(record: CustomRulesetRecord) -> float:
    if not record.rating_count:
        return 0.0
    return round((record.rating_sum or 0) / record.rating_count, 2)


@router.get("/rulesets")
async def list_rulesets(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Return built-in rulesets plus this account's custom rulesets."""
    result = await db.execute(
        select(CustomRulesetRecord)
        .where(CustomRulesetRecord.account_id == account_id)
        .order_by(CustomRulesetRecord.updated_at.desc())
    )
    customs = [_custom_response(r) for r in result.scalars().all()]

    built_ins = []
    for ruleset_id in sorted(BUILTIN_RULESETS):
        try:
            manifest = _ruleset_manifest(ruleset_id)
            built_ins.append({
                "id": ruleset_id,
                "name": manifest.get("name", ruleset_id),
                "description": manifest.get("description", ""),
                "is_builtin": True,
                "base_ruleset_id": None,
            })
        except FileNotFoundError:
            continue

    return {"rulesets": built_ins + customs}


@router.post("/rulesets")
async def create_ruleset(
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Fork a built-in ruleset into a custom ruleset."""
    base_ruleset_id = data.get("base_ruleset_id", "osric")
    if base_ruleset_id not in BUILTIN_RULESETS:
        raise HTTPException(status_code=400, detail=f"Unknown base ruleset: {base_ruleset_id}")

    try:
        load_ruleset(base_ruleset_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))

    name = data.get("name", f"Custom {base_ruleset_id}").strip()
    if not name:
        name = f"Custom {base_ruleset_id}"

    record = CustomRulesetRecord(
        account_id=account_id,
        base_ruleset_id=base_ruleset_id,
        name=name,
        description=data.get("description", ""),
        overrides_json=json.dumps(data.get("overrides", {})),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"ruleset": _custom_response(record)}


@router.get("/rulesets/{ruleset_id}")
async def get_ruleset(
    ruleset_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Resolve a ruleset: built-ins return their manifest; custom rulesets
    merge their overrides onto the base manifest."""
    if ruleset_id in BUILTIN_RULESETS:
        return {"ruleset": _ruleset_manifest(ruleset_id)}

    record = await _load_readable_ruleset(ruleset_id, account_id, db)
    overrides = json.loads(record.overrides_json or "{}")
    manifest = _ruleset_manifest(record.base_ruleset_id, overrides)
    manifest["custom_id"] = record.id
    manifest["base_ruleset_id"] = record.base_ruleset_id
    manifest["name"] = record.name
    manifest["description"] = record.description or ""
    return {"ruleset": manifest}


@router.put("/rulesets/{ruleset_id}")
async def update_ruleset(
    ruleset_id: str,
    data: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Update a custom ruleset's metadata or overrides."""
    record = await _load_owned_ruleset(ruleset_id, account_id, db)

    if "name" in data:
        record.name = data["name"].strip() or record.name
    if "description" in data:
        record.description = data.get("description", "")
    if "overrides" in data:
        record.overrides_json = json.dumps(data["overrides"] or {})
    if "tags" in data:
        tags = data["tags"]
        record.tags = json.dumps(tags if isinstance(tags, list) else [])

    await db.commit()
    await db.refresh(record)
    return {"ruleset": _custom_response(record)}


@router.delete("/rulesets/{ruleset_id}")
async def delete_ruleset(
    ruleset_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Delete a custom ruleset."""
    record = await _load_owned_ruleset(ruleset_id, account_id, db)

    await db.delete(record)
    await db.commit()
    return {"deleted": True}


async def _load_owned_ruleset(
    ruleset_id: str,
    account_id: int,
    db: AsyncSession,
) -> CustomRulesetRecord:
    result = await db.execute(
        select(CustomRulesetRecord).where(CustomRulesetRecord.id == ruleset_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    if record.account_id != account_id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this ruleset")
    return record


async def _load_readable_ruleset(
    ruleset_id: str,
    account_id: int,
    db: AsyncSession,
) -> CustomRulesetRecord:
    """Load a custom ruleset the caller may read: own, public/unlisted published."""
    result = await db.execute(
        select(CustomRulesetRecord).where(CustomRulesetRecord.id == ruleset_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    if record.account_id == account_id:
        return record
    if record.status == "published" and record.visibility in ("public", "unlisted"):
        return record
    raise HTTPException(status_code=403, detail="Not allowed to view this ruleset")


async def resolve_ruleset(ruleset_id: str, account_id: int | None = None, db: AsyncSession | None = None) -> Ruleset:
    """Load either a built-in ruleset or a custom ruleset with overrides.

    This helper is used by other backend modules that need the active ruleset
    for a dungeon/campaign/session. It does NOT perform auth; callers must
    ensure the account is allowed to use the ruleset.
    """
    if ruleset_id in BUILTIN_RULESETS or ":" not in ruleset_id:
        # Built-ins and legacy ids resolve directly.
        return load_ruleset(ruleset_id)

    if db is None or account_id is None:
        return load_ruleset("osric")

    result = await db.execute(
        select(CustomRulesetRecord).where(
            CustomRulesetRecord.id == ruleset_id,
            CustomRulesetRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        return load_ruleset("osric")

    overrides = json.loads(record.overrides_json or "{}")
    return load_ruleset(record.base_ruleset_id, overrides)


# -----------------------------------------------------------------------------
# Marketplace: publish, rate, and fork rulesets
# -----------------------------------------------------------------------------
@router.post("/rulesets/{ruleset_id}/publish")
async def publish_ruleset(
    ruleset_id: str,
    data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Publish a draft ruleset so it appears in the marketplace."""
    record = await _load_owned_ruleset(ruleset_id, account_id, db)
    if record.status not in ("draft", "archived"):
        raise HTTPException(status_code=400, detail="Ruleset cannot be published from its current state")
    record.status = "published"
    if data:
        visibility = data.get("visibility")
        if visibility in ("public", "unlisted", "private"):
            record.visibility = visibility
        tags = data.get("tags")
        if isinstance(tags, list):
            record.tags = json.dumps(tags)
    await db.commit()
    await db.refresh(record)
    return {"ruleset": _custom_response(record)}


@router.post("/rulesets/{ruleset_id}/unpublish")
async def unpublish_ruleset(
    ruleset_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Unpublish/archive a published ruleset."""
    record = await _load_owned_ruleset(ruleset_id, account_id, db)
    if record.status != "published":
        raise HTTPException(status_code=400, detail="Ruleset is not published")
    record.status = "archived"
    await db.commit()
    await db.refresh(record)
    return {"ruleset": _custom_response(record)}


@router.get("/marketplace/rulesets")
async def list_marketplace_rulesets(
    tags: str | None = Query(None, description="Comma-separated tags"),
    min_rating: float | None = Query(None, ge=0, le=5),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List published public custom rulesets with optional filters."""
    filters = [
        CustomRulesetRecord.status == "published",
        CustomRulesetRecord.visibility == "public",
    ]
    if search:
        filters.append(CustomRulesetRecord.name.ilike(f"%{search}%"))

    result = await db.execute(
        select(CustomRulesetRecord)
        .where(and_(*filters))
        .order_by(CustomRulesetRecord.updated_at.desc())
    )
    records = result.scalars().all()

    if tags:
        wanted = {t.strip().lower() for t in tags.split(",") if t.strip()}
        records = [r for r in records if wanted.intersection({t.lower() for t in json.loads(r.tags or "[]")})]

    if min_rating is not None:
        records = [r for r in records if _average_ruleset_rating(r) >= min_rating]

    return {"rulesets": [_custom_response(r) for r in records]}


@router.post("/marketplace/rulesets/{ruleset_id}/rate")
async def rate_ruleset(
    ruleset_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Rate a public published custom ruleset (1-5 stars)."""
    record = await _load_readable_ruleset(ruleset_id, account_id, db)
    if record.status != "published":
        raise HTTPException(status_code=400, detail="Ruleset is not published")
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="rating must be an integer")
    if not 1 <= rating <= 5:
        raise HTTPException(status_code=400, detail="rating must be between 1 and 5")

    record.rating_sum = (record.rating_sum or 0) + rating
    record.rating_count = (record.rating_count or 0) + 1
    await db.commit()
    await db.refresh(record)
    return {
        "ruleset": _custom_response(record),
        "average_rating": _average_ruleset_rating(record),
    }


@router.post("/marketplace/rulesets/{ruleset_id}/fork")
async def fork_ruleset(
    ruleset_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Clone a public/unlisted published custom ruleset into the caller's account."""
    result = await db.execute(select(CustomRulesetRecord).where(CustomRulesetRecord.id == ruleset_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    if source.status != "published" or source.visibility == "private":
        raise HTTPException(status_code=403, detail="Ruleset is not available to fork")

    source.download_count = (source.download_count or 0) + 1

    fork = CustomRulesetRecord(
        account_id=account_id,
        base_ruleset_id=source.base_ruleset_id,
        name=f"{source.name} (fork)",
        description=source.description,
        overrides_json=source.overrides_json,
        status="draft",
        visibility="private",
        parent_id=source.id,
    )
    db.add(fork)
    await db.commit()
    await db.refresh(fork)
    return {"ruleset": _custom_response(fork)}
