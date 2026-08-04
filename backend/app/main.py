"""Sanctuary FastAPI entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.modules import router as modules_router
from backend.app.api.rulesets import router as rulesets_router
from backend.app.api.sessions import router as sessions_router
from backend.app.config import SETTINGS, ROOT
from backend.app.db import Base, engine
from backend.app.socket_manager import socket_app

FRONTEND_DIST = ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Sanctuary", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/api")
app.include_router(rulesets_router, prefix="/api")
app.include_router(modules_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "env": SETTINGS.app_env}


@app.get("/health/db")
async def health_db():
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.scalar()
    return {"status": "ok", "db": row == 1}


@app.get("/api/whoami")
async def whoami(user: dict = None):
    # Placeholder until Tenshin auth is wired.
    return {"user": user or {"name": "guest", "id": None}}


# Socket.IO is mounted under /ws; the static catch-all must come last.
app.mount("/ws", socket_app)

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            from fastapi.responses import FileResponse

            return FileResponse(index)
        return {"status": "backend only", "path": full_path}
