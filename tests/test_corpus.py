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


def test_abandoned_tables_are_the_reviewed_set():
    """find_tables() drops a block if it never finds a real data row (e.g. a
    "TABLE X: NAME CONTINUED" caption artifact with no data of its own -
    see tools/extract.py). Most of those ids still have a real committed
    file from a sibling block that *did* find data; this pins the ids that
    end up with NO committed file at all, so a future regex tweak that
    silently drops a real table fails loudly instead of just shrinking the
    corpus under a passing `len(files) > 150` check.
    """
    from tools.extract import find_tables, pdf_text

    pdfs = [
        Path("C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"),
        Path("C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf"),
    ]
    for p in pdfs:
        if not p.exists():
            import pytest
            pytest.skip(f"source PDF not present: {p}")

    abandoned = set()
    for p in pdfs:
        find_tables(pdf_text(p))
        abandoned |= set(find_tables.last_abandoned)

    committed_ids = {p.name.split("_", 1)[0] for p in TABLES.glob("*.yaml")}
    fully_missing = abandoned - committed_ids
    assert fully_missing == {"2.2.2j"}, (
        f"a table id vanished from the corpus entirely: {fully_missing}")


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
            pytest.skip(f"source PDF not present: {p}")

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
