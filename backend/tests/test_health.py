import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_version():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/version")
    assert r.status_code == 200
    assert "version" in r.json()


@pytest.mark.asyncio
async def test_licence():
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
        r = await client.get("/licence")
    assert r.status_code == 200
    data = r.json()
    assert "OSRIC" in data["notice"]
    assert "SRD" in data["srn"]
