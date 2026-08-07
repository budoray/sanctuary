"""OSRIC ruleset adapter."""
from backend.app.rulesets.base import Ruleset


class OSRICRuleset(Ruleset):
    # Player-facing generation modes (OSRIC 3.0 Player Guide §1.1).
    GEN_MODES = ("hardest", "difficult", "normal", "flexible")

    # Classes eligible for percentile (exceptional) strength.
    EXCEPTIONAL_CLASSES = ("fighter", "paladin", "ranger")

    @property
    def ABILITIES(self) -> tuple[str, ...]:
        return tuple(self.abilities)

    @property
    def ANCESTRIES(self) -> tuple[str, ...]:
        return tuple(self.load_yaml("ancestries").keys())

    @property
    def CLASSES(self) -> tuple[str, ...]:
        return tuple(self.load_yaml("classes").keys())

    def ancestry(self, name: str) -> dict:
        """OSRIC 3.0 §1.2.1-1.2.7: one ancestry's adjustments, limits and class access."""
        data = self.load_yaml("ancestries")
        a = data.get(name)
        if a is None:
            raise KeyError(f"unknown ancestry: {name!r}")
        return a

    def game_class(self, name: str) -> dict:
        """OSRIC 3.0 §1.3.1-1.3.10: one class's requirements, hit die and tables."""
        data = self.load_yaml("classes")
        c = data.get(name)
        if c is None:
            raise KeyError(f"unknown class: {name!r}")
        return c

    def eligible_classes(self, scores: dict, ancestry_name: str) -> list[str]:
        """Classes this character may take: allowed by ancestry AND meeting the
        class's own ability minimums."""
        allowed = set(self.ancestry(ancestry_name)["allowed_classes"])
        out = []
        for name in self.CLASSES:
            if name not in allowed:
                continue
            if any(scores.get(k, 0) < v for k, v in self.game_class(name)["minimums"].items()):
                continue
            out.append(name)
        return out

    def list_monsters(self) -> list[str]:
        """Return available monster ids by scanning the monsters directory."""
        return super().list_monsters()

    def validate_action(self, session, actor, action):
        # Stub: permit all movement within bounds for the first slice.
        if action.get("type") == "move":
            x = action.get("x", 0)
            y = action.get("y", 0)
            if 0 <= x < session.map.width and 0 <= y < session.map.height:
                return {"ok": True}
            return {"ok": False, "reason": "Out of bounds"}
        return {"ok": True}
