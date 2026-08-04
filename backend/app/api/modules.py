"""Module/adventure API."""
from pathlib import Path

from fastapi import APIRouter
import yaml

from backend.app.config import SETTINGS

router = APIRouter(tags=["modules"])


@router.get("/modules")
async def list_modules():
    modules = []
    if SETTINGS.module_root.exists():
        for path in SETTINGS.module_root.iterdir():
            manifest = path / "module.yaml"
            if manifest.exists():
                data = yaml.safe_load(manifest.read_text())
                modules.append({
                    "id": path.name,
                    "name": data.get("name", path.name),
                    "description": data.get("description", ""),
                    "ruleset": data.get("ruleset"),
                })
    return {"modules": modules}
