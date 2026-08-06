"""Seeded dice with an append-only roll log.

Every die rolled anywhere in Sanctuary comes from here. Same seed plus the same
call sequence produces a byte-identical log, which is what makes a generator
property testable, a bug report reproducible from its seed, and the game
auditable to a player who suspects the dice.

This module imports nothing else from Sanctuary. Nothing else may import
`random`.
"""
import random
import re
from dataclasses import dataclass, field

# NdM, optional dL (drop L lowest), optional +X / -X
_EXPR = re.compile(r"^(\d+)d(\d+)(?:d(\d+))?([+-]\d+)?$")


def parse_expr(expr: str) -> tuple[int, int, int, int]:
    """Parse a dice expression into (count, faces, drop_lowest, modifier)."""
    m = _EXPR.match((expr or "").strip().replace(" ", ""))
    if not m:
        raise ValueError(f"bad dice expression: {expr!r}")
    count = int(m.group(1))
    faces = int(m.group(2))
    drop = int(m.group(3) or 0)
    mods = int(m.group(4) or 0)
    if count < 1:
        raise ValueError(f"need at least one die: {expr!r}")
    if faces < 2:
        raise ValueError(f"a die needs at least two faces: {expr!r}")
    if drop >= count:
        raise ValueError(f"cannot drop {drop} of {count} dice: {expr!r}")
    return count, faces, drop, mods


@dataclass(frozen=True)
class Roll:
    """One roll, with the arithmetic that produced it.

    `faces` is every die as it landed; `kept` is what counted after any drop.
    The client renders the reasoning, not just the number.
    """
    index: int
    expr: str
    faces: tuple[int, ...]
    kept: tuple[int, ...]
    mods: int
    total: int
    reason: str = ""
    tags: dict = field(default_factory=dict)


class Dice:
    """A seeded roller with an append-only log.

    One instance per session. `log` is exposed as a tuple so a caller cannot
    append to it behind the engine's back.
    """

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self._log: list[Roll] = []

    @property
    def log(self) -> tuple[Roll, ...]:
        return tuple(self._log)

    def roll(self, expr: str, reason: str = "", mods: int = 0, **tags) -> Roll:
        """Roll `expr`, record it, return the record."""
        count, faces_n, drop, expr_mods = parse_expr(expr)
        faces = tuple(self._rng.randint(1, faces_n) for _ in range(count))
        kept = tuple(sorted(faces)[drop:]) if drop else faces
        total_mods = expr_mods + int(mods)
        roll = Roll(
            index=len(self._log),
            expr=expr,
            faces=faces,
            kept=kept,
            mods=total_mods,
            total=sum(kept) + total_mods,
            reason=reason,
            tags=dict(tags),
        )
        self._log.append(roll)
        return roll
