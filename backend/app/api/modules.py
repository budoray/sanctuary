"""Module API: load module metadata, import/export S3 adventures, and compiled dungeons."""
import json
import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth import require_account
from backend.app.config import SETTINGS
from backend.app.db import AdventureRecord, DungeonRecord, RoomRecord, get_db
from backend.app.engine import adventure_compiler, bestiary, dungeon_compiler, items, module, validate

router = APIRouter(tags=["modules"])


def _module_response(mod: module.Module) -> dict:
    return {
        "module": {
            "id": mod.id,
            "name": mod.name,
            "ruleset": mod.ruleset,
            "description": mod.description,
            "map": {
                "width": mod.map.width,
                "height": mod.map.height,
                "tile_size": mod.map.tile_size,
                "tiles": mod.map.tiles,
                "theme": mod.map.theme,
            },
            "dungeon_links": mod.dungeon_links,
        }
    }


@router.get("/modules")
async def list_all_modules():
    return {"modules": module.list_modules()}


@router.post("/modules/adventures")
async def create_adventure(
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Create a blank S3 adventure owned by the current account."""
    title = str(data.get("title", "New Adventure")).strip() or "New Adventure"
    ruleset_id = data.get("ruleset_id", "osric") or "osric"
    slug = module._to_slug(title)
    base_slug = slug
    counter = 1
    while True:
        existing = await db.execute(
            select(AdventureRecord).where(
                AdventureRecord.id == slug,
                AdventureRecord.account_id == account_id,
            )
        )
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}_{counter}"
        counter += 1

    doc = {
        "module": {
            "title": title,
            "version": "1.0",
            "start": "start",
        },
        "regions": [],
        "areas": [
            _set_area_id({
                "id": "start",
                "name": "Starting Area",
                "description": "The adventure begins here.",
                "exits": [],
                "contents": [],
                "monsters": [],
                "treasure": [],
                "discoveries": [],
                "width": 8,
                "height": 8,
                "tiles": ["00000000"] * 8,
                "start_x": 1,
                "start_y": 1,
                "entities": [],
            })
        ],
        "monsters": [],
        "items": [],
        "mechanics": [],
    }
    module.save_adventure(slug, doc)

    record = AdventureRecord(
        id=slug,
        account_id=account_id,
        title=title,
        ruleset_id=ruleset_id,
        data_json=json.dumps(doc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"adventure": _adventure_response(record)}


@router.get("/modules/adventures")
async def list_adventures(
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """List S3 adventures owned by the current account."""
    result = await db.execute(
        select(AdventureRecord)
        .where(AdventureRecord.account_id == account_id)
        .order_by(AdventureRecord.updated_at.desc())
    )
    return {"adventures": [_adventure_response(r) for r in result.scalars().all()]}


@router.get("/modules/{module_id}")
async def get_module(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    if module_id.startswith("dungeon:"):
        dungeon_id = module_id.split(":", 1)[1]
        result = await db.execute(select(DungeonRecord).where(DungeonRecord.id == dungeon_id))
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Dungeon not found")
        if record.account_id != account_id and not record.public:
            raise HTTPException(status_code=403, detail="Not allowed to view this dungeon")
        order = list(dict.fromkeys(json.loads(record.room_order or "[]")))
        result = await db.execute(select(RoomRecord).where(RoomRecord.id.in_(order)))
        rooms = {r.id: r for r in result.scalars().all()}
        ordered = [rooms[r_id] for r_id in order if r_id in rooms]
        if not ordered:
            raise HTTPException(status_code=400, detail="Dungeon has no rooms")
        mod, _links = dungeon_compiler.compile(record, ordered)
        return _module_response(mod)

    try:
        loaded = module.load(module_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(loaded, module.Adventure):
        loaded = adventure_compiler.compile(loaded)
    return _module_response(loaded)


@router.get("/modules/{module_id}/format")
async def get_module_format(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Return the module in S3 adventure format.

    For an imported S3 adventure this returns the stored document.  Tactical
    modules are not converted here; they continue to be served by ``GET
    /modules/{module_id}``.
    """
    result = await db.execute(
        select(AdventureRecord).where(AdventureRecord.id == module_id)
    )
    record = result.scalar_one_or_none()
    if record:
        if record.account_id != account_id and not (
            record.status == "published" and record.visibility in ("public", "unlisted")
        ):
            raise HTTPException(status_code=403, detail="Not allowed to view this adventure")
        return {"module_id": module_id, "format": "s3", "data": json.loads(record.data_json)}

    if module.is_adventure(module_id):
        try:
            adv = module.load_adventure(module_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"module_id": module_id, "format": "s3", "data": adv.data.model_dump()}

    raise HTTPException(status_code=404, detail=f"no adventure {module_id!r}")


@router.post("/modules/validate")
async def validate_module_payload(request: Request):
    """Validate a YAML/JSON adventure payload and return any errors."""
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    try:
        data = module.parse_adventure_payload(body, content_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"parse error: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="payload must be a mapping")
    errors = validate.validate_adventure(data)
    return {"valid": not errors, "errors": errors}


@router.post("/modules/import")
async def import_module(
    request: Request,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Import a valid adventure YAML/JSON and save it as a custom module."""
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    try:
        data = module.parse_adventure_payload(body, content_type)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"parse error: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="payload must be a mapping")

    errors = validate.validate_adventure(data)
    if errors:
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})

    title = data.get("module", {}).get("title", "imported-adventure")
    ruleset = data.get("ruleset", "osric")
    slug = module._to_slug(title)
    # Ensure uniqueness per account.
    base_slug = slug
    counter = 1
    while True:
        existing = await db.execute(
            select(AdventureRecord).where(
                AdventureRecord.id == slug,
                AdventureRecord.account_id == account_id,
            )
        )
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}_{counter}"
        counter += 1

    # Persist to filesystem and database.
    module.save_adventure(slug, data)

    record = AdventureRecord(
        id=slug,
        account_id=account_id,
        title=title,
        ruleset_id=ruleset,
        data_json=json.dumps(data),
    )
    db.add(record)
    await db.commit()

    return {"module_id": slug, "title": title, "format": "s3"}


@router.get("/bestiary")
async def list_bestiary():
    """Return the slugs of all available monster templates."""
    return {"monsters": bestiary.base_ids()}


@router.get("/items")
async def list_items():
    """Return the available treasure/item templates."""
    return {
        "items": [
            {"id": k, "name": v["name"], "type": v["type"], "slot": v.get("slot")}
            for k, v in items.LOOT_TABLE.items()
        ]
    }


# -----------------------------------------------------------------------------
# DM Workshop: S3 adventure editor endpoints
# -----------------------------------------------------------------------------
def _adventure_response(record: AdventureRecord, include_data: bool = True) -> dict:
    response = {
        "id": record.id,
        "title": record.title,
        "ruleset_id": record.ruleset_id or "osric",
        "status": record.status or "draft",
        "visibility": record.visibility or "private",
        "rating_sum": record.rating_sum or 0,
        "rating_count": record.rating_count or 0,
        "download_count": record.download_count or 0,
        "tags": json.loads(record.tags or "[]"),
        "parent_id": record.parent_id,
        "account_id": record.account_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if include_data:
        response["data"] = json.loads(record.data_json or "{}")
    return response


def _average_rating(record: AdventureRecord) -> float:
    if not record.rating_count:
        return 0.0
    return round((record.rating_sum or 0) / record.rating_count, 2)


async def _load_owned_adventure(
    module_id: str,
    account_id: int,
    db: AsyncSession,
) -> AdventureRecord:
    result = await db.execute(select(AdventureRecord).where(AdventureRecord.id == module_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Adventure not found")
    if record.account_id != account_id:
        raise HTTPException(status_code=403, detail="Not allowed to edit this adventure")
    return record


async def _load_readable_adventure(
    module_id: str,
    account_id: int,
    db: AsyncSession,
) -> AdventureRecord:
    """Load an adventure the caller may read: own, public/unlisted published, or admin."""
    result = await db.execute(select(AdventureRecord).where(AdventureRecord.id == module_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Adventure not found")
    if record.account_id == account_id:
        return record
    if record.status == "published" and record.visibility in ("public", "unlisted"):
        return record
    raise HTTPException(status_code=403, detail="Not allowed to view this adventure")


def _set_area_id(area: dict) -> dict:
    if not area.get("id"):
        area["id"] = str(uuid.uuid4())[:8]
    return area


async def _persist_adventure(record: AdventureRecord, data: dict, db: AsyncSession) -> None:
    errors = validate.validate_adventure(data, check_reachability=False)
    if errors:
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})
    module.save_adventure(record.id, data, check_reachability=False)
    record.data_json = json.dumps(data)
    await db.commit()


@router.get("/modules/{module_id}/areas")
async def list_areas(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """List areas for an adventure."""
    record = await _load_owned_adventure(module_id, account_id, db)
    data = json.loads(record.data_json or "{}")
    return {"areas": data.get("areas", [])}


@router.post("/modules/{module_id}/areas")
async def update_area(
    module_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Add or update an area in the adventure, including its tile grid and entities."""
    record = await _load_owned_adventure(module_id, account_id, db)
    doc = json.loads(record.data_json or "{}")
    incoming = dict(data)
    areas = doc.setdefault("areas", [])

    # Merge with the existing area so a partial save (e.g. just metadata)
    # does not wipe the tile grid or entity placement.
    existing = None
    incoming_id = incoming.get("id")
    if incoming_id is not None:
        for a in areas:
            if str(a.get("id")) == str(incoming_id):
                existing = a
                break

    if existing is not None:
        area = _set_area_id({**existing, **incoming})
    else:
        area = _set_area_id(incoming)

    grid_errors = validate.validate_area_grid(area)
    if grid_errors:
        raise HTTPException(status_code=422, detail={"valid": False, "errors": grid_errors})

    for idx, a in enumerate(areas):
        if str(a.get("id")) == str(area["id"]):
            areas[idx] = area
            break
    else:
        areas.append(area)

    # Ensure the module start area still exists.
    start = doc.setdefault("module", {}).get("start")
    area_ids = {str(a.get("id")) for a in areas if isinstance(a, dict)}
    if start not in area_ids and areas:
        doc["module"]["start"] = areas[0].get("id")

    await _persist_adventure(record, doc, db)
    return {"areas": doc.get("areas", [])}


@router.post("/modules/{module_id}/areas/{area_id}/exits")
async def add_exit(
    module_id: str,
    area_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Append an exit to an area."""
    record = await _load_owned_adventure(module_id, account_id, db)
    doc = json.loads(record.data_json or "{}")
    areas = doc.get("areas", [])
    target = None
    for area in areas:
        if str(area.get("id")) == str(area_id):
            target = area
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Area not found")

    exit_data = dict(data)
    exit_data.setdefault("kind", "passage")
    target.setdefault("exits", []).append(exit_data)
    await _persist_adventure(record, doc, db)
    return {"area": target}


@router.post("/modules/{module_id}/areas/{area_id}/contents")
async def add_content(
    module_id: str,
    area_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Add or update a content entry (monster, trap, treasure) in an area."""
    record = await _load_owned_adventure(module_id, account_id, db)
    doc = json.loads(record.data_json or "{}")
    areas = doc.get("areas", [])
    target = None
    for area in areas:
        if str(area.get("id")) == str(area_id):
            target = area
            break
    if target is None:
        raise HTTPException(status_code=404, detail="Area not found")

    content = dict(data)
    uid = content.get("uid")
    contents = target.setdefault("contents", [])
    if uid:
        for idx, existing in enumerate(contents):
            if existing.get("uid") == uid:
                contents[idx] = content
                break
        else:
            contents.append(content)
    else:
        content["uid"] = str(uuid.uuid4())[:8]
        contents.append(content)

    await _persist_adventure(record, doc, db)
    return {"area": target}


@router.put("/modules/{module_id}")
async def update_adventure(
    module_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Update adventure metadata (title, ruleset)."""
    record = await _load_owned_adventure(module_id, account_id, db)
    doc = json.loads(record.data_json or "{}")
    if "title" in data:
        title = str(data["title"]).strip()
        if title:
            record.title = title
            doc.setdefault("module", {})["title"] = title
    if "ruleset_id" in data:
        record.ruleset_id = data["ruleset_id"]
    await _persist_adventure(record, doc, db)
    await db.refresh(record)
    return {"adventure": _adventure_response(record)}


@router.post("/modules/{module_id}/compile")
async def compile_adventure(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Compile the adventure into a tactical module ready for play."""
    record = await _load_owned_adventure(module_id, account_id, db)
    data = json.loads(record.data_json or "{}")
    errors = validate.validate_adventure(data)
    if errors:
        raise HTTPException(status_code=422, detail={"valid": False, "errors": errors})
    adventure = module.Adventure(
        id=record.id,
        ruleset=record.ruleset_id or "osric",
        data=module.AdventureData.model_validate(data),
    )
    mod = adventure_compiler.compile(adventure)
    return _module_response(mod)


# -----------------------------------------------------------------------------
# Marketplace: publish, rate, and fork adventures
# -----------------------------------------------------------------------------
@router.post("/modules/{module_id}/publish")
async def publish_adventure(
    module_id: str,
    data: dict | None = None,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Publish a draft adventure so it appears in the marketplace."""
    record = await _load_owned_adventure(module_id, account_id, db)
    if record.status not in ("draft", "archived"):
        raise HTTPException(status_code=400, detail="Adventure cannot be published from its current state")
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
    return {"adventure": _adventure_response(record)}


@router.post("/modules/{module_id}/unpublish")
async def unpublish_adventure(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Unpublish/archive a published adventure."""
    record = await _load_owned_adventure(module_id, account_id, db)
    if record.status != "published":
        raise HTTPException(status_code=400, detail="Adventure is not published")
    record.status = "archived"
    await db.commit()
    await db.refresh(record)
    return {"adventure": _adventure_response(record)}


@router.get("/marketplace/adventures")
async def list_marketplace_adventures(
    tags: str | None = Query(None, description="Comma-separated tags"),
    min_rating: float | None = Query(None, ge=0, le=5),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List published public adventures with optional filters."""
    filters = [
        AdventureRecord.status == "published",
        AdventureRecord.visibility == "public",
    ]
    if tags:
        wanted = {t.strip().lower() for t in tags.split(",") if t.strip()}
        if wanted:
            # Client-side filter after load; SQLite does not have a native JSON array operator.
            pass
    if search:
        filters.append(AdventureRecord.title.ilike(f"%{search}%"))

    result = await db.execute(
        select(AdventureRecord)
        .where(and_(*filters))
        .order_by(AdventureRecord.updated_at.desc())
    )
    records = result.scalars().all()

    if tags:
        wanted = {t.strip().lower() for t in tags.split(",") if t.strip()}
        records = [r for r in records if wanted.intersection({t.lower() for t in json.loads(r.tags or "[]")})]

    if min_rating is not None:
        records = [r for r in records if _average_rating(r) >= min_rating]

    return {
        "adventures": [_adventure_response(r, include_data=False) for r in records],
    }


@router.post("/marketplace/adventures/{module_id}/rate")
async def rate_adventure(
    module_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Rate a public published adventure (1-5 stars)."""
    record = await _load_readable_adventure(module_id, account_id, db)
    if record.status != "published":
        raise HTTPException(status_code=400, detail="Adventure is not published")
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
        "adventure": _adventure_response(record, include_data=False),
        "average_rating": _average_rating(record),
    }


@router.post("/marketplace/adventures/{module_id}/fork")
async def fork_adventure(
    module_id: str,
    db: AsyncSession = Depends(get_db),
    account_id: int = Depends(require_account),
):
    """Copy a public/unlisted published adventure into the caller's library."""
    result = await db.execute(select(AdventureRecord).where(AdventureRecord.id == module_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Adventure not found")
    if source.status != "published" or source.visibility == "private":
        raise HTTPException(status_code=403, detail="Adventure is not available to fork")

    source.download_count = (source.download_count or 0) + 1

    title = f"{source.title} (fork)"
    slug = module._to_slug(title)
    base_slug = slug
    counter = 1
    while True:
        existing = await db.execute(
            select(AdventureRecord).where(
                AdventureRecord.id == slug,
                AdventureRecord.account_id == account_id,
            )
        )
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}_{counter}"
        counter += 1

    source_path = SETTINGS.module_root / module_id
    target_path = SETTINGS.module_root / slug
    if source_path.exists() and not target_path.exists():
        shutil.copytree(source_path, target_path)

    data = json.loads(source.data_json or "{}")
    data.setdefault("module", {})["title"] = title
    module.save_adventure(slug, data, check_reachability=False)

    fork = AdventureRecord(
        id=slug,
        account_id=account_id,
        title=title,
        ruleset_id=source.ruleset_id or "osric",
        data_json=json.dumps(data),
        status="draft",
        visibility="private",
        parent_id=source.id,
    )
    db.add(fork)
    await db.commit()
    await db.refresh(fork)
    return {"adventure": _adventure_response(fork)}
