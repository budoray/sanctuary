"""Base ruleset interface."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml


class Ruleset(ABC):
    def __init__(self, manifest: dict[str, Any], root: Path | None = None):
        self.manifest = manifest
        self.root = root or Path()

    @property
    def id(self) -> str:
        return self.manifest.get("id", "unknown")

    @property
    def name(self) -> str:
        return self.manifest.get("name", self.id)

    @property
    def abilities(self) -> list[str]:
        return list(self.manifest.get("abilities", []))

    @property
    def gen_modes(self) -> list[dict[str, Any]]:
        return list(self.manifest.get("gen_modes", []))

    @property
    def default_damage_expr(self) -> str:
        return self.manifest.get("default_damage_expr", "1d6")

    def content_path(self, key: str) -> Path | None:
        """Return an absolute path to a content directory/file declared in the manifest."""
        content = self.manifest.get("content", {})
        rel = content.get(key)
        if not rel:
            return None
        return (self.root / rel).resolve()

    def load_yaml(self, key: str) -> Any:
        """Load a YAML content file declared in the manifest."""
        path = self.content_path(key)
        if path is None or not path.exists():
            raise FileNotFoundError(f"Ruleset {self.id} missing content: {key}")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def list_monsters(self) -> list[str]:
        """Return available monster ids by scanning the monsters directory."""
        monsters_dir = self.content_path("monsters")
        if monsters_dir is None or not monsters_dir.exists():
            return []
        return sorted(
            p.stem
            for p in monsters_dir.glob("*.yaml")
            if p.is_file() and not p.stem.startswith("_")
        )

    @abstractmethod
    def validate_action(self, session, actor, action: dict[str, Any]) -> dict[str, Any]:
        """Return {ok: bool, reason?: str, result?: dict}."""
        ...
