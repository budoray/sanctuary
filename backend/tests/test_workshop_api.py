import json
import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.config import SETTINGS
from backend.app.main import fastapi_app


@pytest.fixture
def cleanup_workshop_adventures():
    """Remove adventures created by workshop tests from the DB and filesystem."""
    created: set[str] = set()
    yield created
    for adv_id in created:
        path = SETTINGS.module_root / adv_id / "adventure.yaml"
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


@pytest.mark.asyncio
async def test_create_adventure(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Workshop Test", "ruleset_id": "osric"})
            assert resp.status_code == 200
            body = resp.json()
            adv = body["adventure"]
            assert adv["title"] == "Workshop Test"
            assert adv["data"]["module"]["start"] == "start"
            cleanup_workshop_adventures.add(adv["id"])


@pytest.mark.asyncio
async def test_add_area_and_list(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Area Test"})
            assert resp.status_code == 200
            adv_id = resp.json()["adventure"]["id"]
            cleanup_workshop_adventures.add(adv_id)

            area = {
                "id": "hall",
                "name": "Grand Hall",
                "description": "A large hall.",
                "width": 6,
                "height": 6,
                "tiles": ["000000"] * 6,
                "start_x": 1,
                "start_y": 1,
                "entities": [],
            }
            post = await client.post(f"/api/modules/{adv_id}/areas", json=area)
            assert post.status_code == 200

            get = await client.get(f"/api/modules/{adv_id}/areas")
            assert get.status_code == 200
            areas = get.json()["areas"]
            assert any(a["id"] == "hall" for a in areas)


@pytest.mark.asyncio
async def test_add_exit(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Exit Test"})
            assert resp.status_code == 200
            adv_id = resp.json()["adventure"]["id"]
            cleanup_workshop_adventures.add(adv_id)

            await client.post(f"/api/modules/{adv_id}/areas", json={
                "id": "hall",
                "name": "Hall",
                "width": 6,
                "height": 6,
                "tiles": ["000000"] * 6,
                "start_x": 1,
                "start_y": 1,
                "entities": [],
            })
            exit_resp = await client.post(f"/api/modules/{adv_id}/areas/start/exits", json={
                "to": "hall",
                "kind": "passage",
                "from_x": 7,
                "from_y": 1,
                "to_x": 1,
                "to_y": 1,
            })
            assert exit_resp.status_code == 200
            data = exit_resp.json()["area"]
            assert any(e["to"] == "hall" for e in data.get("exits", []))


@pytest.mark.asyncio
async def test_compile_adventure(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Compile Test"})
            assert resp.status_code == 200
            adv_id = resp.json()["adventure"]["id"]
            cleanup_workshop_adventures.add(adv_id)

            await client.post(f"/api/modules/{adv_id}/areas", json={
                "id": "hall",
                "name": "Hall",
                "width": 6,
                "height": 6,
                "tiles": ["000000"] * 6,
                "start_x": 1,
                "start_y": 1,
                "entities": [],
            })
            await client.post(f"/api/modules/{adv_id}/areas/start/exits", json={
                "to": "hall",
                "kind": "passage",
                "from_x": 7,
                "from_y": 1,
                "to_x": 1,
                "to_y": 1,
            })
            comp = await client.post(f"/api/modules/{adv_id}/compile")
            assert comp.status_code == 200
            mod = comp.json()["module"]
            assert mod["name"] == "Compile Test"
            assert mod["map"]["width"] > 0
            assert mod["map"]["height"] > 0
            links = mod.get("dungeon_links") or {}
            assert "7,1" in links
            assert links["7,1"]["kind"] == "passage"


@pytest.mark.asyncio
async def test_compile_unreachable_area(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Unreachable Test"})
            assert resp.status_code == 200
            adv_id = resp.json()["adventure"]["id"]
            cleanup_workshop_adventures.add(adv_id)

            await client.post(f"/api/modules/{adv_id}/areas", json={
                "id": "isolated",
                "name": "Isolated Room",
                "width": 4,
                "height": 4,
                "tiles": ["0000"] * 4,
                "start_x": 1,
                "start_y": 1,
                "entities": [],
            })
            comp = await client.post(f"/api/modules/{adv_id}/compile")
            assert comp.status_code == 422
            errors = comp.json()["detail"]["errors"]
            assert any("isolated" in err and "unreachable" in err for err in errors)


@pytest.mark.asyncio
async def test_adventure_owner_only(cleanup_workshop_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/adventures", json={"title": "Owned Test"})
            assert resp.status_code == 200
            adv_id = resp.json()["adventure"]["id"]
            cleanup_workshop_adventures.add(adv_id)

            other = await client.get(f"/api/modules/{adv_id}/areas", headers={"X-Tenshin-Dev-Account": "2"})
            assert other.status_code == 403
