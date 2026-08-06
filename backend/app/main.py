"""Sanctuary FastAPI entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
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
from backend.app.tenshin_gate import name_from_cookie_header

FRONTEND_DIST = ROOT / "frontend" / "dist"


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


@fastapi_app.get("/version")
async def version():
    version_file = ROOT / "VERSION"
    version = version_file.read_text().strip() if version_file.exists() else "unknown"
    return {"version": version}


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
async def whoami(request: Request, account_id: int = Depends(require_account)):
    name = name_from_cookie_header(request.headers.get("cookie", ""))
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


FRONTEND_ASSETS = FRONTEND_DIST / "assets"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

if FRONTEND_ASSETS.exists():
    fastapi_app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS), name="assets")

if FRONTEND_INDEX.exists():
    @fastapi_app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        from fastapi.responses import FileResponse

        return FileResponse(FRONTEND_INDEX)
else:
    @fastapi_app.get("/{full_path:path}")
    async def serve_backend_only(full_path: str):
        return {"status": "backend only", "path": full_path}


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
