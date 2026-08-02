"""Step definitions for features/module.feature."""
import pytest
from pytest_bdd import scenarios, given, when, then

from sanctuary import module

scenarios("../features/module.feature")

FIXTURE = "data/modules/weeping_cistern.yaml"


def _base_doc() -> dict:
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
                "contents": [], "monsters": [], "treasure": [], "discoveries": [],
            },
            {
                "id": 2,
                "name": "Room Two",
                "description": "Another room.",
                "exits": [], "contents": [], "monsters": [], "treasure": [],
                "discoveries": [
                    {"what": "a coin", "trigger": {"action": "search", "scope": "floor"}},
                ],
            },
        ],
        "monsters": [], "items": [], "mechanics": [],
    }


@given("the Weeping Cistern module", target_fixture="doc_or_module")
def weeping_cistern():
    return FIXTURE


@given(
    "a module where area 1's door leads to an area that does not exist",
    target_fixture="doc_or_module",
)
def door_to_nowhere():
    doc = _base_doc()
    doc["areas"][0]["exits"][0]["to"] = 999
    return doc


@given("a module where two areas are both numbered 1", target_fixture="doc_or_module")
def duplicate_area_numbers():
    doc = _base_doc()
    doc["areas"][1]["id"] = 1
    return doc


@given(
    "a module whose 2-sided wandering table only lists one encounter",
    target_fixture="doc_or_module",
)
def short_wandering_table():
    doc = _base_doc()
    doc["regions"][0]["table"]["entries"] = ["only one"]
    return doc


@given(
    "a module where a discovery has a chance to be found but no stated interval",
    target_fixture="doc_or_module",
)
def discovery_missing_interval():
    doc = _base_doc()
    doc["areas"][1]["discoveries"][0]["trigger"]["chance"] = "1-in-6"
    return doc


@when("the GM loads it", target_fixture="outcome")
def gm_loads_it(doc_or_module):
    try:
        return ("loaded", module.load(doc_or_module))
    except module.ModuleError as e:
        return ("refused", e)


@then("it loads without complaint")
def loads_without_complaint(outcome):
    kind, result = outcome
    assert kind == "loaded", result


@then("it has two regions checking on different schedules")
def two_regions_different_schedules(outcome):
    m = outcome[1]
    cadences = {(r["check"]["chance"], r["check"]["every"]) for r in m.regions}
    assert len(cadences) == 2


@then("it has a monster found nowhere but this module")
def module_local_monster(outcome):
    m = outcome[1]
    assert any(mo["name"].lower() == "silt lurker" for mo in m.doc["monsters"])


@then("it has a discovery that only turns up after searching for a while")
def time_gated_discovery(outcome):
    m = outcome[1]
    gated = [
        d for a in m.areas for d in a["discoveries"]
        if d["trigger"].get("chance") and d["trigger"].get("per")
    ]
    assert gated


@then("the module is refused")
def module_is_refused(outcome):
    kind, result = outcome
    assert kind == "refused", "module loaded when it should have been refused"


@then("the complaint names area 1 and the missing area")
def complaint_names_area_and_missing(outcome):
    _, err = outcome
    text = str(err)
    assert "area 1" in text
    assert "999" in text


@then("the complaint names the duplicate area number")
def complaint_names_duplicate(outcome):
    _, err = outcome
    assert "duplicate" in str(err) and "1" in str(err)


@then("the complaint names the mismatch between the die and the entry count")
def complaint_names_die_mismatch(outcome):
    _, err = outcome
    assert "needs 2 entries" in str(err)


@then("the complaint says the discovery is missing its interval")
def complaint_names_missing_interval(outcome):
    _, err = outcome
    assert "chance but no 'per'" in str(err)


@when("the GM saves it and loads it again", target_fixture="reloaded")
def save_and_reload(doc_or_module, tmp_path):
    m = module.load(doc_or_module)
    path = module.save(m, tmp_path / "roundtrip.yaml")
    return (m, module.load(path))


@then("the reloaded module is identical to the original")
def reloaded_is_identical(reloaded):
    original, again = reloaded
    assert original == again
