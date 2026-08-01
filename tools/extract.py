"""One-shot OSRIC PDF -> YAML table extractor.

Run manually; never imported by app.py. The committed YAML is the runtime
truth and the PDFs are never read at runtime.

    python tools/extract.py "C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf" data/tables

The output is deliberately raw: each table keeps its lines as printed. Typed
interpretation belongs in sanctuary/tables.py, where one table's quirks cannot
break another's.
"""
import re
import sys
import unicodedata
from pathlib import Path

# TABLE 1.3.4.4A: FIGHTER LEVEL ADVANCEMENT   /   TABLE D-2A: ROOM SIZE
_HEADER = re.compile(r"^\s*TABLE\s+([0-9][0-9.]*[A-Za-z]?|D-\d+[A-Za-z]?)\s*[:.]\s*(.+?)\s*$")
# A data row starts with a number, a range, a die code, or a short label.
_PROSE = re.compile(r"^\s*(Notes?:|[-\u2022*]\s|\*|After |Use this table|This table)")
# Running headers/footers, e.g. "44 | OSRIC 3.0 - PART ONE: ..." or
# " CHAPTER THREE: CHARACTER CLASS  | 43". Skip, don't terminate the block.
_FURNITURE = re.compile(r"^\s*(\d+\s*\|.*OSRIC 3\.0|.*OSRIC 3\.0.*\|.*|\d+\s*\|.+|.+\|\s*\d+)\s*$")


def normalise(text: str) -> str:
    """Apply Unicode NFKC normalisation.

    NFKC expands the ligatures the wiki PDFs are set with (U+FB00-FB06,
    e.g. "\ufb03" -> "ffi") and folds compatibility characters like non-breaking
    space (U+00A0) and superscript digits to their plain form. It leaves
    en-dashes (U+2013) and curly quotes untouched, which is what matters
    here: en-dashes are meaningful in OSRIC ranges like "4-5".
    """
    return unicodedata.normalize("NFKC", text)


def slug(name: str) -> str:
    s = normalise(name).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


# A die-roll lead-in: "1 ", "1-4 ", "01-10 ", "1+ ", "2-3+ " ... digits, an
# optional dash range, an optional %/+, then whitespace. Used only to judge
# a whole block afterwards (see `find_tables`), never to decide line by
# line whether a single row is prose or data - that judgement call is
# genuinely undecidable for rows like "Lieutenant Special as type as type",
# which have no digit and read exactly like a sentence out of context.
_ROW_NUM = re.compile(r"^\d+(?:[–-]\d+)?[%+]?\s")


def _has_data_row(lines: list[str]) -> bool:
    """True if any line in a collected block is unambiguous table data: a
    numbered/ranged die-roll row, or a line starting '<'/'*' (e.g. the
    monster to-hit table's "<1-1")."""
    return any(bool(_ROW_NUM.match(l)) or l[:1] in "<*" for l in lines)


def _dedup_key(table_id: str, name: str) -> tuple[str, str]:
    """Key used to spot a "TABLE X: NAME CONTINUED" caption artifact as a
    duplicate of the table it continues. Id alone is too broad - a header
    regex quirk mis-parses ids like "1.4.2.3A.1" down to "1.4.2.3a", which
    would otherwise make genuinely different sub-tables (Containers, Mounts
    and Pack Animals) collide with the unrelated General Equipment table
    under the same id. (id, name) alone is too narrow - the caption doesn't
    always repeat the name verbatim (compare 2.8.1b, where it does, to
    1.3.7.4b, where the caption adds " CONTINUED" to a different-looking
    name). Stripping a trailing "CONTINUED" and collapsing whitespace before
    keying catches both without conflating unrelated tables that merely
    share a mis-parsed id."""
    normalised = re.sub(r"\s+CONTINUED\s*$", "", " ".join(name.split()), flags=re.IGNORECASE)
    return (table_id, normalised)


def find_tables(text: str) -> list[dict]:
    """Slice `text` into table blocks. Each block runs from its TABLE header
    until prose, a blank run, or the next header, keeping every line as
    printed - no per-line filtering, since a real row can be indistinguishable
    from prose out of context (e.g. "Lieutenant Special as type as type").

    Blocks are judged as a whole only after being fully collected, when
    there's more to go on than one line at a time:
    - a block with at least one recognisable data row (`_has_data_row`) is
      always kept;
    - a block with none is kept too, UNLESS its id duplicates a block
      already kept from this book - that's the "TABLE X: NAME CONTINUED"
      caption case: a stray duplicate heading from PDF column reordering
      that carries no data of its own. That one is abandoned. Matched on id
      alone, not (id, name): the caption's name usually - but not always -
      literally repeats the original ("NIGHTTIME ENCOUNTERS CONTINUED"
      twice for 2.8.1b), but sometimes doesn't ("THIEF SKILLS FOR MONKS"
      vs "... CONTINUED" for 1.3.7.4b), and an exact-name match misses the
      second shape - the whole point here is to catch a data-less header
      under an id we've already seen real data for, whatever it's titled.
    """
    blocks: list[dict] = []
    current: dict | None = None
    blanks = 0
    seen_row = False  # has this block collected a line matching _ROW_NUM yet?

    def close():
        if current is not None:
            blocks.append(current)

    for raw in normalise(text).splitlines():
        m = _HEADER.match(raw)
        if m:
            close()
            current = {"id": m.group(1).lower(), "name": m.group(2).strip(), "lines": []}
            blanks = 0
            seen_row = False
            continue
        if current is None:
            continue
        line = raw.rstrip()
        if not current["name"] and line.strip():
            # The name sometimes wraps to its own line, e.g. "TABLE 2.13.1E:"
            # with "MISCELLANEOUS WEAPONS PROPERTIES" on the next - the
            # header regex then captures an empty name. Take it from here.
            current["name"] = line.strip()
            continue
        if not line.strip():
            blanks += 1
            if blanks >= 2 and current["lines"]:
                close()
                current = None
            continue
        if line.startswith("=== PAGE"):
            if current["lines"]:
                close()
                current = None
            continue
        if _FURNITURE.match(line):
            # Running header/footer, e.g. "56 | OSRIC 3.0 - PART ONE: ...".
            continue
        if _PROSE.match(line) and seen_row:
            # A block that hasn't collected a real row yet can't be ended by
            # a description sentence: several real tables (e.g. D-7, and
            # NPC AND MONSTER REACTION) open with a multi-line intro that
            # itself contains "This table..." phrasing before the first row
            # ever shows up, and closing there drops the whole table (as
            # before round 1). Once a block has a real row, _PROSE still
            # ends it as usual - this isn't deciding row-by-row whether a
            # line is data, only tracking whether the block as a whole has
            # produced any unambiguous evidence yet, the same _ROW_NUM
            # pattern `_has_data_row` uses to judge the finished block.
            close()
            current = None
            continue
        blanks = 0
        stripped = line.strip()
        if _ROW_NUM.match(stripped):
            seen_row = True
        current["lines"].append(stripped)
    close()

    out: list[dict] = []
    abandoned_ids: list[str] = []
    no_numeric_ids: list[str] = []
    seen_keys: set[tuple[str, str]] = set()
    for t in blocks:
        if not t["lines"]:
            continue
        has_row = _has_data_row(t["lines"])
        key = _dedup_key(t["id"], t["name"])
        if not has_row and key in seen_keys:
            abandoned_ids.append(t["id"])
            continue
        out.append(t)
        seen_keys.add(key)
        if not has_row:
            no_numeric_ids.append(t["id"])
    find_tables.last_abandoned = abandoned_ids
    find_tables.last_no_numeric_rows = no_numeric_ids
    return out


find_tables.last_abandoned = []
find_tables.last_no_numeric_rows = []


def pdf_text(path: Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    parts = []
    for i, page in enumerate(reader.pages, start=1):
        parts.append(f"=== PAGE {i} ===")
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def write_tables(tables: list[dict], out_dir: Path, source: str) -> int:
    import yaml

    out_dir.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    for t in tables:
        doc = {"id": t["id"], "name": t["name"], "source": source, "lines": t["lines"]}
        stem = f"{t['id']}_{slug(t['name'])}"
        # Same id AND name can appear twice in one book (e.g. a "TABLE X:
        # NAME CONTINUED" caption repeated for a table split across pages).
        # Disambiguate rather than silently overwriting - losing a block
        # here is exactly the kind of divergence the round-trip test exists
        # to catch, but only if the file it clobbers is still written first.
        seen[stem] = seen.get(stem, 0) + 1
        if seen[stem] > 1:
            stem = f"{stem}_{seen[stem]}"
        path = out_dir / f"{stem}.yaml"
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )
    return len(tables)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    pdf, out_dir = Path(argv[1]), Path(argv[2])
    tables = find_tables(pdf_text(pdf))
    n = write_tables(tables, out_dir, source=pdf.name)
    print(f"extracted {n} tables from {pdf.name} into {out_dir}")
    if find_tables.last_abandoned:
        print(f"abandoned (duplicate caption, no data row): {find_tables.last_abandoned}")
    if find_tables.last_no_numeric_rows:
        print(f"kept but no numeric rows (eyeball these): {find_tables.last_no_numeric_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
