import pytest
from types import SimpleNamespace

from backend.app.engine import character as char_engine
from backend.app.engine import module, session
from backend.app.engine.narrator import Narrator

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def disable_ollama_narration():
    """Keep AI DM tests fast by disabling Ollama calls."""
    original = session.narrator
    session.narrator = Narrator(
        settings=SimpleNamespace(
            ollama_enabled=False,
            ollama_timeout=0.1,
            ollama_host="",
            ollama_model="",
        )
    )
    yield
    session.narrator = original


@pytest.fixture
def sample_module():
    return module.load("sample_lair")


@pytest.fixture
def hero():
    return char_engine.generate(
        seed=1,
        mode="normal",
        ancestry_name="human",
        class_names=["fighter"],
        name="Test",
    )


async def test_monster_moves_toward_and_attacks_player(sample_module, hero):
    st = await session.new_game("ai1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    # Place goblin one tile away so it can step in and attack.
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    await session._run_dm_turn(st, sample_module, session.Dice(seed=42))
    assert any("attacks" in entry for entry in st["log"])


async def test_wounded_monster_with_low_morale_retreats(sample_module, hero):
    st = await session.new_game("ai2", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["max_hp"] = 4
    goblin["hp"] = 2
    goblin["morale_checked_50"] = False
    goblin["x"] = st["player"]["x"] + 2
    goblin["y"] = st["player"]["y"]
    start_x, start_y = goblin["x"], goblin["y"]
    # Search for a seed that causes this goblin to fail its morale check.
    retreated = False
    for seed in range(1, 200):
        test_state = await session.new_game("ai2", sample_module, hero, seed=42)
        test_goblin = test_state["monsters"][0]
        test_goblin["max_hp"] = 4
        test_goblin["hp"] = 2
        test_goblin["morale_checked_50"] = False
        test_goblin["x"] = test_state["player"]["x"] + 2
        test_goblin["y"] = test_state["player"]["y"]
        await session._run_dm_turn(test_state, sample_module, session.Dice(seed=seed))
        if test_goblin.get("retreating"):
            st = test_state
            goblin = test_goblin
            retreated = True
            break
    assert retreated, "could not find a seed that causes retreat"
    assert goblin["x"] != start_x or goblin["y"] != start_y
    assert any("retreats" in entry for entry in st["log"])


async def test_monster_uses_ranged_attack_when_at_range(sample_module, hero):
    st = await session.new_game("ai3", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["ranged_damage"] = "1d6"
    goblin["x"] = st["player"]["x"] + 3
    goblin["y"] = st["player"]["y"]
    initial_hp = st["player"]["hp"]
    await session._run_dm_turn(st, sample_module, session.Dice(seed=42))
    assert any("shoots" in entry for entry in st["log"])


async def test_ai_dm_disabled_when_human_dm_present(sample_module, hero):
    st = await session.new_game("ai4", sample_module, hero, seed=42)
    st["dm_account_id"] = 99
    # Default should disable AI DM when a human DM is present.
    assert session._ai_dm_enabled(st) is False
    st = await session.act(st, sample_module, "end_turn")
    # With a human DM present, the engine waits for the manual dm_turn action.
    assert st["phase"] == session.PHASE_DM


async def test_toggle_ai_dm_by_owner(sample_module, hero):
    st = await session.new_game("ai5", sample_module, hero, seed=42, account_id=1)
    assert st["ai_dm_enabled"] is True
    st = await session.act(st, sample_module, "toggle_ai_dm", account_id=1)
    assert st["ai_dm_enabled"] is False
    assert any("AI DM disabled" in entry for entry in st["log"])
