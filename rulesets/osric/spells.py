"""OSRIC spell definitions and resolution.

Spell data is loaded from YAML so it can be modded without touching code.
"""
from __future__ import annotations

from engine.dice import roll_expression
from rulesets.osric import loader


SPELLS: dict[str, dict] = loader.load_spells("spells.yaml") or {}
CLASS_SPELLS_RAW: dict[str, list[str]] = loader.load_spells("class_spells.yaml") or {}

# Resolve spell ids into full spell dicts.
CLASS_SPELLS: dict[str, list[dict]] = {
    class_id: [SPELLS[sid] for sid in spell_ids if sid in SPELLS]
    for class_id, spell_ids in CLASS_SPELLS_RAW.items()
}


def class_spells(class_id: str) -> list[dict]:
    return list(CLASS_SPELLS.get(class_id, []))


def initial_spell_slots(class_id: str) -> dict[str, int]:
    """First-level spell slots for casters; empty for non-casters."""
    if class_id in CLASS_SPELLS:
        return {"1": 1}
    return {}


def resolve_spell(
    caster: dict,
    spell_id: str,
) -> dict:
    """Resolve a spell cast by caster. Returns a result dict."""
    spell = SPELLS.get(spell_id)
    if not spell:
        raise ValueError(f"Unknown spell: {spell_id}")

    result = {
        "caster": caster.get("name"),
        "spell": spell["name"],
        "damage": 0,
        "heal": 0,
        "hit": True,
    }

    if spell.get("heal"):
        result["heal"] = roll_expression(spell["heal"])["total"]
    elif spell.get("damage"):
        result["damage"] = roll_expression(spell["damage"])["total"]

    return result
