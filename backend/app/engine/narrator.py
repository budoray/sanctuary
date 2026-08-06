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

_RANGED_HIT_SELF = [
    "Your shot finds its mark.",
    "The missile strikes true.",
    "You loose a well-aimed shot.",
    "Your projectile bites into the foe.",
]

_RANGED_MISS_SELF = [
    "Your shot goes wide.",
    "The missile whistles past your target.",
    "You fire but miss.",
    "Your aim is off by inches.",
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

_ROOM = [
    "A damp chamber stretches before you, its corners lost in shadow.",
    "Cracked flagstones and crumbling pillars hint at forgotten grandeur.",
    "The air is thick with dust and the smell of old stone.",
    "Flickering torchlight reveals a room heavy with silence.",
    "Water drips somewhere in the dark, counting the seconds.",
]

_TRAP_DISCOVERED = [
    "A suspicious groove in the floor betrays a hidden mechanism.",
    "You notice a thin wire glinting in the torchlight.",
    "The stones here are slightly misaligned—something lies beneath.",
    "A faint click echoes from underfoot as you shift your weight.",
]

_TRAP_TRIGGERED = [
    "A hidden trap springs with a sharp snap.",
    "Spikes lance up from the floor without warning.",
    "A weighted blade swings down from the ceiling.",
    "The floor gives way just enough to bite into flesh.",
]

_HAZARD_LAVA = [
    "Searing lava bites at {name}.",
    "Molten stone sears {name}'s flesh.",
    "The lava hisses as it touches {name}.",
]

_HAZARD_SPIKES = [
    "Jagged spikes leap up beneath {name}.",
    "Rusted spikes pierce {name}.",
    "The floor bites {name} with iron teeth.",
]

_HAZARD_GENERIC = [
    "The hazard claims its due from {name}.",
    "Perilous stone catches {name}.",
]

_BANTER = [
    "The crowd roars, hungry for blood.",
    "A harsh voice calls for a proper kill.",
    "Dust and jeers fill the air.",
    "Somewhere, a gate grinds open.",
]

_PHASE = [
    "{name} falters, then surges with renewed fury!",
    "Wounded, {name} calls forth more shadows to its aid.",
    "{name}'s form shifts; the fight just got uglier.",
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


def _template_ranged_attack(
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
            out.append(_pick(_RANGED_HIT_SELF, rng))
        else:
            out.append(_pick(_RANGED_MISS_SELF, rng))
    else:
        # Monster ranged attacks reuse melee enemy templates for now.
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

    def _party_status_summary(
        self, attacker: dict[str, Any], target: dict[str, Any]
    ) -> str:
        """Short combat context for prompts: who is hurt and how badly."""
        tokens = [attacker, target]
        summaries: list[str] = []
        for t in tokens:
            hp = t.get("hp", 0)
            max_hp = t.get("max_hp", hp or 1)
            ratio = hp / max_hp if max_hp else 1
            if ratio <= 0.25 and hp > 0:
                summaries.append(f"{t.get('name', 'someone')} is bloodied")
            elif hp <= 0 and t.get("alive", True):
                summaries.append(f"{t.get('name', 'someone')} has fallen")
        return f"{' ; '.join(summaries)}." if summaries else ""

    async def narrate_opening(
        self, rng: random.Random | None = None, module: str = "", mode: str = "campaign"
    ) -> str:
        mode_hint = "an arena pit" if mode == "arena" else "a torch-lit dungeon"
        quest_hook = f"in '{module}'" if module else "where danger waits"
        prompt = (
            f"Set the scene: a lone adventurer steps into {mode_hint} "
            f"{quest_hook}. Mention a rumour or goal in one sentence. Keep it under 35 words."
        )
        return (await self._ollama(prompt)) or _pick(
            _OPENING, rng or random.Random()
        )

    async def narrate_room(
        self, module_name: str, room_type: str | None = None, rng: random.Random | None = None
    ) -> str:
        """Describe a room or area when the party first enters it."""
        kind = room_type or "chamber"
        prompt = (
            f"Describe the adventurers entering a {kind} in '{module_name}' "
            "in one vivid sentence. Mention the atmosphere and any obvious threat. Keep it under 25 words."
        )
        return (await self._ollama(prompt)) or _pick(_ROOM, rng or random.Random())

    async def narrate_trap(
        self, name: str, triggered: bool = True, rng: random.Random | None = None
    ) -> str:
        """Describe a trap being discovered or triggered."""
        prompt = (
            f"Describe {name} being {'triggered' if triggered else 'discovered'} "
            "in one vivid sentence. Keep it under 25 words."
        )
        pool = _TRAP_TRIGGERED if triggered else _TRAP_DISCOVERED
        return (await self._ollama(prompt)) or _pick(pool, rng or random.Random())

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
        target_species = target.get("name", "foe")
        party_status = self._party_status_summary(attacker, target)
        if attacker.get("type") == "player":
            verb = "strikes" if hit else "misses"
            prompt = (
                f"The adventurer {verb} the {target_species}. {party_status} "
                f"{'The blow is fatal.' if fatal else ''} One vivid sentence."
            )
        else:
            verb = "hits" if hit else "misses"
            prompt = (
                f"The {attacker_name} {verb} the adventurer. {party_status} "
                f"{'The blow is fatal.' if fatal else ''} One vivid sentence."
            )
        result = await self._ollama(prompt)
        if result:
            return [result]
        return _template_attack(attacker, target, hit, fatal, rng)

    async def narrate_ranged_attack(
        self,
        attacker: dict[str, Any],
        target: dict[str, Any],
        hit: bool,
        fatal: bool,
        rng: random.Random | None = None,
    ) -> list[str]:
        attacker_name = attacker.get("name", "the attacker")
        target_name = target.get("name", "the target")
        target_species = target.get("name", "foe")
        party_status = self._party_status_summary(attacker, target)
        if attacker.get("type") == "player":
            verb = "hits" if hit else "misses"
            prompt = (
                f"The adventurer fires a missile and {verb} the {target_species}. {party_status} "
                f"{'The shot is fatal.' if fatal else ''} One vivid sentence."
            )
        else:
            verb = "hits" if hit else "misses"
            prompt = (
                f"The {attacker_name} fires a missile and {verb} the adventurer. {party_status} "
                f"{'The shot is fatal.' if fatal else ''} One vivid sentence."
            )
        result = await self._ollama(prompt)
        if result:
            return [result]
        return _template_ranged_attack(attacker, target, hit, fatal, rng)

    async def narrate_victory(
        self, rng: random.Random | None = None, module: str = ""
    ) -> str:
        hook = f" in {module}" if module else ""
        prompt = (
            "The last enemy falls. Describe the brief, grim quiet after the "
            f"fight{hook} and hint at what might come next in one sentence."
        )
        return (await self._ollama(prompt)) or _pick(
            _VICTORY, rng or random.Random()
        )

    async def narrate_banter(
        self, room_type: str | None = None, rng: random.Random | None = None
    ) -> str:
        """Arena crowd or environmental commentary."""
        prompt = (
            "Describe the reaction of an unseen arena crowd or the environment "
            "in one terse sentence. Keep it under 20 words."
        )
        return (await self._ollama(prompt)) or _pick(_BANTER, rng or random.Random())

    async def narrate_hazard(
        self,
        hazard_name: str,
        victim_name: str,
        rng: random.Random | None = None,
    ) -> str:
        """Describe a hazard hurting someone."""
        prompt = (
            f"Describe {hazard_name} harming {victim_name} in one vivid sentence. "
            "Keep it under 20 words."
        )
        result = await self._ollama(prompt)
        if result:
            return result
        lowered = hazard_name.lower()
        if "lava" in lowered:
            pool = _HAZARD_LAVA
        elif "spike" in lowered:
            pool = _HAZARD_SPIKES
        else:
            pool = _HAZARD_GENERIC
        return _pick(pool, rng or random.Random()).format(name=victim_name)

    async def narrate_phase_transition(
        self, boss_name: str, phase: dict[str, Any], rng: random.Random | None = None
    ) -> str:
        """Describe a boss entering a new combat phase."""
        prompt = (
            f"Describe {boss_name} transforming or rallying into a deadlier phase "
            "in one vivid sentence. Keep it under 25 words."
        )
        return (await self._ollama(prompt)) or _pick(
            _PHASE, rng or random.Random()
        ).format(name=boss_name)

    async def narrate_dm_turn(
        self, events: list[str], rng: random.Random | None = None
    ) -> str | None:
        """Summarise a full DM turn in one or two sentences."""
        if not events:
            return None
        prompt = (
            "As a terse old-school fantasy dungeon master, summarise these "
            "foes' actions in one or two vivid sentences. No lists, no rules.\n\n"
            + "\n".join(f"- {e}" for e in events)
        )
        return (await self._ollama(prompt)) or " ".join(events)
