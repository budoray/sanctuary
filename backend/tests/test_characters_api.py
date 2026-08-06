import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_create_and_list_character():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            create_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Test Fighter",
                "seed": 1,
            })
        assert create_resp.status_code == 200
        char = create_resp.json()["character"]
        assert char["name"] == "Test Fighter"
        assert char["classes"] == ["fighter"]

        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            list_resp = await client.get("/api/characters")
        assert list_resp.status_code == 200
        ids = [c["id"] for c in list_resp.json()["characters"]]
        assert char["id"] in ids
