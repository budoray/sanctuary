"""One-shot magic-item text extractor (OSRIC 3.0 GM Guide, Chapter Thirteen).

Run manually; never imported by app.py. Companion to tools/extract.py, which
extracts the numbered die-roll TABLEs (already committed under
data/tables/2.13.*) - this script extracts the PROSE item descriptions that
sit between those tables (Sections 2.13.2 Potions through 2.13.11
Artifacts), which tools/extract.py never touches (it only recognises
"TABLE X:" blocks).

    python tools/extract_items.py <source.txt> data/items

`<source.txt>` is a plaintext page dump of the GM Guide (page markers like
"=== PAGE 268 ===", running headers/footers, PDF-justified hyphen breaks
like "includ-\ning") starting no earlier than "2.13.2. POTIONS" - anything
before that is die-roll tables, not item prose, and would only pollute the
extraction. Every entry in the prose reads "Name (classes): description...",
one after another with no other punctuation, so the description runs until
the next such match.

Kept deliberately dumb, per the extract.py convention: no attempt to parse
game mechanics (charges, ego, bonuses) out of the prose - that belongs in
sanctuary/treasure.py or a caller that wants it, not the extractor.
"""
import re
import sys
import unicodedata
from pathlib import Path

_PAGE = re.compile(r"^=== PAGE \d+ ===$")
# Running headers/footers, e.g. "268 | OSRIC 3.0 - PART THREE: TREASURE" or
# "CHAPTER THIRTEEN: MAGIC ITEMS (POTIONS) | 275" - same shape tools/extract.py
# strips from table blocks.
_FURNITURE = re.compile(r"^\s*(\d+\s*\|.*OSRIC 3\.0|.*OSRIC 3\.0.*\|.*|\d+\s*\|.+|.+\|\s*\d+)\s*$")
_SECTION_START = re.compile(r"2\.13\.2\.\s+POTIONS")

# A class-restriction code: "any", or 1-4 letters from ACDFIMPRT (the book
# sometimes prints a multi-class item's code concatenated with no separator,
# e.g. "(CP)" for Cleric+Paladin, "(AT)" for Assassin+Thief - not just the
# comma-separated "(F, P)" form).
_CLASS_CODE = r"(?:any|[ACDFIMPRT]{1,4}(?:\s*(?:,|and|&)\s*[ACDFIMPRT]{1,4})*)"
_ITEM = re.compile(rf"([A-Z][A-Za-z0-9'’,\-/ ]{{1,70}}?)\s*\(({_CLASS_CODE})\):\s")


def normalise(text: str) -> str:
    """NFKC-normalise, per the house convention - expands ligatures
    (U+FB00-FB06) and folds compatibility characters."""
    return unicodedata.normalize("NFKC", text)


def slug(name: str) -> str:
    """Same recipe as tools/extract.py's slug() - lowercase, non-alnum -> _."""
    s = normalise(name).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def clean_lines(text: str) -> list[str]:
    """Drop page markers, running headers/footers and blank lines."""
    out = []
    for raw in normalise(text).splitlines():
        line = raw.strip()
        if not line or _PAGE.match(line) or _FURNITURE.match(line):
            continue
        out.append(line)
    return out


_HYPHEN_BREAK = re.compile(r"([A-Za-z])\s*-$")


def join_lines(lines: list[str]) -> str:
    """Rejoin PDF-wrapped lines into one flowing block. A line ending in a
    hyphen right after a letter is a justified-text word-break - sometimes
    printed tight ("includ-" + "ing" = "including"), sometimes with the
    justification gap still in front of the hyphen ("dura -" + "tion" =
    "duration") - and joins with no space either way; everything else joins
    with a single space, since the source wraps mid-sentence with no other
    marker."""
    buf = ""
    for line in lines:
        if not buf:
            buf = line
        elif _HYPHEN_BREAK.search(buf):
            buf = _HYPHEN_BREAK.sub(r"\1", buf) + line
        else:
            buf = buf + " " + line
    return re.sub(r"\s+", " ", buf).strip()


def find_items(blob: str) -> list[dict]:
    """Every "Name (classes): description" entry in the joined prose blob,
    description running to the next such entry (or end of text)."""
    matches = list(_ITEM.finditer(blob))
    items = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        items.append({
            "name": m.group(1).strip(),
            "classes": m.group(2).strip(),
            "description": blob[m.end():end].strip(),
        })
    return items


def write_items(items: list[dict], out_dir: Path, source: str) -> int:
    import yaml

    out_dir.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    for it in items:
        doc = {
            "name": it["name"],
            "classes": it["classes"],
            "description": it["description"],
            "source": source,
        }
        stem = slug(it["name"])
        seen[stem] = seen.get(stem, 0) + 1
        if seen[stem] > 1:
            stem = f"{stem}_{seen[stem]}"
        path = out_dir / f"{stem}.yaml"
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )
    return len(items)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    src, out_dir = Path(argv[1]), Path(argv[2])
    text = src.read_text(encoding="utf-8")
    m = _SECTION_START.search(text)
    if m:
        text = text[m.start():]
    blob = join_lines(clean_lines(text))
    items = find_items(blob)
    n = write_items(items, out_dir, source="OSRIC_3.0_Gamemaster_Guide.pdf")
    print(f"extracted {n} items from {src.name} into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
