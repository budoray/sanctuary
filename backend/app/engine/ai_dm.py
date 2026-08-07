"""Deterministic AI DM policy for tactical monster turns.

The policy is fully deterministic: every decision that is not a pure
function of state uses the session ``Dice`` instance.  No call to the
``random`` module is made from this file.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Awaitable, Callable, Protocol

from backend.app.engine import resolve
from backend.app.engine.dice import Dice

TILE_WALL = "1"
TILE_TRAP = "2"
TILE_HAZARD_1 = "3"
TILE_HAZARD_2 = "4"
TILE_EVENT = "5"

RANGED_RANGE = 4


class AIDMCallbacks(Protocol):
    """Execution hooks supplied by the session engine.

    Keeping the session helpers behind this protocol avoids a circular
    import between ``ai_dm.py`` and ``session.py``.
    """

    async def attack(self, attacker: dict[str, Any], target: dict[str, Any]) -> None:
        ...

    async def ranged_attack(self, attacker: dict[str, Any], target: dict[str, Any]) -> None:
        ...

    async def move(self, token: dict[str, Any], x: int, y: int) -> None:
        ...

    def line_of_sight(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        ...

    def has_cover(self, target: dict[str, Any]) -> bool:
        ...

    def is_flanking(self, attacker: dict[str, Any], target: dict[str, Any]) -> bool:
        ...

    def token_at(self, x: int, y: int) -> dict[str, Any] | None:
        ...


class AIDM:
    """Deterministic monster tactics for one DM turn.

    Construct with the current session state, module, dice instance, and a
    callbacks object that can execute the chosen actions.  Call
    ``await take_turn()`` to run every living monster and return a list of
    short event descriptions suitable for the narrator.
    """

    def __init__(
        self,
        state: dict[str, Any],
        module: Any,
        d: Dice,
        callbacks: AIDMCallbacks,
    ):
        self.state = state
        self.module = module
        self.d = d
        self.cb = callbacks
        self.events: list[str] = []

    def _map(self):
        return self.module.map

    def _walkable_and_free(self, x: int, y: int, occupant_ok: tuple[int, int] | None = None) -> bool:
        m = self._map()
        if not m.in_bounds(x, y) or not m.walkable(x, y):
            return False
        occupant = self.cb.token_at(x, y)
        if occupant is None:
            return True
        if occupant_ok is not None and (x, y) == occupant_ok:
            return True
        return False

    def _is_hazard(self, x: int, y: int) -> bool:
        m = self._map()
        if not m.in_bounds(x, y):
            return False
        tile = m.tiles[y][x]
        return tile in (TILE_HAZARD_1, TILE_HAZARD_2)

    def _has_cover_here(self, x: int, y: int) -> bool:
        m = self._map()
        if not m.in_bounds(x, y):
            return False
        # Forest brush tile grants cover.
        if getattr(m, "theme", None) == "forest" and m.tiles[y][x] == TILE_HAZARD_1:
            return True
        # Adjacency to a wall grants cover.
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if m.in_bounds(nx, ny) and m.tiles[ny][nx] == TILE_WALL:
                return True
        return False

    def _distance(self, a: dict[str, Any], b: dict[str, Any]) -> int:
        return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])

    def _living_players(self) -> list[dict[str, Any]]:
        return [p for p in self.state.get("players", []) if p.get("alive", True)]

    def _downed_players(self) -> list[dict[str, Any]]:
        return [p for p in self._living_players() if p.get("down", False)]

    def _living_monsters(self) -> list[dict[str, Any]]:
        return [m for m in self.state.get("monsters", []) if m.get("alive", True)]

    def _nearest_player(self, monster: dict[str, Any], candidates: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
        players = candidates if candidates is not None else self._living_players()
        if not players:
            return None
        return min(players, key=lambda p: self._distance(monster, p))

    def _is_cruel(self, monster: dict[str, Any]) -> bool:
        """Undead and similar monsters finish the fallen."""
        name = monster.get("name", "").lower()
        return any(keyword in name for keyword in ("skeleton", "zombie", "ghoul", "wraith", "spectre", "vampire"))

    def _hd_base(self, monster: dict[str, Any]) -> float:
        return resolve._hd_base_and_bonus(monster.get("hit_dice", "1"))[0]

    def _morale_check(self, monster: dict[str, Any], reason: str) -> resolve.MoraleResult | None:
        result = resolve.morale(self.d, self._hd_base(monster))
        self.state["log"].append(
            f"{monster['name']} checks morale ({reason}): {result.outcome} "
            f"(base {result.base}%, rolled {result.roll})."
        )
        monster["morale_failed"] = not result.passed
        if not result.passed:
            monster["retreating"] = result.outcome == "retreats"
            monster["surrendered"] = result.outcome == "surrenders"
        return result

    def _check_morale(self, monster: dict[str, Any]) -> None:
        if not monster.get("alive", True):
            return
        if monster.get("surrendered") or monster.get("retreating"):
            return

        max_hp = monster.get("max_hp", max(monster.get("hp", 1), 1))

        # 50% HP threshold.
        if not monster.get("morale_checked_50") and monster.get("hp", max_hp) <= max_hp / 2:
            monster["morale_checked_50"] = True
            self._morale_check(monster, "wounded")
            return

        # Falling allies: at least half of the starting monsters are down.
        total = len(self.state.get("monsters", []))
        alive = len(self._living_monsters())
        if not monster.get("morale_checked_falling") and total > 1 and alive <= total / 2:
            monster["morale_checked_falling"] = True
            self._morale_check(monster, "allies falling")

    def _choose_target(self, monster: dict[str, Any]) -> dict[str, Any] | None:
        if monster.get("retreating") or monster.get("surrendered"):
            return None

        # Revenge: go after whoever wounded this monster last.
        wounded_by = monster.get("last_wounded_by")
        if wounded_by:
            avenger = next((p for p in self._living_players() if p["id"] == wounded_by), None)
            if avenger is not None:
                return avenger

        # Cruel monsters prey on the downed if any are reachable.
        if self._is_cruel(monster):
            downed = self._downed_players()
            if downed:
                return self._nearest_player(monster, downed)

        return self._nearest_player(monster)

    def _bfs_next_step(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        avoid_hazards: bool = True,
        prefer_cover: bool = False,
    ) -> tuple[int, int] | None:
        """Return the first tile of a shortest path from ``start`` to ``goal``.

        The goal tile may be occupied (e.g. by the target).  Hazards are
        avoided when possible.  Cover is preferred among equally-good first
        steps using a deterministic tie-breaker.
        """
        if start == goal:
            return None

        def neighbors(pos):
            x, y = pos
            # Deterministic order: north, east, south, west.
            for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                yield x + dx, y + dy

        def search():
            queue: deque[tuple[tuple[int, int], list[tuple[int, int]]]] = deque([(start, [])])
            seen = {start}
            best_paths: list[list[tuple[int, int]]] = []
            while queue:
                pos, path = queue.popleft()
                if pos == goal:
                    if not best_paths or len(path) == len(best_paths[0]):
                        best_paths.append(path)
                    elif len(path) < len(best_paths[0]):
                        best_paths = [path]
                    continue
                for nxt in neighbors(pos):
                    if nxt in seen:
                        continue
                    nx, ny = nxt
                    if not self._walkable_and_free(nx, ny, occupant_ok=goal):
                        continue
                    if avoid_hazards and self._is_hazard(nx, ny):
                        continue
                    seen.add(nxt)
                    queue.append((nxt, path + [nxt]))
            return best_paths

        paths = search()
        if not paths and avoid_hazards:
            paths = search()

        if not paths:
            return None

        if len(paths) == 1:
            return paths[0][0]

        if prefer_cover:
            cover_paths = [p for p in paths if self._has_cover_here(*p[0])]
            if cover_paths:
                paths = cover_paths

        # Deterministic tie-break: prefer north, then east, then south, then west.
        def sort_key(p):
            x, y = p[0]
            sx, sy = start
            if y < sy:
                return 0
            if x > sx:
                return 1
            if y > sy:
                return 2
            return 3

        return sorted(paths, key=sort_key)[0][0]

    def _retreat_step(self, monster: dict[str, Any]) -> tuple[int, int] | None:
        """Move one tile away from the nearest living player, avoiding hazards."""
        nearest = self._nearest_player(monster)
        if nearest is None:
            return None
        start = (monster["x"], monster["y"])
        current_dist = self._distance(monster, nearest)
        candidates: list[tuple[int, int, int]] = []
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            nx, ny = start[0] + dx, start[1] + dy
            if not self._walkable_and_free(nx, ny):
                continue
            if self._is_hazard(nx, ny):
                continue
            dist = abs(nx - nearest["x"]) + abs(ny - nearest["y"])
            if dist > current_dist:
                candidates.append((dist, nx, ny))
        if not candidates:
            # No safe tile increases distance; settle for any safe tile.
            for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                nx, ny = start[0] + dx, start[1] + dy
                if self._walkable_and_free(nx, ny) and not self._is_hazard(nx, ny):
                    candidates.append((0, nx, ny))
        if not candidates:
            return None
        # Pick the tile that increases distance the most; tie-break deterministically.
        candidates.sort(key=lambda t: (-t[0], t[1], t[2]))
        return candidates[0][1], candidates[0][2]

    def _flanking_tile(self, monster: dict[str, Any], target: dict[str, Any]) -> tuple[int, int] | None:
        """Return a free tile opposite an ally of the target, if one exists."""
        for ally in self._living_monsters():
            if ally["id"] == monster["id"]:
                continue
            if self._distance(ally, target) != 1:
                continue
            dx = ally["x"] - target["x"]
            dy = ally["y"] - target["y"]
            opp_x = target["x"] - dx
            opp_y = target["y"] - dy
            if self._walkable_and_free(opp_x, opp_y):
                return opp_x, opp_y
        return None

    def _adjacent(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"]) == 1

    def _in_ranged_range(self, attacker: dict[str, Any], target: dict[str, Any]) -> bool:
        return self._distance(attacker, target) <= RANGED_RANGE

    async def _act(self, monster: dict[str, Any]) -> None:
        if not monster.get("alive", True):
            return
        if monster.get("surrendered"):
            self.events.append(f"{monster['name']} surrenders.")
            return

        self._check_morale(monster)

        if monster.get("retreating"):
            step = self._retreat_step(monster)
            if step is not None:
                await self.cb.move(monster, step[0], step[1])
                self.events.append(f"{monster['name']} retreats.")
            else:
                self.events.append(f"{monster['name']} holds its ground, looking for an escape.")
            return

        target = self._choose_target(monster)
        if target is None:
            return

        # Flank if an ally is already engaged on the far side.
        flank_tile = self._flanking_tile(monster, target)
        moved = False
        if not self._adjacent(monster, target):
            goal = (target["x"], target["y"])
            if flank_tile is not None and not self._adjacent({"x": flank_tile[0], "y": flank_tile[1]}, target):
                # Safety: a flanking tile must be adjacent to the target.
                flank_tile = None
            if flank_tile is not None:
                goal = flank_tile
            prefer_cover = monster.get("ranged_damage") is not None or self._in_ranged_range(monster, target)
            step = self._bfs_next_step(
                (monster["x"], monster["y"]),
                goal,
                avoid_hazards=True,
                prefer_cover=prefer_cover,
            )
            if step is not None:
                await self.cb.move(monster, step[0], step[1])
                moved = True
                self.events.append(f"{monster['name']} moves toward {target['name']}.")

        # If adjacent, prefer melee; otherwise try ranged.
        if self._adjacent(monster, target):
            await self.cb.attack(monster, target)
            self.events.append(f"{monster['name']} attacks {target['name']}.")
        elif self._in_ranged_range(monster, target) and self.cb.line_of_sight(
            monster["x"], monster["y"], target["x"], target["y"]
        ):
            # Default ranged damage for monsters without an explicit missile weapon.
            if "ranged_damage" not in monster:
                monster["ranged_damage"] = monster.get("damage", "1d6")
            await self.cb.ranged_attack(monster, target)
            self.events.append(f"{monster['name']} shoots {target['name']}.")
        elif moved:
            # Already logged move.
            pass
        else:
            self.events.append(f"{monster['name']} hesitates, unable to reach {target['name']}.")

    async def take_turn(self) -> list[str]:
        for monster in list(self.state.get("monsters", [])):
            if self.state.get("status") != "active":
                break
            await self._act(monster)
        return self.events
