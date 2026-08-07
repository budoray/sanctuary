"""Ruleset API: list built-ins, fork/customize, and resolve rulesets."""
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


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

    result = await db.execute(
        select(CustomRulesetRecord).where(
            CustomRulesetRecord.id == ruleset_id,
            CustomRulesetRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Ruleset not found")

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
    result = await db.execute(
        select(CustomRulesetRecord).where(
            CustomRulesetRecord.id == ruleset_id,
            CustomRulesetRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    if "name" in data:
        record.name = data["name"].strip() or record.name
    if "description" in data:
        record.description = data.get("description", "")
    if "overrides" in data:
        record.overrides_json = json.dumps(data["overrides"] or {})

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
    result = await db.execute(
        select(CustomRulesetRecord).where(
            CustomRulesetRecord.id == ruleset_id,
            CustomRulesetRecord.account_id == account_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Ruleset not found")

    await db.delete(record)
    await db.commit()
    return {"deleted": True}


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
