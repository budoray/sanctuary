"""OSRIC dungeon crawl backend.

Self-contained OSRIC rules engine; no external Sanctuary dependency.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine.dice import DiceError, roll_expression
from rulesets.osric import adapter as osric
from rulesets.osric import combat as osric_combat
from rulesets.osric import loader as osric_loader
from rulesets.osric import spells as osric_spells

ROOT = Path(__file__).parent

app = FastAPI(title="OSRIC Dungeon")


class CharacterAction(BaseModel):
    character: dict
    item_id: str


class EquipAction(BaseModel):
    character: dict
    item_id: str
    equip: bool = True


class BuyPackage(BaseModel):
    character: dict
    package_id: str | None = None
    equip: bool = True


class AttackAction(BaseModel):
    attacker: dict
    defender: dict
    ranged: bool = False
    range_ft: int = 0


class SpellAction(BaseModel):
    caster: dict
    spell_id: str
    target: dict | None = None


class LevelUpAction(BaseModel):
    character: dict


class CreateCharacter(BaseModel):
    name: str
    ancestry: str
    class_id: str
    alignment: str
    roll_method: str = "3d6_in_order"
    abilities: dict[str, int] | None = None


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/osric/rules")
def osric_rules():
    return {
        "core": osric.CORE,
        "rolling": osric.ROLLING,
        "progression": osric.PROGRESSION,
        "combat": osric.COMBAT,
        "ability_modifiers": osric.ABILITY_MODIFIERS,
        "class_features": osric.CLASS_FEATURES,
    }


@app.get("/api/osric/class-features/{class_id}")
def class_features(class_id: str):
    if class_id not in osric.CLASSES:
        raise HTTPException(status_code=404, detail=f"Unknown class: {class_id}")
    return osric.class_features(class_id)


@app.get("/api/osric/options")
def osric_options():
    return {
        "ancestries": [
            {
                "id": aid,
                "name": osric.get_ancestry(aid)["name"],
                "allowed_classes": osric.get_ancestry(aid).get("allowed_classes", []),
            }
            for aid in osric.ancestry_ids()
        ],
        "classes": [
            {
                "id": cid,
                "name": klass["name"],
                "hit_die": klass.get("hit_die", 8),
                "prime_requisites": klass.get("prime_requisites", []),
                "ability_score_requirements": klass.get("ability_score_requirements", {}),
                "allowed_alignments": klass.get("allowed_alignments", []),
                "armour_allowed": klass.get("armour_allowed", []),
                "weapons_allowed": klass.get("weapons_allowed", []),
                "shields_allowed": klass.get("shields_allowed", False),
                "fighter_type": klass.get("fighter_type", False),
                "next_level_xp": klass.get("next_level_xp", 0),
            }
            for cid, klass in [(cid, osric.get_class(cid)) for cid in osric.class_ids()]
        ],
        "alignments": osric.ALIGNMENTS,
        "equipment": [
            {
                "id": iid,
                "name": item["name"],
                "category": item["category"],
                "cost_cp": item["cost_cp"],
                "missile": item.get("missile", False),
                "range": item.get("range"),
                "ac_ascending": item.get("ac_ascending"),
                "ac_ascending_modifier": item.get("ac_ascending_modifier"),
                "damage": item.get("damage"),
                "weight": item.get("weight"),
                "subcategory": item.get("subcategory"),
            }
            for iid, item in osric.EQUIPMENT_BY_ID.items()
        ],
        "spells": osric_spells.CLASS_SPELLS,
    }


def _rebuild_sheet(character: dict, inventory: list[dict]) -> dict:
    """Rebuild the OSRIC sheet and preserve transient state like spell slots."""
    slots = character.get("sheet", {}).get("spell_slots", osric_spells.initial_spell_slots(character["class"]))
    sheet = osric.build_sheet(
        character["ancestry"],
        character["class"],
        character["alignment"],
        character["abilities"],
        character["hit_points"],
        inventory=inventory,
        starting_gold=character["starting_gold"],
    )
    sheet["spell_slots"] = slots
    return sheet


@app.get("/api/osric/roll-abilities")
def roll_abilities(method: str = "3d6"):
    return {"pool": osric.roll_ability_pool(method)}


@app.post("/api/osric/character")
def create_character(req: CreateCharacter):
    try:
        data = osric.create_character_data(
            req.ancestry, req.class_id, req.alignment, req.name, req.roll_method, req.abilities
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    data["remaining_gold"] = data["starting_gold"]
    data["inventory"] = []
    data["sheet"] = osric.build_sheet(
        req.ancestry,
        req.class_id,
        req.alignment,
        data["abilities"],
        data["hit_points"],
        inventory=[],
        starting_gold=data["starting_gold"],
    )
    data["sheet"]["spell_slots"] = osric_spells.initial_spell_slots(req.class_id)
    return data


@app.post("/api/osric/buy")
def buy_item(req: CharacterAction):
    item = osric.get_equipment(req.item_id)
    character = req.character
    cost_gp = item["cost_cp"] / 100
    if character.get("remaining_gold", 0) < cost_gp:
        raise HTTPException(status_code=400, detail="Not enough gold.")

    inventory = osric.add_item(character.get("inventory", []), req.item_id, quantity=1)
    character["inventory"] = inventory
    character["remaining_gold"] -= cost_gp
    character["sheet"] = _rebuild_sheet(character, inventory)
    return character


@app.post("/api/osric/sell")
def sell_item(req: CharacterAction):
    item = osric.get_equipment(req.item_id)
    character = req.character
    inventory = character.get("inventory", [])
    idx = next((i for i, e in enumerate(inventory) if e.get("item_id") == req.item_id), None)
    if idx is None:
        raise HTTPException(status_code=400, detail="Item not in inventory.")

    entry = inventory[idx]
    sell_ratio = osric.COMBAT.get("sell_back_ratio", 0.5)
    sell_price_gp = item["cost_cp"] / 100 * sell_ratio
    character["remaining_gold"] = round(character.get("remaining_gold", 0) + sell_price_gp, 1)
    if entry.get("quantity", 1) > 1:
        entry["quantity"] -= 1
    else:
        inventory.pop(idx)
    character["inventory"] = inventory
    character["sheet"] = _rebuild_sheet(character, inventory)
    return character


@app.post("/api/osric/buy-package")
def buy_package(req: BuyPackage):
    """Buy a configurable starter package (defaults to the character's class package)."""
    character = req.character
    class_id = character.get("class", "")
    package_id = req.package_id or class_id
    package = osric.CLASS_FEATURES.get("starting_packages", {}).get(package_id)
    if not package:
        raise HTTPException(status_code=400, detail=f"No starter package for '{package_id}'.")

    inventory = list(character.get("inventory", []))
    remaining = float(character.get("remaining_gold", 0))
    unaffordable: list[str] = []

    for item_id in package.get("items", []):
        try:
            item = osric.get_equipment(item_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        cost_gp = item["cost_cp"] / 100
        if remaining < cost_gp:
            unaffordable.append(item["name"])
            continue
        remaining -= cost_gp
        inventory = osric.add_item(inventory, item_id, quantity=1)
        if req.equip and item.get("category") in ("armour", "shields", "weapons"):
            try:
                inventory = osric.equip_item(inventory, item_id, class_id=class_id)
            except ValueError:
                # Item cannot be equipped by this class; keep it in inventory.
                pass

    if unaffordable:
        raise HTTPException(status_code=400, detail=f"Cannot afford: {', '.join(unaffordable)}")

    character["inventory"] = inventory
    character["remaining_gold"] = round(remaining, 2)
    character["sheet"] = _rebuild_sheet(character, inventory)
    return character


@app.post("/api/osric/equip")
def equip_item(req: EquipAction):
    character = req.character
    try:
        if req.equip:
            inventory = osric.equip_item(
                character.get("inventory", []), req.item_id, class_id=character.get("class", "")
            )
        else:
            inventory = osric.unequip_item(character.get("inventory", []), req.item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    character["inventory"] = inventory
    character["sheet"] = _rebuild_sheet(character, inventory)
    return character


@app.post("/api/osric/attack")
def resolve_attack(req: AttackAction):
    """Resolve a single melee or ranged attack using OSRIC THAC0 vs descending AC."""
    return osric_combat.resolve_attack(req.attacker, req.defender, req.ranged, req.range_ft)


@app.post("/api/osric/spell")
def cast_spell(req: SpellAction):
    caster = req.caster
    spell = osric_spells.SPELLS.get(req.spell_id)
    if not spell:
        raise HTTPException(status_code=400, detail=f"Unknown spell: {req.spell_id}")
    if caster.get("class", "") not in spell["classes"]:
        raise HTTPException(status_code=400, detail=f"{caster.get('class')} cannot cast {spell['name']}.")

    slots = caster.get("sheet", {}).get("spell_slots", {})
    level_key = str(spell["level"])
    if int(slots.get(level_key, slots.get(spell["level"], 0))) <= 0:
        raise HTTPException(status_code=400, detail="No spell slots remaining.")

    new_slots = dict(slots)
    new_slots[level_key] = int(new_slots.get(level_key, new_slots.get(spell["level"], 0))) - 1
    caster["sheet"]["spell_slots"] = new_slots

    result = osric_spells.resolve_spell(caster, req.spell_id)
    result["target"] = (req.target or {}).get("name")
    return {"result": result, "character": caster}


@app.post("/api/osric/level-up")
def level_up(req: LevelUpAction):
    return osric.level_up(req.character)


@app.post("/api/roll")
def roll_dice_endpoint(expression: str = Form(...)):
    try:
        result = roll_expression(expression)
    except DiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@app.get("/version")
def version():
    version_text = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    return {"version": version_text}


app.mount("/", StaticFiles(directory=ROOT / "static"), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("LOAD_PORT", "8700"))
    uvicorn.run("app:app", host="127.0.0.1", port=port)
