"""Top-down grid map logic."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Token:
    id: str
    name: str
    x: int
    y: int
    color: str = "#e74c3c"
    owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "owner": self.owner,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Token":
        return cls(
            id=data["id"],
            name=data["name"],
            x=data["x"],
            y=data["y"],
            color=data.get("color", "#e74c3c"),
            owner=data.get("owner"),
        )


@dataclass
class GameMap:
    width: int = 20
    height: int = 15
    tile_size: int = 32
    tokens: list[Token] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "tile_size": self.tile_size,
            "tokens": [t.to_dict() for t in self.tokens],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameMap":
        gm = cls(
            width=data.get("width", 20),
            height=data.get("height", 15),
            tile_size=data.get("tile_size", 32),
        )
        gm.tokens = [Token.from_dict(t) for t in data.get("tokens", [])]
        return gm

    def token_at(self, x: int, y: int) -> Token | None:
        for token in self.tokens:
            if token.x == x and token.y == y:
                return token
        return None
