"""Tenshin shared-cookie authentication wrapper for FastAPI."""
from fastapi import HTTPException, Request

from backend.app.tenshin_gate import resolve_account


def require_account(request: Request) -> int:
    """Return the Tenshin account_id from the session cookie, or 401."""
    acct = resolve_account(
        request.headers.get("cookie", ""),
        request.query_params.get("_acct") or request.headers.get("x-tenshin-dev-account"),
    )
    if acct is None:
        raise HTTPException(status_code=401, detail="No Tenshin Arts session.")
    return acct
