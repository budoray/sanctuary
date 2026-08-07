import json

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.db import CharacterRecord, SessionRecord, get_db
from backend.app.instance_manager import advance_idle_instances
from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_create_join_leave_persists_character_state():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            owner_char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "InstanceOwner",
                "seed": 1,
            })
            assert owner_char_resp.status_code == 200
            owner_char_id = owner_char_resp.json()["character"]["id"]

            instance_resp = await client.post("/api/sessions", json={
                "character_id": owner_char_id,
                "module_id": "sample_lair",
                "visibility": "public",
            })
            assert instance_resp.status_code == 200
            instance_id = instance_resp.json()["session"]["id"]

            headers = {"X-Tenshin-Dev-Account": "2"}
            joiner_char_resp = await client.post("/api/characters", headers=headers, json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "InstanceJoiner",
                "seed": 7,
            })
            assert joiner_char_resp.status_code == 200
            joiner_char_id = joiner_char_resp.json()["character"]["id"]

            join_resp = await client.post(
                f"/api/sessions/{instance_id}/join",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            assert join_resp.status_code == 200
            assert len(join_resp.json()["session"]["players"]) == 2

            # Simulate in-instance progression for the joiner.
            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == instance_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                joiner = next(
                    p for p in state["players"] if p.get("character_id") == joiner_char_id
                )
                joiner["xp"] = 75
                joiner["gold"] = 42
                joiner["hp"] = 6
                joiner["max_hp"] = 10
                joiner["level"] = 2
                record.state = json.dumps(state)
                await db.commit()

            leave_resp = await client.post(
                f"/api/sessions/{instance_id}/leave",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            assert leave_resp.status_code == 200
            assert leave_resp.json()["left"] is True
            session = leave_resp.json()["session"]
            assert len(session["players"]) == 2
            joiner = next(
                p for p in session["players"] if p.get("character_id") == joiner_char_id
            )
            assert joiner["ai_controlled"] is True

            char_resp = await client.get(
                f"/api/characters/{joiner_char_id}", headers=headers
            )
            assert char_resp.status_code == 200
            character = char_resp.json()["character"]
            assert character["xp"] == 75
            assert character["gold"] == 42
            assert character["hit_points"] == 6
            assert character["max_hp"] == 10
            assert character["level"] == 2


@pytest.mark.asyncio
async def test_ai_dm_advances_when_no_players_present():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "AIDMTest",
                "seed": 3,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            instance_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "module_id": "sample_lair",
            })
            assert instance_resp.status_code == 200
            instance_id = instance_resp.json()["session"]["id"]

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == instance_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["phase"] = "dm"
                record.state = json.dumps(state)
                await db.commit()

            advanced = await advance_idle_instances()
            assert advanced >= 1

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == instance_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                assert state["phase"] == "player"
                assert state["turn"] >= 2


@pytest.mark.asyncio
async def test_only_owner_or_dm_can_pause_and_resume():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "PauseOwner",
                "seed": 4,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            instance_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "module_id": "sample_lair",
                "visibility": "public",
            })
            assert instance_resp.status_code == 200
            instance_id = instance_resp.json()["session"]["id"]

            other_headers = {"X-Tenshin-Dev-Account": "2"}
            other_char_resp = await client.post("/api/characters", headers=other_headers, json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["cleric"],
                "name": "Rando",
                "seed": 5,
            })
            assert other_char_resp.status_code == 200

            # A non-owner cannot pause.
            bad_pause = await client.post(
                f"/api/sessions/{instance_id}/pause", headers=other_headers
            )
            assert bad_pause.status_code == 403

            pause_resp = await client.post(f"/api/sessions/{instance_id}/pause")
            assert pause_resp.status_code == 200
            assert pause_resp.json()["paused"] is True
            assert pause_resp.json()["session"]["status"] == "paused"

            # A non-owner cannot resume.
            bad_resume = await client.post(
                f"/api/sessions/{instance_id}/resume", headers=other_headers
            )
            assert bad_resume.status_code == 403

            resume_resp = await client.post(f"/api/sessions/{instance_id}/resume")
            assert resume_resp.status_code == 200
            assert resume_resp.json()["resumed"] is True
            assert resume_resp.json()["session"]["status"] == "active"
