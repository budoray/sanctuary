"""Base ruleset interface."""
from abc import ABC, abstractmethod
from typing import Any


class Ruleset(ABC):
    def __init__(self, manifest: dict[str, Any]):
        self.manifest = manifest

    @property
    def id(self) -> str:
        return self.manifest.get("id", "unknown")

    @property
    def name(self) -> str:
        return self.manifest.get("name", self.id)

    @abstractmethod
    def validate_action(self, session, actor, action: dict[str, Any]) -> dict[str, Any]:
        """Return {ok: bool, reason?: str, result?: dict}."""
        ...
