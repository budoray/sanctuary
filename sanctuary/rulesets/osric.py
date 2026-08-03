"""The OSRIC 3.0 pack: the rules this game was born playing, behind the
ruleset seam so the engine no longer knows whose rules it runs.

Every mechanic delegates to the existing, fully-tested modules -
`sanctuary.character` for chargen, `sanctuary.resolve` for combat - so the
pack changes NOTHING about how OSRIC plays; it only changes WHO the engine
asks. The manifest (`data/rulesets/osric/ruleset.yaml`) carries the data;
this adapter carries the arithmetic, because real systems need real code
(exceptional strength, the ranger's two first-level hit dice, multiclass
division are not YAML-shaped).
"""
from pathlib import Path

import yaml

from sanctuary import character, resolve

_ROOT = Path(__file__).resolve().parent.parent.parent


class OsricPack:
    """`ruleset.Ruleset` over the OSRIC corpus in data/."""

    def __init__(self, manifest_path: Path):
        m = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        self.id = m["id"]
        self.name = m["name"]
        self.title = m["title"]
        self.version = str(m["version"])
        self.licence_notice = m["licence_notice"].replace("\n", " ").strip()
        self.abilities = tuple(m["abilities"])
        self.save_heading = m["save_heading"]
        self.default_damage_expr = m["default_damage_expr"]
        self._gen_modes = list(m["gen_modes"])
        self._selected_class = m["selected_class"]
        self._portraits = yaml.safe_load(
            (_ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))["portraits"]

    # -- chargen -------------------------------------------------------
    def gen_modes(self) -> list[dict]:
        return [dict(mode) for mode in self._gen_modes]

    def ancestry_names(self) -> list[str]:
        return list(character.ANCESTRIES)

    def class_names(self) -> list[str]:
        return list(character.CLASSES)

    def ancestry_allowed_classes(self, ancestry: str) -> list[str]:
        return list(character.ancestry(ancestry)["allowed_classes"])

    def portrait_for(self, class_name: str) -> str:
        return self._portraits.get(class_name, self._portraits["default"])

    def roll_abilities(self, dice, mode: str) -> dict:
        return character.roll_abilities(dice, mode)

    def arrangeable(self, mode: str) -> bool:
        return character.arrangeable(mode)

    def generate(self, **kwargs):
        return character.generate(**kwargs)

    # -- combat --------------------------------------------------------
    def attack(self, dice, attacker, target_ac: int, damage_expr: str):
        return resolve.attack(dice, attacker, target_ac, damage_expr=damage_expr)

    def morale(self, dice, hit_dice: float):
        return resolve.morale(dice, hit_dice=hit_dice)

    # -- presentation --------------------------------------------------
    def vitals_line(self, c) -> str:
        hit = c.modifiers["hit"]
        dmg = c.modifiers["damage"]
        return (f"{c.hit_points} hp · AC {c.armour_class} · "
                f"to hit {'+' if hit >= 0 else ''}{hit} · "
                f"damage {'+' if dmg >= 0 else ''}{dmg} · seed {c.seed}")

    @staticmethod
    def _label(value: str) -> str:
        """`magic-user` -> `Magic-User` - the tile's display name."""
        return "-".join(w.capitalize() for w in value.split("-"))

    def client_manifest(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "licence_notice": self.licence_notice,
            "abilities": list(self.abilities),
            "save_heading": self.save_heading,
            "gen_modes": self.gen_modes(),
            "ancestries": self.ancestry_names(),
            "classes": [
                {"value": c, "label": self._label(c), "portrait": self.portrait_for(c),
                 "selected": c == self._selected_class}
                for c in self.class_names()
            ],
        }
