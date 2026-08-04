"""Top-down grid map logic with dungeon tiles."""
from dataclasses import dataclass, field
from typing import Any


TILE_FLOOR = "floor"
TILE_WALL = "wall"
TILE_DOOR = "door"


@dataclass
class Token:
    id: str
    name: str
    x: int
    y: int
    color: str = "#e74c3c"
    owner: str | None = None
    hp: int = 0
    max_hp: int = 0
    ac: int = 10

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "color": self.color,
            "owner": self.owner,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
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
            hp=data.get("hp", 0),
            max_hp=data.get("max_hp", 0),
            ac=data.get("ac", 10),
        )

    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass
class GameMap:
    width: int = 20
    height: int = 15
    tile_size: int = 32
    tiles: list[list[str]] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)

    def __post_init__(self):
        if not self.tiles:
            self.tiles = [[TILE_FLOOR for _ in range(self.width)] for _ in range(self.height)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "tile_size": self.tile_size,
            "tiles": self.tiles,
            "tokens": [t.to_dict() for t in self.tokens],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameMap":
        gm = cls(
            width=data.get("width", 20),
            height=data.get("height", 15),
            tile_size=data.get("tile_size", 32),
            tiles=[row[:] for row in data.get("tiles", [])],
        )
        gm.tokens = [Token.from_dict(t) for t in data.get("tokens", [])]
        return gm

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_at(self, x: int, y: int) -> str:
        if not self.in_bounds(x, y):
            return TILE_WALL
        return self.tiles[y][x]

    def is_walkable(self, x: int, y: int) -> bool:
        return self.tile_at(x, y) in (TILE_FLOOR, TILE_DOOR)

    def token_at(self, x: int, y: int) -> Token | None:
        for token in self.tokens:
            if token.x == x and token.y == y and token.is_alive():
                return token
        return None

    def tokens_in_radius(self, x: int, y: int, radius: int) -> list[Token]:
        result = []
        for token in self.tokens:
            if not token.is_alive():
                continue
            dx = token.x - x
            dy = token.y - y
            if dx * dx + dy * dy <= radius * radius:
                result.append(token)
        return result
