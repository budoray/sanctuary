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
# optional dash range, an optional %/+, then whitespace. Deliberately does
# NOT match "1. " (a numbered prose sentence like "1. You've sworn...") or
# "1.3.8. " (an OSRIC section heading) - both are digit-led but followed by
# a period, not a range/percent/plus/space.
_ROW_NUM = re.compile(r"^\d+(?:[–-]\d+)?[%+]?\s")
# OSRIC's dotted section headings ("1.3.8. PALADIN"): digit-led and already
# all-caps, so they'd otherwise pass the all-caps fallback below too.
_SECTION_HEADING = re.compile(r"^\d+(\.\d+)+\.?\s")


def _row_start(line: str) -> bool:
    """True if `line` looks like the start of table data: a numbered/ranged
    row, or an all-caps column-header row (e.g. "D20 RESULT", "LEVEL CLIMB
    HIDE..."). False for ordinary prose sentences, which use lowercase, and
    for section headings, which are digit-led and all-caps like a row."""
    line = line.strip()
    if _SECTION_HEADING.match(line):
        return False
    if _ROW_NUM.match(line) or line[:1] in "<*":
        return True
    return line == line.upper()


_INTRO_BUDGET = 8  # give up on a header that never reaches a data row


def find_tables(text: str) -> list[dict]:
    """Slice `text` into table blocks. Each block runs from its TABLE header
    until prose, a blank run, or the next header."""
    out: list[dict] = []
    current: dict | None = None
    blanks = 0
    intro_skipped = 0
    abandoned = False
    for raw in normalise(text).splitlines():
        m = _HEADER.match(raw)
        if m:
            if current:
                out.append(current)
            current = {"id": m.group(1).lower(), "name": m.group(2).strip(), "lines": []}
            blanks = 0
            intro_skipped = 0
            abandoned = False
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
                out.append(current)
                current = None
            continue
        if line.startswith("=== PAGE"):
            # A long intro can push a table's data past a page break; only
            # treat the break as the block's end once it actually has rows.
            if current["lines"]:
                out.append(current)
                current = None
            continue
        if not current["lines"] and (abandoned or not _row_start(line)):
            # Descriptive text under the header, before any data row ("Note:
            # ..." or a wrapped intro sentence) - not data, and it shouldn't
            # terminate a block that hasn't started yet either. Keep waiting,
            # but only for a few lines: past _INTRO_BUDGET this is very
            # likely a "TABLE ...CONTINUED" caption artifact with no data of
            # its own (a stray duplicate heading from column reordering).
            # Give up for good rather than risk a later line - a short
            # ALL-CAPS fragment inside otherwise unrelated prose - being
            # mistaken for a row and swallowing the rest of that prose as
            # fake table data.
            intro_skipped += 1
            if intro_skipped > _INTRO_BUDGET:
                abandoned = True
            continue
        if _PROSE.match(line):
            out.append(current)
            current = None
            continue
        if _FURNITURE.match(line):
            continue
        blanks = 0
        current["lines"].append(line.strip())
    if current:
        out.append(current)
    return [t for t in out if t["lines"]]


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
