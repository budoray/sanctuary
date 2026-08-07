"""Load a ruleset manifest + adapter."""
from pathlib import Path
from typing import Any

import yaml

from backend.app.config import SETTINGS
from backend.app.rulesets.base import Ruleset
from backend.app.rulesets.osric import OSRICRuleset


RULESET_ADAPTERS = {
    "osric": OSRICRuleset,
}


def load_ruleset(ruleset_id: str, overrides: dict[str, Any] | None = None) -> Ruleset:
    path = SETTINGS.ruleset_root / ruleset_id / "ruleset.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Ruleset not found: {ruleset_id}")
    manifest = yaml.safe_load(path.read_text())
    manifest.setdefault("id", ruleset_id)
    if overrides:
        _merge(manifest, overrides)
    adapter_cls = RULESET_ADAPTERS.get(ruleset_id, Ruleset)
    return adapter_cls(manifest, root=path.parent)


def _merge(base: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Shallow-merge overrides into the manifest. Deep-merge only 'content'."""
    for key, value in overrides.items():
        if key == "content" and isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key].update(value)
        else:
            base[key] = value
