import pytest

from backend.app.ai import portraits
from backend.app.config import SETTINGS


@pytest.mark.asyncio
async def test_static_portrait_url_when_pixellab_not_configured(monkeypatch):
    monkeypatch.setattr(SETTINGS, "pixellab_host", None)
    url = await portraits.generate_portrait_url("a prompt", "fighter")
    assert url is None


@pytest.mark.asyncio
async def test_static_portrait_url_uses_class():
    assert portraits.static_portrait_url("fighter") == "/portraits/fighter.png"
    assert portraits.static_portrait_url("Magic-User") == "/portraits/magic-user.png"
    assert portraits.static_portrait_url("unknown") == "/portraits/generic.png"


@pytest.mark.asyncio
async def test_generate_portrait_prefers_image_url(monkeypatch):
    monkeypatch.setattr(SETTINGS, "pixellab_host", "http://pixellab.test")
    monkeypatch.setattr(SETTINGS, "pixellab_key", "secret-key")
    monkeypatch.setattr(SETTINGS, "pixellab_model", "flux")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"image_url": "http://cdn.test/portrait.png"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            assert url == "http://pixellab.test/api/v1/generate"
            assert json["model"] == "flux"
            assert "prompt" in json
            assert headers["Authorization"] == "Bearer secret-key"
            return FakeResponse()

    monkeypatch.setattr("backend.app.ai.portraits.httpx.AsyncClient", FakeClient)

    url = await portraits.generate_portrait_url("a prompt", "thief")
    assert url == "http://cdn.test/portrait.png"


@pytest.mark.asyncio
async def test_generate_portrait_falls_back_to_url_field(monkeypatch):
    monkeypatch.setattr(SETTINGS, "pixellab_host", "http://pixellab.test")

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"url": "http://cdn.test/fallback.png"}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            return FakeResponse()

    monkeypatch.setattr("backend.app.ai.portraits.httpx.AsyncClient", FakeClient)

    url = await portraits.generate_portrait_url("another prompt")
    assert url == "http://cdn.test/fallback.png"


@pytest.mark.asyncio
async def test_generate_portrait_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr(SETTINGS, "pixellab_host", "http://pixellab.test")

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            raise RuntimeError("connection refused")

    monkeypatch.setattr("backend.app.ai.portraits.httpx.AsyncClient", FakeClient)

    url = await portraits.generate_portrait_url("prompt")
    assert url is None


@pytest.mark.asyncio
async def test_build_prompt_includes_name_class_and_ancestry():
    prompt = portraits.build_prompt("Elara", "ranger", "elf")
    assert "Elara" in prompt
    assert "ranger" in prompt
    assert "elf" in prompt
