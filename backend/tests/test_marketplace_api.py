import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.config import SETTINGS
from backend.app.db import AdventureRecord, AsyncSessionLocal, CustomRulesetRecord
from backend.app.main import fastapi_app


@pytest.fixture
def cleanup_marketplace_adventures():
    """Remove adventures created by marketplace tests from the DB and filesystem."""
    created: set[str] = set()
    yield created

    async def _clean():
        async with AsyncSessionLocal() as db:
            for adv_id in created:
                result = await db.execute(select(AdventureRecord).where(AdventureRecord.id == adv_id))
                record = result.scalar_one_or_none()
                if record:
                    await db.delete(record)
                path = SETTINGS.module_root / adv_id / "adventure.yaml"
                if path.exists():
                    path.unlink()
                parent = path.parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
            await db.commit()

    import asyncio

    asyncio.run(_clean())


@pytest.fixture
def cleanup_marketplace_rulesets():
    """Remove custom rulesets created by marketplace tests from the DB."""
    created: set[str] = set()
    yield created

    async def _clean():
        async with AsyncSessionLocal() as db:
            for ruleset_id in created:
                result = await db.execute(select(CustomRulesetRecord).where(CustomRulesetRecord.id == ruleset_id))
                record = result.scalar_one_or_none()
                if record:
                    await db.delete(record)
            await db.commit()

    import asyncio

    asyncio.run(_clean())


@pytest.mark.asyncio
async def test_publish_adventure_and_list_and_rate(cleanup_marketplace_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Create an adventure as account 1.
            create = await client.post("/api/modules/adventures", json={"title": "Marketplace Adventure", "ruleset_id": "osric"})
            assert create.status_code == 200
            adv = create.json()["adventure"]
            adv_id = adv["id"]
            cleanup_marketplace_adventures.add(adv_id)
            assert adv["status"] == "draft"
            assert adv["visibility"] == "private"

            # Publish it publicly with tags.
            pub = await client.post(
                f"/api/modules/{adv_id}/publish",
                json={"visibility": "public", "tags": ["dungeon", "test"]},
            )
            assert pub.status_code == 200
            published = pub.json()["adventure"]
            assert published["status"] == "published"
            assert published["visibility"] == "public"
            assert set(published["tags"]) == {"dungeon", "test"}

            # List marketplace and find it.
            market = await client.get("/api/marketplace/adventures")
            assert market.status_code == 200
            adventures = market.json()["adventures"]
            found = next((a for a in adventures if a["id"] == adv_id), None)
            assert found is not None
            assert found["title"] == "Marketplace Adventure"

            # Filter by tag.
            tagged = await client.get("/api/marketplace/adventures?tags=dungeon")
            assert tagged.status_code == 200
            assert any(a["id"] == adv_id for a in tagged.json()["adventures"])

            # Filter by non-matching tag.
            none = await client.get("/api/marketplace/adventures?tags=space")
            assert none.status_code == 200
            assert not any(a["id"] == adv_id for a in none.json()["adventures"])

            # Rate it.
            rate = await client.post(f"/api/marketplace/adventures/{adv_id}/rate", json={"rating": 5})
            assert rate.status_code == 200
            rated = rate.json()
            assert rated["average_rating"] == 5.0
            assert rated["adventure"]["rating_count"] == 1

            # min_rating filter should now include it.
            min_rate = await client.get("/api/marketplace/adventures?min_rating=4.5")
            assert min_rate.status_code == 200
            assert any(a["id"] == adv_id for a in min_rate.json()["adventures"])


@pytest.mark.asyncio
async def test_fork_adventure_is_private_draft(cleanup_marketplace_adventures):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Owner account creates and publishes an adventure.
            create = await client.post("/api/modules/adventures", json={"title": "Forkable Adventure"})
            assert create.status_code == 200
            adv_id = create.json()["adventure"]["id"]
            cleanup_marketplace_adventures.add(adv_id)

            pub = await client.post(f"/api/modules/{adv_id}/publish", json={"visibility": "public"})
            assert pub.status_code == 200

            # Another account forks it.
            fork = await client.post(
                f"/api/marketplace/adventures/{adv_id}/fork",
                headers={"X-Tenshin-Dev-Account": "2"},
            )
            assert fork.status_code == 200
            forked = fork.json()["adventure"]
            fork_id = forked["id"]
            cleanup_marketplace_adventures.add(fork_id)
            assert forked["status"] == "draft"
            assert forked["visibility"] == "private"
            assert forked["parent_id"] == adv_id
            assert forked["account_id"] == 2
            assert forked["title"] == "Forkable Adventure (fork)"

            # Account 2 can read its fork in S3 format.
            fmt = await client.get(f"/api/modules/{fork_id}/format", headers={"X-Tenshin-Dev-Account": "2"})
            assert fmt.status_code == 200
            assert fmt.json()["data"]["module"]["title"] == "Forkable Adventure (fork)"

            # Account 2 cannot publish/unpublish the original.
            bad_pub = await client.post(
                f"/api/modules/{adv_id}/unpublish",
                headers={"X-Tenshin-Dev-Account": "2"},
            )
            assert bad_pub.status_code == 403


@pytest.mark.asyncio
async def test_publish_ruleset_and_list_and_rate(cleanup_marketplace_rulesets):
    async with LifespanManager(fastapi_app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as client:
            # Create a custom ruleset.
            create = await client.post(
                "/api/rulesets",
                json={
                    "base_ruleset_id": "osric",
                    "name": "Marketplace Ruleset",
                    "description": "A shared custom ruleset.",
                    "overrides": {"default_damage_expr": "1d8"},
                    "tags": ["osric", "homebrew"],
                },
            )
            assert create.status_code == 200
            ruleset = create.json()["ruleset"]
            ruleset_id = ruleset["id"]
            cleanup_marketplace_rulesets.add(ruleset_id)
            assert ruleset["status"] == "draft"

            # Publish it publicly.
            pub = await client.post(
                f"/api/rulesets/{ruleset_id}/publish",
                json={"visibility": "public"},
            )
            assert pub.status_code == 200
            published = pub.json()["ruleset"]
            assert published["status"] == "published"
            assert published["visibility"] == "public"

            # List marketplace.
            market = await client.get("/api/marketplace/rulesets")
            assert market.status_code == 200
            rulesets = market.json()["rulesets"]
            found = next((r for r in rulesets if r["id"] == ruleset_id), None)
            assert found is not None
            assert found["name"] == "Marketplace Ruleset"

            # Rate it.
            rate = await client.post(f"/api/marketplace/rulesets/{ruleset_id}/rate", json={"rating": 4})
            assert rate.status_code == 200
            rated = rate.json()
            assert rated["average_rating"] == 4.0
            assert rated["ruleset"]["rating_count"] == 1
