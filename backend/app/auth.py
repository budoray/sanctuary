"""Tenshin shared-cookie authentication wrapper for FastAPI."""
import os

from fastapi import HTTPException, Request

from backend.app.config import SETTINGS
from backend.app.tenshin_gate import admin_from_cookie_header, resolve_account


def require_account(request: Request) -> int:
    """Return the Tenshin account_id from the session cookie, or 401."""
    acct = resolve_account(
        request.headers.get("cookie", ""),
        request.query_params.get("_acct") or request.headers.get("x-tenshin-dev-account"),
    )
    if acct is None:
        raise HTTPException(status_code=401, detail="No Tenshin Arts session.")
    return acct


def _admin_ids_from_env() -> set[int]:
    """Parse the SANCTUARY_ADMIN_IDS env var into a set of account IDs."""
    raw = SETTINGS.sanctuary_admin_ids or os.environ.get("SANCTUARY_ADMIN_IDS", "")
    if not raw:
        return set()
    ids = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return ids


def is_admin(account_id: int, cookie_header: str) -> bool:
    """True if the account is an admin by cookie flag or configured admin IDs."""
    if admin_from_cookie_header(cookie_header):
        return True
    if account_id in _admin_ids_from_env():
        return True
    return False


def require_admin(request: Request) -> int:
    """Return the admin account_id, or 403/401."""
    account_id = require_account(request)
    if not is_admin(account_id, request.headers.get("cookie", "")):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return account_id
