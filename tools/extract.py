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
# all-caps, so they'd otherwise pass the caps-header check below too.
_SECTION_HEADING = re.compile(r"^\d+(\.\d+)+\.?\s")
# Book structure, not table structure: "CHAPTER NINE: ..." / "PART ONE: ...".
_CHAPTER_OR_PART = re.compile(r"^(CHAPTER|PART)\s")


def _is_row(line: str) -> bool:
    """True if `line` is unambiguous table data on its own: a numbered/
    ranged die-roll row, or a line starting '<'/'*' (e.g. the monster
    to-hit table's "<1-1")."""
    line = line.strip()
    return bool(_ROW_NUM.match(line)) or line[:1] in "<*"


def _is_heading(line: str) -> bool:
    """True for book structure, not table structure: OSRIC's dotted section
    numbers ("1.3.8. PALADIN") and chapter/part titles ("CHAPTER NINE:
    ...", "PART ONE: ..."). ALL-CAPS like a real header, but never one."""
    line = line.strip()
    return bool(_SECTION_HEADING.match(line) or _CHAPTER_OR_PART.match(line))


def _is_caps_header_candidate(line: str) -> bool:
    """True if `line` might be part of a column-header row (e.g. "D20
    RESULT", or "LOCKS" - one piece of a "PICK LOCKS" header wrapped across
    several narrow-column lines). This only ever buffers a *candidate* - see
    `find_tables` - so even a single ALL-CAPS word (e.g. "ALCHEMIST", a
    hireling's name turning up in running prose) is fine to buffer: on its
    own it can never open a block, only a real row (or, once buffered,
    something that reads as one - see `_looks_tabular`) can."""
    line = line.strip()
    return bool(line) and not _is_heading(line) and line == line.upper()


def _looks_tabular(line: str) -> bool:
    """True if `line`, following a buffered header candidate, reads like a
    data row even without a leading number - e.g. "Cure Light Wounds Augury
    Cure Blindness Divination" (an all-Title-Case list of spell names) or
    "Out of Fields 1d6 rounds 2d6 days - 100/day" (contains dice/currency
    figures). False for an ordinary prose sentence, which always contains a
    lowercase-led word ("the", "is", "a stronghold...") and no digits."""
    line = line.strip()
    if _is_heading(line) or _PROSE.match(line):
        return False
    if line == line.upper():
        # A further ALL-CAPS line (e.g. a second wrapped "MODIFIER" column
        # header) is still just another header candidate, even if it has a
        # digit in it ("D20 RESULT") - never treat it as the data row that
        # commits the block, or it pre-empts the real header from finishing.
        return False
    if any(c.isdigit() for c in line):
        return True
    words = line.split()
    return bool(words) and all(not w[:1].isalpha() or w[:1].isupper() for w in words)


_INTRO_BUDGET = 8  # give up on a header that never reaches a data row


def find_tables(text: str) -> list[dict]:
    """Slice `text` into table blocks. Each block runs from its TABLE header
    until prose, a blank run, or the next header.

    A block only "opens" (starts keeping lines) once real evidence of a
    table shows up within `_INTRO_BUDGET` lines: either an unambiguous data
    row (`_is_row`), or a data-shaped line (`_looks_tabular`) following at
    least one buffered header-candidate line. A header-candidate alone -
    a chapter title, a single ALL-CAPS word - never opens a block by
    itself; that's what previously let unrelated prose get swallowed as
    fake table data.
    """
    out: list[dict] = []
    abandoned_ids: list[str] = []
    current: dict | None = None
    pending: list[str] = []
    held: list[str] = []
    header_lines: set[str] = set()
    blanks = 0
    intro_budget_left = 0
    after_heading = False

    def close():
        # A block with rows is a real table; one with none never found
        # evidence it had data and is reported, not silently discarded.
        # Anything still `held` (see below) was never vindicated as real
        # data, so it's dropped rather than tacked on as a trailing row.
        if current is None:
            return
        if current["lines"]:
            out.append(current)
        else:
            abandoned_ids.append(current["id"])

    for raw in normalise(text).splitlines():
        m = _HEADER.match(raw)
        if m:
            close()
            current = {"id": m.group(1).lower(), "name": m.group(2).strip(), "lines": []}
            pending = []
            held = []
            header_lines = set()
            blanks = 0
            intro_budget_left = _INTRO_BUDGET
            after_heading = False
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
                held = []
                close()
                current = None
            continue
        if line.startswith("=== PAGE"):
            # A long intro can push a table's data past a page break; only
            # treat the break as the block's end once it actually has rows.
            if current["lines"]:
                held = []
                close()
                current = None
            continue
        if _FURNITURE.match(line):
            # Running header/footer, e.g. "56 | OSRIC 3.0 - PART ONE: ...".
            # Checked before anything else too: "56 " alone looks exactly
            # like a die-roll row lead-in, and must never open a block.
            continue
        if not current["lines"]:
            if intro_budget_left <= 0:
                continue
            stripped = line.strip()
            if _is_row(stripped) or (pending and not after_heading and _looks_tabular(stripped)):
                # First real evidence this header actually has a table:
                # commit any provisional header lines, then this row.
                current["lines"].extend(pending)
                header_lines = set(pending)
                pending = []
                blanks = 0
                current["lines"].append(stripped)
                continue
            if not after_heading and _is_caps_header_candidate(stripped):
                # A candidate header line doesn't cost budget: real column
                # headers can wrap across many narrow-column lines (e.g.
                # "PICK \n LOCKS \n PICK \n POCKETS ..."), and none of them
                # commit anything by themselves - only a real row, or a
                # tabular-looking line once buffered, does.
                pending.append(stripped)
                after_heading = False
                continue
            # Descriptive text under the header, before any data row ("Note:
            # ..." or a wrapped intro sentence) - not data, and it shouldn't
            # terminate a block that hasn't started yet either. Keep waiting,
            # but only for a few lines: past _INTRO_BUDGET this is very
            # likely a "TABLE ...CONTINUED" caption artifact with no data of
            # its own (a stray duplicate heading from column reordering).
            after_heading = _is_heading(stripped)
            intro_budget_left -= 1
            continue
        if _PROSE.match(line):
            held = []
            close()
            current = None
            continue
        stripped = line.strip()
        words = stripped.split()
        if (
            not held
            and stripped not in header_lines
            and 1 <= len(words) <= 2
            and any(c.isalpha() for c in stripped)
            and stripped == stripped.upper()
            and not any(c.isdigit() for c in stripped)
        ):
            # A short ALL-CAPS, digit-free line ("SCRIBE", "SAUROPODS") is
            # ambiguous: it could be a new prose entry's heading (the table
            # ended - this book runs straight into unrelated prose with no
            # blank line or page break to mark it) or a genuine sub-section
            # heading within the same table ("SAUROPODS" / "D6 RESULT ERA" /
            # more rows). Hold it and decide from what follows, rather than
            # committing either way on this line alone.
            held = [stripped]
            continue
        if held:
            if _is_row(stripped) or _is_caps_header_candidate(stripped):
                # Vindicated: a real row or another header-shaped line
                # followed, so the held line was a table sub-heading.
                current["lines"].extend(held)
                held = []
            else:
                # Not vindicated: an ordinary line followed, so the held
                # line was where the table's real content actually ended.
                held = []
                close()
                current = None
                continue
        blanks = 0
        current["lines"].append(line.strip())
    close()
    find_tables.last_abandoned = abandoned_ids
    return [t for t in out if t["lines"]]


find_tables.last_abandoned = []


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
        print(f"abandoned (header found, no data row): {find_tables.last_abandoned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
