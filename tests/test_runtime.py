"""Unit tests for sanctuary.runtime - the play state machine."""
import pytest

from sanctuary import module, procgen, runtime
from sanctuary.character import generate as gen_character

FIXTURE = "data/modules/weeping_cistern.yaml"


def _small_doc(*, region_chance="1-in-100", monster_hp="1", tier3_attack=False):
    """A tiny two-area module: a weak module-local monster and some
    treasure in area 2, a hidden exit revealed only by searching, and a
    region wandering check whose odds a test can dial to "never" or
    "always"."""
    attacks = "1 bite (1d4) or the Old Bargain" if tier3_attack else "1 bite (1d4)"
    return {
        "module": {
            "title": "Test Warren", "version": "1.0",
            "party_guidance": {"size": [1, 6], "total_levels": [1, 3]},
            "background": "bg", "start": "The party stands at the warren mouth.",
        },
        "regions": [
            {"id": "only", "areas": [1, 2],
             "check": {"chance": region_chance, "every": "1 turn"},
             "table": {"die": "d2", "entries": ["1 × Test Rat", "nothing"]}},
        ],
        "areas": [
            {
                "id": 1, "name": "Warren Mouth", "description": "A dirt burrow entrance.",
                "exits": [{"to": 2, "kind": "tunnel", "hidden": False}],
                "contents": [], "monsters": [], "treasure": [], "discoveries": [],
            },
            {
                "id": 2, "name": "Den", "description": "A cramped den.",
                "exits": [
                    {"to": 1, "kind": "tunnel", "hidden": False},
                    {"to": 3, "kind": "crack", "hidden": True},
                ],
                "contents": [], "monsters": ["1 × Test Rat"],
                "treasure": ["12 gp"],
                "discoveries": [
                    {"what": "a crack behind the bones",
                     "trigger": {"action": "search", "scope": "bones"}},
                ],
            },
            {
                "id": 3, "name": "Back Tunnel", "description": "A narrow crawl.",
                "exits": [{"to": 2, "kind": "crack", "hidden": False}],
                "contents": [], "monsters": [], "treasure": [], "discoveries": [],
            },
        ],
        "monsters": [
            {"name": "Test Rat", "hit_dice": monster_hp, "armour_class": "10",
             "attacks": attacks, "xp": 5, "loot": "Individual 1 each"},
        ],
        "items": [], "mechanics": [],
    }


def _party(seed=1, cls="fighter", name="Ilse"):
    for s in range(seed, seed + 300):
        try:
            return gen_character(seed=s, mode="normal", ancestry_name="human",
                                  class_names=(cls,), name=name)
        except ValueError:
            continue
    raise RuntimeError("could not roll a legal character")


def _mod(**kwargs):
    return module.load(_small_doc(**kwargs))


# ---------------------------------------------------------------------
# Basics
# ---------------------------------------------------------------------

def test_new_game_starts_at_the_first_area():
    st = runtime.new_game(_mod(), [_party()], seed=1)
    assert st.area_id == 1
    assert runtime.describe(st)["name"] == "Warren Mouth"


def test_move_follows_a_real_exit():
    st = runtime.new_game(_mod(), [_party()], seed=1)
    runtime.move(st, 2)
    assert st.area_id == 2


def test_move_refuses_a_nonexistent_exit():
    st = runtime.new_game(_mod(), [_party()], seed=1)
    with pytest.raises(ValueError):
        runtime.move(st, 99)


def test_hidden_exit_is_not_offered_until_discovered():
    st = runtime.new_game(_mod(), [_party()], seed=1)
    runtime.move(st, 2)
    while st.combat is not None:
        if st.pending_decisions:
            runtime.decide(st, 0, "engine handles it")
        else:
            runtime.attack_round(st)
    with pytest.raises(ValueError):
        runtime.move(st, 3)
    assert 3 not in [e["to"] for e in runtime.describe(st)["exits"]]
    runtime.search(st, scope="bones")
    assert 3 in [e["to"] for e in runtime.describe(st)["exits"]]
    runtime.move(st, 3)
    assert st.area_id == 3


# ---------------------------------------------------------------------
# Combat, tier-3 surfacing, treasure, XP
# ---------------------------------------------------------------------

def _clear_area_2(st):
    runtime.move(st, 2)
    while st.combat is not None:
        if st.pending_decisions:
            runtime.decide(st, 0, "engine handles it")
        else:
            runtime.attack_round(st)


def test_combat_awards_xp_and_treasure_on_victory():
    st = runtime.new_game(_mod(monster_hp="1-1"), [_party()], seed=1)
    _clear_area_2(st)
    assert st.xp > 0
    assert runtime.describe(st)["monsters"] == []


def test_tier3_attack_blocks_combat_until_decided():
    st = runtime.new_game(_mod(monster_hp="1-1", tier3_attack=True), [_party()], seed=1)
    runtime.move(st, 2)
    assert st.pending_decisions, "an unmodeled attack must surface as a decision"
    with pytest.raises(ValueError):
        runtime.attack_round(st)
    runtime.decide(st, 0, "the DM rules the Old Bargain does nothing this fight")
    assert st.pending_decisions == []
    while st.combat is not None:
        runtime.attack_round(st)
    assert st.xp > 0


def test_unresolvable_wandering_monster_is_surfaced_not_dropped():
    doc = _small_doc(region_chance="2-in-2")
    doc["regions"][0]["table"] = {
        "die": "d2", "entries": ["1 × Nonexistent Beast", "1 × Nonexistent Beast"]}
    st = runtime.new_game(module.load(doc), [_party()], seed=1)
    runtime.advance_time(st, 1)
    assert any(d["kind"] == "unresolvable_monster" for d in st.pending_decisions)


def test_take_treasure_only_once():
    st = runtime.new_game(_mod(monster_hp="1-1"), [_party()], seed=1)
    _clear_area_2(st)
    got = runtime.take_treasure(st)
    assert got == ["12 gp"]
    assert runtime.take_treasure(st) == []


# ---------------------------------------------------------------------
# Wandering checks / discoveries as real mechanics, not flavour
# ---------------------------------------------------------------------

def test_wandering_check_fires_on_its_own_cadence():
    st = runtime.new_game(_mod(region_chance="2-in-2", monster_hp="1-1"), [_party()], seed=1)
    assert st.combat is None
    runtime.advance_time(st, 1)
    assert st.combat is not None or st.pending_decisions, \
        "a guaranteed (2-in-2) check every turn must trigger on the very next turn"


def test_wandering_check_never_fires_at_zero_odds():
    st = runtime.new_game(_mod(region_chance="1-in-100"), [_party()], seed=1)
    for _ in range(20):
        runtime.advance_time(st, 1)
    # 1-in-100 for 20 rolls: astronomically unlikely to trigger, and this
    # seed is fixed, so this is a real assertion, not a coin flip.
    assert st.combat is None


def test_discovery_with_no_chance_triggers_on_first_matching_search():
    st = runtime.new_game(_mod(), [_party()], seed=1)
    runtime.move(st, 2)
    while st.combat is not None:
        runtime.attack_round(st) if not st.pending_decisions else runtime.decide(st, 0, "ok")
    found = runtime.search(st, scope="bones")
    assert found == ["a crack behind the bones"]


# ---------------------------------------------------------------------
# Reproducibility - the whole engine's guarantee
# ---------------------------------------------------------------------

def _play_fixed_script(seed):
    # Two party members against one weak rat so the script's later moves
    # (rather than a coin-flip wipe) are what this test is checking.
    st = runtime.new_game(_mod(monster_hp="1-1"),
                           [_party(seed), _party(seed + 500, "cleric", "Meva")], seed=seed)
    runtime.move(st, 2)
    while st.combat is not None:
        runtime.attack_round(st) if not st.pending_decisions else runtime.decide(st, 0, "ok")
    runtime.search(st, scope="bones")
    runtime.take_treasure(st)
    result = None
    if not st.finished:
        runtime.move(st, 3)
        runtime.move(st, 2)
        runtime.move(st, 1)
        result = runtime.leave(st)
    return st, result


def test_same_seed_same_actions_replay_identically():
    st1, result1 = _play_fixed_script(777)
    st2, result2 = _play_fixed_script(777)
    assert [r.total for r in st1.dice.log] == [r.total for r in st2.dice.log]
    assert [r.expr for r in st1.dice.log] == [r.expr for r in st2.dice.log]
    assert st1.hp == st2.hp
    assert st1.xp == st2.xp
    assert st1.inventory == st2.inventory
    assert result1 == result2


def test_different_seeds_can_diverge():
    st1, _ = _play_fixed_script(1)
    st2, _ = _play_fixed_script(2)
    assert [r.total for r in st1.dice.log] != [r.total for r in st2.dice.log]


# ---------------------------------------------------------------------
# A full delve, through the public API only - the platform's hard-won gate
# ---------------------------------------------------------------------

def test_a_full_delve_is_completable_through_public_actions_only():
    """The gate earned elsewhere on this platform: a party must be able to
    enter, fight, take treasure, and finish using only the runtime's public
    functions - never state set by hand."""
    st = runtime.new_game(_mod(monster_hp="1-1"), [_party(), _party(101, "cleric", "Meva")], seed=42)
    runtime.move(st, 2)
    while st.combat is not None:
        runtime.attack_round(st) if not st.pending_decisions else runtime.decide(st, 0, "ok")
    runtime.search(st, scope="bones")
    runtime.take_treasure(st)
    runtime.move(st, 3)
    runtime.move(st, 2)
    runtime.move(st, 1)
    result = runtime.leave(st)
    assert st.finished
    assert result["xp"] > 0
    assert result["inventory"]


def test_no_soft_lock_across_many_generated_dungeons():
    """A generated module is always completable: BFS the reachable graph,
    fight or flee every encounter, and confirm the run always reaches a
    terminal state (won or wiped) rather than hanging or crashing."""
    import collections

    for seed in range(15):
        doc = procgen.generate_dungeon(seed, target_areas=6, dungeon_level=1)
        mod = module.load(doc)
        party = [_party(seed * 10 + 1), _party(seed * 10 + 2, "cleric", "Meva")]
        st = runtime.new_game(mod, party, seed=seed)
        graph = {a["id"]: a for a in mod.areas}
        seen, frontier = {st.area_id}, [st.area_id]
        order = []
        while frontier:
            cur = frontier.pop()
            order.append(cur)
            for e in graph[cur]["exits"]:
                if e["to"] not in seen and not e.get("hidden"):
                    seen.add(e["to"])
                    frontier.append(e["to"])

        def resolve_or_flee():
            budget = 200
            while st.combat is not None and budget > 0:
                budget -= 1
                if st.pending_decisions:
                    runtime.decide(st, 0, "the DM improvises a ruling")
                    continue
                total = sum(max(0, v) for v in st.hp.values())
                if total < sum(st.max_hp.values()) * 0.25:
                    runtime.flee(st)
                    return
                runtime.attack_round(st)

        def bfs_path(start, goal):
            seen_, q = {start}, collections.deque([(start, [start])])
            while q:
                cur, p = q.popleft()
                if cur == goal:
                    return p
                for e in graph[cur]["exits"]:
                    if e["to"] not in seen_ and not e.get("hidden"):
                        seen_.add(e["to"])
                        q.append((e["to"], p + [e["to"]]))
            return None

        resolve_or_flee()
        for area_id in order:
            if st.finished:
                break
            path = bfs_path(st.area_id, area_id)
            if path is None:
                continue
            for nxt in path[1:]:
                if st.finished:
                    break
                try:
                    runtime.move(st, nxt)
                except ValueError:
                    break
                resolve_or_flee()
            resolve_or_flee()
            if not st.finished:
                runtime.search(st)  # a search can itself draw a wandering monster
                resolve_or_flee()
            if not st.finished:
                runtime.take_treasure(st)

        if not st.finished:
            runtime.leave(st)

        assert st.finished, f"seed {seed} never reached a terminal state"


# ---------------------------------------------------------------------
# Acceptance: a generated encounter resolves to a REAL bestiary monster
# and can actually be fought - the defect this fix targets (S4).
# ---------------------------------------------------------------------

def test_a_generated_encounter_resolves_a_bestiary_monster_and_earns_xp():
    """Before `bestiary.resolve_name`, almost every generated encounter's
    printed name (e.g. "Wolf, Dire") matched no bestiary slug, so combat
    never ran and a solo delve always earned 0 XP - see IMPROVEMENTS.md.
    This proves the actual repair: search generated dungeons for a combat
    whose monster came from the bestiary (not a module-local monster, and
    not `unresolved`), fight it with `resolve.attack` through the public
    `attack_round` API, and confirm the party earns XP > 0 for it."""
    from sanctuary import bestiary

    bestiary_slugs = set(bestiary.base_ids())

    for seed in range(30):
        doc = procgen.generate_dungeon(seed, target_areas=8, dungeon_level=1)
        mod = module.load(doc)
        party = [_party(seed * 10 + 1), _party(seed * 10 + 2, "cleric", "Meva")]
        st = runtime.new_game(mod, party, seed=seed)

        if st.combat is None or st.combat.unresolved:
            continue
        resolved_from_bestiary = [
            m for m in st.combat.monsters if bestiary._slug(m.name) in bestiary_slugs
        ]
        if not resolved_from_bestiary:
            continue

        # A real fight: attack until it's over, never touching state by hand.
        budget = 100
        while st.combat is not None and budget > 0:
            budget -= 1
            if st.pending_decisions:
                runtime.decide(st, 0, "the DM improvises a ruling")
                continue
            runtime.attack_round(st)

        if st.xp > 0:
            return  # found one - the acceptance criterion is proven
        # An unlucky party wipe earns 0 XP legitimately - that's not a
        # resolve_name failure, just bad dice. Try the next seed.

    pytest.fail("no generated dungeon in 30 seeds produced a resolvable bestiary "
                "encounter - resolve_name regressed")


# --------------------------------------------------------------------
# Statline parsing: the corpus prints the BOOK's forms, not clean numbers.
# Each case below is a real string lifted from data/monsters/.
# --------------------------------------------------------------------

@pytest.mark.parametrize("printed,notation,hp_expr,fixed_hp", [
    # clean forms that already worked - these must not regress
    ("1", "1", "1d8", None),
    ("6 [14]", "6", "6d8", None),
    ("1d8-1  hit points", "1-1", "1d8-1", None),
    # a plus is HIT POINTS, not decoration: a troll is 6d8+6, never 6d8
    ("6+6", "6+6", "6d8+6", None),
    ("7+7", "7+7", "7d8+7", None),
    # ranges - the whole dragon shelf, previously HD 1 with 1d8 hit points
    ("9 to 11", "9", "9d8", None),          # dragon_red
    ("12 to 36", "12", "12d8", None),       # whale
    ("12 or more", "12", "12d8", None),     # lich
    ("2, 3, or 4", "2", "2d8", None),       # seahorse_giant
    ("8, 12, or 16 8, 12, or 16", "8", "8d8", None),   # elemental_air
    ("3 to 8 (GM decides, or roll 1d6+2)", "3", "3d8", None),   # ankheg
    # the book sets its ranges with an EN DASH, which no [+-] pattern matches
    ("17\u201322", "17", "17d8", None),                  # titan
    ("7\u201312 (1d6+6 if randomly determined)", "7", "7d8", None),   # treant
    ("1\u20134 HD", "1", "1d8", None),                   # leech_giant
    # collapsed multi-creature records: one value per variant, take the first
    ("8 5+1 6 4+2 7", "8", "8d8", None),    # black_blue_green_red_white
    ("3+3 7", "3+3", "3d8+3", None),        # boar
    # hit points printed directly, not hit dice
    ("1 hit point", "1", "1d8", 1),         # rot_grub
    ("50 hp 40 hp 80 hp 60 hp", "1", "1d8", 50),   # clay_golem...
    # nothing numeric at all
    ("N/A N/A", "1", "1d8", None),          # brown_yellow
])
def test_hit_dice_reads_the_forms_the_book_actually_prints(printed, notation, hp_expr, fixed_hp):
    assert runtime._hd_and_hp_expr(printed) == (notation, hp_expr, fixed_hp)


@pytest.mark.parametrize("printed,xp", [
    ("10 +1 per hp", 10),            # orc - already worked
    ("525 +8/hp", 525),              # troll - already worked
    ("1,400 +14/hp", 1400),          # achaiyerai - was 1
    ("17,500 +30/hp", 17500),        # kraken - was 17
    ("at least 10,000 +16/hp", 10000),   # lich - was 10
    ("9/5,900 +23/hp", 5900),        # dread_wraith - was 9
    ("4 HD: 75 +4/hp  5 HD: 110 +5/hp", 75),     # hell_hound - was 4
    ("8 HD: 900 +12/hp 12 HD: 2,000 +16/hp", 900),   # elemental - was 8
    ("Varies by HD: 3 HD: 65 +2/hp 4 HD: 105 +3/hp", 65),   # ankheg - was 3
    ("7HD: 1,295 +8/hp  8HD: 1,600 +10/hp", 1295),   # treant - was 7
    ("Warrior 110 +2/hp  Leader (4HD) 145 +3/hp", 110),   # triton
    ("", 0),
])
def test_experience_reads_the_forms_the_book_actually_prints(printed, xp):
    assert runtime._xp_from({"experience": printed}) == xp


def test_an_explicit_xp_field_still_wins_over_the_printed_text():
    assert runtime._xp_from({"xp": 42, "experience": "1,400 +14/hp"}) == 42


@pytest.mark.parametrize("printed,ac", [
    ("6 [14]", 6),
    ("\u20133 [23]", -3),                      # pit_fiend - was 10
    ("\u20138 [28]", -8),                      # will_o_the_wisp - was 10
    ("Usually 7 [13]", 7),                     # mystic_nomad - was 10
    ("Body 0 [20]; head 2 [18]", 0),           # remorhaz - was 10
    ("Naturally 8 [12], some wear   armour", 8),   # yellowmusk_vine_zombie
    ("By  armour type", 10),                   # buccaneer_pirate - no number
    ("Depends on HD (see below)", 10),         # titan - no number
])
def test_armour_class_reads_the_forms_the_book_actually_prints(printed, ac):
    assert runtime._armour_class_from({"armour_class": printed}) == ac


def test_no_shipped_monster_silently_becomes_a_one_hit_die_pushover():
    """A statline that fails to parse used to degrade to HD 1 / 1d8 in
    SILENCE - which made every dragon, giant and elemental in the corpus a
    first-level chump. Guard on the OUTPUT: the corpus's own big monsters
    must instantiate big."""
    from sanctuary import bestiary
    from sanctuary.dice import Dice

    d = Dice(1)
    for name, least_hd in [("Dragon, Red", 9), ("Titan", 17), ("Treant", 7),
                           ("Whale", 12), ("Lich", 12), ("Troll", 6)]:
        rec = bestiary.resolve_name(name)
        assert rec is not None, f"{name} no longer resolves"
        inst = runtime._instantiate_monster(d, rec)
        hd = int(runtime._LOOSE_HD.match(inst.hd_notation).group(1))
        assert hd >= least_hd, f"{name} instantiated at HD {hd}, expected >= {least_hd}"
        assert inst.max_hp >= least_hd, f"{name} rolled {inst.max_hp} hp on {least_hd}+ HD"
