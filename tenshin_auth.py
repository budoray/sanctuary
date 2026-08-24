"""Tenshin Arts auth — session cookies (hub) and game gate (verify only).

Canonical source: website/dropins/ — sync with deploy/sync-dropins.sh.
Hub issues cookies; games verify them with the same TENSHIN_SECRET. No shared DB.
"""
from __future__ import annotations

import hmac
import os
import sys
from http.cookies import SimpleCookie
from urllib.parse import urlparse

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_DEV_SECRET = "dev-insecure-secret-change-me"
COOKIE_NAME = "tenshin_session"
MAX_AGE = 60 * 60 * 24 * 30


def _settings_val(name: str, default=None):
    try:
        from config import settings
        return getattr(settings, name, default)
    except ImportError:
        return default


def _secret() -> str:
    s = _settings_val("tenshin_secret", "") or os.environ.get("TENSHIN_SECRET") or _DEV_SECRET
    return s or _DEV_SECRET


SECRET = _secret()


def _site_url() -> str:
    url = _settings_val("tenshin_site_url") or os.environ.get(
        "TENSHIN_SITE_URL", "https://tenshinarts.com")
    return url.rstrip("/")


SITE_URL = _site_url()

DEV_MODE = os.environ.get("TENSHIN_DEV", "").lower() in ("1", "true", "yes")
DEV_ACCOUNT = int(os.environ.get("TENSHIN_DEV_ACCOUNT", "1"))

if DEV_MODE:
    print(
        "[WARN] TENSHIN_DEV is ON - auth is BYPASSED; every request runs as a dev "
        "account. NEVER set TENSHIN_DEV in production.",
        file=sys.stderr,
        flush=True,
    )

_serializer = URLSafeTimedSerializer(SECRET, salt="tenshin-session")


def secret_configured() -> bool:
    return bool(SECRET and SECRET != _DEV_SECRET)


def secret_ok(provided: str) -> bool:
    """Constant-time check for server-to-server routes (feedback, admin)."""
    if not provided or SECRET == _DEV_SECRET:
        return False
    return hmac.compare_digest(str(provided), SECRET)


def issue_token(account_id: int, username: str, *, admin: bool = False) -> str:
    payload: dict = {"id": int(account_id), "u": username}
    if admin:
        payload["adm"] = 1
    return _serializer.dumps(payload)


def read_token(token: str) -> dict | None:
    return _decode(token)


def _decode(token: str) -> dict | None:
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None
    if not isinstance(data, dict) or "id" not in data:
        return None
    return data


def verify_token(token: str):
    """Return the Tenshin account_id (int) or None."""
    d = _decode(token)
    return int(d["id"]) if d and "id" in d else None


def token_is_admin(token: str) -> bool:
    d = _decode(token)
    return bool(d and d.get("adm"))


def cookie_domain() -> str | None:
    domain = (
        _settings_val("tenshin_cookie_domain")
        or os.environ.get("TENSHIN_COOKIE_DOMAIN")
        or ""
    ).strip()
    if domain:
        return domain
    host = (urlparse(SITE_URL).hostname or "").lower()
    if host in ("tenshinarts.com", "www.tenshinarts.com"):
        return ".tenshinarts.com"
    return None


def cookie_secure() -> bool:
    if os.environ.get("TENSHIN_DEV", "").lower() in ("1", "true", "yes"):
        return False
    secure = _settings_val("cookie_secure")
    if secure is not None:
        return bool(secure)
    return os.environ.get("COOKIE_SECURE", "true").lower() not in ("0", "false", "no")


def safe_next(raw: str | None, default: str = "/games.html") -> str:
    """Only redirect to tenshinarts.com or its subdomains after login."""
    if not raw:
        return default
    target = raw.strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    parsed = urlparse(target)
    if parsed.scheme not in ("http", "https"):
        return default
    host = (parsed.hostname or "").lower()
    if host in ("tenshinarts.com", "www.tenshinarts.com") or host.endswith(".tenshinarts.com"):
        return target
    return default


def _morsel(cookie_header: str):
    if not cookie_header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return None
    return jar.get(COOKIE_NAME)


def account_from_cookie_header(cookie_header: str):
    """Pull the session cookie out of a raw Cookie header and verify it."""
    m = _morsel(cookie_header)
    return verify_token(m.value) if m else None


def name_from_cookie_header(cookie_header: str):
    """Username on this session cookie, or None."""
    m = _morsel(cookie_header)
    d = _decode(m.value) if m else None
    return (d.get("u") or None) if d else None


def admin_from_cookie_header(cookie_header: str) -> bool:
    """True if the session cookie carries the admin flag (or in dev mode)."""
    if DEV_MODE:
        return True
    m = _morsel(cookie_header)
    return token_is_admin(m.value) if m else False


def resolve_account(cookie_header: str, dev_override=None):
    """Account id for this request. None when auth fails in production."""
    if DEV_MODE:
        if dev_override not in (None, ""):
            try:
                return int(dev_override)
            except (ValueError, TypeError):
                pass
        return DEV_ACCOUNT
    return account_from_cookie_header(cookie_header)


def require_account(request):
    """FastAPI dependency: returns account_id, or 401."""
    from fastapi import HTTPException

    acct = resolve_account(
        request.headers.get("cookie", ""),
        request.query_params.get("_acct") or request.headers.get("x-tenshin-dev-account"))
    if acct is None:
        raise HTTPException(status_code=401, detail="No Tenshin Arts session.")
    return acct


if not secret_configured() and not DEV_MODE:
    print(
        "[WARN] TENSHIN_SECRET is not configured — session cookies will not work in production.",
        file=sys.stderr,
        flush=True,
    )
