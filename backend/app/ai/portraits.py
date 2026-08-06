"""Portrait helpers for characters.

When PIXELLAB_HOST is configured, generate_portrait_url can produce an AI
image URL for a character. Otherwise it falls back to the static class
portraits shipped with the frontend build.
"""
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


async def generate_portrait_url(prompt: str, class_name: str | None = None) -> str | None:
    """Generate a portrait URL if an external pixel-art service is configured.

    This is a stub that validates configuration and returns None when no host
    is set, letting callers fall back to static class portraits. A real
    implementation would POST to the configured host/model and return the
    resulting image URL.
    """
    if not SETTINGS.pixellab_host:
        return None

    # Placeholder for a real Pixellab / image-generation call.
    # model = SETTINGS.pixellab_model or "flux"
    # host = SETTINGS.pixellab_host.rstrip("/")
    # return f"{host}/api/v1/generate?model={model}&prompt={quote(prompt)}"
    return None


def character_portrait_url(name: str, class_name: str | None = None) -> str:
    """Best-effort portrait URL for a character.

    Prefers an AI-generated result when configured, otherwise a static
    class portrait. Falls back to the generic fighter portrait if the class
    is unknown.
    """
    generated = None
    if SETTINGS.pixellab_host:
        # Fire-and-forget async calls are awkward in synchronous callers;
        # for now we rely on static portraits until a service is wired in.
        generated = None

    if generated:
        return generated

    return static_portrait_url(class_name)
