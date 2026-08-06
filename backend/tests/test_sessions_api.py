import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_create_session_and_act():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "SessionTest",
                "seed": 1,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            session_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "module_id": "sample_lair",
            })
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            move_resp = await client.post(f"/api/sessions/{session_id}/act", json={
                "action": "move",
                "x": 3,
                "y": 2,
            })
            assert move_resp.status_code == 200
            assert move_resp.json()["session"]["player"]["x"] == 3

            list_resp = await client.get("/api/sessions")
            assert list_resp.status_code == 200
            assert any(s["id"] == session_id for s in list_resp.json()["sessions"])
