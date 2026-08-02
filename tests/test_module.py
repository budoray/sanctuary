import copy

import pytest
import yaml

from sanctuary import module

FIXTURE = "data/modules/weeping_cistern.yaml"


def _valid_doc() -> dict:
    """A minimal document that satisfies every validation rule, so each
    test below can mutate exactly the one thing it means to break."""
    return {
        "module": {
            "title": "Test Module",
            "version": "1.0",
            "party_guidance": {"size": [4, 6], "total_levels": [1, 3]},
            "background": "bg",
            "start": "start",
        },
        "regions": [
            {
                "id": "only",
                "areas": [1, 2],
                "check": {"chance": "1-in-6", "every": "1 turn"},
                "table": {"die": "d2", "entries": ["a", "b"]},
            }
        ],
        "areas": [
            {
                "id": 1,
                "name": "Room One",
                "description": "A room.",
                "exits": [{"to": 2, "kind": "door", "hidden": False}],
                "contents": [],
                "monsters": [],
                "treasure": [],
                "discoveries": [],
            },
            {
                "id": 2,
                "name": "Room Two",
                "description": "Another room.",
                "exits": [],
                "contents": [],
                "monsters": [],
                "treasure": [],
                "discoveries": [
                    {"what": "a coin", "trigger": {"action": "search", "scope": "floor"}},
                ],
            },
        ],
        "monsters": [],
        "items": [],
        "mechanics": [],
    }


# --- load / save round trip -------------------------------------------

def test_load_from_dict_returns_a_module():
    m = module.load(_valid_doc())
    assert m.title == "Test Module"
    assert len(m.areas) == 2


def test_round_trip_load_save_load(tmp_path):
    m = module.load(_valid_doc())
    path = module.save(m, tmp_path / "out.yaml")
    assert module.load(path) == m


def test_fixture_module_loads_and_validates_clean():
    problems = module.validate(
        yaml.safe_load(open(FIXTURE, encoding="utf-8").read())
    )
    assert problems == []
    m = module.load(FIXTURE)
    assert m.title == "The Weeping Cistern"


def test_fixture_module_round_trips(tmp_path):
    m = module.load(FIXTURE)
    path = module.save(m, tmp_path / "out.yaml")
    assert module.load(path) == m


def test_fixture_exercises_every_required_feature():
    m = module.load(FIXTURE)
    doc = m.doc
    assert len(doc["regions"]) == 2
    cadences = {(r["check"]["chance"], r["check"]["every"]) for r in doc["regions"]}
    assert len(cadences) == 2, "regions must use different check cadences"
    assert any(mo["name"].lower() == "silt lurker" for mo in doc["monsters"])
    assert any("candle" in it["name"].lower() for it in doc["items"])
    assert all(me.get("tier") == 3 for me in doc["mechanics"])
    assert doc["mechanics"], "must ship at least one tier-3 mechanic"
    hidden_exits = [
        e for a in doc["areas"] for e in a["exits"] if e["hidden"]
    ]
    assert hidden_exits, "must ship at least one hidden exit"
    gated = [
        d for a in doc["areas"] for d in a["discoveries"]
        if d["trigger"].get("chance") and d["trigger"].get("per")
    ]
    assert gated, "must ship a discovery gated on both action and time"


def test_load_invalid_document_raises_module_error():
    doc = _valid_doc()
    doc["areas"][0]["exits"][0]["to"] = 999
    with pytest.raises(module.ModuleError):
        module.load(doc)


# --- individual validation rules ---------------------------------------

def test_exit_to_nonexistent_area_is_reported():
    doc = _valid_doc()
    doc["areas"][0]["exits"][0]["to"] = 999
    problems = module.validate(doc)
    assert any("999" in p.message and p.where == "area 1" for p in problems)


def test_region_covering_no_areas_is_reported():
    doc = _valid_doc()
    doc["regions"][0]["areas"] = [50, 60]
    problems = module.validate(doc)
    assert any("covers no area" in p.message for p in problems)


def test_duplicate_area_ids_are_reported():
    doc = _valid_doc()
    doc["areas"][1]["id"] = 1
    problems = module.validate(doc)
    assert any("duplicate area ids" in p.message for p in problems)


def test_wandering_table_entry_count_mismatch_is_reported():
    doc = _valid_doc()
    doc["regions"][0]["table"]["entries"] = ["only one"]
    problems = module.validate(doc)
    assert any("needs 2 entries, has 1" in p.message for p in problems)


def test_discovery_with_chance_but_no_per_is_reported():
    doc = _valid_doc()
    doc["areas"][1]["discoveries"][0]["trigger"]["chance"] = "1-in-6"
    problems = module.validate(doc)
    assert any("chance but no 'per'" in p.message for p in problems)


def test_missing_required_key_is_reported():
    doc = _valid_doc()
    del doc["module"]["title"]
    problems = module.validate(doc)
    assert any("title" in p.message and p.where == "module" for p in problems)


def test_validate_reports_all_problems_not_just_the_first():
    """A DM fixing a broken module needs the whole list."""
    doc = _valid_doc()
    doc["areas"][0]["exits"][0]["to"] = 999
    doc["areas"][1]["id"] = 1
    doc["regions"][0]["table"]["entries"] = ["only one"]
    problems = module.validate(doc)
    messages = " | ".join(p.message for p in problems)
    assert "non-existent area" in messages
    assert "duplicate area ids" in messages
    assert "needs 2 entries" in messages
    assert len(problems) >= 3


def test_valid_document_has_no_problems():
    assert module.validate(_valid_doc()) == []


def test_valid_document_is_untouched_by_validation():
    doc = _valid_doc()
    before = copy.deepcopy(doc)
    module.validate(doc)
    assert doc == before
