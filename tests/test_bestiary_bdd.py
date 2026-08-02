"""Step definitions for features/bestiary.feature."""
import pytest
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import bestiary

scenarios("../features/bestiary.feature")


@pytest.fixture(autouse=True)
def isolated_overlay_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(bestiary, "_OVERLAY_DIR", tmp_path / "overlays")


@given("the goblin from the book", target_fixture="original_morale")
def goblin_from_book():
    return bestiary.load("goblin")["morale"]


@when("a GM raises that goblin's morale for a tougher warband")
def raise_goblin_morale(original_morale):
    bestiary.edit("goblin", morale=original_morale + 20)


@then("the goblin on their table has the higher morale")
def goblin_is_tougher(original_morale):
    assert bestiary.load("goblin")["morale"] == original_morale + 20


@then("the goblin printed in the book is unchanged")
def book_goblin_unchanged(original_morale):
    path = bestiary._base_path("goblin")
    import yaml
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["morale"] == original_morale


@given("a GM has already raised a goblin's morale", target_fixture="original_morale")
def gm_already_raised_morale():
    original = bestiary.load("goblin")["morale"]
    bestiary.edit("goblin", morale=original + 20)
    return original


@when("the GM discards that change")
def discard_change():
    bestiary.reset("goblin")


@then("the goblin is back to exactly what the book printed")
def goblin_restored(original_morale):
    assert bestiary.load("goblin")["morale"] == original_morale


@when(parsers.parse('a GM creates a custom monster called "{name}"'), target_fixture="custom_monster")
def create_custom(name):
    return bestiary.create(name=name, hit_dice="2", armour_class=7)


@then("it appears in their bestiary with the same fields as any book monster")
def custom_has_same_shape(custom_monster):
    book_monster = bestiary.load("goblin")
    assert set(custom_monster.keys()) >= {
        "name", "frequency", "size", "alignment", "move", "armour_class", "hit_dice",
        "melee_attacks", "senses", "lair_chance", "intelligence", "morale", "loot",
        "experience", "description",
    }
    assert custom_monster["name"] == "Sewer Rat King"
    assert book_monster["hit_dice"]  # sanity: the book monster still loads fine too


@given(parsers.parse("a monster worth {xp} experience points"), target_fixture="base_xp")
def a_monster_worth_xp(xp):
    return int(xp.replace(",", ""))


@when("a GM checks how dangerous it is", target_fixture="computed_level")
def check_danger(base_xp):
    return bestiary.monster_level(base_xp)


@then(parsers.parse("they're told it's a level {level:d} monster"))
def told_level(computed_level, level):
    assert computed_level == level


@given("the achaiyerai, a monster with a special attack beyond simple combat", target_fixture="monster")
def the_achaiyerai():
    return bestiary.load("achaiyerai")


@when("a GM looks up what it can do", target_fixture="abilities_text")
def look_up_abilities(monster):
    return " ".join(a["text"] for a in monster["abilities"])


@then("its Toxic Cloud is still there in the text, not silently dropped")
def toxic_cloud_present(abilities_text):
    assert "Toxic Cloud" in abilities_text
