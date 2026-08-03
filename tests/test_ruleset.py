"""Tests for the ruleset seam (sanctuary/ruleset.py + sanctuary/rulesets/).

The seam exists so the engine plays by whatever pack it is handed - OSRIC
is the first pack, not the only possible one. These tests prove three
things: the registry loads packs by name, the OSRIC pack changes NOTHING
about how the game plays (it delegates to the same tested modules), and -
the point of the exercise - a scripted test-double pack can drive a delve
through runtime without sanctuary.resolve being consulted at all.
"""
import os
from pathlib import Path
from types import SimpleNamespace

# ⚠ BEFORE `import app` - see the note in test_app.py. TENSHIN_DEV latches
# at import time; every route hit here needs dev mode.
os.environ.setdefault("TENSHIN_DEV", "1")

import pytest
from fastapi.testclient import TestClient

import app as sanctuary_app
from sanctuary import character, module, resolve, ruleset, rulesets, runtime
from sanctuary.dice import Dice

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(sanctuary_app.app)


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------

def test_osric_pack_loads_by_name():
    pack = rulesets.load("osric")
    assert pack.id == "osric"
    assert "osric" in rulesets.registered()


def test_load_is_cached():
    assert rulesets.load("osric") is rulesets.load("osric")


def test_unknown_pack_fails_loudly():
    with pytest.raises(KeyError):
        rulesets.load("not-a-ruleset")


# ---------------------------------------------------------------------
# OSRIC pack: delegation honesty - the pack changes WHO the engine asks,
# never what the answer is
# ---------------------------------------------------------------------

def _legal_seed(mode, ancestry, classes):
    """Some (seed, mode, ancestry, classes) combinations cannot produce a
    legal character (ability minimums) - scan for one that can."""
    for seed in range(1, 400):
        try:
            character.generate(seed=seed, mode=mode, ancestry_name=ancestry,
                               class_names=classes, name="Test")
            return seed
        except ValueError:
            continue
    raise RuntimeError(f"no legal seed for {mode}/{ancestry}/{classes}")


def test_generate_matches_the_character_module_for_every_mode():
    pack = rulesets.load("osric")
    for entry in pack.gen_modes():
        mode = entry["value"]
        seed = _legal_seed(mode, "human", ("fighter",))
        kwargs = dict(seed=seed, mode=mode, ancestry_name="human",
                      class_names=("fighter",), name="Test")
        # Character equality excludes `log`; identical inputs must produce
        # identical records whichever door you come in by.
        assert pack.generate(**kwargs) == character.generate(**kwargs)


def test_chargen_surface_delegates_to_the_character_module():
    pack = rulesets.load("osric")
    assert pack.ancestry_names() == list(character.ANCESTRIES)
    assert pack.class_names() == list(character.CLASSES)
    for a in character.ANCESTRIES:
        assert pack.ancestry_allowed_classes(a) == \
            list(character.ancestry(a)["allowed_classes"])
    assert pack.roll_abilities(Dice(seed=5), "normal") == \
        character.roll_abilities(Dice(seed=5), "normal")
    for entry in pack.gen_modes():
        assert pack.arrangeable(entry["value"]) == character.arrangeable(entry["value"])


def test_combat_delegates_to_the_resolve_module():
    pack = rulesets.load("osric")
    c = character.generate(seed=_legal_seed("normal", "human", ("fighter",)),
                           mode="normal", ancestry_name="human",
                           class_names=("fighter",), name="Test")
    via_pack = pack.attack(Dice(seed=9), c, 10, pack.default_damage_expr)
    direct = resolve.attack(Dice(seed=9), c, 10, damage_expr=pack.default_damage_expr)
    assert (via_pack.hit, via_pack.damage) == (direct.hit, direct.damage)
    via_pack = pack.morale(Dice(seed=9), hit_dice=2.0)
    direct = resolve.morale(Dice(seed=9), hit_dice=2.0)
    assert (via_pack.passed, via_pack.outcome) == (direct.passed, direct.outcome)


# ---------------------------------------------------------------------
# The manifest the client boots from
# ---------------------------------------------------------------------

def test_ruleset_manifest_matches_the_character_data():
    m = client.get("/api/ruleset").json()
    assert m["id"] == "osric"
    assert m["ancestries"] == list(character.ANCESTRIES)
    assert [c["value"] for c in m["classes"]] == list(character.CLASSES)
    assert m["save_heading"] == rulesets.load("osric").save_heading
    # At most one selected mode/class - the select and the tiles need a
    # single initial choice each.
    assert sum(1 for e in m["gen_modes"] if e.get("selected")) == 1
    assert sum(1 for c in m["classes"] if c.get("selected")) == 1


def test_every_manifest_portrait_exists_on_disk():
    m = client.get("/api/ruleset").json()
    for c in m["classes"]:
        p = c["portrait"]
        assert p.startswith("/static/"), p
        assert (ROOT / p.lstrip("/")).is_file(), p


def test_app_serves_the_loaded_packs_licence():
    assert sanctuary_app.LICENCE_NOTICE == rulesets.load("osric").licence_notice


# ---------------------------------------------------------------------
# The seam itself: a scripted test-double pack drives a real delve.
# If runtime ever called sanctuary.resolve directly, none of these
# scripted outcomes could happen.
# ---------------------------------------------------------------------

class _DoublePack:
    """A ruleset that plays by made-up rules: the party always hits for
    exactly 7, monsters always whiff, and morale always routs. Registered
    under a test-only name and removed afterwards."""

    id = "double"
    name = "Test Double"
    title = "Double"
    version = "0"
    licence_notice = "test only"
    abilities = ("strength",)
    save_heading = "Saves"
    default_damage_expr = "1d4"

    def __init__(self):
        self.attack_calls = []

    def gen_modes(self):
        return [{"value": "normal", "label": "Normal", "selected": True}]

    def ancestry_names(self):
        return ["human"]

    def class_names(self):
        return ["fighter"]

    def ancestry_allowed_classes(self, ancestry):
        return ["fighter"]

    def portrait_for(self, class_name):
        return "/static/art/portraits/fighter.png"

    def roll_abilities(self, dice, mode):
        return {"strength": 12}

    def arrangeable(self, mode):
        return False

    def generate(self, **kwargs):
        # The Character record is engine-shared; a real pack would fill it
        # with its own arithmetic.
        return character.generate(**kwargs)

    def attack(self, dice, attacker, target_ac, damage_expr):
        self.attack_calls.append((attacker, target_ac, damage_expr))
        if isinstance(attacker, str):
            # Monsters attack by hit-dice notation - scripted whiff.
            return SimpleNamespace(hit=False, damage=0)
        return SimpleNamespace(hit=True, damage=7)

    def morale(self, dice, hit_dice):
        return SimpleNamespace(passed=False, outcome="break and run")

    def vitals_line(self, character):
        return "double vitals"

    def client_manifest(self):
        return {"id": self.id}


def _double_doc():
    """A two-area warren with one fixed-hp monster - 30 hit points exactly,
    so the scripted 7 damage is measurable to the point."""
    return {
        "module": {
            "title": "Double Warren", "version": "1.0",
            "party_guidance": {"size": [1, 6], "total_levels": [1, 3]},
            "background": "bg", "start": "start",
        },
        "regions": [
            {"id": "only", "areas": [1, 2],
             "check": {"chance": "1-in-100", "every": "1 turn"},
             "table": {"die": "d2", "entries": ["1 × Test Ogre", "nothing"]}},
        ],
        "areas": [
            {"id": 1, "name": "Mouth", "description": "d",
             "exits": [{"to": 2, "kind": "tunnel", "hidden": False}],
             "contents": [], "monsters": [], "treasure": [], "discoveries": []},
            {"id": 2, "name": "Den", "description": "d",
             "exits": [{"to": 1, "kind": "tunnel", "hidden": False}],
             "contents": [], "monsters": ["1 × Test Ogre"],
             "treasure": [], "discoveries": []},
        ],
        "monsters": [
            {"name": "Test Ogre", "hit_dice": "30 hit points",
             "armour_class": "10", "attacks": "1 club (1d4)", "xp": 5,
             "loot": "Individual 1 each"},
        ],
        "items": [], "mechanics": [],
    }


def _double_party():
    for seed in range(1, 300):
        try:
            return character.generate(seed=seed, mode="normal",
                                      ancestry_name="human",
                                      class_names=("fighter",), name="Ilse")
        except ValueError:
            continue
    raise RuntimeError("could not roll a legal character")


@pytest.fixture
def double_pack():
    double = _DoublePack()
    ruleset.register("double", lambda path: double)
    try:
        yield double
    finally:
        # Leave the registry as we found it - other tests enumerate it.
        ruleset._FACTORIES.pop("double", None)
        ruleset._INSTANCES.pop("double", None)


def test_the_engine_plays_by_the_pack_it_is_handed(double_pack):
    st = runtime.new_game(module.load(_double_doc()), [_double_party()],
                          seed=1, ruleset=ruleset.load("double"))
    runtime.move(st, 2)
    assert st.combat is not None
    ogre = st.combat.monsters[0]
    assert ogre.hp == 30

    runtime.attack_round(st)

    # The scripted 7 landed - resolve.attack could not produce this line.
    assert ogre.hp == 23
    # Every attack asked the pack for the damage expression, not resolve.
    assert double_pack.attack_calls
    assert all(call[2] == "1d4" for call in double_pack.attack_calls)
    # Scripted morale routed the survivor - the log line is the double's
    # own words, and victory resolved through the normal engine path.
    assert "The surviving monsters break and run." in st.log
    assert st.combat is None
    assert st.xp == 5
    assert 2 in st.cleared_areas


def test_environment_override_selects_a_registered_pack(double_pack, monkeypatch):
    """app.py reads SANCTUARY_RULESET at startup (app.py:47); any registered
    name is loadable through the same mechanism."""
    monkeypatch.setenv("SANCTUARY_RULESET", "double")
    assert rulesets.load(os.environ["SANCTUARY_RULESET"]).id == "double"


def test_the_running_app_selected_the_pack_the_environment_named():
    expected = os.environ.get("SANCTUARY_RULESET", "osric")
    assert sanctuary_app.RULESET.id == expected
