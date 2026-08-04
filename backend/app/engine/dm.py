"""AI / human DM controller."""
import json
from typing import Any

import httpx

from backend.app.config import SETTINGS


class DMController:
    """Pluggable DM. Defaults to Ollama locally; falls back to a simple rule DM."""

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
