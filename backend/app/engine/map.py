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

    def neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        """Return walkable neighbor coordinates."""
        result = []
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nx, ny = x + dx, y + dy
            if self.is_walkable(nx, ny):
                result.append((nx, ny))
        return result

    def pathfind(self, start_x: int, start_y: int, goal_x: int, goal_y: int) -> list[tuple[int, int]]:
        """A* pathfinding. Returns a list of coordinates from start to goal, excluding start."""
        import heapq

        if not self.is_walkable(goal_x, goal_y):
            return []

        start = (start_x, start_y)
        goal = (goal_x, goal_y)
        if start == goal:
            return []

        open_set = [(0, start)]
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score: dict[tuple[int, int], int] = {start: 0}
        f_score: dict[tuple[int, int], int] = {start: abs(start_x - goal_x) + abs(start_y - goal_y)}
        visited = set()

        while open_set:
            _, current = heapq.heappop(open_set)
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.reverse()
                return path

            if current in visited:
                continue
            visited.add(current)

            for nx, ny in self.neighbors(*current):
                neighbor = (nx, ny)
                tentative = g_score[current] + 1
                if tentative < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    f_score[neighbor] = tentative + abs(nx - goal_x) + abs(ny - goal_y)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []
