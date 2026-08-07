import json
import pytest
import yaml
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport

from backend.app.config import SETTINGS
from backend.app.main import fastapi_app


SAMPLE_ADVENTURE = {
    "module": {
        "title": "The Test Tombs",
        "version": "0.1",
        "party_guidance": {"size": [4, 6], "total_levels": [8, 12]},
        "background": "A sealed tomb ripe for plunder.",
        "start": "entrance",
    },
    "regions": [
        {
            "id": "upper_tombs",
            "areas": ["entrance", "hall"],
            "check": {"chance": "1-in-6", "every": "3 turns"},
            "table": {
                "die": "d6",
                "entries": [
                    {"roll": 1, "monster": "goblin", "count": "1d6"},
                ],
            },
        }
    ],
    "areas": [
        {
            "id": "entrance",
            "name": "Dusty Entrance",
            "description": "A narrow passage leads east.",
            "exits": [{"to": "hall", "kind": "passage"}],
            "discoveries": [
                {
                    "what": "a rusted iron key",
                    "trigger": {"action": "search", "scope": "sarcophagus"},
                }
            ],
        },
        {
            "id": "hall",
            "name": "Grand Hall",
            "description": "Pillars line the hall.",
            "exits": [{"to": "entrance", "kind": "passage"}],
            "monsters": [{"monster": "goblin", "count": 2}],
        },
    ],
    "monsters": [
        {
            "id": "tomb_guardian",
            "name": "Tomb Guardian",
            "hit_dice": "2",
            "armour_class": 6,
        }
    ],
    "items": [
        {
            "id": "key_of_warding",
            "name": "Key of Warding",
            "type": "key",
        }
    ],
    "mechanics": [
        {
            "id": "tomb_seal",
            "name": "Sealed Door",
            "prose": "The door opens only with the Key of Warding.",
            "trigger": {"action": "touch", "scope": "sealed_door"},
        }
    ],
}


@pytest.fixture
def cleanup_imported_modules():
    """Remove any modules created by import tests after the test runs."""
    created: set[str] = set()
    yield created
    for slug in created:
        path = SETTINGS.module_root / slug / "adventure.yaml"
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


@pytest.mark.asyncio
async def test_validate_valid_adventure():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/validate", json=SAMPLE_ADVENTURE)
            assert resp.status_code == 200
            body = resp.json()
            assert body["valid"] is True
            assert body["errors"] == []


@pytest.mark.asyncio
async def test_validate_yaml_payload():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            payload = yaml.safe_dump(SAMPLE_ADVENTURE)
            resp = await client.post(
                "/api/modules/validate",
                content=payload,
                headers={"content-type": "application/yaml"},
            )
            assert resp.status_code == 200
            assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_validate_missing_area_exit_target():
    bad = json.loads(json.dumps(SAMPLE_ADVENTURE))
    bad["areas"][0]["exits"][0]["to"] = "nonexistent"

    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/validate", json=bad)
            assert resp.status_code == 200
            body = resp.json()
            assert body["valid"] is False
            assert any("nonexistent" in err and "does not exist" in err for err in body["errors"])


@pytest.mark.asyncio
async def test_validate_unreachable_area():
    bad = json.loads(json.dumps(SAMPLE_ADVENTURE))
    bad["areas"].append({
        "id": "secret_vault",
        "name": "Secret Vault",
        "exits": [],
    })

    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/validate", json=bad)
            assert resp.status_code == 200
            body = resp.json()
            assert body["valid"] is False
            assert any("secret_vault" in err and "unreachable" in err for err in body["errors"])


@pytest.mark.asyncio
async def test_validate_unrecognised_trigger():
    bad = json.loads(json.dumps(SAMPLE_ADVENTURE))
    bad["areas"][0]["discoveries"][0]["trigger"]["action"] = "juggle"

    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/validate", json=bad)
            assert resp.status_code == 200
            body = resp.json()
            assert body["valid"] is False
            assert any("juggle" in err and "not recognised" in err for err in body["errors"])


@pytest.mark.asyncio
async def test_import_and_format_roundtrip(cleanup_imported_modules):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/import", json=SAMPLE_ADVENTURE)
            assert resp.status_code == 200
            body = resp.json()
            assert body["format"] == "s3"
            assert body["title"] == "The Test Tombs"
            slug = body["module_id"]
            cleanup_imported_modules.add(slug)

            fmt_resp = await client.get(f"/api/modules/{slug}/format")
            assert fmt_resp.status_code == 200
            fmt = fmt_resp.json()
            assert fmt["format"] == "s3"
            assert fmt["data"]["module"]["title"] == "The Test Tombs"
            assert len(fmt["data"]["areas"]) == 2


@pytest.mark.asyncio
async def test_import_invalid_payload_fails():
    bad = json.loads(json.dumps(SAMPLE_ADVENTURE))
    bad["areas"][0]["exits"][0]["to"] = "nowhere"

    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/import", json=bad)
            assert resp.status_code == 422
            assert "nowhere" in str(resp.json()["detail"]["errors"])


@pytest.mark.asyncio
async def test_list_modules_includes_tactical_and_s3(cleanup_imported_modules):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.post("/api/modules/import", json=SAMPLE_ADVENTURE)
            assert resp.status_code == 200
            slug = resp.json()["module_id"]
            cleanup_imported_modules.add(slug)

            list_resp = await client.get("/api/modules")
            assert list_resp.status_code == 200
            modules = list_resp.json()["modules"]
            assert any(m["id"] == "sample_lair" and m["format"] == "tactical" for m in modules)
            assert any(m["id"] == slug and m["format"] == "s3" for m in modules)


@pytest.mark.asyncio
async def test_get_module_still_loads_tactical_module():
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            resp = await client.get("/api/modules/sample_lair")
            assert resp.status_code == 200
            mod = resp.json()["module"]
            assert mod["name"] == "The Goblin Lair"
            assert mod["map"]["width"] == 18
