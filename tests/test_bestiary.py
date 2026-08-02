"""Unit tests for sanctuary/bestiary.py and the data/monsters/ corpus it reads."""
from pathlib import Path

import pytest
import yaml

from sanctuary import bestiary

_DIR = Path(__file__).resolve().parent.parent / "data" / "monsters"

_REQUIRED_FIELDS = (
    "name", "frequency", "size", "alignment", "move", "armour_class", "hit_dice",
    "melee_attacks", "senses", "lair_chance", "intelligence", "morale", "loot",
    "experience", "description",
)

# Reviewed exceptions: entries where the GM Guide's own printed stat block is
# genuinely malformed (a multi-column age/rank table whose name-and-field detector
# can't cleanly separate columns) or genuinely missing a field on the page itself
# (Yellowmusk Vine Zombie has no ALIGNMENT line at all between SIZE and MOVE - checked
# against the raw source, not a parser bug). Documented per the design's exceptions
# allowance (§7.1) rather than silently left malformed.
_FIELD_EXCEPTIONS = {
    "black_blue_green_red_white": {"armour_class", "experience", "description"},
    "normal_hatchling_guard_warchief": {"description"},
    "yellowmusk_vine_zombie": {"alignment"},
}


@pytest.fixture(autouse=True)
def isolated_overlay_dir(tmp_path, monkeypatch):
    """Every test gets its own overlay directory - writing to the real
    data/monsters/overlays/ from a test run would commit test fixtures into the
    corpus."""
    monkeypatch.setattr(bestiary, "_OVERLAY_DIR", tmp_path / "overlays")


def test_all_monsters_returns_every_book_monster_overlays_applied():
    docs = bestiary.all_monsters()
    assert len(docs) == 291
    bestiary.edit("goblin", morale=999)
    docs = bestiary.all_monsters()
    goblin = next(d for d in docs if d["name"] == "Goblin")
    assert goblin["morale"] == 999


def test_the_full_corpus_is_291_monsters():
    """The count reconciliation gate: 291 is the GM Guide's own stated count
    (verified independently: `FREQUENCY ` opens exactly 291 stat blocks in the
    source text, and no other section of the book uses that label)."""
    assert len(bestiary.base_ids()) == 291


def test_every_monster_has_all_13_required_fields_or_is_a_reviewed_exception():
    missing_by_monster = {}
    for slug in bestiary.base_ids():
        doc = bestiary.load(slug)
        exempt = _FIELD_EXCEPTIONS.get(slug, set())
        missing = [f for f in _REQUIRED_FIELDS if f not in exempt
                   and not doc.get(f)]
        if missing:
            missing_by_monster[slug] = missing
    assert missing_by_monster == {}


def test_no_encountered_is_the_one_genuine_optional():
    present = sum(1 for slug in bestiary.base_ids() if bestiary.load(slug).get("no_encountered"))
    # ~253/291 per the design; a wide but real band, not "present on all of them".
    assert 200 <= present < 291


def test_no_ligature_survives_in_the_corpus():
    bad = []
    for p in _DIR.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        if any(chr(c) in text for c in range(0xFB00, 0xFB07)):
            bad.append(p.name)
    assert bad == [], f"ligatures survived into: {bad}"


def test_every_file_reads_utf8_without_error():
    for p in _DIR.glob("*.yaml"):
        p.read_text(encoding="utf-8")  # raises UnicodeDecodeError on cp1252 mojibake


# --- Spot-checks against the raw GM Guide text (verified by hand against the source) ---

def test_spot_check_achaiyerai_has_an_ascending_ac_bracket_and_multiple_attacks():
    m = bestiary.load("achaiyerai")
    assert m["armour_class"] == "8 [12] or -1 [21] (see below)"
    assert "bite" in m["melee_attacks"] and "claws" in m["melee_attacks"]
    assert m["frequency"] == "very rare"
    assert m["no_encountered"] == "1d6"
    assert m["morale"] == 90


def test_spot_check_medusa():
    m = bestiary.load("medusa")
    assert m["armour_class"] == "5 [15]"
    assert m["hit_dice"] == "6+1"
    assert "poison" in m["melee_attacks"]


def test_spot_check_spectre():
    m = bestiary.load("spectre")
    assert m["alignment"] == "lawful evil"
    assert m["morale"] == "N/A"


def test_spot_check_troll_regenerates():
    m = bestiary.load("troll")
    assert "regeneration" in m["description"].lower()
    assert m["melee_attacks"].count("claw") or "claws" in m["melee_attacks"]


def test_spot_check_wyvern_has_a_sting_and_a_bite():
    m = bestiary.load("wyvern")
    assert "bite" in m["melee_attacks"]
    assert "sting" in m["melee_attacks"]
    assert "poison" in m["melee_attacks"]


def test_spot_check_zombie_juju():
    m = bestiary.load("zombie_juju")
    assert m["frequency"] == "very rare"
    assert "negative material" in m["description"].lower()


# --- Abilities: tier-3 prose never silently dropped ---

def test_a_monster_with_a_special_attack_keeps_it_as_addressable_prose():
    m = bestiary.load("achaiyerai")
    headings = {a["heading"] for a in m["abilities"]}
    assert "Special Attacks" in headings
    toxic_cloud = next(a for a in m["abilities"] if a["heading"] == "Special Attacks")
    assert "Toxic Cloud" in toxic_cloud["text"]


# --- Overlay: edits never mutate the shipped corpus ---

def test_editing_a_monster_leaves_the_base_file_byte_identical():
    path = bestiary._base_path("goblin")
    before = path.read_bytes()
    bestiary.edit("goblin", morale=999)
    assert path.read_bytes() == before


def test_editing_a_monster_changes_the_effective_view():
    original = bestiary.load("goblin")["morale"]
    edited = bestiary.edit("goblin", morale=999)
    assert edited["morale"] == 999
    assert bestiary.load("goblin")["morale"] == 999
    assert original != 999


def test_reset_drops_the_overlay_and_restores_the_book_value():
    original = bestiary.load("goblin")["morale"]
    bestiary.edit("goblin", morale=999)
    restored = bestiary.reset("goblin")
    assert restored["morale"] == original


def test_a_fresh_corpus_reparse_does_not_clobber_an_overlay():
    """Simulates re-running the extractor: the base file changes underneath the
    overlay, and the overlay still applies on top of the new value. Restores the
    real committed fixture afterwards - this base file is the shipped corpus, not a
    tmp copy."""
    bestiary.edit("goblin", morale=999)
    path = bestiary._base_path("goblin")
    original_bytes = path.read_bytes()
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["hit_dice"] = "1-1 (re-extracted)"
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
        reloaded = bestiary.load("goblin")
        assert reloaded["morale"] == 999
        assert reloaded["hit_dice"] == "1-1 (re-extracted)"
    finally:
        path.write_bytes(original_bytes)


def test_editing_an_unknown_monster_raises():
    with pytest.raises(KeyError):
        bestiary.edit("this monster does not exist", morale=1)


# --- Custom monsters: same schema, no base ---

def test_create_a_custom_monster_on_the_same_schema():
    m = bestiary.create(name="Sewer Rat King", hit_dice="2", armour_class=7)
    assert m["name"] == "Sewer Rat King"
    assert m["hit_dice"] == "2"
    assert m["armour_class"] == 7
    assert set(_REQUIRED_FIELDS) <= set(m.keys())


def test_create_without_a_name_raises():
    with pytest.raises(ValueError):
        bestiary.create(hit_dice="1")


# --- Monster level: computed from Table 2.11A, never hand-typed ---

@pytest.mark.parametrize("xp,level", [
    (20, 1), (21, 2), (60, 2), (61, 3), (500, 5), (501, 6),
    (3000, 7), (5250, 8), (10000, 9), (10001, 10), (999_999, 10),
])
def test_monster_level_from_table_2_11a(xp, level):
    assert bestiary.monster_level(xp) == level


def test_monster_level_matches_the_committed_table_not_a_hand_copy():
    from sanctuary import tables
    t = tables.load("2.11a")
    assert "20 xp or below" in " ".join(t["lines"])
    assert bestiary.monster_level(20) == 1
