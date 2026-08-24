"""Sanctuary VTT — FastAPI entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import db
import tenshin_version
from config import settings
from tenshin_auth import require_account

ROOT = Path(__file__).parent

from engine.dice import DiceError, roll_expression
from engine.test_ground import apply_move, get_test_ground
from rulesets.osric.adapter import (
    ABILITIES,
    ALIGNMENTS,
    add_item,
    create_character_data,
    equipment_ids,
    equipment_options,
    equip_item,
    get_equipment,
    remove_item,
    serialise_character,
    unequip_item,
)
from rulesets.osric.adapter import class_ids as osric_class_ids
from rulesets.osric.adapter import ancestry_ids as osric_ancestry_ids


def _apply_pending_moves(moves):
    for move in moves:
        token = db.get_token(move.character_id)
        if token:
            x, y = apply_move(token["x"], token["y"], move.direction)
            db.place_token(move.character_id, x, y)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_sanctuary_schema()
    ground = get_test_ground(settings.decision_timeout_seconds)
    ground.on_tick = _apply_pending_moves
    ground.participant_count_fn = lambda: len(db.list_tokens())
    yield


app = FastAPI(lifespan=lifespan, title="Sanctuary")


def _account(request: Request) -> int:
    return require_account(request)


@app.get("/version")
def version():
    return PlainTextResponse(tenshin_version.get_version())


def _landing():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/")
def landing():
    return _landing()


@app.get("/about")
def about():
    return _landing()


@app.get("/begin")
def begin(request: Request):
    try:
        _account(request)
    except HTTPException:
        return RedirectResponse("/", status_code=303)
    return FileResponse(ROOT / "static" / "begin.html")


@app.get("/live")
def live_landing():
    """Sanctuary has no spectator live stream; /live redirects to the about page."""
    return RedirectResponse("/", status_code=303)


@app.get("/api/me")
def api_me(request: Request):
    try:
        account_id = _account(request)
        return {"logged_in": True, "account_id": account_id}
    except HTTPException:
        return {"logged_in": False}


@app.get("/api/ruleset/osric/options")
def osric_options():
    return {
        "ancestries": [
            {"id": aid, "name": aid.replace("_", " ").title()}
            for aid in osric_ancestry_ids()
        ],
        "classes": [
            {"id": cid, "name": cid.replace("_", " ").title()}
            for cid in osric_class_ids()
        ],
        "alignments": ALIGNMENTS,
        "abilities": ABILITIES["abilities"],
        "roll_method": ABILITIES["roll_method"],
    }


@app.post("/api/characters")
def create_character(
    request: Request,
    name: str = Form(...),
    ancestry: str = Form(...),
    class_id: str = Form(..., alias="class"),
    alignment: str = Form(...),
):
    account_id = _account(request)
    try:
        data = create_character_data(ancestry, class_id, alignment, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    character_id = db.create_character(
        account_id,
        data["name"],
        data["ancestry"],
        data["class"],
        data["alignment"],
        data["abilities"],
        data["hit_points"],
        data["sheet"],
        data["inventory"],
    )
    # Place token on test ground at origin.
    db.place_token(character_id, 0, 0)
    return JSONResponse({"id": character_id, **data})


@app.get("/api/characters")
def list_characters(request: Request):
    account_id = _account(request)
    rows = db.list_characters(account_id)
    return [serialise_character(row) for row in rows]


@app.get("/api/characters/{character_id}")
def get_character(request: Request, character_id: int):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")
    return serialise_character(row)


@app.get("/api/ruleset/osric/equipment")
def osric_equipment():
    return {"equipment": equipment_options()}


@app.post("/api/roll")
def roll_dice_endpoint(expression: str = Form(...)):
    try:
        result = roll_expression(expression)
    except DiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.get("/api/characters/{character_id}/inventory")
def get_inventory(request: Request, character_id: int):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")
    return {
        "character_id": character_id,
        "inventory": row.get("inventory") or [],
        "equipment": equipment_options(),
    }


@app.post("/api/characters/{character_id}/inventory")
def add_inventory_item(
    request: Request,
    character_id: int,
    item_id: str = Form(...),
    quantity: int = Form(1),
    equipped: bool = Form(False),
):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")
    if item_id not in equipment_ids():
        raise HTTPException(status_code=400, detail="Unknown equipment.")

    inventory = row.get("inventory") or []
    try:
        inventory = add_item(
            inventory, item_id, quantity=quantity, equipped=equipped, class_id=row["class"]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.set_inventory(character_id, account_id, inventory)
    return serialise_character(db.get_character(character_id, account_id))


@app.delete("/api/characters/{character_id}/inventory/{item_id}")
def delete_inventory_item(request: Request, character_id: int, item_id: str):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")

    inventory = remove_item(row.get("inventory") or [], item_id)
    db.set_inventory(character_id, account_id, inventory)
    return serialise_character(db.get_character(character_id, account_id))


@app.post("/api/characters/{character_id}/inventory/{item_id}/equip")
def equip_inventory_item(request: Request, character_id: int, item_id: str):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")

    try:
        inventory = equip_item(row.get("inventory") or [], item_id, class_id=row["class"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.set_inventory(character_id, account_id, inventory)
    return serialise_character(db.get_character(character_id, account_id))


@app.post("/api/characters/{character_id}/inventory/{item_id}/unequip")
def unequip_inventory_item(request: Request, character_id: int, item_id: str):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")

    inventory = unequip_item(row.get("inventory") or [], item_id)
    db.set_inventory(character_id, account_id, inventory)
    return serialise_character(db.get_character(character_id, account_id))


@app.post("/api/test-ground/{character_id}/move")
def move_token(request: Request, character_id: int, direction: int = Form(...)):
    account_id = _account(request)
    row = db.get_character(character_id, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Character not found.")

    token = db.get_token(character_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found.")

    ground = get_test_ground(settings.decision_timeout_seconds)
    if not ground.submit_move(character_id, direction):
        raise HTTPException(status_code=409, detail="Move already submitted this round.")

    state = ground.get_state()
    return {
        "status": "pending",
        "character_id": character_id,
        "direction": direction,
        "round": state["round"],
        "pending_count": state["pending_count"],
        "expected_count": state["expected_count"],
    }


@app.get("/api/test-ground/state")
def test_ground_state():
    from engine.grid import TILES_PER_10FT

    ground = get_test_ground(settings.decision_timeout_seconds)
    state = ground.get_state()
    tokens = db.list_tokens()
    return {
        "round": state["round"],
        "timer_end": state["timer_end"],
        "pending_count": state["pending_count"],
        "expected_count": state["expected_count"],
        "decision_timeout_seconds": settings.decision_timeout_seconds,
        "scale": {"tiles_per_10ft": TILES_PER_10FT},
        "tokens": [
            {
                "character_id": t["character_id"],
                "x": t["x"],
                "y": t["y"],
                "name": t["name"],
                "ancestry": t["ancestry"],
                "class": t["class"],
            }
            for t in tokens
        ],
    }


# Static assets — registered after API routes.
app.mount("/", StaticFiles(directory=ROOT / "static"), name="static")


if __name__ == "__main__":
    dev = os.environ.get("TENSHIN_DEV", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "app:app" if dev else app,
        host=settings.load_host,
        port=settings.load_port,
        reload=dev,
    )
