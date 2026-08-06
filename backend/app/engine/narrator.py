"""DM narration with optional Ollama-powered prose.

The ``Narrator`` tries a local Ollama model first for vivid, varied
 descriptions and silently falls back to the built-in template pools when
 Ollama is disabled, unreachable, or slow.
"""
from __future__ import annotations

import random
from typing import Any, Awaitable, Callable

from backend.app.ai import ollama
from backend.app.config import SETTINGS, Settings

_OPENING = [
    "The dungeon is silent, save for dripping water.",
    "Torchlight flickers across the damp stone walls.",
    "A cold draft carries the smell of rot from somewhere ahead.",
    "The silence is broken only by the snap of your torch.",
]

_MOVE_SELF = [
    "You step carefully across the flagstones.",
    "Your boots scrape softly against the floor.",
    "You shift position, eyes fixed on the enemy.",
    "You move with purpose across the chamber.",
]

_MOVE_ENEMY = [
    "{name} scurries closer, blade ready.",
    "{name} darts to a new position with a snarl.",
    "{name} shuffles forward, beady eyes locked on you.",
    "{name} circles, looking for an opening.",
]

_HIT_SELF = [
    "Your blow lands true.",
    "You strike with grim determination.",
    "Steel meets flesh.",
    "You find your mark.",
]

_HIT_ENEMY = [
    "{name}'s weapon bites into you.",
    "{name} lands a stinging blow.",
    "Pain lances through you as {name} strikes.",
    "{name}'s attack finds a gap in your guard.",
]

_MISS_SELF = [
    "Your swing cuts only air.",
    "You overextend and miss.",
    "The blow glances harmlessly aside.",
    "Your attack is parried at the last moment.",
]

_MISS_ENEMY = [
    "{name} lunges but you deflect the blow.",
    "{name} swings wild and misses.",
    "You duck under {name}'s clumsy strike.",
    "{name} snaps at you but finds nothing.",
]

_KILL = [
    "{name} crumples to the ground, still.",
    "{name} lets out a final gasp and falls.",
    "{name} collapses in a heap.",
    "{name} dies at your feet.",
]

_PLAYER_FALL = [
    "You fall, the world fading to black.",
    "Darkness takes you.",
    "Your strength fails and you crumple to the stone.",
]

_VICTORY = [
    "The chamber grows quiet. You stand victorious.",
    "The threat is ended. For now.",
    "You wipe your blade clean and catch your breath.",
]

_SYSTEM = (
    "You are a terse old-school fantasy dungeon master. "
    "Reply with one or two vivid sentences. No lists, no rules, no signatures."
)


def _pick(pool: list[str], rng: random.Random) -> str:
    return rng.choice(pool)


def _template_move(token: dict[str, Any], rng: random.Random | None) -> str | None:
    if token.get("type") == "player":
        return _pick(_MOVE_SELF, rng or random.Random())
    return _pick(_MOVE_ENEMY, rng or random.Random()).format(name=token["name"])


def _template_attack(
    attacker: dict[str, Any],
    target: dict[str, Any],
    hit: bool,
    fatal: bool,
    rng: random.Random | None,
) -> list[str]:
    rng = rng or random.Random()
    out: list[str] = []
    if attacker.get("type") == "player":
        if hit:
            out.append(_pick(_HIT_SELF, rng))
        else:
            out.append(_pick(_MISS_SELF, rng))
    else:
        if hit:
            out.append(_pick(_HIT_ENEMY, rng).format(name=attacker["name"]))
        else:
            out.append(_pick(_MISS_ENEMY, rng).format(name=attacker["name"]))

    if fatal:
        if target.get("type") == "player":
            out.append(_pick(_PLAYER_FALL, rng))
        else:
            out.append(_pick(_KILL, rng).format(name=target["name"]))
    return out


class Narrator:
    """Produces combat and movement descriptions, preferring Ollama when available."""

    def __init__(
        self,
        settings: Settings | None = None,
        ollama_generate: Callable[..., Awaitable[str | None]] | None = None,
    ):
        self.settings = settings or SETTINGS
        self.ollama_generate: Callable[..., Awaitable[str | None]] = (
            ollama_generate or ollama.generate
        )

    async def _ollama(self, prompt: str, system: str | None = None) -> str | None:
        if not self.settings.ollama_enabled:
            return None
        return await self.ollama_generate(
            prompt,
            system=system or _SYSTEM,
            timeout=self.settings.ollama_timeout,
        )

    async def narrate_opening(self, rng: random.Random | None = None) -> str:
        prompt = (
            "Set the scene: a lone adventurer steps into a torch-lit dungeon "
            "chamber where danger waits. Keep it under 30 words."
        )
        return (await self._ollama(prompt)) or _pick(
            _OPENING, rng or random.Random()
        )

    async def narrate_move(
        self, token: dict[str, Any], rng: random.Random | None = None
    ) -> str | None:
        if token.get("type") == "player":
            prompt = "Describe the adventurer moving cautiously across damp stone in one vivid sentence."
        else:
            prompt = (
                f"Describe {token.get('name', 'the creature')} scurrying to a "
                "new position in one vivid sentence."
            )
        return (await self._ollama(prompt)) or _template_move(token, rng)

    async def narrate_attack(
        self,
        attacker: dict[str, Any],
        target: dict[str, Any],
        hit: bool,
        fatal: bool,
        rng: random.Random | None = None,
    ) -> list[str]:
        attacker_name = attacker.get("name", "the attacker")
        target_name = target.get("name", "the target")
        if attacker.get("type") == "player":
            verb = "strikes" if hit else "misses"
            prompt = (
                f"The adventurer {verb} {target_name}. "
                f"{'The blow is fatal.' if fatal else ''} One vivid sentence."
            )
        else:
            verb = "hits" if hit else "misses"
            prompt = (
                f"{attacker_name} {verb} the adventurer. "
                f"{'The blow is fatal.' if fatal else ''} One vivid sentence."
            )
        result = await self._ollama(prompt)
        if result:
            return [result]
        return _template_attack(attacker, target, hit, fatal, rng)

    async def narrate_victory(self, rng: random.Random | None = None) -> str:
        prompt = (
            "The last enemy falls. Describe the brief, grim quiet after the "
            "fight in one sentence."
        )
        return (await self._ollama(prompt)) or _pick(
            _VICTORY, rng or random.Random()
        )
