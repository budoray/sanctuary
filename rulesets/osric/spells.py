"""OSRIC spell definitions and resolution.

Spell data is loaded from YAML so it can be modded without touching code.
"""
from __future__ import annotations

from engine.dice import roll_expression
from rulesets.osric import combat as osric_combat
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
    target: dict | None = None,
    roll_save: int | None = None,
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
        "saving_throw": None,
        "condition": None,
        "duration": spell.get("duration"),
    }

    save_key = spell.get("saving_throw")
    saving_throw_result = None
    if save_key:
        target_number = spell.get("save_target")
        if target_number is None and target is not None:
            target_number = target.get("sheet", {}).get("saving_throws", {}).get(save_key)
        if target_number is None:
            target_number = 15
        save_roll = roll_save if roll_save is not None else osric_combat._roll_d20()
        success = save_roll >= target_number
        saving_throw_result = {
            "key": save_key,
            "target": target_number,
            "roll": save_roll,
            "success": success,
        }
        result["saving_throw"] = saving_throw_result

    apply_effect = saving_throw_result is None or not saving_throw_result["success"]
    half_on_save = spell.get("half_on_save", False)
    if saving_throw_result and saving_throw_result["success"] and half_on_save:
        apply_effect = True
        result["saved"] = True
    elif saving_throw_result:
        result["saved"] = False

    if apply_effect:
        if spell.get("heal"):
            rolled = roll_expression(str(spell["heal"]))
            result["heal"] = rolled["total"]
            result["heal_die"] = spell["heal"]
        if spell.get("damage"):
            rolled = roll_expression(str(spell["damage"]))
            result["damage"] = rolled["total"]
            result["damage_die"] = spell["damage"]
            if saving_throw_result and saving_throw_result["success"] and half_on_save:
                result["damage"] = max(1, result["damage"] // 2)

        if spell.get("condition"):
            result["condition"] = spell["condition"]
    else:
        result["hit"] = False

    return result
