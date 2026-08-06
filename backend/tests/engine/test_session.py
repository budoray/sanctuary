import pytest
from types import SimpleNamespace

from backend.app.engine import character as char_engine
from backend.app.engine import module, session
from backend.app.engine.narrator import Narrator

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def disable_ollama_narration():
    """Keep Phase 5 session tests fast by disabling Ollama calls."""
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


async def test_new_game(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    assert st["module_id"] == "sample_lair"
    assert st["phase"] == "player"
    assert st["player"]["name"] == "Test"
    assert len(st["monsters"]) == 2


async def test_player_move(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st = await session.act(st, sample_module, "move", x=3, y=2)
    assert st["player"]["x"] == 3


async def test_player_move_into_wall_fails(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    with pytest.raises(ValueError):
        await session.act(st, sample_module, "move", x=0, y=0)


async def test_player_attack_goblin(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    # Walk next to goblin_1 at (14,10). Player starts at (2,2).
    path = [
        (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2),
        (13, 2), (14, 2), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7), (14, 8), (14, 9),
    ]
    for x, y in path:
        st = await session.act(st, sample_module, "move", x=x, y=y)
        st["phase"] = "player"  # keep it player turn for movement
    st = await session.act(st, sample_module, "attack", target_id="goblin_1")
    assert st["phase"] == "dm"


async def test_dm_turn_advances_turn(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st = await session.act(st, sample_module, "end_turn")
    assert st["phase"] == "dm"
    st = await session.act(st, sample_module, "dm_turn")
    assert st["phase"] == "player"
    assert st["turn"] == 2


async def test_new_game_with_timer(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42, turn_timer_seconds=30)
    assert st["turn_timer_seconds"] == 30
    assert st["turn_deadline"] is not None


async def test_timer_deadline_resets_after_dm_turn(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42, turn_timer_seconds=30)
    st = await session.act(st, sample_module, "end_turn")
    assert st["turn_deadline"] is None
    st = await session.act(st, sample_module, "dm_turn")
    assert st["phase"] == "player"
    assert st["turn_deadline"] is not None


async def test_add_player_increases_party(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    hero2 = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["fighter"], name="Elara")
    token = await session.add_player(st, sample_module, hero2, "char2", account_id=2)
    assert token["id"] == "player_1"
    assert len(st["players"]) == 2
    assert st["players"][1]["name"] == "Elara"


async def test_add_player_finds_free_tile(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    # Occupy the default spawn tile with a monster-like token so the new player must spread out.
    st["players"][0]["x"] = sample_module.player_start[0]
    st["players"][0]["y"] = sample_module.player_start[1]
    hero2 = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["fighter"], name="Bruenor")
    token = await session.add_player(st, sample_module, hero2, "char3", account_id=3)
    assert (token["x"], token["y"]) != (sample_module.player_start[0], sample_module.player_start[1])
    assert sample_module.map.walkable(token["x"], token["y"])
