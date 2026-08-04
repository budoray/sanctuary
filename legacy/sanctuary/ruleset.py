"""The ruleset seam: one protocol, one registry.

A RULESET is a pack of rules the engine can play: a manifest in
`data/rulesets/<id>/ruleset.yaml` plus a Python adapter implementing the
surface below. OSRIC 3.0 ships as the first pack; the engine never calls
`sanctuary.character` or `sanctuary.resolve` directly at play time - it
calls the loaded pack, so another system can be plugged in by name
(`SANCTUARY_RULESET`) without an engine change.

The protocol is deliberately SMALL: only what the runtime, the session
driver, the API and the client actually call. Anything a pack needs beyond
it (OSRIC's turn-undead matrix, say) stays inside that pack's adapter -
the seam is what a delve cannot run without, not every rule ever written.

This module imports nothing of ours: it is the root the packs hang from,
and the dependency-chain invariant walks every top-level module.
"""
from pathlib import Path
from typing import Any, Protocol

PACKS_DIR = Path(__file__).resolve().parent.parent / "data" / "rulesets"


class Ruleset(Protocol):
    """What a pack must provide for the table to run.

    Manifest/branding attributes are plain data; everything else is a
    callable. `generate` returns the engine's shared Character record -
    its `scores`/`saves`/`modifiers` dicts are open, so a pack fills them
    with its own abilities, categories and modifier keys.
    """

    id: str
    name: str
    title: str
    version: str
    licence_notice: str
    abilities: tuple[str, ...]
    save_heading: str
    default_damage_expr: str

    def gen_modes(self) -> list[dict]:
        """Chargen modes as `{value, label}` dicts; at most one `selected`."""
        ...

    def ancestry_names(self) -> list[str]: ...
    def class_names(self) -> list[str]: ...
    def ancestry_allowed_classes(self, ancestry: str) -> list[str]: ...
    def portrait_for(self, class_name: str) -> str: ...

    def roll_abilities(self, dice: Any, mode: str) -> dict: ...
    def arrangeable(self, mode: str) -> bool: ...
    def generate(self, *, seed: int, mode: str, ancestry_name: str,
                 class_names, name: str = "", arrangement: dict | None = None) -> Any: ...

    def attack(self, dice: Any, attacker: Any, target_ac: int,
               damage_expr: str) -> Any:
        """One attack. `attacker` is a Character or a monster's hit-dice
        notation - the pack decides what that means."""
        ...

    def morale(self, dice: Any, hit_dice: float) -> Any:
        """A morale check with at least `.passed` and `.outcome`."""
        ...

    def vitals_line(self, character: Any) -> str:
        """The sheet's one-line summary of the character's numbers."""
        ...

    def client_manifest(self) -> dict:
        """Everything the browser forge needs to build itself from the
        pack: modes, ancestries, classes with portrait URLs, headings,
        title and licence."""
        ...


# --------------------------------------------------------------------
# Registry. `sanctuary.rulesets` registers the packs that ship with the
# game at import; tests (and later, third-party packs) may register more.
# --------------------------------------------------------------------

_FACTORIES: dict[str, Any] = {}
_INSTANCES: dict[str, Ruleset] = {}


def register(name: str, factory) -> None:
    """Register `factory(manifest_path: Path) -> Ruleset` under `name`."""
    _FACTORIES[name] = factory
    _INSTANCES.pop(name, None)


def load(name: str) -> Ruleset:
    """The pack named `name`, built once and cached. Unknown names fail
    loudly - a misspelt ruleset must never silently play by other rules."""
    if name not in _FACTORIES:
        raise KeyError(
            f"no ruleset pack named {name!r} - registered: "
            f"{', '.join(sorted(_FACTORIES)) or '(none)'}")
    if name not in _INSTANCES:
        _INSTANCES[name] = _FACTORIES[name](PACKS_DIR / name / "ruleset.yaml")
    return _INSTANCES[name]


def registered() -> list[str]:
    return sorted(_FACTORIES)
