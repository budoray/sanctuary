"""Tests for drop-in/drop-out co-op and AI takeover of absent players."""
import json

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.db import SessionRecord, get_db
from backend.app.engine import module as module_engine, session as session_engine
from backend.app.main import fastapi_app


@pytest.mark.asyncio
async def test_player_leave_becomes_ai_controlled():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            owner_char_resp = await client.post(
                "/api/characters",
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "Owner",
                    "seed": 1,
                },
            )
            assert owner_char_resp.status_code == 200
            owner_char_id = owner_char_resp.json()["character"]["id"]

            instance_resp = await client.post(
                "/api/sessions",
                json={
                    "character_id": owner_char_id,
                    "module_id": "sample_lair",
                    "visibility": "public",
                },
            )
            assert instance_resp.status_code == 200
            instance_id = instance_resp.json()["session"]["id"]

            headers = {"X-Tenshin-Dev-Account": "2"}
            joiner_char_resp = await client.post(
                "/api/characters",
                headers=headers,
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "Joiner",
                    "seed": 7,
                },
            )
            assert joiner_char_resp.status_code == 200
            joiner_char_id = joiner_char_resp.json()["character"]["id"]

            join_resp = await client.post(
                f"/api/sessions/{instance_id}/join",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            assert join_resp.status_code == 200
            assert len(join_resp.json()["session"]["players"]) == 2

            leave_resp = await client.post(
                f"/api/sessions/{instance_id}/leave",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            assert leave_resp.status_code == 200
            session = leave_resp.json()["session"]
            assert len(session["players"]) == 2
            joiner = next(
                p
                for p in session["players"]
                if p.get("character_id") == joiner_char_id
            )
            assert joiner["ai_controlled"] is True


@pytest.mark.asyncio
async def test_ai_controlled_player_takes_turn():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            char_resp = await client.post(
                "/api/characters",
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "AITest",
                    "seed": 1,
                },
            )
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            session_resp = await client.post(
                "/api/sessions",
                json={"character_id": char_id, "module_id": "sample_lair"},
            )
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["players"][0]["ai_controlled"] = True
                # Clear any surprise round so the AI player can act immediately.
                state.pop("surprise_round", None)
                state.pop("surprise_free_side", None)
                # Make the player durable and the monster a one-hit kill so the
                # AI action is deterministic and the test isn't at the mercy of
                # dice rolls.
                state["players"][0]["hp"] = 100
                state["players"][0]["max_hp"] = 100
                state["players"][0]["damage"] = "1d20+10"
                # Place a monster adjacent so the AI can attack it.
                state["monsters"][0]["x"] = state["players"][0]["x"] + 1
                state["monsters"][0]["y"] = state["players"][0]["y"]
                state["monsters"][0]["ac"] = 20  # guaranteed hit
                state["monsters"][0]["hp"] = 1
                initial_hp = state["monsters"][0]["hp"]
                initial_turn = state["turn"]
                initial_phase = state["phase"]
                record.state = json.dumps(state)
                await db.commit()

            mod = module_engine.load("sample_lair")
            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state = await session_engine.run_ai_players(state, mod)
                record.state = json.dumps(state)
                await db.commit()

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                assert state["monsters"][0]["hp"] < initial_hp
                # The AI taking its turn must advance the game: either the
                # phase moves out of player, a new round starts, or combat ends.
                assert (
                    state["phase"] != initial_phase
                    or state["turn"] > initial_turn
                    or state["status"] != "active"
                )


@pytest.mark.asyncio
async def test_player_rejoins_and_regains_control():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            owner_char_resp = await client.post(
                "/api/characters",
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "Owner",
                    "seed": 1,
                },
            )
            assert owner_char_resp.status_code == 200
            owner_char_id = owner_char_resp.json()["character"]["id"]

            instance_resp = await client.post(
                "/api/sessions",
                json={
                    "character_id": owner_char_id,
                    "module_id": "sample_lair",
                    "visibility": "public",
                },
            )
            assert instance_resp.status_code == 200
            instance_id = instance_resp.json()["session"]["id"]

            headers = {"X-Tenshin-Dev-Account": "2"}
            joiner_char_resp = await client.post(
                "/api/characters",
                headers=headers,
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "Joiner",
                    "seed": 7,
                },
            )
            assert joiner_char_resp.status_code == 200
            joiner_char_id = joiner_char_resp.json()["character"]["id"]

            await client.post(
                f"/api/sessions/{instance_id}/join",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            await client.post(
                f"/api/sessions/{instance_id}/leave",
                headers=headers,
                json={"character_id": joiner_char_id},
            )

            rejoin_resp = await client.post(
                f"/api/sessions/{instance_id}/join",
                headers=headers,
                json={"character_id": joiner_char_id},
            )
            assert rejoin_resp.status_code == 200
            session = rejoin_resp.json()["session"]
            joiner = next(
                p
                for p in session["players"]
                if p.get("character_id") == joiner_char_id
            )
            assert joiner["ai_controlled"] is False
            assert len(session["players"]) == 2


@pytest.mark.asyncio
async def test_multi_player_session_advances_through_all_players_then_monsters():
    from backend.app.engine import character as char_engine

    mod = module_engine.load("sample_lair")
    hero = char_engine.generate(
        seed=1, mode="normal", ancestry_name="human", class_names=["fighter"], name="Owner"
    )
    st = await session_engine.new_game("coop1", mod, hero, seed=42)

    hero2 = char_engine.generate(
        seed=7, mode="normal", ancestry_name="human", class_names=["fighter"], name="Joiner"
    )
    await session_engine.add_player(st, mod, hero2, "char2", account_id=2)

    # Player 1 ends turn, advancing to the joiner's turn.
    st = await session_engine.act(st, mod, "end_turn")
    assert st["active_player_index"] == 1

    # The joiner is AI-controlled; ending their turn triggers the AI action and
    # then the DM turn, starting a new round back at player 1.
    st["players"][1]["ai_controlled"] = True
    st = await session_engine.act(st, mod, "end_turn")
    assert st["turn"] >= 2
    assert st["phase"] == "player"
    assert st["active_player_index"] == 0


@pytest.mark.asyncio
async def test_take_control_endpoint_resumes_human_control():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            char_resp = await client.post(
                "/api/characters",
                json={
                    "mode": "normal",
                    "ancestry": "human",
                    "classes": ["fighter"],
                    "name": "Controller",
                    "seed": 1,
                },
            )
            assert char_resp.status_code == 200
            char_id = char_resp.json()["character"]["id"]

            session_resp = await client.post(
                "/api/sessions",
                json={"character_id": char_id, "module_id": "sample_lair"},
            )
            assert session_resp.status_code == 200
            session_id = session_resp.json()["session"]["id"]

            async for db in get_db():
                result = await db.execute(
                    select(SessionRecord).where(SessionRecord.id == session_id)
                )
                record = result.scalar_one()
                state = json.loads(record.state)
                state["players"][0]["ai_controlled"] = True
                record.state = json.dumps(state)
                await db.commit()

            take_resp = await client.post(
                f"/api/sessions/{session_id}/take-control",
                json={"character_id": char_id},
            )
            assert take_resp.status_code == 200
            assert take_resp.json()["control"] is True
            assert take_resp.json()["session"]["players"][0]["ai_controlled"] is False
