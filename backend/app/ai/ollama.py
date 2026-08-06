"""Async client for a local Ollama instance.

Falls back to ``None`` on any error so the rest of the game keeps running
when Ollama is not installed, not running, or too slow.
"""
from __future__ import annotations

from typing import Any

import httpx

from backend.app.config import SETTINGS


def _default_system() -> str:
    return (
        "You are a terse old-school fantasy dungeon master. "
        "Reply with one or two vivid sentences. No lists, no rules, no signatures."
    )


async def generate(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    options: dict[str, Any] | None = None,
) -> str | None:
    """Ask the configured Ollama model to generate text.

    Returns the generated string, or ``None`` if Ollama is unavailable or
    returns an error. Network failures are swallowed so callers can fall back.
    """
    host = SETTINGS.ollama_host.rstrip("/")
    if not host:
        return None

    model = model or SETTINGS.ollama_model
    if not model:
        return None

    timeout = timeout or SETTINGS.ollama_timeout
    system = system or _default_system()
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
    }
    if options is not None:
        body["options"] = options
    else:
        body["options"] = {"temperature": 0.8, "num_predict": 80}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{host}/api/generate", json=body)
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "")
            return text.strip() if isinstance(text, str) else None
    except Exception:
        return None


async def is_available() -> bool:
    """Quick health check for the configured Ollama host."""
    host = SETTINGS.ollama_host.rstrip("/")
    if not host:
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{host}/")
            return response.status_code == 200
    except Exception:
        return False
