"""Unit tests for sanctuary.session - the solo driver over runtime.State."""
import pytest

from sanctuary import module, session
from sanctuary.character import generate as gen_character


def _party(seed=1, cls="fighter", name="Ilse"):
    for s in range(seed, seed + 300):
        try:
            return gen_character(seed=s, mode="normal", ancestry_name="human",
                                  class_names=(cls,), name=name)
        except ValueError:
            continue
    raise RuntimeError("could not roll a legal character")


def _mod():
    return module.load({
        "module": {
            "title": "Session Test", "version": "1.0",
            "party_guidance": {"size": [1, 6], "total_levels": [1, 3]},
            "background": "bg", "start": "You stand at the door.",
        },
        "regions": [
            {"id": "only", "areas": [1, 2],
             "check": {"chance": "1-in-100", "every": "1 turn"},
             "table": {"die": "d2", "entries": ["1 × Rat", "nothing"]}},
        ],
        "areas": [
            {"id": 1, "name": "Door", "description": "A door.",
             "exits": [{"to": 2, "kind": "door", "hidden": False}],
             "contents": [], "monsters": [], "treasure": [], "discoveries": []},
            {"id": 2, "name": "Room", "description": "A room.",
             "exits": [{"to": 1, "kind": "door", "hidden": False}],
             "contents": [], "monsters": ["1 × Rat"], "treasure": ["3 gp"],
             "discoveries": []},
        ],
        "monsters": [
            {"name": "Rat", "hit_dice": "1-1", "armour_class": "9",
             "attacks": "1 bite (1d3)", "xp": 3, "loot": "Nil"},
        ],
        "items": [], "mechanics": [],
    })


def test_start_returns_a_view_of_the_opening_area():
    out = session.start("s1", _mod(), [_party()], seed=1)
    assert out["name"] == "Door"
    assert out["party"][0]["hp"] > 0
    session.end("s1")


def test_act_dispatches_to_the_runtime_and_returns_a_fresh_view():
    session.start("s2", _mod(), [_party()], seed=1)
    out = session.act("s2", "move", to=2)
    assert out["area_id"] == 2
    assert out["in_combat"]
    session.end("s2")


def test_act_with_an_unknown_action_raises():
    session.start("s3", _mod(), [_party()], seed=1)
    with pytest.raises(ValueError):
        session.act("s3", "teleport")
    session.end("s3")


def test_unknown_session_raises_keyerror():
    with pytest.raises(KeyError):
        session.act("nope", "move", to=2)


def test_view_carries_the_dice_log_for_the_tray():
    session.start("s4", _mod(), [_party()], seed=1)
    session.act("s4", "move", to=2)
    out = session.act("s4", "attack") if not session.view("s4")["pending_decisions"] \
        else session.act("s4", "decide", index=0, ruling="ok")
    assert out["rolls"], "the dice tray needs every roll, with reasons"
    assert all("reason" in r for r in out["rolls"])
    session.end("s4")


def test_full_solo_delve_through_the_session_api_only():
    session.start("s5", _mod(), [_party(), _party(200, "cleric", "Meva")], seed=5)
    session.act("s5", "move", to=2)
    while session.view("s5")["in_combat"]:
        v = session.view("s5")
        if v["pending_decisions"]:
            session.act("s5", "decide", index=0, ruling="ok")
        else:
            session.act("s5", "attack")
    session.act("s5", "take_treasure")
    session.act("s5", "move", to=1)
    out = session.act("s5", "leave")
    assert out["finished"]
    session.end("s5")
