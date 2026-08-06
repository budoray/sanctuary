"""Template-based DM narration.

Produces varied combat and movement descriptions. Designed so an LLM backend
(Ollama, etc.) can be swapped in later without changing the call sites.
"""
import random
from typing import Any


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


def _pick(pool: list[str], rng: random.Random) -> str:
    return rng.choice(pool)


def narrate_opening(rng: random.Random | None = None) -> str:
    return _pick(_OPENING, rng or random.Random())


def narrate_move(token: dict[str, Any], rng: random.Random | None = None) -> str | None:
    rng = rng or random.Random()
    if token.get("type") == "player":
        return _pick(_MOVE_SELF, rng)
    return _pick(_MOVE_ENEMY, rng).format(name=token["name"])


def narrate_attack(
    attacker: dict[str, Any],
    target: dict[str, Any],
    hit: bool,
    fatal: bool,
    rng: random.Random | None = None,
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


def narrate_victory(rng: random.Random | None = None) -> str:
    return _pick(_VICTORY, rng or random.Random())
