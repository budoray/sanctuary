"""OSRIC ruleset adapter."""
from backend.app.rulesets.base import Ruleset


class OSRICRuleset(Ruleset):
    def validate_action(self, session, actor, action):
        # Stub: permit all movement within bounds for the first slice.
        if action.get("type") == "move":
            x = action.get("x", 0)
            y = action.get("y", 0)
            if 0 <= x < session.map.width and 0 <= y < session.map.height:
                return {"ok": True}
            return {"ok": False, "reason": "Out of bounds"}
        return {"ok": True}
