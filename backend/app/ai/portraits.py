"""Portrait helpers for characters.

When PIXELLAB_HOST is configured, generate_portrait_url can produce an AI
image URL for a character. Otherwise it falls back to the static class
portraits shipped with the frontend build.
"""
import httpx

from backend.app.config import SETTINGS


STATIC_PORTRAIT_ROOT = "/portraits"


def static_portrait_url(class_name: str | None) -> str:
    """Return a frontend-static portrait URL based on the character's class."""
    key = (class_name or "fighter").lower().replace(" ", "-")
    # The generic portrait is used when a specific class asset is missing.
    if key not in {
        "fighter",
        "cleric",
        "magic-user",
        "thief",
        "paladin",
        "ranger",
        "druid",
        "assassin",
        "monk",
        "illusionist",
    }:
        key = "generic"
    return f"{STATIC_PORTRAIT_ROOT}/{key}.png"


def build_prompt(name: str, class_name: str | None = None, ancestry: str | None = None) -> str:
    """Build a PixelLab-friendly prompt for a character portrait."""
    parts = ["retro pixel art fantasy portrait"]
    if name:
        parts.append(f"of {name}")
    if class_name:
        parts.append(f"a {class_name}")
    if ancestry:
        parts.append(f"({ancestry})")
    parts.append("16-bit RPG style, head and shoulders, simple background")
    return ", ".join(parts)


async def generate_portrait_url(prompt: str, class_name: str | None = None) -> str | None:
    """Generate a portrait URL if an external pixel-art service is configured.

    Posts to ``{PIXELLAB_HOST}/api/v1/generate`` with the configured model and
    prompt. Accepts a JSON response containing either ``image_url`` or ``url``.
    Returns ``None`` when PixelLab is not configured or the call fails, letting
    callers fall back to static class portraits.
    """
    if not SETTINGS.pixellab_host:
        return None

    host = SETTINGS.pixellab_host.rstrip("/")
    headers = {"Content-Type": "application/json"}
    if SETTINGS.pixellab_key:
        headers["Authorization"] = f"Bearer {SETTINGS.pixellab_key}"

    payload = {
        "model": SETTINGS.pixellab_model or "flux",
        "prompt": prompt,
    }

    try:
        async with httpx.AsyncClient(timeout=SETTINGS.pixellab_timeout) as client:
            resp = await client.post(f"{host}/api/v1/generate", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    return data.get("image_url") or data.get("url")


async def character_portrait_url(
    name: str, class_name: str | None = None, ancestry: str | None = None
) -> str:
    """Best-effort portrait URL for a character.

    Prefers an AI-generated result when configured, otherwise a static
    class portrait. Falls back to the generic fighter portrait if the class
    is unknown.
    """
    if SETTINGS.pixellab_host:
        prompt = build_prompt(name, class_name, ancestry)
        generated = await generate_portrait_url(prompt, class_name)
        if generated:
            return generated

    return static_portrait_url(class_name)
