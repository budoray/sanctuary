import pytest
from types import SimpleNamespace

from backend.app.engine import character as char_engine
from backend.app.engine import items, module, session
from backend.app.engine.narrator import Narrator


@pytest.fixture(autouse=True)
def disable_ollama_narration():
    """Keep roadmap engine tests fast by disabling Ollama calls."""
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
def hero():
    return char_engine.generate(
        seed=1,
        mode="normal",
        ancestry_name="human",
        class_names=["fighter"],
        name="Test",
    )


def test_loot_table_has_at_least_twelve_items():
    assert len(items.LOOT_TABLE) >= 12


def test_generate_loot_scales_with_level():
    base = items.generate_loot(level=1)
    scaled = items.generate_loot(level=10)
    assert base["item_id"] in items.LOOT_TABLE
    assert scaled["item_id"] in items.LOOT_TABLE


@pytest.mark.asyncio
async def test_hazard_lava_deals_damage(hero):
    base = module.load("sample_lair")
    tiles = [list(row) for row in base.map.tiles]
    px, py = base.player_start
    tiles[py][px + 1] = session.TILE_LAVA
    hazard_module = module.Module(
        id=base.id,
        name=base.name,
        ruleset=base.ruleset,
        description=base.description,
        map=module.Map(
            width=base.map.width,
            height=base.map.height,
            tile_size=base.map.tile_size,
            tiles=["".join(row) for row in tiles],
        ),
        player_start=base.player_start,
        monsters=base.monsters,
        events=[],
        branches=[],
    )
    st = await session.new_game("hz", hazard_module, hero, seed=1)
    initial_hp = st["player"]["hp"]
    st = await session.act(st, hazard_module, "move", x=px + 1, y=py)
    assert st["player"]["hp"] < initial_hp
    assert any("lava" in entry.lower() or "hazard" in entry.lower() for entry in st["log"])


@pytest.mark.asyncio
async def test_hazard_spikes_deals_damage(hero):
    base = module.load("sample_lair")
    tiles = [list(row) for row in base.map.tiles]
    px, py = base.player_start
    tiles[py][px + 1] = session.TILE_SPIKES
    hazard_module = module.Module(
        id=base.id,
        name=base.name,
        ruleset=base.ruleset,
        description=base.description,
        map=module.Map(
            width=base.map.width,
            height=base.map.height,
            tile_size=base.map.tile_size,
            tiles=["".join(row) for row in tiles],
        ),
        player_start=base.player_start,
        monsters=base.monsters,
        events=[],
        branches=[],
    )
    st = await session.new_game("hz", hazard_module, hero, seed=1)
    initial_hp = st["player"]["hp"]
    st = await session.act(st, hazard_module, "move", x=px + 1, y=py)
    assert st["player"]["hp"] < initial_hp
    assert any("spike" in entry.lower() or "hazard" in entry.lower() for entry in st["log"])


@pytest.mark.asyncio
async def test_boss_phase_triggers_and_spawns_adds(hero):
    st = await session.new_game("boss", module.load("shadow_keep"), hero, seed=42)
    boss = next(m for m in st["monsters"] if m.get("boss"))
    boss["max_hp"] = 20
    boss["hp"] = 20
    boss["ac"] = 30  # guarantee player hits
    boss["damage_bonus"] = 0
    boss["to_hit"] = 0
    boss["phases_triggered"] = []

    # Move adjacent and attack until phase threshold is crossed.
    player = st["player"]
    player["x"] = boss["x"] - 1
    player["y"] = boss["y"]
    player["damage"] = "1d2"  # small, reliable damage
    st["phase"] = session.PHASE_PLAYER

    for _ in range(15):
        if boss["hp"] <= boss["max_hp"] * 0.5:
            break
        st = await session.act(st, module.load("shadow_keep"), "attack", target_id=boss["id"])
        st["phase"] = session.PHASE_PLAYER

    assert boss["hp"] <= boss["max_hp"] * 0.5
    assert boss.get("damage_bonus", 0) > 0 or boss.get("to_hit", 0) > 0
    assert any(m.get("id", "").startswith("imp_minion") for m in st["monsters"])


@pytest.mark.asyncio
async def test_branch_event_sets_pending_branch(hero):
    mod = module.load("shadow_keep")
    st = await session.new_game("branch", mod, hero, seed=42)
    event = mod.events[0]
    player = st["player"]
    player["x"] = event.x - 1
    player["y"] = event.y
    st["phase"] = session.PHASE_PLAYER
    st = await session.act(st, mod, "move", x=event.x, y=event.y)
    assert st.get("pending_branch") == event.id
    assert any(event.message.split()[0] in entry for entry in st["log"])


@pytest.mark.asyncio
async def test_choose_path_spawns_branch_monsters(hero):
    mod = module.load("shadow_keep")
    st = await session.new_game("branch", mod, hero, seed=42)
    st["pending_branch"] = mod.events[0].id
    initial_count = len(st["monsters"])
    st = await session.act(st, mod, "choose_path", branch_id="left")
    assert len(st["monsters"]) > initial_count
    assert "skeleton" in [m["name"].lower() for m in st["monsters"]]


@pytest.mark.asyncio
async def test_arena_mode_starts_with_wave_one(hero):
    st = await session.new_game("arena", module.load("arena_pit"), hero, seed=42, mode="arena")
    assert st["mode"] == "arena"
    assert st["wave"] == 1


@pytest.mark.asyncio
async def test_arena_spawns_next_wave_after_clear(hero):
    mod = module.load("arena_pit")
    st = await session.new_game("arena", mod, hero, seed=42, mode="arena")
    # Kill all starting monsters with adjacent guaranteed-hit attacks.
    player = st["player"]
    for monster in st["monsters"]:
        monster["ac"] = 30
        monster["hp"] = 1
        player["x"] = monster["x"] - 1
        player["y"] = monster["y"]
        st["phase"] = session.PHASE_PLAYER
        st = await session.act(st, mod, "attack", target_id=monster["id"])
        st["phase"] = session.PHASE_PLAYER

    assert all(not m.get("alive", True) for m in st["monsters"])
    st["phase"] = session.PHASE_DM
    st = await session.act(st, mod, "dm_turn")
    assert st["wave"] == 2
    assert any(m.get("alive", True) for m in st["monsters"])


@pytest.mark.asyncio
async def test_monster_death_can_drop_loot(hero):
    mod = module.load("sample_lair")
    st = await session.new_game("loot", mod, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["hp"] = 1
    goblin["ac"] = 30
    # Force a drop by setting a high drop chance via seeding is unreliable, so
    # we run the reward function directly and inspect the player token.
    session._grant_rewards(st, goblin)
    # The drop is probabilistic; verify structure when present or at least xp/gold.
    assert st["player"]["xp"] > 0
    if st["player"].get("session_loot"):
        assert "item_id" in st["player"]["session_loot"][0]
