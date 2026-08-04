"""AI / human DM controller."""
import json
from typing import Any

import httpx

from backend.app.config import SETTINGS


class DMController:
    """Pluggable DM. Defaults to Ollama locally; falls back to a simple rule DM."""

    async def take_turn(self, session) -> dict[str, Any]:
        """Return a DM turn result: {token_id, x, y, narration}."""
        player = session.player_token()
        enemies = session.dm_tokens()
        if not player or not enemies:
            return {"narration": "The chamber is still."}

        # Simple AI: move the closest enemy one tile toward the player.
        target = min(enemies, key=lambda e: abs(e.x - player.x) + abs(e.y - player.y))
        dx = 0 if target.x == player.x else (1 if player.x > target.x else -1)
        dy = 0 if target.y == player.y else (1 if player.y > target.y else -1)
        new_x = max(0, min(session.map.width - 1, target.x + dx))
        new_y = max(0, min(session.map.height - 1, target.y + dy))

        context = {
            "event": f"{target.name} moves toward {player.name}.",
            "session": session.to_dict(),
        }
        narration = await self.narrate(context)
        return {
            "token_id": target.id,
            "x": new_x,
            "y": new_y,
            "narration": narration,
        }

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
            "Describe the following event in one or two vivid sentences.\n\n"
            f"Event: {event}\n"
            f"Session: {json.dumps(session, default=str)}\n"
        )

    def _fallback(self, context: dict[str, Any]) -> str:
        event = context.get("event", "")
        if "moved" in event.lower():
            return "The figure shifts across the stone floor."
        return "The dungeon is silent, save for dripping water."
