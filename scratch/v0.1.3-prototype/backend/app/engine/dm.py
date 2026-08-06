"""AI / human DM controller."""
import json
import random
from typing import Any

import httpx

from backend.app.config import SETTINGS


class DMController:
    """Pluggable DM. Defaults to Ollama locally; falls back to a simple rule DM."""

    async def take_turn(self, session) -> dict[str, Any]:
        """Return a DM turn result: {token_id, x, y, narration, attack?, damage?}.

        The DM controller must not mutate session state directly; the caller
        applies damage/movement events from the returned result.
        """
        player = session.player_token()
        enemies = session.dm_tokens()
        if not player or not enemies:
            return {"narration": "The chamber is still."}

        # Simple AI: move the closest enemy one tile toward the player.
        target = min(enemies, key=lambda e: abs(e.x - player.x) + abs(e.y - player.y))
        distance = abs(target.x - player.x) + abs(target.y - player.y)

        result: dict[str, Any] = {"token_id": target.id}

        if distance == 1:
            # Attack the player. OSRIC-ish: d20 roll, hit on AC or better.
            roll = random.randint(1, 20)
            hit = roll >= player.ac
            damage = random.randint(1, 4) if hit else 0
            result["attack"] = {"target_id": player.id, "damage": damage, "hit": hit, "roll": roll}
            event = (
                f"{target.name} attacks {player.name} and {'hits' if hit else 'misses'}"
                + (f" for {damage} damage." if hit else ".")
            )
            result["narration"] = await self.narrate({
                "event": event,
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
        text = event.lower()

        if "misses" in text:
            return random.choice([
                "A blade whistles through empty air.",
                "The blow glances off armor and stone alike.",
                "Teeth snap shut on nothing.",
                "The attacker overextends, leaving an opening.",
            ])

        if "hits" in text or "damage" in text:
            return random.choice([
                "Steel finds flesh in the gloom.",
                "A wet cry echoes off the walls.",
                "The strike lands with a sickening crunch.",
                "Pain flares sharp and sudden.",
            ])

        if "moves toward" in text or "moved" in text:
            return random.choice([
                "Claws scrape over cold flagstones as it closes in.",
                "Shadows lengthen with each step it takes.",
                "It pads forward, eyes fixed and unblinking.",
                "The stench grows stronger as it nears.",
            ])

        if "cannot reach" in text:
            return random.choice([
                "It snarls at the obstacle, foiled for now.",
                "Frustrated claws rake the stone.",
                "It paces, searching for another way through.",
                "The barrier holds, but not for long.",
            ])

        return random.choice([
            "The dungeon is silent, save for dripping water.",
            "Somewhere in the dark, something shifts.",
            "Torchlight flickers against damp stone.",
            "A draft carries the smell of old decay.",
        ])
