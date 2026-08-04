"""OSRIC character model and helpers."""
import random
from dataclasses import dataclass, field
from typing import Any


ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]


def roll_3d6() -> int:
    return sum(random.randint(1, 6) for _ in range(3))


def ability_mod(score: int) -> int:
    if score >= 16:
        return 2
    if score <= 7:
        return -1
    if score <= 5:
        return -2
    return 0


@dataclass
class Character:
    id: str
    account_id: int
    name: str
    race: str
    class_: str
    level: int = 1
    hp: int = 0
    max_hp: int = 0
    ac: int = 10
    abilities: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.abilities:
            self.abilities = {a: roll_3d6() for a in ABILITIES}
        if self.max_hp == 0:
            self.max_hp = max(1, random.randint(1, 8) + ability_mod(self.abilities.get("con", 10)))
        if self.hp == 0:
            self.hp = self.max_hp
        self.ac = 10 + ability_mod(self.abilities.get("dex", 10))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "name": self.name,
            "race": self.race,
            "class": self.class_,
            "level": self.level,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
            "abilities": self.abilities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Character":
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            name=data["name"],
            race=data["race"],
            class_=data["class"],
            level=data.get("level", 1),
            hp=data.get("hp", 0),
            max_hp=data.get("max_hp", 0),
            ac=data.get("ac", 10),
            abilities=data.get("abilities", {}),
        )


def make_character(account_id: int, name: str, race: str = "Human", class_: str = "Fighter") -> Character:
    return Character(
        id="",
        account_id=account_id,
        name=name,
        race=race,
        class_=class_,
    )
