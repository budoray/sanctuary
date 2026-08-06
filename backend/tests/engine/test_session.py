import pytest

from backend.app.engine import character as char_engine
from backend.app.engine import module, session


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


def test_new_game(sample_module, hero):
    st = session.new_game("s1", sample_module, hero, seed=42)
    assert st["module_id"] == "sample_lair"
    assert st["phase"] == "player"
    assert st["player"]["name"] == "Test"
    assert len(st["monsters"]) == 2


def test_player_move(sample_module, hero):
    st = session.new_game("s1", sample_module, hero, seed=42)
    st = session.act(st, sample_module, "move", x=3, y=2)
    assert st["player"]["x"] == 3


def test_player_move_into_wall_fails(sample_module, hero):
    st = session.new_game("s1", sample_module, hero, seed=42)
    with pytest.raises(ValueError):
        session.act(st, sample_module, "move", x=0, y=0)


def test_player_attack_goblin(sample_module, hero):
    st = session.new_game("s1", sample_module, hero, seed=42)
    # Walk next to goblin_1 at (14,10). Player starts at (2,2).
    path = [
        (3, 2), (4, 2), (5, 2), (6, 2), (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2),
        (13, 2), (14, 2), (14, 3), (14, 4), (14, 5), (14, 6), (14, 7), (14, 8), (14, 9),
    ]
    for x, y in path:
        st = session.act(st, sample_module, "move", x=x, y=y)
        st["phase"] = "player"  # keep it player turn for movement
    st = session.act(st, sample_module, "attack", target_id="goblin_1")
    assert st["phase"] == "dm"


def test_dm_turn_advances_turn(sample_module, hero):
    st = session.new_game("s1", sample_module, hero, seed=42)
    st = session.act(st, sample_module, "end_turn")
    assert st["phase"] == "dm"
    st = session.act(st, sample_module, "dm_turn")
    assert st["phase"] == "player"
    assert st["turn"] == 2
