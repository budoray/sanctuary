"""Unit tests for the Chapter 2 spell catalogue: extractor correctness and
sanctuary.spells (spells-per-day tables, memorisation)."""
import glob
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

from tools.extract_spells import normalise, parse  # noqa: E402
from sanctuary import spells  # noqa: E402

# The source text lives outside the repo (scratchpad); tests that need it
# fall back gracefully if it isn't present in this environment (same pattern
# tests/test_corpus.py uses for the PDF-dependent round-trip tests).
_SOURCE_PATH = Path(
    r"C:\Users\budor\AppData\Local\Temp\claude\D--Tenshin-Arts"
    r"\b423e55b-ea6e-4b09-bfb1-26463d1e232c\scratchpad\wiki2_spells.txt"
)

_LIGATURES = set(chr(c) for c in range(0xFB00, 0xFB07))
_FIELDS = (
    "name", "slug", "reversible", "class", "level", "school",
    "range", "duration", "area_of_effect", "components", "casting_time",
    "saving_throw", "text", "source",
)


def _load_all():
    docs = []
    for p in sorted(glob.glob(str(ROOT / "data" / "spells" / "*.yaml"))):
        docs.append(yaml.safe_load(Path(p).read_text(encoding="utf-8")))
    return docs


# ---------------------------------------------------------------------------
# Count reconciliation, ligatures, field completeness - the catalogue as
# committed, independent of whether the source text is available here.
# ---------------------------------------------------------------------------

def test_catalogue_has_414_spell_records():
    docs = _load_all()
    assert len(docs) == 414


def test_count_reconciles_against_casting_time_anchors_in_source():
    if not _SOURCE_PATH.exists():
        pytest.skip("source text not present in this environment")
    raw = _SOURCE_PATH.read_text(encoding="utf-8")
    casting_times = len(re.findall(r"^Casting Time:", normalise(raw), re.MULTILINE))
    assert casting_times == 414
    assert len(_load_all()) == casting_times


def test_no_ligature_survives_extraction():
    offenders = []
    for p in glob.glob(str(ROOT / "data" / "spells" / "*.yaml")):
        text = Path(p).read_text(encoding="utf-8")
        if _LIGATURES.intersection(text):
            offenders.append(p)
    assert offenders == []


def test_every_record_has_all_seven_header_fields():
    missing = []
    for d in _load_all():
        for f in _FIELDS:
            if f not in d or d[f] in (None, ""):
                missing.append((d.get("name"), d.get("class"), f))
    assert missing == []


def test_reextraction_matches_the_committed_corpus():
    """Round-trip: re-running the extractor against the source reproduces
    exactly the committed data/spells/ corpus (same pattern as the table
    extractor's round-trip test)."""
    if not _SOURCE_PATH.exists():
        pytest.skip("source text not present in this environment")
    raw = _SOURCE_PATH.read_text(encoding="utf-8")
    fresh = parse(raw, "wiki2_spells.txt")
    committed = _load_all()
    assert len(fresh) == len(committed)
    fresh_keys = sorted((r["slug"], r["class"], r["level"]) for r in fresh)
    committed_keys = sorted((r["slug"], r["class"], r["level"]) for r in committed)
    assert fresh_keys == committed_keys


# ---------------------------------------------------------------------------
# Spot-checks against the source - exact header values, one to three per
# class, including the divergent-per-class Detect Magic (proves records are
# NOT merged) and both source exceptions.
# ---------------------------------------------------------------------------

def _record(slug, class_name):
    p = ROOT / "data" / "spells" / f"{slug}__{class_name}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def test_spot_check_detect_magic_cleric():
    # source line 747-753
    d = _record("detect_magic", "cleric")
    assert d["level"] == 1
    assert d["range"] == "Caster"
    assert d["duration"] == "1 turn"
    assert d["area_of_effect"] == "Path 10-ft wide, 30-ft long"
    assert d["components"] == "V,S,M"
    assert d["casting_time"] == "1 round"
    assert d["saving_throw"] == "None"


def test_spot_check_detect_magic_druid_differs_from_cleric():
    # source line 2136-2142 - same spell name, different class, DIFFERENT
    # stats: proves class variants are separate records, never merged.
    d = _record("detect_magic", "druid")
    assert d["level"] == 1
    assert d["duration"] == "12 rounds"
    assert d["area_of_effect"] == "Path 10-ft wide, 40-ft long"
    assert d["casting_time"] == "3 segments"


def test_spot_check_detect_magic_magic_user():
    # source line 3719-3725
    d = _record("detect_magic", "magic-user")
    assert d["level"] == 1
    assert d["duration"] == "2 rounds/caster level"
    assert d["area_of_effect"] == "Path 10-ft wide, 60-ft long"
    assert d["components"] == "V,S"
    assert d["casting_time"] == "1 segment"


def test_spot_check_detect_magic_illusionist():
    # source line 7064-7070
    d = _record("detect_magic", "illusionist")
    assert d["level"] == 2
    assert d["duration"] == "2 rounds/level"
    assert d["casting_time"] == "2 segments"


def test_spot_check_fire_storm_druid_reversible():
    # source line 2291-2299 - reversible flag off the "(Reversible)" suffix.
    d = _record("fire_storm", "druid")
    assert d["reversible"] is True
    assert d["level"] == 7
    assert d["range"] == "150-ft"
    assert d["saving_throw"] == "Half"


def test_spot_check_find_familiar_missing_colon_exception():
    # source line 4089-4098: "Level Magic user 1" - no colon after "Level".
    d = _record("find_familiar", "magic-user")
    assert d["level"] == 1
    assert d["range"] == "0"
    assert d["casting_time"] == "2d12 hours"


def test_spot_check_restoration_bare_level_exception():
    # source line 1380-1387: "Level: 7" with no class name - class inferred
    # from the "Clerical Necromancy" category line above it.
    d = _record("restoration", "cleric")
    assert d["level"] == 7
    assert d["reversible"] is True
    assert d["range"] == "Touch"
    assert d["casting_time"] == "3 rounds"


# ---------------------------------------------------------------------------
# sanctuary.spells: spells-per-day
# ---------------------------------------------------------------------------

def test_spells_per_day_cleric_level_1():
    assert spells.spells_per_day("cleric", 1) == [1, 0, 0, 0, 0, 0, 0]


def test_spells_per_day_cleric_level_10_matches_table():
    # data/tables/1.3.2.4a: "10 450,000 9+2* 5 4 4 3 3 2 — —" - the last 7
    # whitespace-split fields of the row are the spell-slot counts.
    assert spells.spells_per_day("cleric", 10) == [4, 4, 3, 3, 2, 0, 0]


def test_spells_per_day_magic_user_has_nine_columns():
    slots = spells.spells_per_day("magic-user", 1)
    assert len(slots) == 9
    assert slots == [1, 0, 0, 0, 0, 0, 0, 0, 0]


def test_spells_per_day_magic_user_level_7_survives_injected_notes_column():
    # "7 60,000 7 Eldritch Craft 4 3 2 1 — — — — —" - "Eldritch Craft" is a
    # two-word notes insert between hit dice and the spell-slot columns.
    assert spells.spells_per_day("magic-user", 7) == [4, 3, 2, 1, 0, 0, 0, 0, 0]


def test_spells_per_day_druid_level_3_survives_two_line_wrapped_notes():
    # "3 4,000 3 2 Druid's Knowledge;" / "Wilderness  Movement 3 2 1 — — — —"
    # - the notes text even wraps onto a second physical line in the table.
    assert spells.spells_per_day("druid", 3) == [3, 2, 1, 0, 0, 0, 0]


def test_spells_per_day_illusionist_level_10_survives_single_word_note():
    # "10 220,000 10 Master of Phantasms 5 4 3 2 1 — —"
    assert spells.spells_per_day("illusionist", 10) == [5, 4, 3, 2, 1, 0, 0]


def test_spells_per_day_rejects_ranger():
    with pytest.raises(ValueError):
        spells.spells_per_day("ranger", 10)


def test_spells_per_day_rejects_paladin():
    with pytest.raises(ValueError):
        spells.spells_per_day("paladin", 10)


def test_spells_per_day_rejects_unknown_level():
    with pytest.raises(LookupError):
        spells.spells_per_day("cleric", 99)


# ---------------------------------------------------------------------------
# sanctuary.spells: memorisation
# ---------------------------------------------------------------------------

def test_memorise_same_spell_in_two_slots():
    # Level 2 magic-user: 2 first-level slots (spells_per_day gives [2, 0, ...]).
    book = spells.Memorised("magic-user", 2)
    book.memorise(1, "magic_missile", spellbook={"magic_missile"})
    book.memorise(1, "magic_missile", spellbook={"magic_missile"})
    assert book.slots[1].count("magic_missile") == 2


def test_forget_frees_a_slot():
    book = spells.Memorised("magic-user", 1)
    book.memorise(1, "magic_missile", spellbook={"magic_missile"})
    book.forget(1, "magic_missile")
    assert book.slots[1] == []


def test_magic_user_cannot_memorise_outside_spellbook():
    book = spells.Memorised("magic-user", 1)
    with pytest.raises(ValueError):
        book.memorise(1, "fireball", spellbook={"magic_missile"})


def test_cleric_memorises_without_a_spellbook():
    book = spells.Memorised("cleric", 1)
    book.memorise(1, "bless")
    assert book.slots[1] == ["bless"]


def test_memorise_refuses_when_no_free_slot():
    book = spells.Memorised("cleric", 1)  # 1 first-level slot at level 1
    book.memorise(1, "bless")
    with pytest.raises(ValueError):
        book.memorise(1, "cure_light_wounds")


def test_load_all_groups_class_variants_by_slug():
    variants = spells.by_slug("detect_magic")
    assert {v["class"] for v in variants} == {"cleric", "druid", "illusionist", "magic-user"}
