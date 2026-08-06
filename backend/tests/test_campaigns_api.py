import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

import backend.app.api.campaigns as campaigns_module
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


@pytest.mark.asyncio
async def test_dm_transfer_and_role_management():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Account 1 creates a campaign.
            create_resp = await client.post("/api/campaigns", json={
                "name": "Transfer Test",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert create_resp.status_code == 200
            campaign_id = create_resp.json()["campaign"]["id"]

            # Account 2 joins as a player.
            headers2 = {"X-Tenshin-Dev-Account": "2"}
            join_resp = await client.post(
                f"/api/campaigns/{campaign_id}/join", headers=headers2, json={"password": "secret"}
            )
            assert join_resp.status_code == 200

            # Verify member list.
            members_resp = await client.get(f"/api/campaigns/{campaign_id}/members")
            assert members_resp.status_code == 200
            members = members_resp.json()["members"]
            assert any(m["account_id"] == 2 and m["role"] == "player" for m in members)

            # Transfer DM role to account 2.
            transfer_resp = await client.post(
                f"/api/campaigns/{campaign_id}/transfer_dm", json={"account_id": 2}
            )
            assert transfer_resp.status_code == 200
            campaign = transfer_resp.json()["campaign"]
            assert campaign["dm_account_id"] == 2

            members_resp = await client.get(f"/api/campaigns/{campaign_id}/members")
            members = members_resp.json()["members"]
            assert any(m["account_id"] == 2 and m["role"] == "dm" for m in members)
            assert any(m["account_id"] == 1 and m["role"] == "player" for m in members)

            # Account 2 (now DM) can promote account 1 back to DM.
            role_resp = await client.post(
                f"/api/campaigns/{campaign_id}/members/1/role",
                headers=headers2,
                json={"role": "dm"},
            )
            assert role_resp.status_code == 200
            assert role_resp.json()["role"] == "dm"

            # Kick account 2.
            kick_resp = await client.post(
                f"/api/campaigns/{campaign_id}/members/2/role",
                json={"role": "none"},
            )
            assert kick_resp.status_code == 200
            members_resp = await client.get(f"/api/campaigns/{campaign_id}/members")
            members = members_resp.json()["members"]
            assert not any(m["account_id"] == 2 for m in members)


@pytest.mark.asyncio
async def test_only_dm_or_admin_can_manage_members(monkeypatch):
    # Dev mode makes every account an admin by cookie flag, so override the
    # campaigns helper to treat only account 1 as an admin for this test.
    monkeypatch.setattr(
        campaigns_module, "is_admin", lambda account_id, _header: account_id == 1
    )

    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            create_resp = await client.post("/api/campaigns", json={
                "name": "Locked",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert create_resp.status_code == 200
            campaign_id = create_resp.json()["campaign"]["id"]

            headers2 = {"X-Tenshin-Dev-Account": "2"}
            await client.post(
                f"/api/campaigns/{campaign_id}/join", headers=headers2, json={"password": "secret"}
            )

            # Account 2 may not transfer DM or manage members.
            transfer_resp = await client.post(
                f"/api/campaigns/{campaign_id}/transfer_dm",
                headers=headers2,
                json={"account_id": 2},
            )
            assert transfer_resp.status_code == 403

            role_resp = await client.post(
                f"/api/campaigns/{campaign_id}/members/1/role",
                headers=headers2,
                json={"role": "player"},
            )
            assert role_resp.status_code == 403
