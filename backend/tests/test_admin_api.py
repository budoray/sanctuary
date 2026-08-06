import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app import auth as auth_module
from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_admin_endpoints_are_accessible_in_dev_mode(monkeypatch):
    # In dev mode every account is an admin via the cookie flag, so this
    # exercises the admin router wiring rather than the env-var fallback.
    monkeypatch.setattr(auth_module.SETTINGS, "sanctuary_admin_ids", "")
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Create a campaign and a session to administrate.
            campaign_resp = await client.post("/api/campaigns", json={
                "name": "Admin Target",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert campaign_resp.status_code == 200
            campaign_id = campaign_resp.json()["campaign"]["id"]

            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "AdminHero",
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
            session_id = session_resp.json()["session"]["id"]

            campaigns_resp = await client.get("/api/admin/campaigns")
            assert campaigns_resp.status_code == 200
            campaigns = campaigns_resp.json()["campaigns"]
            assert any(c["id"] == campaign_id for c in campaigns)

            sessions_resp = await client.get("/api/admin/sessions")
            assert sessions_resp.status_code == 200
            sessions = sessions_resp.json()["sessions"]
            assert any(s["id"] == session_id for s in sessions)

            del_session = await client.delete(f"/api/admin/sessions/{session_id}")
            assert del_session.status_code == 200
            assert del_session.json()["deleted"] is True

            del_campaign = await client.delete(f"/api/admin/campaigns/{campaign_id}")
            assert del_campaign.status_code == 200
            assert del_campaign.json()["deleted"] is True

            campaigns_resp = await client.get("/api/admin/campaigns")
            assert not any(c["id"] == campaign_id for c in campaigns_resp.json()["campaigns"])


@pytest.mark.asyncio
async def test_admin_env_var_allows_non_cookie_admin(monkeypatch):
    # Verify that the SANCTUARY_ADMIN_IDS fallback works independently of the
    # session-cookie admin flag by forcing the cookie check to return False.
    monkeypatch.setattr(auth_module.SETTINGS, "sanctuary_admin_ids", "1,42")
    monkeypatch.setattr(auth_module, "admin_from_cookie_header", lambda _header: False)

    from backend.app.auth import is_admin

    assert is_admin(1, "") is True
    assert is_admin(42, "") is True
    assert is_admin(99, "") is False


@pytest.mark.asyncio
async def test_whoami_exposes_admin_flag():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.get("/api/whoami")
            assert resp.status_code == 200
            data = resp.json()["user"]
            assert "is_admin" in data
            assert data["is_admin"] is True  # dev mode
