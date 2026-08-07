"""Sanctuary FastAPI entry point."""
from contextlib import asynccontextmanager
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request as StarletteRequest
from starlette.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.admin import router as admin_router
from backend.app.api.arena import router as arena_router
from backend.app.api.campaigns import router as campaigns_router
from backend.app.api.characters import router as characters_router
from backend.app.api.dm import router as dm_router
from backend.app.api.modules import router as modules_router
from backend.app.api.progression import router as progression_router
from backend.app.api.sessions import router as sessions_router
from backend.app.api.social import router as social_router
from backend.app.config import SETTINGS, ROOT
from backend.app.db import Base, engine
from backend.app.auth import is_admin, require_account, require_admin
import httpx

from backend.app.socket_manager import socket_app
from backend.app.tenshin_gate import COOKIE_NAME, MAX_AGE, account_from_cookie_header, name_from_cookie_header

FRONTEND_DIST = ROOT / "frontend" / "static"


def _shared_cookie_domain() -> str | None:
    """Return the parent domain to use for the shared session cookie.

    A cookie set with Domain=tenshinarts.com is sent to tenshinarts.com and all
    subdomains (e.g. sanctuary.tenshinarts.com). Localhost is skipped.
    """
    hostname = urlparse(SETTINGS.tenshin_site_url).hostname or ""
    if not hostname or "." not in hostname:
        return None
    return hostname.lstrip("www.")


def _upgrade_session_cookie(token: str) -> str | None:
    """Rebuild the session cookie with a shared parent-domain so subdomains see it."""
    domain = _shared_cookie_domain()
    if not domain:
        return None
    jar = SimpleCookie()
    jar[COOKIE_NAME] = token
    m = jar[COOKIE_NAME]
    m["domain"] = domain
    m["path"] = "/"
    m["max-age"] = str(MAX_AGE)
    m["httponly"] = True
    m["samesite"] = "Lax"
    if SETTINGS.tenshin_site_url.startswith("https"):
        m["secure"] = True
    return m.OutputString()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    app_dir = Path(__file__).resolve().parent
    alembic_ini = app_dir.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    # Alembic's command.upgrade is synchronous and may start its own event loop,
    # so run it in a worker thread to avoid "cannot be called from a running loop".
    import asyncio

    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    yield
    await engine.dispose()


fastapi_app = FastAPI(title="Sanctuary", lifespan=lifespan)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fastapi_app.include_router(admin_router, prefix="/api")
fastapi_app.include_router(characters_router, prefix="/api")
fastapi_app.include_router(campaigns_router, prefix="/api")
fastapi_app.include_router(dm_router, prefix="/api")
fastapi_app.include_router(modules_router, prefix="/api")
fastapi_app.include_router(progression_router, prefix="/api")
fastapi_app.include_router(sessions_router, prefix="/api")
fastapi_app.include_router(social_router, prefix="/api")
fastapi_app.include_router(arena_router, prefix="/api")


@fastapi_app.get("/health")
async def health():
    return {"status": "ok", "env": SETTINGS.app_env}


@fastapi_app.get("/health/ready")
async def health_ready():
    """Readiness probe: verifies DB and (when enabled) Ollama are reachable."""
    from sqlalchemy import text

    db_ok = False
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            db_ok = result.scalar() == 1
    except Exception:
        db_ok = False

    ollama_ok = False
    if SETTINGS.ollama_enabled:
        try:
            async with httpx.AsyncClient(timeout=SETTINGS.ollama_timeout) as client:
                resp = await client.get(f"{SETTINGS.ollama_host}/api/tags")
                ollama_ok = resp.status_code == 200
        except Exception:
            ollama_ok = False
    else:
        ollama_ok = True

    if db_ok and ollama_ok:
        return {"status": "ok", "db": True, "ollama": ollama_ok}
    raise HTTPException(
        status_code=503,
        detail={"status": "not ready", "db": db_ok, "ollama": ollama_ok},
    )


@fastapi_app.get("/version", response_class=PlainTextResponse)
async def version():
    version_file = ROOT / "VERSION"
    return version_file.read_text().strip() if version_file.exists() else "unknown"


@fastapi_app.get("/health/db")
async def health_db():
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.scalar()
    return {"status": "ok", "db": row == 1}


@fastapi_app.get("/api/config")
async def app_config():
    """Public runtime configuration used by the frontend."""
    return {
        "pixellab_host": bool(SETTINGS.pixellab_host),
        "ollama_enabled": SETTINGS.ollama_enabled,
    }


@fastapi_app.get("/api/whoami")
async def whoami(
    request: Request,
    response: Response,
    account_id: int = Depends(require_account),
):
    name = name_from_cookie_header(request.headers.get("cookie", ""))
    token = request.cookies.get(COOKIE_NAME)
    if token:
        upgraded = _upgrade_session_cookie(token)
        if upgraded:
            response.headers["Set-Cookie"] = upgraded
    return {"user": {"id": account_id, "name": name or "player", "is_admin": is_admin(account_id, request.headers.get("cookie", ""))}}


@fastapi_app.get("/licence")
async def licence():
    return {
        "notice": (
            "Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License "
            "and is not affiliated with Mythmere Games LLC."
        ),
        "srn": (
            "This work includes material taken from the System Reference Document 5.1 ('SRD 5.1') by "
            "Wizards of the Coast LLC and available at https://dnd.wizards.com/resources/systems-reference-document. "
            "The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License "
            "available at https://creativecommons.org/licenses/by/4.0/legalcode."
        ),
    }


if FRONTEND_DIST.exists():
    fastapi_app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


class SharedSessionCookieMiddleware(BaseHTTPMiddleware):
    """Re-issue a host-only session cookie with the parent domain so subdomains share it."""

    async def dispatch(self, request: StarletteRequest, call_next: RequestResponseEndpoint):
        response = await call_next(request)
        if response.status_code == 200 and "text/html" in response.headers.get("content-type", ""):
            token = request.cookies.get(COOKIE_NAME)
            if token and account_from_cookie_header(request.headers.get("cookie", "")) is not None:
                upgraded = _upgrade_session_cookie(token)
                if upgraded:
                    response.headers["Set-Cookie"] = upgraded
        return response


fastapi_app.add_middleware(SharedSessionCookieMiddleware)


class SocketIOMiddleware:
    """Forward /ws/* to the Socket.IO ASGI app without path stripping."""

    def __init__(self, app, socket_app):
        self.app = app
        self.socket_app = socket_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket") and scope.get("path", "").startswith("/ws"):
            await self.socket_app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


app = SocketIOMiddleware(fastapi_app, socket_app)
