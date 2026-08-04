"""Game session state machine."""
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.app.engine.map import GameMap, Token, TILE_FLOOR, TILE_WALL, TILE_DOOR


@dataclass
class GameSession:
    id: str
    module_id: str
    ruleset_id: str
    account_id: int | None = None
    map: GameMap = field(default_factory=GameMap)
    version: int = 0
    turn: int = 1
    phase: str = "player"  # "player" or "dm"
    log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "ruleset_id": self.ruleset_id,
            "account_id": self.account_id,
            "version": self.version,
            "turn": self.turn,
            "phase": self.phase,
            "log": self.log,
            "map": self.map.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSession":
        return cls(
            id=data["id"],
            module_id=data["module_id"],
            ruleset_id=data["ruleset_id"],
            account_id=data.get("account_id"),
            map=GameMap.from_dict(data.get("map", {})),
            version=data.get("version", 0),
            turn=data.get("turn", 1),
            phase=data.get("phase", "player"),
            log=data.get("log", []),
        )

    def apply(self, event_type: str, payload: dict[str, Any]) -> None:
        if event_type == "token_moved":
            token_id = payload.get("token_id")
            for token in self.map.tokens:
                if token.id == token_id:
                    token.x = payload.get("x", token.x)
                    token.y = payload.get("y", token.y)
                    break
        elif event_type == "token_damaged":
            token_id = payload.get("token_id")
            for token in self.map.tokens:
                if token.id == token_id:
                    token.hp = max(0, token.hp - payload.get("damage", 0))
                    break
        elif event_type == "token_added":
            self.map.tokens.append(Token.from_dict(payload))
        elif event_type == "token_removed":
            self.map.tokens = [t for t in self.map.tokens if t.id != payload.get("token_id")]
        elif event_type == "dm_turn":
            self.turn = payload.get("turn", self.turn)
            self.phase = "player"
            if "entry" in payload:
                self.log.append(payload["entry"])
            if payload.get("game_over"):
                self.phase = "game_over"
        self.version += 1

    def end_player_turn(self) -> None:
        self.phase = "dm"

    def player_token(self) -> Token | None:
        return next((t for t in self.map.tokens if t.owner == "player" and t.is_alive()), None)

    def dm_tokens(self) -> list[Token]:
        return [t for t in self.map.tokens if t.owner != "player" and t.is_alive()]

    def add_token(
        self,
        name: str,
        x: int,
        y: int,
        color: str = "#e74c3c",
        owner: str | None = None,
        hp: int = 0,
        max_hp: int = 0,
        ac: int = 10,
    ) -> Token:
        token = Token(
            id=str(uuid.uuid4())[:8],
            name=name,
            x=x,
            y=y,
            color=color,
            owner=owner,
            hp=hp,
            max_hp=max_hp,
            ac=ac,
        )
        self.map.tokens.append(token)
        return token


def _build_lair() -> GameMap:
    """Create a small sample dungeon: a room with a corridor and a side chamber."""
    width, height = 24, 16
    tiles = [[TILE_WALL for _ in range(width)] for _ in range(height)]

    def carve_rect(x1: int, y1: int, x2: int, y2: int):
        for y in range(y1, y2):
            for x in range(x1, x2):
                tiles[y][x] = TILE_FLOOR

    # Main hall
    carve_rect(2, 2, 12, 10)
    # Corridor east
    carve_rect(12, 5, 20, 7)
    # Goblin chamber
    carve_rect(20, 3, 23, 9)
    # Door between hall and corridor
    tiles[5][11] = TILE_DOOR
    tiles[6][11] = TILE_DOOR

    gm = GameMap(width=width, height=height, tile_size=32, tiles=tiles)
    return gm


def new_session(account_id: int | None = None, module_id: str = "sample_lair", ruleset_id: str = "osric") -> GameSession:
    session = GameSession(
        id=str(uuid.uuid4())[:8],
        module_id=module_id,
        ruleset_id=ruleset_id,
        account_id=account_id,
        map=_build_lair(),
    )
    session.add_token("Hero", 3, 4, owner="player", hp=8, max_hp=8, ac=10)
    session.add_token("Goblin", 21, 5, color="#2ecc71", hp=4, max_hp=4, ac=6)
    return session
