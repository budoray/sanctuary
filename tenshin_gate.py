"""Drop-in auth gate for Tenshin Arts games.

Copy this ONE file into a game repo. It verifies the session cookie the website
issues — no shared database, no network call. The only requirement: the game
process runs with the SAME TENSHIN_SECRET as the website.

FastAPI games (Freight Mogul):
    from tenshin_gate import require_account
    @app.get("/")
    def home(account_id: int = Depends(require_account)):
        ...   # account_id is the Tenshin user; key saves by it

Custom servers, on the HTTP request / WS handshake:
    from tenshin_gate import resolve_account
    account_id = resolve_account(headers.get("cookie", ""))
    if account_id is None: reject — send them to SITE_URL, not to a login page of your own

DEV / PLAYTEST MODE
    Set TENSHIN_DEV=1 to BYPASS auth entirely — every request runs as a dev
    account (TENSHIN_DEV_ACCOUNT, default 1), so `python app.py` plays locally
    with no login. Bots/multiple players can each pick an account per request via
    the `?_acct=<n>` query param or the `X-Tenshin-Dev-Account: <n>` header.
    NEVER set TENSHIN_DEV in production — it turns the lock off.
"""
import hmac
import os
import sys
from http.cookies import SimpleCookie

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_DEV_SECRET = "dev-insecure-secret-change-me"
SECRET = os.environ.get("TENSHIN_SECRET") or _DEV_SECRET


def secret_ok(provided: str) -> bool:
    """Constant-time check that `provided` matches the shared TENSHIN_SECRET, used by every
    server-to-server route (the Command Center's /admin/players, the feedback hub). Fails CLOSED
    when the secret isn't really configured — a box still on the public dev fallback rejects
    everything rather than trusting a known string. Never compare the secret with `==`/`!=`."""
    if not provided or SECRET == _DEV_SECRET:
        return False
    return hmac.compare_digest(str(provided), SECRET)
COOKIE_NAME = "tenshin_session"
MAX_AGE = 60 * 60 * 24 * 30
# Games have no login of their own. One Tenshin Arts account opens every game, so an un-authed
# request is sent to the site — never to a per-game login page.
SITE_URL = os.environ.get("TENSHIN_SITE_URL", "https://tenshinarts.com").rstrip("/")

# ── dev / playtest bypass ─────────────────────────────────────────────────────
DEV_MODE = os.environ.get("TENSHIN_DEV", "").lower() in ("1", "true", "yes")
DEV_ACCOUNT = int(os.environ.get("TENSHIN_DEV_ACCOUNT", "1"))
if DEV_MODE:
    print("[WARN] TENSHIN_DEV is ON - auth is BYPASSED; every request runs as a dev "
          "account. NEVER set TENSHIN_DEV in production.", file=sys.stderr, flush=True)

_serializer = URLSafeTimedSerializer(SECRET, salt="tenshin-session")


def _decode(token: str):
    if not token:
        return None
    try:
        return _serializer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def verify_token(token: str):
    """Return the Tenshin account_id (int) or None."""
    d = _decode(token)
    return int(d["id"]) if d and "id" in d else None


def token_is_admin(token: str) -> bool:
    d = _decode(token)
    return bool(d and d.get("adm"))


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
    """Pull the session cookie out of a raw `Cookie:` header and verify it."""
    m = _morsel(cookie_header)
    return verify_token(m.value) if m else None


def name_from_cookie_header(cookie_header: str):
    """The Tenshin USERNAME on this session cookie, or None. A game with no login of its own
    still knows who is playing, so a new save can be named after the account instead of
    "Player7". Tokens issued before the name was baked in carry no `u` — treat that as None
    and fall back to whatever the game called people before."""
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
    """The account_id for this request. In dev mode returns a fixed dev account
    (optionally overridden per-request) WITHOUT any login; otherwise verifies the
    real Tenshin session cookie. Returns None only when auth fails in prod."""
    if DEV_MODE:
        if dev_override not in (None, ""):
            try:
                return int(dev_override)
            except (ValueError, TypeError):
                pass
        return DEV_ACCOUNT
    return account_from_cookie_header(cookie_header)


# ── FastAPI helper (import lazily so non-FastAPI games don't need it) ──────────
def require_account(request):
    """FastAPI dependency: returns account_id, or 401. Games do not host a login page — the
    client decides what to show; the site is where an account is made and signed into."""
    from fastapi import HTTPException

    acct = resolve_account(
        request.headers.get("cookie", ""),
        request.query_params.get("_acct") or request.headers.get("x-tenshin-dev-account"))
    if acct is None:
        raise HTTPException(status_code=401, detail="No Tenshin Arts session.")
    return acct
