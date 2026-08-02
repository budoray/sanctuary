"""Unit tests for sanctuary.treasure: loot classes, gems, jewellery, and the
magic-item determination chain."""
import re
from pathlib import Path

import yaml

from sanctuary.dice import Dice
from sanctuary import treasure

ROOT = Path(__file__).resolve().parent.parent
TREASURE_DIR = ROOT / "data" / "treasure"
ITEMS_DIR = ROOT / "data" / "items"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return s.strip("_")


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


# --- magic-item determination chain (2.13.1a onward) -----------------------

def test_magic_item_type_covers_every_d20_result():
    seen = set()
    for seed in range(200):
        seen.add(treasure.roll_magic_item_type(Dice(seed)))
    assert seen == {
        "armour_or_shield", "miscellaneous_magic", "miscellaneous_weapon",
        "potion", "ring", "rod_staff_wand", "scroll", "sword",
    }


def test_magic_item_type_same_seed_same_category():
    assert treasure.roll_magic_item_type(Dice(3)) == treasure.roll_magic_item_type(Dice(3))


def test_special_sword_and_weapon_and_ioun_stone_never_error_across_many_seeds():
    # 2.13.1n, 1o and 1u are flat d100 tables spanning the whole range
    # (including the book's own "96-00" wraparound row) - every seed must
    # resolve to a row, never raise.
    for seed in range(300):
        d = Dice(seed)
        treasure.roll_special_sword(d)
        treasure.roll_special_weapon(d)
        treasure.roll_ioun_stone(d)


def test_ioun_stone_never_returns_the_re_roll_instruction_itself():
    for seed in range(300):
        name = treasure.roll_ioun_stone(Dice(seed)).name
        assert not name.lower().startswith("re-roll")


def test_miscellaneous_magic_item_never_errors_across_many_seeds():
    # 2.13.1p (rarity) -> 1q/1r/1s/1t (specific item). Several of these
    # tables were only partially committed to data/tables/ by the shared
    # extractor (a table crossing a page break loses its remainder - see
    # data/treasure/misc_magic_items_overflow.yaml's note); this is the
    # regression test for that gap actually being closed.
    for seed in range(1000):
        item = treasure.roll_miscellaneous_magic_item(Dice(seed))
        assert item.name


def test_miscellaneous_magic_item_same_seed_same_item():
    a = treasure.roll_miscellaneous_magic_item(Dice(123))
    b = treasure.roll_miscellaneous_magic_item(Dice(123))
    assert a == b


def test_special_sword_percentages_match_the_book():
    """Table 2.13.1n: Vorpal Blade is a single-result 1-in-100 (row "90"),
    Luck Blade is the widest band, 54-69 (16/100)."""
    row = next(r for r in treasure._rows("2.13.1n") if "Vorpal" in r)
    assert row[0] == "90"
    row = next(r for r in treasure._rows("2.13.1n") if "Luck" in r)
    assert re.sub(r"[–—]", "-", row[0]) == "54-69"


# --- data/items corpus -------------------------------------------------

def test_item_corpus_is_substantial():
    files = list(ITEMS_DIR.glob("*.yaml"))
    assert len(files) > 250, f"only {len(files)} magic items extracted"


def test_every_item_file_parses_and_has_a_name():
    for p in ITEMS_DIR.glob("*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert doc["name"], f"{p.name} has no name"
        assert doc["source"]


def test_no_ligature_survives_in_item_corpus():
    bad = []
    for p in ITEMS_DIR.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        if any(chr(c) in text for c in range(0xFB00, 0xFB07)):
            bad.append(p.name)
    assert bad == [], f"ligatures survived into: {bad}"


def test_miscellaneous_magic_item_names_mostly_reconcile_with_the_corpus():
    """Every named (non-meta) result across the four miscellaneous-magic
    rarity tiers (2.13.1q-1t) should have a matching data/items file. A
    fuzzy prefix match absorbs the source's own footnote markers (e.g.
    "Strand of Prayer Beads1") and the odd table row a page-break wrapped
    mid-name - tracked with a threshold rather than exact equality so a
    handful of known, reported gaps don't make this test brittle."""
    item_slugs = [p.stem for p in ITEMS_DIR.glob("*.yaml")]
    total = hit = 0
    for table_id in ("2.13.1q", "2.13.1r", "2.13.1s", "2.13.1t"):
        for row in treasure._rows(table_id):
            name, _value = treasure._name_and_value(row[1:])
            if name.lower().startswith(("roll", "re-roll")):
                continue  # a re-roll instruction, not a named item
            total += 1
            slug = _slug(name)
            if any(slug.startswith(s) or s.startswith(slug) for s in item_slugs):
                hit += 1
    assert total > 150
    assert hit / total > 0.85, f"only {hit}/{total} miscellaneous magic items reconciled"
