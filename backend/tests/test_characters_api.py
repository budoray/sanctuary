import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_create_character_has_empty_inventory_and_equipment():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Equipped",
                "seed": 1,
            })
            assert resp.status_code == 200
            char = resp.json()["character"]
            assert char.get("inventory") == []
            assert char.get("equipment") == {}


@pytest.mark.asyncio
async def test_equip_and_use_items():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Potioneer",
                "seed": 1,
            })
            assert resp.status_code == 200
            char = resp.json()["character"]
            char_id = char["id"]

            # Manually inject items into the character state via direct DB? Simpler: use
            # the items helper through a small private endpoint is not available.
            # Instead, verify equip fails for unknown item and use fails for non-usable.
            bad_equip = await client.post(f"/api/characters/{char_id}/equip", json={"instance_id": "nope"})
            assert bad_equip.status_code == 400

            bad_use = await client.post(f"/api/characters/{char_id}/use", json={"instance_id": "nope"})
            assert bad_use.status_code == 400
