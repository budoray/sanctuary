"""Sanctuary FastAPI entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.characters import router as characters_router
from backend.app.api.modules import router as modules_router
from backend.app.api.rulesets import router as rulesets_router
from backend.app.api.sessions import router as sessions_router
from backend.app.config import SETTINGS, ROOT
from backend.app.db import Base, engine
from backend.app.engine.store import EventRecord, SnapshotRecord  # noqa: F401  registers models
from backend.app.auth import require_account
from backend.app.socket_manager import socket_app
from backend.app.tenshin_gate import name_from_cookie_header

FRONTEND_DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

fastapi_app.include_router(sessions_router, prefix="/api")
fastapi_app.include_router(characters_router, prefix="/api")
fastapi_app.include_router(rulesets_router, prefix="/api")
fastapi_app.include_router(modules_router, prefix="/api")


@fastapi_app.get("/health")
async def health():
    return {"status": "ok", "env": SETTINGS.app_env}


@fastapi_app.get("/health/db")
async def health_db():
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.scalar()
    return {"status": "ok", "db": row == 1}


@fastapi_app.get("/api/whoami")
async def whoami(request: Request, account_id: int = Depends(require_account)):
    name = name_from_cookie_header(request.headers.get("cookie", ""))
    return {"user": {"id": account_id, "name": name or "player"}}


if FRONTEND_DIST.exists():
    fastapi_app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @fastapi_app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            from fastapi.responses import FileResponse

            return FileResponse(index)
        return {"status": "backend only", "path": full_path}


class SocketIOMiddleware:
    """Forward /ws/* to the Socket.IO ASGI app without path stripping.

    Starlette's Mount strips prefixes before calling sub-apps, which breaks
    python-socketio's ASGI path matching when mounted under /ws. This tiny
    middleware routes on the raw scope path instead.
    """

    def __init__(self, app, socket_app):
        self.app = app
        self.socket_app = socket_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") in ("http", "websocket") and scope.get("path", "").startswith("/ws"):
            await self.socket_app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


# uvicorn imports `app` from this module. The middleware wraps FastAPI so
# /ws/socket.io traffic goes to Socket.IO and everything else goes to FastAPI.
app = SocketIOMiddleware(fastapi_app, socket_app)
