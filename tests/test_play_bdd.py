"""Step definitions for features/play.feature."""
from pytest_bdd import given, parsers, scenarios, then, when

from sanctuary import module, procgen, runtime
from sanctuary.character import generate as gen_character

scenarios("../features/play.feature")


def _party(seed=1, cls="fighter", name="Ilse"):
    for s in range(seed, seed + 300):
        try:
            return gen_character(seed=s, mode="normal", ancestry_name="human",
                                  class_names=(cls,), name=name)
        except ValueError:
            continue
    raise RuntimeError("could not roll a legal character")


def _small_dungeon(*, region_chance="1-in-100", tier3_attack=False):
    attacks = "1 bite (1d4) or the Old Bargain" if tier3_attack else "1 bite (1d4)"
    return module.load({
        "module": {
            "title": "Test Warren", "version": "1.0",
            "party_guidance": {"size": [1, 6], "total_levels": [1, 3]},
            "background": "bg", "start": "The party stands at the warren mouth.",
        },
        "regions": [
            {"id": "only", "areas": [1, 2],
             "check": {"chance": region_chance, "every": "1 turn"},
             "table": {"die": "d2", "entries": ["1 × Test Rat", "1 × Test Rat"]}},
        ],
        "areas": [
            {"id": 1, "name": "Warren Mouth", "description": "A dirt burrow entrance.",
             "exits": [{"to": 2, "kind": "tunnel", "hidden": False}],
             "contents": [], "monsters": [], "treasure": [], "discoveries": []},
            {"id": 2, "name": "Den", "description": "A cramped den.",
             "exits": [
                 {"to": 1, "kind": "tunnel", "hidden": False},
                 {"to": 3, "kind": "crack", "hidden": True},
             ],
             "contents": [], "monsters": ["1 × Test Rat"], "treasure": ["12 gp"],
             "discoveries": [
                 {"what": "a crack behind the bones",
                  "trigger": {"action": "search", "scope": "bones"}},
             ]},
            {"id": 3, "name": "Back Tunnel", "description": "A narrow crawl.",
             "exits": [{"to": 2, "kind": "crack", "hidden": False}],
             "contents": [], "monsters": [], "treasure": [], "discoveries": []},
        ],
        "monsters": [
            {"name": "Test Rat", "hit_dice": "1-1", "armour_class": "10",
             "attacks": attacks, "xp": 5, "loot": "Individual 1 each"},
        ],
        "items": [], "mechanics": [],
    })


def _clear_combat(st):
    while st.combat is not None:
        if st.pending_decisions:
            runtime.decide(st, 0, "the DM rules it a plain attack this fight")
        else:
            runtime.attack_round(st)


# ---------------------------------------------------------------------
# Full delve
# ---------------------------------------------------------------------

@given("a solo party stands at the mouth of a small dungeon", target_fixture="state")
def party_at_dungeon_mouth():
    st = runtime.new_game(_small_dungeon(), [_party(), _party(500, "cleric", "Meva")], seed=1)
    return st


@when("the party fights its way to the treasure and leaves")
def party_fights_and_leaves(state):
    runtime.move(state, 2)
    _clear_combat(state)
    runtime.take_treasure(state)
    runtime.leave(state)


@then("the delve ends with the party's own dice log to show for it")
def delve_ends_with_a_log(state):
    assert state.finished
    assert state.dice.log


@then("the party has treasure in hand")
def party_has_treasure(state):
    assert state.inventory


# ---------------------------------------------------------------------
# Tier-3 surfacing
# ---------------------------------------------------------------------

@given("a solo party meets a monster with an attack the table has no rule for",
       target_fixture="state")
def party_meets_unmodeled_attack():
    st = runtime.new_game(_small_dungeon(tier3_attack=True), [_party()], seed=1)
    runtime.move(st, 2)
    return st


@then("the party is asked how that attack goes, not left to guess")
def party_is_asked(state):
    assert state.pending_decisions


@then("the fight will not continue until the party rules on it")
def fight_waits_for_a_ruling(state):
    try:
        runtime.attack_round(state)
        raised = False
    except ValueError:
        raised = True
    assert raised, "combat must refuse to proceed with a decision still pending"


# ---------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------

def _fixed_script(seed):
    st = runtime.new_game(_small_dungeon(), [_party(seed), _party(seed + 500, "cleric", "Meva")],
                           seed=seed)
    runtime.move(st, 2)
    _clear_combat(st)
    runtime.search(st, scope="bones")
    runtime.take_treasure(st)
    if not st.finished:
        runtime.leave(st)
    return st


@given("a solo party plays through a dungeon making a fixed set of choices",
       target_fixture="first_run")
def first_scripted_run():
    return _fixed_script(4242)


@given("a second party plays through the same dungeon making the same choices",
       target_fixture="second_run")
def second_scripted_run():
    return _fixed_script(4242)


@then("both parties see the exact same dice, in the exact same order")
def same_dice_in_order(first_run, second_run):
    assert [r.total for r in first_run.dice.log] == [r.total for r in second_run.dice.log]
    assert [r.expr for r in first_run.dice.log] == [r.expr for r in second_run.dice.log]


# ---------------------------------------------------------------------
# Resting attracts wandering monsters
# ---------------------------------------------------------------------

@given("a solo party is resting in a dungeon room with a wandering danger",
       target_fixture="state")
def party_resting_with_danger():
    return runtime.new_game(_small_dungeon(region_chance="2-in-2"), [_party()], seed=1)


@when("the party rests turn after turn")
def party_rests_repeatedly(state):
    runtime.rest(state, turns=1)


@then("something eventually finds them")
def something_finds_them(state):
    assert state.combat is not None or state.pending_decisions


# ---------------------------------------------------------------------
# Hidden passages
# ---------------------------------------------------------------------

@given("a solo party stands in a room with a passage nobody has found yet",
       target_fixture="state")
def party_in_room_with_hidden_passage():
    st = runtime.new_game(_small_dungeon(), [_party()], seed=1)
    runtime.move(st, 2)
    _clear_combat(st)
    return st


@then("the party cannot walk through a passage it hasn't found")
def cannot_walk_hidden_passage(state):
    try:
        runtime.move(state, 3)
        raised = False
    except ValueError:
        raised = True
    assert raised


@when("the party searches the room and finds it")
def party_searches_and_finds(state):
    found = runtime.search(state, scope="bones")
    assert found


@then("the party can walk through it")
def party_can_now_walk_through(state):
    runtime.move(state, 3)
    assert state.area_id == 3


# ---------------------------------------------------------------------
# No soft lock
# ---------------------------------------------------------------------

@given("a GM generates dungeons on twenty different seeds", target_fixture="dungeons")
def gm_generates_twenty_dungeons():
    return [procgen.generate_dungeon(seed, target_areas=10, dungeon_level=1)
            for seed in range(20)]


@then("a party in every one of them can always reach a way out")
def every_dungeon_is_reachable(dungeons):
    for doc in dungeons:
        all_ids = {a["id"] for a in doc["areas"]}
        assert procgen.reachable_area_ids(doc) == all_ids
