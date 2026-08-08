import json

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.db import CharacterRecord, SessionRecord, get_db
from backend.app.engine import module as module_engine
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


@pytest.mark.asyncio
async def test_join_campaign_session():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Account 1 creates a campaign.
            campaign_resp = await client.post("/api/campaigns", json={
                "name": "Joinable",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert campaign_resp.status_code == 200
            campaign_id = campaign_resp.json()["campaign"]["id"]

            # Account 2 creates a character and joins the campaign.
            headers = {"X-Tenshin-Dev-Account": "2"}
            char_resp = await client.post("/api/characters", headers=headers, json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Joiner",
                "seed": 7,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            join_campaign_resp = await client.post(
                f"/api/campaigns/{campaign_id}/join", headers=headers, json={"password": "secret"}
            )
            assert join_campaign_resp.status_code == 200

            # Account 1 creates a character to start the session.
            char1_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Founder",
                "seed": 1,
            })
            assert char1_resp.status_code == 200
            char1_id = char1_resp.json()["character"]["id"]

            # Account 1 starts a campaign session.
            session_resp = await client.post("/api/sessions", json={
                "character_id": char1_id,
                "campaign_id": campaign_id,
                "module_id": "sample_lair",
            })
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            # Account 2 joins the session with its own character.
            join_resp = await client.post(
                f"/api/sessions/{session_id}/join", headers=headers, json={"character_id": char_id}
            )
            assert join_resp.status_code == 200
            session = join_resp.json()["session"]
            assert len(session["players"]) == 2
            p2 = next((p for p in session["players"] if p.get("account_id") == 2), None)
            assert p2 is not None

            # Account 2 cannot act when it is not their turn.
            bad_move = await client.post(
                f"/api/sessions/{session_id}/act", headers=headers, json={"action": "move", "x": p2['x'], "y": p2['y']}
            )
            assert bad_move.status_code == 403

            # Account 1 ends turn, passing control to account 2.
            end_resp = await client.post(f"/api/sessions/{session_id}/act", json={"action": "end_turn"})
            assert end_resp.status_code == 200
            assert end_resp.json()["session"]["active_player_index"] == 1

            # Move account 2's token one tile to the right if possible.
            good_move = await client.post(
                f"/api/sessions/{session_id}/act", headers=headers, json={"action": "move", "x": p2['x'] + 1, "y": p2['y']}
            )
            assert good_move.status_code == 200

            # Account 2 now sees the session in their list.
            list_resp = await client.get("/api/sessions", headers=headers)
            assert list_resp.status_code == 200
            assert any(s["id"] == session_id for s in list_resp.json()["sessions"])


@pytest.mark.asyncio
async def test_only_campaign_sessions_can_be_joined():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Solo",
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

            join_resp = await client.post(
                f"/api/sessions/{session_id}/join", json={"character_id": char_id}
            )
            assert join_resp.status_code == 400


@pytest.mark.asyncio
async def test_winning_session_persists_progression():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "ProgressionTest",
                "seed": 1,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]
            initial_xp = char_resp.json()["character"].get("xp", 0)

            session_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "module_id": "sample_lair",
            })
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            # Set up a guaranteed kill: one monster adjacent with 1 HP and terrible AC.
            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["monsters"][0]["x"] = state["player"]["x"] + 1
                state["monsters"][0]["y"] = state["player"]["y"]
                state["monsters"][0]["hp"] = 1
                state["monsters"][0]["ac"] = 20
                if len(state["monsters"]) > 1:
                    state["monsters"][1]["alive"] = False
                record.state = json.dumps(state)
                await db.commit()

            attack_resp = await client.post(f"/api/sessions/{session_id}/act", json={
                "action": "attack",
                "target_id": "goblin_1",
            })
            assert attack_resp.status_code == 200
            assert attack_resp.json()["session"]["status"] == "won"
            player = attack_resp.json()["session"]["player"]
            assert player["xp"] > 0
            assert player["gold"] > 0

            char_get_resp = await client.get(f"/api/characters/{char_id}")
            assert char_get_resp.status_code == 200
            updated = char_get_resp.json()["character"]
            assert updated["xp"] > initial_xp
            assert updated["gold"] > 0


@pytest.mark.asyncio
async def test_save_progression_persists_mid_session():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "SaveTest",
                "seed": 1,
            })
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]
            initial_gold = char_resp.json()["character"].get("gold", 0)

            session_resp = await client.post("/api/sessions", json={
                "character_id": char_id,
                "module_id": "sample_lair",
            })
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["players"][0]["xp"] = 75
                state["players"][0]["gold"] = 42
                state["players"][0]["hp"] = 8
                state["players"][0]["max_hp"] = 12
                state["players"][0]["level"] = 2
                state["players"][0].setdefault("session_loot", []).append({
                    "instance_id": "loot01",
                    "item_id": "healing_potion",
                    "name": "Potion of Healing",
                    "type": "potion",
                    "slot": "consumable",
                    "effects": {"hp_restore": 10},
                })
                record.state = json.dumps(state)
                await db.commit()

            save_resp = await client.post(f"/api/sessions/{session_id}/save")
            assert save_resp.status_code == 200
            assert save_resp.json()["saved"] is True
            assert char_id in save_resp.json()["character_ids"]

            char_get_resp = await client.get(f"/api/characters/{char_id}")
            assert char_get_resp.status_code == 200
            updated = char_get_resp.json()["character"]
            assert updated["xp"] == 75
            assert updated["gold"] == 42
            assert updated["hit_points"] == 8
            assert updated["max_hp"] == 12
            assert updated["level"] == 2
            assert any(i.get("instance_id") == "loot01" for i in updated.get("inventory", []))

            # A second save on the now-clean session loot should not duplicate the item.
            save_resp2 = await client.post(f"/api/sessions/{session_id}/save")
            assert save_resp2.status_code == 200
            char_get_resp2 = await client.get(f"/api/characters/{char_id}")
            inventory = char_get_resp2.json()["character"].get("inventory", [])
            assert sum(1 for i in inventory if i.get("instance_id") == "loot01") == 1


@pytest.mark.asyncio
async def test_save_progression_rejects_won_session():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "WonSaveTest",
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

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["status"] = "won"
                record.state = json.dumps(state)
                record.status = "won"
                await db.commit()

            save_resp = await client.post(f"/api/sessions/{session_id}/save")
            assert save_resp.status_code == 400


@pytest.mark.asyncio
async def test_advance_campaign_session_to_next_module():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            campaign_resp = await client.post("/api/campaigns", json={
                "name": "Journey",
                "password": "secret",
                "module_ids": ["sample_lair", "sunken_crypt"],
            })
            assert campaign_resp.status_code == 200
            campaign_id = campaign_resp.json()["campaign"]["id"]

            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "Journeyer",
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

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["monsters"][0]["x"] = state["player"]["x"] + 1
                state["monsters"][0]["y"] = state["player"]["y"]
                state["monsters"][0]["hp"] = 1
                state["monsters"][0]["ac"] = 20
                if len(state["monsters"]) > 1:
                    state["monsters"][1]["alive"] = False
                record.state = json.dumps(state)
                await db.commit()

            attack_resp = await client.post(f"/api/sessions/{session_id}/act", json={
                "action": "attack",
                "target_id": "goblin_1",
            })
            assert attack_resp.status_code == 200
            assert attack_resp.json()["session"]["status"] == "won"

            advance_resp = await client.post(f"/api/sessions/{session_id}/advance")
            assert advance_resp.status_code == 200
            advanced = advance_resp.json()["session"]
            assert advanced["status"] == "active"
            assert advanced["module_id"] == "sunken_crypt"
            assert len(advanced["monsters"]) == 4

            get_resp = await client.get(f"/api/sessions/{session_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["session"]["module_id"] == "sunken_crypt"


@pytest.mark.asyncio
async def test_dm_spawn_and_prop_endpoints():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            campaign_resp = await client.post("/api/campaigns", json={
                "name": "DM Tools",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert campaign_resp.status_code == 200
            campaign_id = campaign_resp.json()["campaign"]["id"]

            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "DmTester",
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
            player = session_resp.json()["session"]["player"]

            spawn_resp = await client.post(f"/api/sessions/{session_id}/dm/spawn", json={
                "name": "goblin",
                "x": player["x"] + 1,
                "y": player["y"],
                "scale": 2,
            })
            assert spawn_resp.status_code == 200
            spawned = spawn_resp.json()["session"]["monsters"][-1]
            assert spawned["max_hp"] >= 2
            assert "x2" in spawned["name"]

            prop_resp = await client.post(f"/api/sessions/{session_id}/dm/prop", json={
                "type": "torch",
                "x": player["x"] + 2,
                "y": player["y"],
            })
            assert prop_resp.status_code == 200
            assert prop_resp.json()["session"]["props"][0]["type"] == "torch"

            clear_resp = await client.post(f"/api/sessions/{session_id}/dm/prop", json={
                "type": "clear",
                "x": player["x"] + 2,
                "y": player["y"],
            })
            assert clear_resp.status_code == 200
            assert len(clear_resp.json()["session"]["props"]) == 0


@pytest.mark.asyncio
async def test_dm_trap_endpoint():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            campaign_resp = await client.post("/api/campaigns", json={
                "name": "DM Traps",
                "password": "secret",
                "module_ids": ["sample_lair"],
            })
            assert campaign_resp.status_code == 200
            campaign_id = campaign_resp.json()["campaign"]["id"]

            char_resp = await client.post("/api/characters", json={
                "mode": "normal",
                "ancestry": "human",
                "classes": ["fighter"],
                "name": "TrapTester",
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
            player = session_resp.json()["session"]["player"]

            trap_resp = await client.post(f"/api/sessions/{session_id}/dm/trap", json={
                "x": player["x"] + 1,
                "y": player["y"],
                "damage": "2d6",
            })
            assert trap_resp.status_code == 200
            traps = trap_resp.json()["session"]["traps"]
            assert len(traps) == 1
            assert traps[0]["x"] == player["x"] + 1
            assert traps[0]["y"] == player["y"]
            assert traps[0]["damage"] == "2d6"
