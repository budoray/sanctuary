import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "data" / "tables"


def load(table_id: str) -> dict:
    matches = list(TABLES.glob(f"{table_id}_*.yaml"))
    assert matches, f"no committed table {table_id}"
    return yaml.safe_load(matches[0].read_text(encoding="utf-8"))


def test_corpus_is_committed_and_substantial():
    files = list(TABLES.glob("*.yaml"))
    assert len(files) > 150, f"only {len(files)} tables extracted"


def test_no_ligatures_survived():
    bad = []
    for p in TABLES.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        if any(chr(c) in text for c in range(0xFB00, 0xFB07)):
            bad.append(p.name)
    assert bad == [], f"ligatures survived into: {bad}"


def test_spot_check_fighter_advancement():
    t = load("1.3.4.4a")
    assert "FIGHTER" in t["name"].upper()
    joined = " | ".join(t["lines"])
    assert "9 250,000 9" in joined, "fighter L9 should need 250,000 XP"


def test_spot_check_fighter_to_hit():
    t = load("1.3.4.4c")
    rows = [ln for ln in t["lines"] if ln.startswith("1 ")]
    assert rows, "no level-1 row in the fighter to-hit table"
    # Level 1 needs 10 to hit AC 10 - the first number after the level.
    assert rows[0].split()[1] == "10"


def test_spot_check_monster_to_hit_is_from_the_gm_guide():
    t = load("2.1.2a")
    assert "Gamemaster" in t["source"]
    assert any(ln.startswith("8-9+") or ln.startswith("8\u20139+") for ln in t["lines"])


def test_every_table_has_an_id_name_and_lines():
    for p in TABLES.glob("*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert doc["id"], p.name
        assert doc["name"], p.name
        assert doc["lines"], p.name


def test_corpus_is_internally_consistent_without_the_pdfs():
    """Always runs, PDFs or not - this is what actually verifies the corpus
    in an environment where the two round-trip tests below are skipped.
    It cannot catch a table that was extracted wrong to begin with (only
    re-running the extractor against the source PDFs can - see
    test_extraction_round_trips), but it does catch a table that was
    hand-edited AFTER extraction: a hand-edit is very unlikely to also keep
    every file's shape, id uniqueness and reachability intact.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from sanctuary import tables as _tables
    _tables._index.cache_clear()

    files = list(TABLES.glob("*.yaml"))
    assert files, "no committed tables"

    ids = set()
    for p in files:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        for key in ("id", "name", "source", "lines"):
            assert doc.get(key), f"{p.name} missing {key!r}"
        assert not any(chr(c) in p.read_text(encoding="utf-8") for c in range(0xFB00, 0xFB07)), (
            f"ligature survived into {p.name}")
        ids.add(doc["id"].lower())

    index = _tables._index()
    assert set(index) == ids, (
        "tables._index() and the committed file set disagree on which ids exist: "
        f"index-only {set(index) - ids}, files-only {ids - set(index)}")
    n_files_via_index = sum(len(paths) for paths in index.values())
    assert n_files_via_index == len(files), (
        f"{len(files)} files on disk but tables._index() only reaches "
        f"{n_files_via_index} of them")
    assert len(ids) == len(index), "unique-id count disagrees with the self-check's own count"


def test_abandoned_tables_are_the_reviewed_set():
    """find_tables() abandons a whole block only when it has no recognisable
    data row (`_has_data_row`) AND its id duplicates a block already kept
    from the same book - the "TABLE X: NAME CONTINUED" caption artifact
    case (see tools/extract.py). Every one of these ids still has a real
    committed file from the sibling block that *did* have data, so nothing
    should ever vanish from the corpus entirely; this pins both facts so a
    future regex tweak that silently drops or newly abandons a table fails
    loudly instead of just shrinking the corpus under a passing
    `len(files) > 150` check.
    """
    from tools.extract import find_tables, pdf_text

    pdfs = [
        Path("C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"),
        Path("C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf"),
    ]
    for p in pdfs:
        if not p.exists():
            import pytest
            pytest.skip(
                f"source PDF missing: {p} does not exist in this environment - "
                "the corpus round-trip guarantee (data/tables/ matches a fresh "
                "extraction of the book) is UNVERIFIED here. See "
                "test_corpus_is_internally_consistent_without_the_pdfs for what "
                "still runs without the PDFs.")

    abandoned = set()
    for p in pdfs:
        find_tables(pdf_text(p))
        abandoned |= set(find_tables.last_abandoned)

    assert abandoned == {"1.3.7.4b", "1.6.12c", "2.12.5a", "2.2.2b", "2.8.1b", "2.9.1a"}, (
        f"abandoned set changed: {sorted(abandoned)}")

    committed_ids = {p.name.split("_", 1)[0] for p in TABLES.glob("*.yaml")}
    fully_missing = abandoned - committed_ids
    assert fully_missing == set(), (
        f"a table id vanished from the corpus entirely: {fully_missing}")


def test_kept_rows_that_read_like_prose_are_not_dropped():
    """Round 1 tightened row recognition so hard that genuine data rows with
    no digit - "Lieutenant Special as type as type as type as type as
    type" - were indistinguishable from an intro sentence and got silently
    skipped. Round 2 stopped classifying rows line by line entirely (see
    tools/extract.py); these pin that the two known casualties are back.
    """
    ship_crews = load("2.2.2c")
    assert any(ln.startswith("Lieutenant") for ln in ship_crews["lines"])

    witch_priest = load("2.2.7.1b")
    assert any(ln.startswith("Ettin") for ln in witch_priest["lines"])


def test_no_prose_leaked_into_a_table():
    """Round 1's other bug: an ALL-CAPS line (a chapter title, a hireling's
    name) could open a table block, after which every line was kept
    unconditionally until the next terminator - so "SOLDIERS CONTINUED"
    (no data of its own) swallowed the Alchemist's description, and
    "NIGHTTIME ENCOUNTERS CONTINUED" swallowed Chapter Nine's intro. Both
    caption blocks are now abandoned as duplicates (see
    test_abandoned_tables_are_the_reviewed_set) rather than kept with leaked
    prose."""
    soldiers = load("2.2.2b")
    assert "Alchemist" not in " ".join(soldiers["lines"])

    for p in TABLES.glob("*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "CHAPTER NINE: WILDERNESS ENCOUNTER TABLES" not in " ".join(doc["lines"]), p.name


def test_unarmed_to_hit_keeps_its_first_row_flavour_text():
    """Regression guard for the row round 1 lost from the *other* direction:
    the first row's target number ("2") is preceded by a 3-line description
    ("Attacker is unarmoured (this includes...") that a naive digit/prose
    split discarded. The dumb, whole-block collection in round 2 keeps it."""
    t = load("1.6.12a")
    joined = " ".join(t["lines"])
    assert "Attacker is unarmoured" in joined
    assert "even if they have a better AC than 10 [10])" in joined


def test_extraction_round_trips():
    """Re-running the extractor reproduces the committed corpus exactly."""
    import tempfile

    from tools.extract import find_tables, pdf_text, write_tables

    pdfs = {
        "OSRIC-3.0-Player-Guide-FINAL.v.7.pdf": Path(
            "C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"),
        "OSRIC_3.0_Gamemaster_Guide.pdf": Path(
            "C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf"),
    }
    for p in pdfs.values():
        if not p.exists():
            import pytest
            pytest.skip(
                f"source PDF missing: {p} does not exist in this environment - "
                "the corpus round-trip guarantee (data/tables/ matches a fresh "
                "extraction of the book) is UNVERIFIED here. See "
                "test_corpus_is_internally_consistent_without_the_pdfs for what "
                "still runs without the PDFs.")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for name, p in pdfs.items():
            write_tables(find_tables(pdf_text(p)), out, source=name)
        fresh = {q.name: q.read_text(encoding="utf-8") for q in out.glob("*.yaml")}

    committed = {q.name: q.read_text(encoding="utf-8") for q in TABLES.glob("*.yaml")}
    assert set(fresh) == set(committed), (
        f"only fresh: {sorted(set(fresh) - set(committed))[:5]}; "
        f"only committed: {sorted(set(committed) - set(fresh))[:5]}")
    differing = [k for k in committed if committed[k] != fresh[k]]
    assert differing == [], f"committed tables diverge from the book: {differing[:5]}"


def test_truncation_gate_detects_a_deliberately_shortened_table():
    """The detection gate for the page-break truncation bug (2.12.5a,
    2.13.1r/1s/1t): `continuity_gaps` flags a numbered-range table whose
    rows stop tiling, which is exactly the shape a page break silently
    eating rows leaves behind. Proven here by deliberately truncating a
    real, clean committed table (dropping a row from the middle, the same
    shape the old page-marker bug produced) and reverting - the gate must
    fire on the broken version and stay silent on the real one, on the
    same data, so this isn't just tuned to reject one fixture.
    """
    from tools.extract import continuity_gaps

    real_lines = load("1.3.4.4a")["lines"]  # FIGHTER LEVEL ADVANCEMENT, levels 1-20
    assert continuity_gaps(real_lines) == [], "the real, complete table must not be flagged"

    truncated = [ln for ln in real_lines if not ln.startswith("10 ")]  # drop level 10
    assert truncated != real_lines
    gaps = continuity_gaps(truncated)
    assert gaps, "removing a row from a contiguous level table must be caught"
