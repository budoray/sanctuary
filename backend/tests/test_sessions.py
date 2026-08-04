import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from backend.app.main import app


@pytest_asyncio.fixture
async def client():
    async with LifespanManager(app) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_and_move_token(client):
    r = await client.post("/api/sessions")
    assert r.status_code == 200
    data = r.json()
    session_id = data["session_id"]
    state = data["state"]
    assert len(state["map"]["tokens"]) == 2

    hero = next(t for t in state["map"]["tokens"] if t["name"] == "Hero")
    r = await client.post(
        f"/api/sessions/{session_id}/move",
        json={"token_id": hero["id"], "x": 4, "y": 4},
    )
    assert r.status_code == 200
    new_state = r.json()["state"]
    moved = next(t for t in new_state["map"]["tokens"] if t["name"] == "Hero")
    assert moved["x"] == 4
    assert moved["y"] == 4

    r = await client.get(f"/api/sessions/{session_id}")
    assert r.status_code == 200
    loaded = r.json()["state"]
    loaded_hero = next(t for t in loaded["map"]["tokens"] if t["name"] == "Hero")
    assert loaded_hero["x"] == 4
    assert loaded_hero["y"] == 4


@pytest.mark.asyncio
async def test_create_character(client):
    r = await client.post(
        "/api/characters",
        json={"name": "Elara", "race": "Elf", "class": "Magic-User"},
    )
    assert r.status_code == 200
    char = r.json()["character"]
    assert char["name"] == "Elara"
    assert char["race"] == "Elf"
    assert char["class"] == "Magic-User"
    assert char["level"] == 1
    assert set(char["abilities"].keys()) == {"str", "dex", "con", "int", "wis", "cha"}


