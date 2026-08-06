import random
from types import SimpleNamespace

import pytest

from backend.app.engine.narrator import Narrator

pytestmark = pytest.mark.asyncio


@pytest.fixture
def disabled_settings():
    return SimpleNamespace(
        ollama_enabled=False,
        ollama_timeout=0.1,
        ollama_host="",
        ollama_model="",
    )


async def test_opening_uses_ollama_when_enabled():
    async def fake_generate(prompt, **kwargs):
        return "The torch sputters against ancient stone."

    narrator = Narrator(
        settings=SimpleNamespace(
            ollama_enabled=True,
            ollama_timeout=1.0,
            ollama_host="http://localhost:11434",
            ollama_model="test-model",
        ),
        ollama_generate=fake_generate,
    )
    line = await narrator.narrate_opening(random.Random(1))
    assert "torch sputters" in line


async def test_opening_falls_back_when_ollama_fails(disabled_settings):
    narrator = Narrator(settings=disabled_settings)
    line = await narrator.narrate_opening(random.Random(1))
    assert isinstance(line, str)
    assert len(line) > 0


async def test_move_falls_back_to_template(disabled_settings):
    narrator = Narrator(settings=disabled_settings)
    line = await narrator.narrate_move(
        {"id": "goblin", "name": "Goblin", "type": "monster"},
        random.Random(1),
    )
    assert "Goblin" in line


async def test_attack_returns_list_and_falls_back(disabled_settings):
    narrator = Narrator(settings=disabled_settings)
    lines = await narrator.narrate_attack(
        attacker={"id": "player", "name": "Hero", "type": "player"},
        target={"id": "goblin", "name": "Goblin", "type": "monster"},
        hit=True,
        fatal=False,
        rng=random.Random(1),
    )
    assert isinstance(lines, list)
    assert len(lines) > 0


async def test_room_uses_ollama_when_enabled():
    async def fake_generate(prompt, **kwargs):
        return "Moss clings to the ancient stones."

    narrator = Narrator(
        settings=SimpleNamespace(
            ollama_enabled=True,
            ollama_timeout=1.0,
            ollama_host="http://localhost:11434",
            ollama_model="test-model",
        ),
        ollama_generate=fake_generate,
    )
    line = await narrator.narrate_room("The Sunken Crypt", room_type="crypt", rng=random.Random(1))
    assert "Moss clings" in line


async def test_room_falls_back_when_ollama_disabled(disabled_settings):
    narrator = Narrator(settings=disabled_settings)
    line = await narrator.narrate_room("The Sunken Crypt", room_type="crypt", rng=random.Random(1))
    assert isinstance(line, str)
    assert len(line) > 0


async def test_trap_falls_back_when_ollama_disabled(disabled_settings):
    narrator = Narrator(settings=disabled_settings)
    line = await narrator.narrate_trap("hidden spikes", triggered=True, rng=random.Random(1))
    assert isinstance(line, str)
    assert len(line) > 0


async def test_victory_uses_ollama_when_enabled():
    async def fake_generate(prompt, **kwargs):
        return "Silence claims the chamber."

    narrator = Narrator(
        settings=SimpleNamespace(
            ollama_enabled=True,
            ollama_timeout=1.0,
            ollama_host="http://localhost:11434",
            ollama_model="test-model",
        ),
        ollama_generate=fake_generate,
    )
    line = await narrator.narrate_victory(random.Random(1))
    assert "Silence claims" in line
