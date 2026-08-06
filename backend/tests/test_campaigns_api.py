import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_create_and_join_campaign():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            create_resp = await client.post("/api/campaigns", json={
                "name": "Test Campaign",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert create_resp.status_code == 200
            campaign = create_resp.json()["campaign"]
            assert campaign["name"] == "Test Campaign"

            list_resp = await client.get("/api/campaigns")
            assert list_resp.status_code == 200
            assert any(c["id"] == campaign["id"] for c in list_resp.json()["campaigns"])

            get_resp = await client.get(f"/api/campaigns/{campaign['id']}")
            assert get_resp.status_code == 200
            assert get_resp.json()["campaign"]["is_member"] is True


@pytest.mark.asyncio
async def test_list_campaign_sessions():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            create_resp = await client.post("/api/campaigns", json={
                "name": "Session Listing",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert create_resp.status_code == 200
            campaign_id = create_resp.json()["campaign"]["id"]

            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Lister",
                "seed": 1,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            session_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "campaign_id": campaign_id,
                "module_id": "sample_lair",
            })
            assert session_resp.status_code == 200

            list_resp = await client.get(f"/api/campaigns/{campaign_id}/sessions")
            assert list_resp.status_code == 200
            sessions = list_resp.json()["sessions"]
            assert len(sessions) == 1
            assert sessions[0]["player_count"] == 1
