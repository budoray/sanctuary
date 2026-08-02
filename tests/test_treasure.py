"""Unit tests for sanctuary.treasure: loot classes, gems, jewellery."""
from pathlib import Path

from sanctuary.dice import Dice
from sanctuary import treasure

ROOT = Path(__file__).resolve().parent.parent
TREASURE_DIR = ROOT / "data" / "treasure"


def _session(seed, class_name):
    d = Dice(seed)
    return treasure.roll_hoard(d, class_name)


def test_same_seed_gives_the_identical_hoard():
    a = _session(42, "hoard_1")
    b = _session(42, "hoard_1")
    assert a == b


def test_different_seeds_usually_differ():
    assert _session(42, "hoard_1") != _session(43, "hoard_1")


def test_a_hoard_can_come_up_empty():
    # Hardcoded seed found by brute force (see history) rather than a stub -
    # exercises the real Dice path the same as any other hoard.
    assert treasure.roll_hoard(Dice(5), "hoard_1") == []


def test_all_loot_classes_are_present():
    names = treasure.loot_class_names()
    assert len(names) == 9 + 5 + 12  # Hoard 1-9, Individual 1-5, Cache 1-12
    assert "hoard_1" in names and "individual_1" in names and "cache_12" in names


def test_individual_classes_always_produce_their_amount():
    # Individual 1-5 have no chance line - "3d8 cp each" always happens.
    for seed in range(20):
        line, = treasure.roll_hoard(Dice(seed), "individual_1")
        assert line.kind == "cp"
        assert 3 <= line.amount <= 24


def test_hoard_1_percentages_and_quantities_match_the_book():
    """The book's own worked example (2.12.1.A): 25% 1d6x1000 cp, 30% 1d6x1000
    sp, 35% 1d6x1000 ep, 40% 1d10x1000 gp, 25% 1d4x100 pp, 60% 4d10 gems,
    60% 3d10 jewellery, 30% 3 magic items (any type)."""
    lines = treasure._loot_classes()["hoard_1"]["lines"]
    by_kind = {l["kind"]: l for l in lines}
    assert by_kind["cp"] == {"percent": 25, "qty": "1d6", "multiplier": 1000, "kind": "cp"}
    assert by_kind["gp"] == {"percent": 40, "qty": "1d10", "multiplier": 1000, "kind": "gp"}
    assert by_kind["gems"] == {"percent": 60, "qty": "4d10", "multiplier": 1, "kind": "gems"}
    assert by_kind["magic_item"]["percent"] == 30
    assert by_kind["magic_item"]["qty"] == "3"


def test_hoard_7_percentages_and_quantities_match_the_book():
    """2.12.1.G: 50% 10d4x1000 gp, 50% 1d20x100 pp, 30% 5d4 gems, 25% 1d10
    jewellery, 35% 1 scroll + 4 other magic items."""
    lines = treasure._loot_classes()["hoard_7"]["lines"]
    by_kind = {l["kind"]: l for l in lines}
    assert by_kind["gp"] == {"percent": 50, "qty": "10d4", "multiplier": 1000, "kind": "gp"}
    assert by_kind["pp"] == {"percent": 50, "qty": "1d20", "multiplier": 100, "kind": "pp"}
    assert by_kind["gems"] == {"percent": 30, "qty": "5d4", "multiplier": 1, "kind": "gems"}
    assert by_kind["jewellery"] == {"percent": 25, "qty": "1d10", "multiplier": 1, "kind": "jewellery"}


def test_cache_11_percentages_and_quantities_match_the_book():
    """2.12.1.Y: a Cache 11 is nothing but a 70% chance of 2d6x1000 gp."""
    lines = treasure._loot_classes()["cache_11"]["lines"]
    assert lines == [{"percent": 70, "qty": "2d6", "multiplier": 1000, "kind": "gp"}]


def test_gem_value_is_one_of_the_six_book_categories():
    d = Dice(11)
    for _ in range(50):
        value, category = treasure.gem_value(d)
        assert value > 0
        assert category in treasure._GEM_CATEGORIES


def test_gem_value_same_seed_same_result():
    a = treasure.gem_value(Dice(11))
    b = treasure.gem_value(Dice(11))
    assert a == b


def test_jewellery_reaches_every_form_and_every_d100_value():
    # Every row of the d100 form table must be reachable, including the
    # book's own 98-00 wraparound (see jewellery_types.yaml's note).
    forms = {r["item"] for r in treasure._jewellery_rows()}
    seen = set()
    for seed in range(400):
        _, form, tier = treasure.jewellery(Dice(seed))
        assert tier in {t[0] for t in treasure.TIER_DICE}
        seen.add(form)
    assert seen == forms


def test_no_ligature_survives_in_treasure_data():
    bad = []
    for p in TREASURE_DIR.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        if any(chr(c) in text for c in range(0xFB00, 0xFB07)):
            bad.append(p.name)
    assert bad == [], f"ligatures survived into: {bad}"
