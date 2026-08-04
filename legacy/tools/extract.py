"""One-shot OSRIC PDF -> YAML table extractor.

Run manually; never imported by app.py. The committed YAML is the runtime
truth and the PDFs are never read at runtime.

    python tools/extract.py "<osric-dir>/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf" data/tables

⚠ The books are NOT in this repo and must never be - it is public, and the OSRIC
licence permits reusing monster/spell/item TEXT, not redistributing the books.
`sanctuary/sources.py` resolves where they live (SANCTUARY_OSRIC_DIR env var, then
../_reference/osric, then ~/Downloads).

The output is deliberately raw: each table keeps its lines as printed. Typed
interpretation belongs in sanctuary/tables.py, where one table's quirks cannot
break another's.
"""
import re
import sys
import unicodedata
from pathlib import Path

# TABLE 1.3.4.4A: FIGHTER LEVEL ADVANCEMENT   /   TABLE D-2A: ROOM SIZE
# The id's `(?:\.\d+)?` tail catches a sub-numbered table like
# "TABLE 1.4.2.3A.1: CONTAINERS" - without it, the trailing ".1" falls into
# the `[:.]` separator and the "1" becomes the first word of the name
# ("1: CONTAINERS"), silently merging three distinct sub-tables (Containers,
# Mounts and Pack Animals, and the unrelated General Equipment table) under
# one id that then has to raise on load().
_HEADER = re.compile(
    r"^\s*TABLE\s+([0-9][0-9.]*[A-Za-z]?(?:\.\d+)?|D-\d+[A-Za-z]?)\s*[:.]\s*(.+?)\s*$")
# A handful of table captions never say the word "TABLE" at all (e.g.
# "2.7.2.1A: RANDOM TRAP GENERATION" in the GM Guide, which is why that
# table was never extracted). Scoped to an ALL-CAPS name only - inline
# prose that merely cross-references a table by number ("2.2.2m:
# Information Discovery Time and Cost below.") is always mixed case, so
# this cannot pick those up (checked against both books: exactly one line
# in the whole corpus matches with no "TABLE" prefix).
_HEADER_NO_PREFIX = re.compile(
    r"^\s*([0-9][0-9.]*[A-Za-z]?(?:\.\d+)?)\s*:\s*([A-Z][A-Z0-9 ,'\-]+)\s*$")
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


# A row that opens with a plain number or dash-range ("1 ", "31-35 ",
# "01-10 "), used by `continuity_gaps` to compare consecutive row labels.
# Deliberately looser than `_ROW_NUM` about what follows (no required
# trailing whitespace token shape) since it only needs the numbers, not a
# judgement about whether the rest of the line is prose.
_RANGE_ROW = re.compile(r"^(\d+)(?:[–-](\d+))?\+?(?:\s|$)")


def continuity_gaps(lines: list[str]) -> list[tuple[str, str]]:
    """Detection gate for the page-break truncation bug: a table whose rows
    are consecutive numbered ranges (d100 tables, level tables, hit-dice
    tables...) should tile without a gap - each row's range should pick up
    where the previous one left off. A page break that silently ate rows in
    the middle of a table (the very failure `find_tables`'s page-marker
    handling above exists to prevent) is exactly what breaks that tiling.

    Only ever looks at lines that already look like a numbered range row,
    so a table with no such rows (most text-keyed tables) can never report
    a gap - not a source of new false positives across the corpus, only a
    check that fires when there IS a numbered sequence to check. A restart
    (the next label numerically before the previous one, e.g. a sub-table
    that begins its own "01-10" partway through a block that never got its
    own TABLE header, as in 2.7.3.2F's dragon sub-table) is not a gap and
    is deliberately not flagged - only a genuine skipped value is.
    """
    seq = []
    for line in lines:
        m = _RANGE_ROW.match(line)
        if not m:
            continue
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        # d100 tables write "100" as "00" - a literal 0 would otherwise look
        # like a break before every table's first row ("01-02...").
        if lo == 0:
            lo = 100
        if hi == 0:
            hi = 100
        seq.append((lo, hi, line))
    gaps = []
    for (lo1, hi1, l1), (lo2, hi2, l2) in zip(seq, seq[1:]):
        if lo2 < lo1:
            continue  # a restart (new sub-table), not a gap
        if lo2 not in (hi1, hi1 + 1):
            gaps.append((l1, l2))
    return gaps


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


# How many non-blank lines after a page marker `_table_resumes_after_page`
# will examine before giving up on finding a resuming row. Measured against
# the real truncation cases: a genuine mid-table page break has a row again
# within a handful of content lines (page furniture, maybe a repeated
# multi-line column header - 2.12.5a's own repeats 12 column-label lines,
# one per gp-tier heading, before its next row). A table that actually
# ended on the previous page is followed by ordinary prose, which runs for
# many dozens of lines (a class's full narrative section easily runs
# 80-100 lines) before it ever happens to contain one - 20 gives the real
# cases comfortable margin without being so large it accidentally reaches
# into the next section's prose.
_PAGE_BREAK_LOOKAHEAD = 20


def _table_resumes_after_page(lines: list[str], start: int) -> bool:
    """Should a block stay open across the page marker at `lines[start]`?

    Looks ahead for a genuine data row (`_ROW_NUM` or a `<`/`*` lead-in,
    same test `_has_data_row` uses) among the next `_PAGE_BREAK_LOOKAHEAD`
    non-blank lines, skipping running headers/footers (`_FURNITURE`) since
    those legitimately sit between a page marker and a table's own
    continuation. Stops early at the next TABLE header - if one turns up
    before any row does, this table is over and the header starts the next
    one, not a page-break casualty.

    This is the fix for the SYSTEMIC page-break truncation bug (2.12.5a,
    2.13.1r/1s/1t) without reintroducing the failure mode on the other
    side: unconditionally keeping every block open across every page
    marker used to run the "1.3.3.4c" druid to-hit table straight into the
    whole of the following FIGHTER class narrative, because ordinary prose
    sentences ("When the clash of steel rings out...") don't match
    `_PROSE` and so never closed the block. Looking for a resuming row
    within a bounded window is a block-level judgement about whether the
    page break sits INSIDE a table or at its natural end, not a per-line
    prose/data classification of every intervening line - the debarred
    approach is deciding row-by-row whether to KEEP a line, not this.
    """
    seen = 0
    for line in lines[start + 1:]:
        stripped = line.rstrip()
        if not stripped.strip():
            continue
        if _HEADER.match(stripped) or _HEADER_NO_PREFIX.match(stripped):
            return False
        if _FURNITURE.match(stripped) or stripped.startswith("=== PAGE"):
            continue
        content = stripped.strip()
        if _ROW_NUM.match(content) or content[:1] in "<*":
            return True
        seen += 1
        if seen >= _PAGE_BREAK_LOOKAHEAD:
            return False
    return False


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
      that carries no data of its own. That one is abandoned. Matched on
      `_dedup_key(id, name)` - id AND a normalised name, not id alone: id
      alone is too broad, since a header regex quirk mis-parses ids like
      "1.4.2.3A.1" down to "1.4.2.3a", which would make genuinely different
      sub-tables (Containers, Mounts and Pack Animals) collide with the
      unrelated General Equipment table under the same id. An exact (id,
      name) match is too narrow the other way - the caption's name usually
      repeats the original ("NIGHTTIME ENCOUNTERS CONTINUED" twice for
      2.8.1b) but sometimes doesn't ("THIEF SKILLS FOR MONKS" vs "...
      CONTINUED" for 1.3.7.4b) - so `_dedup_key` strips a trailing
      "CONTINUED" and collapses whitespace before keying, catching both
      shapes without conflating unrelated tables that merely share a
      mis-parsed id.
    """
    blocks: list[dict] = []
    current: dict | None = None
    blanks = 0
    seen_row = False  # has this block collected a line matching _ROW_NUM yet?

    def close():
        if current is not None:
            blocks.append(current)

    all_lines = normalise(text).splitlines()
    for idx, raw in enumerate(all_lines):
        m = _HEADER.match(raw) or _HEADER_NO_PREFIX.match(raw)
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
            # A page marker is page furniture, not an automatic terminator -
            # closing the block unconditionally here is why 2.12.5a and
            # 2.13.1r/1s/1t came out truncated (the SYSTEMIC bug). But
            # keeping every block open unconditionally is its own bug: an
            # ordinary section of prose doesn't match `_PROSE` and would
            # otherwise run on forever after a table that happened to end
            # right at a page boundary. `_table_resumes_after_page` decides
            # which case this is by looking for a resuming data row.
            if not _table_resumes_after_page(all_lines, idx):
                if current["lines"]:
                    close()
                    current = None
                continue
            # Reset the blank-run counter too, so a trailing blank at the
            # bottom of one page plus a leading blank atop the next don't
            # combine into a false "blank run" that ends the block here.
            blanks = 0
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
    truncated: dict[str, list[tuple[str, str]]] = {}
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
        gaps = continuity_gaps(t["lines"])
        if gaps:
            truncated[t["id"]] = gaps
    find_tables.last_abandoned = abandoned_ids
    find_tables.last_no_numeric_rows = no_numeric_ids
    find_tables.last_truncated = truncated
    return out


find_tables.last_abandoned = []
find_tables.last_no_numeric_rows = []
find_tables.last_truncated = {}


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
    if find_tables.last_truncated:
        print("TRUNCATION SUSPECTED (row-range continuity gap - eyeball these):")
        for table_id, gaps in find_tables.last_truncated.items():
            for before, after in gaps:
                print(f"  {table_id}: {before!r} -> {after!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
