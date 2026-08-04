"""Game session state machine."""
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.app.engine.map import GameMap, Token


@dataclass
class GameSession:
    id: str
    module_id: str
    ruleset_id: str
    map: GameMap = field(default_factory=GameMap)
    version: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "ruleset_id": self.ruleset_id,
            "version": self.version,
            "map": self.map.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSession":
        return cls(
            id=data["id"],
            module_id=data["module_id"],
            ruleset_id=data["ruleset_id"],
            map=GameMap.from_dict(data.get("map", {})),
            version=data.get("version", 0),
        )

    def apply(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "token_moved":
            token_id = payload.get("token_id")
            for token in self.map.tokens:
                if token.id == token_id:
                    token.x = payload.get("x", token.x)
                    token.y = payload.get("y", token.y)
                    break
        elif event_type == "token_added":
            self.map.tokens.append(Token.from_dict(payload))
        elif event_type == "token_removed":
            self.map.tokens = [t for t in self.map.tokens if t.id != payload.get("token_id")]
        self.version += 1

    def add_token(
        self,
        name: str,
        x: int,
        y: int,
        color: str = "#e74c3c",
        owner: str | None = None,
    ) -> Token:
        token = Token(
            id=str(uuid.uuid4())[:8],
            name=name,
            x=x,
            y=y,
            color=color,
            owner=owner,
        )
        self.map.tokens.append(token)
        return token


def new_session(module_id: str = "sample_lair", ruleset_id: str = "osric") -> GameSession:
    session = GameSession(
        id=str(uuid.uuid4())[:8],
        module_id=module_id,
        ruleset_id=ruleset_id,
    )
    session.add_token("Hero", 2, 2, owner="player")
    session.add_token("Goblin", 10, 8, color="#2ecc71")
    return session
