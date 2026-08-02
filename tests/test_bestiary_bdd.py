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


@given(parsers.parse('the monster tables print "{printed_name}" for an encounter'),
       target_fixture="printed_name")
def the_monster_tables_print(printed_name):
    return printed_name


@when("the game looks up which monster that names", target_fixture="resolved")
def the_game_looks_it_up(printed_name):
    return bestiary.resolve_name(printed_name)


@then("it finds the dire wolf, ready to fight")
def finds_the_dire_wolf(resolved):
    assert resolved is not None
    assert bestiary._slug(resolved["name"]) == "wolf_dire"
    assert resolved["hit_dice"]


@then("it finds no monster, rather than a wrong one")
def finds_no_monster(resolved):
    assert resolved is None


# --------------------------------------------------------------------
# A statline the engine cannot read does not fail loudly - it quietly
# yields a 1 HD monster worth single-digit XP wearing no armour. These
# scenarios watch the OUTPUT of the corpus's own famous monsters.
# --------------------------------------------------------------------

@when("the party meets whatever that names", target_fixture="instance")
def the_party_meets_it(printed_name):
    from sanctuary import runtime
    from sanctuary.dice import Dice
    record = bestiary.resolve_name(printed_name)
    assert record is not None, f"{printed_name!r} no longer resolves"
    return runtime._instantiate_monster(Dice(1), record)


@then(parsers.parse("it fights with at least {least:d} hit dice"))
def fights_with_hit_dice(instance, least):
    from sanctuary import runtime
    assert int(runtime._LOOSE_HD.match(instance.hd_notation).group(1)) >= least


@then("it has more hit points than a housecat")
def more_hp_than_a_housecat(instance):
    # 8 is the best a single d8 can roll, which is all a 1 HD statline can
    # ever produce - so this fails the moment a dragon collapses back to one.
    assert instance.max_hp > 8


@then(parsers.parse("killing it is worth at least {least:d} experience"))
def worth_at_least(instance, least):
    assert instance.xp >= least


@then("its armour class is better than an unarmoured commoner's")
def armour_better_than_a_commoner(instance):
    assert instance.armour_class < 10  # OSRIC counts DOWN: lower is better
