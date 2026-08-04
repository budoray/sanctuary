"""AI / human DM controller."""
import json
import random
from typing import Any

import httpx

from backend.app.config import SETTINGS


class DMController:
    """Pluggable DM. Defaults to Ollama locally; falls back to a simple rule DM."""

    async def take_turn(self, session) -> dict[str, Any]:
        """Return a DM turn result: {token_id, x, y, narration, attack?, damage?}."""
        player = session.player_token()
        enemies = session.dm_tokens()
        if not player or not enemies:
            return {"narration": "The chamber is still."}

        # Simple AI: move the closest enemy one tile toward the player.
        target = min(enemies, key=lambda e: abs(e.x - player.x) + abs(e.y - player.y))
        distance = abs(target.x - player.x) + abs(target.y - player.y)

        result: dict[str, Any] = {"token_id": target.id}

        if distance == 1:
            # Attack the player.
            damage = max(1, random.randint(1, 4))
            player.hp = max(0, player.hp - damage)
            result["attack"] = {"target_id": player.id, "damage": damage, "hit": True}
            result["narration"] = await self.narrate({
                "event": f"{target.name} attacks {player.name} for {damage} damage.",
                "session": session.to_dict(),
            })
            return result

        # Use A* pathfinding to chase the player around walls and doors.
        path = session.map.pathfind(target.x, target.y, player.x, player.y)
        if path:
            new_x, new_y = path[0]
            # Do not step onto another token unless it's the player.
            occupant = session.map.token_at(new_x, new_y)
            if occupant and occupant.id != player.id:
                new_x, new_y = target.x, target.y
            result["x"] = new_x
            result["y"] = new_y
            context = {
                "event": f"{target.name} moves toward {player.name}.",
                "session": session.to_dict(),
            }
            result["narration"] = await self.narrate(context)
            return result

        result["narration"] = await self.narrate({
            "event": f"{target.name} snarls but cannot reach {player.name}.",
            "session": session.to_dict(),
        })
        return result

    async def narrate(self, context: dict[str, Any]) -> str:
        if SETTINGS.app_env == "test":
            return self._fallback(context)
        try:
            return await self._ollama(context)
        except Exception:
            return self._fallback(context)

    async def _ollama(self, context: dict[str, Any]) -> str:
        prompt = self._build_prompt(context)
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                f"{SETTINGS.ollama_host}/api/generate",
                json={
                    "model": SETTINGS.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip() or self._fallback(context)

    def _build_prompt(self, context: dict[str, Any]) -> str:
        event = context.get("event", "")
        session = context.get("session", {})
        return (
            "You are a terse old-school fantasy DM running an OSRIC adventure. "
            "Describe the following event in one or two vivid sentences."
            "Keep the tone dark, atmospheric, and brief.\n\n"
            f"Event: {event}\n"
            f"Session: {json.dumps(session, default=str)}\n"
        )

    def _fallback(self, context: dict[str, Any]) -> str:
        event = context.get("event", "")
        if "attacks" in event.lower():
            return "Steel clashes in the dark."
        if "moved" in event.lower():
            return "The figure shifts across the stone floor."
        return "The dungeon is silent, save for dripping water."
