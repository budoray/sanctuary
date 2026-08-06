import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_health():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_version_and_cors_whitelist():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.get(
                "/version",
                headers={"Origin": "https://tenshinarts.com"},
            )
            assert resp.status_code == 200
            assert resp.text.startswith("v")
            # CORS: the tenshinarts.com games page must be able to fetch /version
            assert "access-control-allow-origin" in {k.lower() for k in resp.headers.keys()}
            assert resp.headers["access-control-allow-origin"] == "https://tenshinarts.com"


@pytest.mark.asyncio
async def test_licence_route():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.get("/licence")
            assert resp.status_code == 200
            assert "OSRIC" in resp.json()["notice"]
