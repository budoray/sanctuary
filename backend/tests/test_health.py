import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            r = await client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db"] is True
    assert data["ollama"] is True


@pytest.mark.asyncio
async def test_config():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/api/config")
    assert r.status_code == 200
    data = r.json()
    assert "pixellab_host" in data
    assert "ollama_enabled" in data


@pytest.mark.asyncio
async def test_version():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/version")
    assert r.status_code == 200
    assert r.text.startswith("v")


@pytest.mark.asyncio
async def test_licence():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/licence")
    assert r.status_code == 200
    data = r.json()
    assert "OSRIC" in data["notice"]
    assert "SRD" in data["srn"]
