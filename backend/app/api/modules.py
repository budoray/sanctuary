"""Module API: load module metadata."""
from fastapi import APIRouter, HTTPException

from backend.app.engine import bestiary, module

router = APIRouter(tags=["modules"])


@router.get("/modules")
async def list_all_modules():
    return {"modules": module.list_modules()}


@router.get("/modules/{module_id}")
async def get_module(module_id: str):
    try:
        mod = module.load(module_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
        }
    }


@router.get("/bestiary")
async def list_bestiary():
    """Return the slugs of all available monster templates."""
    return {"monsters": bestiary.base_ids()}
