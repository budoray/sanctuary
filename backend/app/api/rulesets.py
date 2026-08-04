"""Ruleset API."""
from pathlib import Path

from fastapi import APIRouter
import yaml

from backend.app.config import SETTINGS

router = APIRouter(tags=["rulesets"])


@router.get("/rulesets")
async def list_rulesets():
    rulesets = []
    if SETTINGS.ruleset_root.exists():
        for path in SETTINGS.ruleset_root.iterdir():
            manifest = path / "ruleset.yaml"
            if manifest.exists():
                data = yaml.safe_load(manifest.read_text())
                rulesets.append({
                    "id": path.name,
                    "name": data.get("name", path.name),
                    "version": data.get("version"),
                    "description": data.get("description", ""),
                })
    return {"rulesets": rulesets}
