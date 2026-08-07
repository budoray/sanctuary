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
    st["ai_dm_enabled"] = False
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
    st["ai_dm_enabled"] = False
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


async def test_player_ranged_attack_hits_within_range(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = 5
    goblin["y"] = 2
    goblin["ac"] = 20  # guaranteed hit (descending AC)
    initial_hp = goblin["hp"]
    st = await session.act(st, sample_module, "ranged", target_id=goblin["id"])
    assert goblin["hp"] < initial_hp
    assert st["phase"] == "dm"


async def test_player_ranged_attack_blocked_by_wall(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st["player"]["x"] = 5
    st["player"]["y"] = 5
    goblin = st["monsters"][0]
    # Place goblin beyond the wall at row 3/4 columns 6-9.
    goblin["x"] = 6
    goblin["y"] = 2
    assert not session._line_of_sight(st, sample_module, st["player"]["x"], st["player"]["y"], goblin["x"], goblin["y"])
    with pytest.raises(ValueError, match="line of sight"):
        await session.act(st, sample_module, "ranged", target_id=goblin["id"])


async def test_killing_monster_grants_xp_and_gold(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["hp"] = 1
    goblin["ac"] = 20  # guaranteed hit
    xp_value = goblin.get("xp_value", 50)
    initial_xp = st["player"].get("xp", 0)
    initial_gold = st["player"].get("gold", 0)
    st = await session.act(st, sample_module, "attack", target_id=goblin["id"])
    assert goblin["alive"] is False
    assert st["player"]["xp"] == initial_xp + xp_value
    assert st["player"]["gold"] == initial_gold + xp_value // 10


async def test_killing_monster_triggers_level_up(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["hp"] = 1
    goblin["ac"] = 20  # guaranteed hit
    st["player"]["xp"] = 95
    st["player"]["level"] = 1
    initial_max_hp = st["player"]["max_hp"]
    st = await session.act(st, sample_module, "attack", target_id=goblin["id"])
    assert st["player"]["level"] == 2
    assert st["player"]["xp"] >= 100
    assert st["player"]["max_hp"] > initial_max_hp
    assert any("reaches level 2" in entry for entry in st["log"])


async def test_player_goes_down_at_zero_hp(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["damage"] = "1d4-3"  # max(1, total) always deals 1
    st["player"]["hp"] = 1
    st["player"]["ac"] = 30  # guaranteed hit (descending AC)
    await session._attack(st, goblin, st["player"], session.Dice(seed=42))
    assert st["player"]["hp"] == 0
    assert st["player"]["down"] is True
    assert st["player"]["alive"] is True
    assert st["status"] == session.STATUS_ACTIVE


async def test_player_dies_below_negative_ten(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["damage"] = "1d20+20"  # 21-40 damage, guaranteed below -10
    st["player"]["hp"] = 1
    st["player"]["ac"] = 30  # guaranteed hit
    await session._attack(st, goblin, st["player"], session.Dice(seed=42))
    assert st["player"]["alive"] is False
    assert st["player"]["down"] is True
    assert st["status"] == session.STATUS_LOST


async def test_stabilize_sets_downed_ally_to_one_hp(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    hero2 = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["cleric"], name="Elara")
    await session.add_player(st, sample_module, hero2, "char2", account_id=2)
    # Place player_1 next to the downed active player.
    st["players"][0]["down"] = True
    st["players"][0]["hp"] = 0
    st["players"][1]["x"] = st["players"][0]["x"] + 1
    st["players"][1]["y"] = st["players"][0]["y"]
    st["active_player_index"] = 1
    st["player"] = session._active_player(st)
    st = await session.act(st, sample_module, "stabilize", target_id="player")
    assert st["players"][0]["down"] is False
    assert st["players"][0]["hp"] == 1
    assert st["phase"] == session.PHASE_DM


async def test_fighter_heavy_strike_deals_damage(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["ac"] = 30  # guaranteed hit
    initial_hp = goblin["hp"]
    d = session.Dice(seed=42)
    await session._ability(st, st["player"], goblin["id"], sample_module, d)
    assert goblin["hp"] < initial_hp


async def test_thief_backstab_deals_damage(sample_module):
    hero = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["thief"], name="Rogue")
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["ac"] = 30
    initial_hp = goblin["hp"]
    d = session.Dice(seed=42)
    await session._ability(st, st["player"], goblin["id"], sample_module, d)
    assert goblin["hp"] < initial_hp


async def test_cleric_turn_undead_deals_damage(sample_module):
    hero = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["cleric"], name="Cleric")
    st = await session.new_game("s1", sample_module, hero, seed=42)
    zombie = st["monsters"][0]
    zombie["name"] = "zombie"
    zombie["x"] = st["player"]["x"] + 1
    zombie["y"] = st["player"]["y"]
    initial_hp = zombie["hp"]
    d = session.Dice(seed=42)
    await session._ability(st, st["player"], zombie["id"], sample_module, d)
    # If the d20 roll is < 10 it misses; retry with fresh dice until it hits.
    if zombie["hp"] == initial_hp:
        for seed in range(1, 100):
            d = session.Dice(seed=seed)
            zombie["hp"] = initial_hp
            await session._ability(st, st["player"], zombie["id"], sample_module, d)
            if zombie["hp"] < initial_hp:
                break
        else:
            pytest.fail("Turn Undead never hit after 100 seeds")
    assert zombie["hp"] < initial_hp


async def test_magic_user_magic_missile_always_hits(sample_module):
    hero = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["magic-user"], name="Wizard")
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    initial_hp = goblin["hp"]
    d = session.Dice(seed=42)
    await session._ability(st, st["player"], goblin["id"], sample_module, d)
    assert goblin["hp"] < initial_hp


async def test_advance_module_keeps_players_and_resets_monsters(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st["status"] = session.STATUS_WON
    st["campaign_stage"] = 1
    st["players"][0]["hp"] = 3
    st["players"][0]["down"] = True
    st["players"][0]["statuses"] = [{"type": "poisoned", "duration": 2, "damage": 1}]
    initial_xp = st["players"][0]["xp"]
    initial_gold = st["players"][0]["gold"]

    next_module = module.load("sunken_crypt")
    st = await session.advance_module(st, next_module)

    assert st["status"] == session.STATUS_ACTIVE
    assert st["module_id"] == "sunken_crypt"
    assert st["turn"] == 1
    assert st["phase"] == session.PHASE_PLAYER
    assert st["active_player_index"] == 0
    assert st["campaign_stage"] == 2
    assert len(st["monsters"]) == len(next_module.monsters)
    assert all(m["alive"] for m in st["monsters"])
    assert st["players"][0]["x"] == next_module.player_start[0]
    assert st["players"][0]["y"] == next_module.player_start[1]
    assert st["players"][0]["hp"] == 3
    assert st["players"][0]["down"] is True
    assert st["players"][0]["statuses"] == [{"type": "poisoned", "duration": 2, "damage": 1}]
    assert st["players"][0]["xp"] == initial_xp
    assert st["players"][0]["gold"] == initial_gold
    assert any("journeys to The Sunken Crypt" in entry for entry in st["log"])


async def test_advance_module_requires_won_status(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    next_module = module.load("sunken_crypt")
    with pytest.raises(ValueError, match="won"):
        await session.advance_module(st, next_module)


def _module_with_trap(base_module):
    """Return a copy of base_module with a trap tile ('2') next to the player start."""
    tiles = [list(row) for row in base_module.map.tiles]
    px, py = base_module.player_start
    tiles[py][px + 1] = "2"
    new_map = module.Map(
        width=base_module.map.width,
        height=base_module.map.height,
        tile_size=base_module.map.tile_size,
        tiles=["".join(row) for row in tiles],
    )
    return module.Module(
        id=base_module.id,
        name=base_module.name,
        ruleset=base_module.ruleset,
        description=base_module.description,
        map=new_map,
        player_start=base_module.player_start,
        monsters=base_module.monsters,
        events=[],
        branches=[],
    )


async def test_trap_tile_is_walkable_and_deals_damage_when_triggered(hero):
    base_module = module.load("sample_lair")
    trap_module = _module_with_trap(base_module)
    assert trap_module.map.walkable(base_module.player_start[0] + 1, base_module.player_start[1])

    st = await session.new_game("trap_test", trap_module, hero, seed=1)
    initial_hp = st["player"]["hp"]
    px, py = st["player"]["x"], st["player"]["y"]
    st = await session.act(st, trap_module, "move", x=px + 1, y=py)
    assert st["player"]["x"] == px + 1
    assert st["player"]["y"] == py
    assert st["player"]["hp"] < initial_hp
    assert any("suffers" in entry and "damage" in entry for entry in st["log"])


async def test_status_ticks_apply_damage_and_expire(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st["player"]["hp"] = 10
    st["player"]["statuses"] = [{"type": "poisoned", "duration": 3, "damage": 1}]
    session._tick_statuses(st)
    assert st["player"]["hp"] == 9
    assert len(st["player"]["statuses"]) == 1
    assert st["player"]["statuses"][0]["duration"] == 2
    session._tick_statuses(st)
    assert st["player"]["hp"] == 8
    session._tick_statuses(st)
    assert st["player"]["hp"] == 7
    assert st["player"]["statuses"] == []


async def test_dm_turn_rolls_initiative_and_may_act_first(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    st["ai_dm_enabled"] = False
    st = await session.act(st, sample_module, "end_turn")
    assert st["phase"] == session.PHASE_DM
    st = await session.act(st, sample_module, "dm_turn")
    assert st["phase"] == session.PHASE_PLAYER
    assert st["turn"] == 2
    assert any("initiative" in entry.lower() or "act first" in entry.lower() for entry in st["log"])


async def test_aoe_damages_monsters_in_radius(sample_module):
    hero = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["magic-user"], name="Wizard")
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin1 = st["monsters"][0]
    goblin2 = st["monsters"][1]
    # Place both goblins within a 2-tile radius of a common point.
    goblin1["x"] = st["player"]["x"] + 2
    goblin1["y"] = st["player"]["y"]
    goblin2["x"] = st["player"]["x"] + 2
    goblin2["y"] = st["player"]["y"] + 1
    initial_hp1 = goblin1["hp"]
    initial_hp2 = goblin2["hp"]
    st = await session.act(st, sample_module, "aoe", center_x=goblin1["x"], center_y=goblin1["y"])
    assert goblin1["hp"] < initial_hp1
    assert goblin2["hp"] < initial_hp2
    assert st["phase"] == session.PHASE_DM


async def test_cover_increases_ranged_target_ac(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = 5
    goblin["y"] = 2
    # Put a wall next to the goblin.
    original_tile = sample_module.map.tiles[2][6]
    tiles = [list(row) for row in sample_module.map.tiles]
    tiles[2][6] = "1"
    wall_module = module.Module(
        id=sample_module.id,
        name=sample_module.name,
        ruleset=sample_module.ruleset,
        description=sample_module.description,
        map=module.Map(
            width=sample_module.map.width,
            height=sample_module.map.height,
            tile_size=sample_module.map.tile_size,
            tiles=["".join(row) for row in tiles],
        ),
        player_start=sample_module.player_start,
        monsters=sample_module.monsters,
        events=[],
        branches=[],
    )
    assert session._has_cover(st, wall_module, goblin)


async def test_flanking_grants_melee_bonus(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    hero2 = char_engine.generate(seed=1, mode="normal", ancestry_name="human", class_names=["fighter"], name="Ally")
    await session.add_player(st, sample_module, hero2, "char2", account_id=2)
    goblin = st["monsters"][0]
    # Hero at (2,2). Place goblin at (3,2) and ally opposite at (4,2).
    st["players"][1]["x"] = 4
    st["players"][1]["y"] = 2
    goblin["x"] = 3
    goblin["y"] = 2
    assert session._is_flanking(st, st["players"][0], goblin)


async def test_validator_rejects_move_into_wall(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    from backend.app.engine import validate
    # Move the player next to the northern wall so (2, 0) is an adjacent wall.
    st["player"]["x"] = 2
    st["player"]["y"] = 1
    with pytest.raises(ValueError, match="blocked"):
        validate.validate_move(st, sample_module, 2, 0)


async def test_validator_rejects_attack_on_non_adjacent_target(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    from backend.app.engine import validate
    st["monsters"][0]["x"] = 10
    st["monsters"][0]["y"] = 10
    with pytest.raises(ValueError, match="adjacent"):
        validate.validate_attack_target(st, st["monsters"][0]["id"])


def _player_token(**overrides):
    """Build a minimal player token for target-number tests."""
    token = {
        "type": "player",
        "classes": ["fighter"],
        "levels": {"fighter": 1},
        "scores": {"strength": 10, "dexterity": 10, "constitution": 10,
                   "intelligence": 10, "wisdom": 10, "charisma": 10},
        "modifiers": {"hit": 0, "damage": 0, "encumbrance_lbs": 0},
        "saves": {"aimed_magic_items": 14, "breath_weapons": 17,
                  "death_paralysis_poison": 12, "petrifaction_polymorph": 15, "spells": 16},
        "damage": "1d8",
        "ranged_damage": "1d6",
        "to_hit": 0,
        "damage_bonus": 0,
    }
    token.update(overrides)
    return token


async def test_strong_fighter_hits_more_often_than_weak_fighter():
    target_ac = 5
    strong = _player_token(modifiers={"hit": 2, "damage": 2, "encumbrance_lbs": 0})
    weak = _player_token(modifiers={"hit": -1, "damage": -1, "encumbrance_lbs": 0})
    # The class table target is the same; the Strength bonus is applied to the roll.
    assert session._attacker_to_hit_bonus(strong) > session._attacker_to_hit_bonus(weak)
    target = session._player_to_hit_target(strong, target_ac)
    raw_roll = target - 1  # a roll that would miss without modifiers
    assert raw_roll + session._attacker_to_hit_bonus(strong) >= target
    assert raw_roll + session._attacker_to_hit_bonus(weak) < target


async def test_strong_fighter_deals_more_damage():
    strong = _player_token(modifiers={"hit": 2, "damage": 2, "encumbrance_lbs": 0})
    weak = _player_token(modifiers={"hit": -1, "damage": -1, "encumbrance_lbs": 0})
    assert session._attacker_damage_bonus(strong) > session._attacker_damage_bonus(weak)


async def test_monster_hd_based_to_hit_favours_higher_hd():
    weak = {"type": "monster", "hit_dice": "1-1"}
    strong = {"type": "monster", "hit_dice": "4"}
    target_ac = 5
    weak_target = session._monster_to_hit_target(weak, target_ac)
    strong_target = session._monster_to_hit_target(strong, target_ac)
    assert strong_target < weak_target


async def test_saving_throw_succeeds_on_high_roll(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    # Give the hero an impossible-to-fail save target for this test.
    st["player"]["saves"]["aimed_magic_items"] = 1
    d = session.Dice(seed=42)
    result = session.saving_throw(d, st["player"], "aimed_magic_items")
    assert result.success is True


async def test_trap_allows_save_for_half_damage(hero):
    base_module = module.load("sample_lair")
    trap_module = _module_with_trap(base_module)
    st = await session.new_game("trap_test", trap_module, hero, seed=1)
    # Seed 1 happens to trigger the trap (1 in 6); the player may save for half.
    px, py = st["player"]["x"], st["player"]["y"]
    st = await session.act(st, trap_module, "move", x=px + 1, y=py)
    assert st["player"]["x"] == px + 1
    assert any("suffers" in entry and "damage" in entry for entry in st["log"])


async def test_morale_check_triggered_at_half_hp(sample_module, hero):
    st = await session.new_game("s1", sample_module, hero, seed=42)
    goblin = st["monsters"][0]
    goblin["x"] = st["player"]["x"] + 1
    goblin["y"] = st["player"]["y"]
    goblin["max_hp"] = 10
    goblin["hp"] = 10
    goblin["ac"] = 30  # guaranteed player hit
    st["player"]["damage"] = "1d6+10"
    st["player"]["damage_bonus"] = 10
    await session._attack(st, st["player"], goblin, session.Dice(seed=42))
    assert goblin["hp"] <= 5
    assert any("checks morale" in entry for entry in st["log"])
