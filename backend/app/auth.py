"""Tenshin shared-cookie authentication stub.

The real implementation will validate the Tenshin Arts session cookie against
TENSHIN_SECRET. For the first vertical slice we accept any caller as 'guest'.
"""
from fastapi import Request

from backend.app.config import SETTINGS


def get_current_user(request: Request) -> dict:
    """Return the logged-in user or a guest placeholder."""
    if not SETTINGS.tenshin_secret:
        return {"id": None, "name": "guest", "admin": False}
    # TODO: validate Tenshin session cookie using TENSHIN_SECRET.
    return {"id": None, "name": "guest", "admin": False}
