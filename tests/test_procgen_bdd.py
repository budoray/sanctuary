"""Step definitions for features/procgen.feature."""
from pytest_bdd import scenarios, given, when, then, parsers

from sanctuary import module, procgen

scenarios("../features/procgen.feature")


@given(parsers.parse("a GM rolls up a dungeon with seed {seed:d}"), target_fixture="dungeon")
def rolls_up_dungeon(seed):
    return procgen.generate_dungeon(seed, target_areas=15)


@given(
    parsers.parse("a second GM rolls up a dungeon with the same seed {seed:d}"),
    target_fixture="second_dungeon",
)
def rolls_up_same_seed_again(seed):
    return procgen.generate_dungeon(seed, target_areas=15)


@then("both dungeons are identical, room for room")
def both_identical(dungeon, second_dungeon):
    assert dungeon == second_dungeon


@then("an empty-handed party can reach every area from the start")
def party_can_reach_everything(dungeon):
    all_ids = {a["id"] for a in dungeon["areas"]}
    assert procgen.reachable_area_ids(dungeon) == all_ids


@then("the GM's own module loader accepts it without complaint")
def module_loader_accepts_it(dungeon):
    module.load(dungeon)  # raises ModuleError on any complaint


@then("every door and passage can be walked back the way it came, except stairs and chutes marked one-way")
def exits_reciprocate(dungeon):
    by_id = {a["id"]: a for a in dungeon["areas"]}
    for area in dungeon["areas"]:
        for exit_ in area["exits"]:
            back = by_id[exit_["to"]]["exits"]
            reciprocates = any(e["to"] == area["id"] for e in back)
            if not reciprocates:
                assert exit_["kind"] == "stairs", (
                    f"area {area['id']}'s {exit_['kind']} exit to "
                    f"{exit_['to']} doesn't reciprocate and isn't stairs")


@given("a GM rolls up a dungeon that hits an impossible table result", target_fixture="fudged")
def dungeon_that_fudges():
    _, dice_ = procgen.generate_dungeon(1, target_areas=12, return_dice=True)
    return dice_


@then("the roll log shows what was fudged and why")
def roll_log_shows_fudges(fudged):
    fudge_rolls = procgen.fudges(fudged)
    assert fudge_rolls
    assert all(r.reason.startswith("fudge:") for r in fudge_rolls)


@given(
    "a GM rolls up two hundred dungeons on two hundred different seeds",
    target_fixture="two_hundred",
)
def two_hundred_dungeons():
    return [
        procgen.generate_dungeon(seed, target_areas=(seed % 20) + 3, dungeon_level=(seed % 5) + 1)
        for seed in range(200)
    ]


@then("none of them crash, none of them are empty, and every area in each is reachable")
def all_two_hundred_are_playable(two_hundred):
    for doc in two_hundred:
        assert doc["areas"]
        all_ids = {a["id"] for a in doc["areas"]}
        assert procgen.reachable_area_ids(doc) == all_ids
