#!/usr/bin/env python3
"""Sanctuary production launcher.

Serves the built Vite frontend as static files and runs the FastAPI backend
on the same port. Caddy proxies sanctuary.tenshinarts.com here.
"""
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT / "frontend" / "static"


def main() -> None:
    port = int(os.environ.get("PORT", "9300"))
    host = os.environ.get("HOST", "127.0.0.1")
    reload = os.environ.get("RELOAD", "0") == "1"

    if not FRONTEND_DIST.exists() and not reload:
        print(f"WARNING: {FRONTEND_DIST} not found. Build or copy the frontend static files.", file=sys.stderr)

    uvicorn.run(
        "backend.app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(ROOT / "backend")] if reload else None,
    )


if __name__ == "__main__":
    main()
