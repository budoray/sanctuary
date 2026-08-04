"""One-shot OSRIC monster extractor: GM Guide + wiki cross-check -> data/monsters/*.yaml.

Run manually; never imported by app.py or sanctuary/bestiary.py. The committed YAML is
the runtime truth; the source .txt dumps are never read at runtime.

    python tools/extract_monsters.py <gm.txt> <wiki.txt> <out_dir>

Dumb capture, per the extractor lesson in IMPROVEMENTS.md: the 13 stat fields are
parsed because the schema is fixed and verified, but everything past EXPERIENCE (the
"Immunities and Resistances" / "Special Features" / ... sections) is kept as whole
prose blobs tagged by heading, never decomposed into an effects DSL. See
docs/superpowers/specs/2026-08-01-sanctuary-design.md §7.2.
"""
import re
import sys
import unicodedata
from pathlib import Path

# The GM Guide's stat block uses these labels, in this fixed order, one per line
# ("LABEL value", value may wrap onto following lines until the next label or the
# description prose begins). NO. ENCOUNTERED is the one genuinely optional label.
_GM_LABELS = [
    "FREQUENCY", "NO. ENCOUNTERED", "SIZE", "ALIGNMENT", "MOVE", "ARMOUR CLASS",
    "HIT DICE", "MELEE ATTACKS", "SENSES", "LAIR CHANCE", "INTELLIGENCE", "MORALE",
    "LOOT", "EXPERIENCE",
]
_FIELD_KEY = {
    "FREQUENCY": "frequency", "NO. ENCOUNTERED": "no_encountered", "SIZE": "size",
    "ALIGNMENT": "alignment", "MOVE": "move", "ARMOUR CLASS": "armour_class",
    "HIT DICE": "hit_dice", "MELEE ATTACKS": "melee_attacks", "SENSES": "senses",
    "LAIR CHANCE": "lair_chance", "INTELLIGENCE": "intelligence", "MORALE": "morale",
    "LOOT": "loot", "EXPERIENCE": "experience",
}
_LABEL_RE = re.compile(
    r"^(" + "|".join(re.escape(l) for l in sorted(_GM_LABELS, key=len, reverse=True)) + r")\s*(.*)$"
)

# Sub-headings that split the free-form prose after EXPERIENCE into tagged sections.
# Tier 3 per §7.2: captured whole, never parsed into structure. "Language" (singular)
# is kept as an alias of "Languages" - the PDF text extraction sometimes wraps the
# plural onto its own following line.
_HEADINGS = {
    "Immunities and Resistances", "Special Features", "Special Attacks",
    "Special Defences", "Surprise and Initiative", "Languages", "Language",
}

# PDF page furniture: page markers and running headers/footers, mirroring
# tools/extract.py's _FURNITURE. A lone "A." style alphabet-divider line is also
# furniture, not a monster name.
_PAGE_MARK = re.compile(r"^=== PAGE \d+ ===$")
_FURNITURE = re.compile(r"^\s*(\d+\s*\|.*OSRIC 3\.0|.*OSRIC 3\.0.*\|.*|\d+\s*\|.+|.+\|\s*\d+)\s*$")
_ALPHA_DIVIDER = re.compile(r"^[A-Z]\.$")

_WIKI_LABEL_RE = re.compile(r"^([A-Z][A-Za-z /.–-]*):\s*(.*)$")
_WIKI_FIELD_MAP = {
    "frequency": "frequency", "no. encountered": "no_encountered", "size": "size",
    "move": "move", "armour class": "armour_class", "hit dice": "hit_dice",
    "lair probability": "lair_chance", "intelligence": "intelligence",
    "alignment": "alignment", "level/xp": "experience", "morale": "morale",
}


def normalise(text: str) -> str:
    """NFKC-normalise: expands ligatures (U+FB00-FB06) and folds compatibility chars."""
    return unicodedata.normalize("NFKC", text)


def slug(name: str) -> str:
    s = normalise(name).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _is_furniture(line: str) -> bool:
    return bool(_PAGE_MARK.match(line) or _FURNITURE.match(line) or _ALPHA_DIVIDER.match(line.strip()))


def _titlecase_name(raw: str) -> str:
    """ACHAIYERAI -> Achaiyerai; AL-MI'RAJ -> Al-Mi'raj; keeps parens/commas as printed."""
    def cap_word(w: str) -> str:
        if not w:
            return w
        parts = re.split(r"([-'])", w)
        return "".join(p if p in "-'" else (p[:1].upper() + p[1:].lower()) for p in parts)
    return " ".join(cap_word(w) for w in raw.split(" "))


def parse_gm(text: str) -> list[dict]:
    """Split the GM Guide dump into monster stat blocks, anchored on lines starting
    "FREQUENCY " - the one label that opens every entry and appears nowhere else in
    the book (291 occurrences, matching the book's own stated monster count)."""
    lines = normalise(text).splitlines()
    freq_idx = [i for i, l in enumerate(lines) if l.startswith("FREQUENCY ")]

    def find_name(before: int) -> tuple[str, int]:
        j = before - 1
        while j >= 0 and (not lines[j].strip() or _is_furniture(lines[j])):
            j -= 1
        return lines[j].strip(), j

    monsters = []
    for n, start in enumerate(freq_idx):
        name_raw, name_idx = find_name(start)
        end = find_name(freq_idx[n + 1])[1] if n + 1 < len(freq_idx) else len(lines)
        # Most monsters sit back-to-back, so `end` is the next monster's name line.
        # A few are the last monster before a real gap - the alphabetical A-Z list
        # ends, and the next "FREQUENCY " line the book prints is a magic item's
        # guardian creature, chapters later. Without a cap, that gap (a whole
        # intervening chapter of unrelated prose and tables) reads as this
        # monster's own ability text. A "CHAPTER n:" or "TABLE n" heading never
        # appears inside genuine monster prose, so the first one after `start` is
        # always that gap opening, and ends the block early.
        for j in range(start, end):
            if re.match(r"^(CHAPTER [A-Z]+:|TABLE \d)", lines[j]):
                end = j
                break
        block = [l for l in lines[start:end] if l.strip() and not _is_furniture(l)]
        monsters.append(_parse_gm_block(_titlecase_name(name_raw), block))
    return monsters


def _parse_gm_block(name: str, block_lines: list[str]) -> dict:
    fields: dict[str, list[str]] = {}
    current = None
    i = 0
    # Fixed-order labelled fields: FREQUENCY .. EXPERIENCE.
    while i < len(block_lines):
        line = block_lines[i]
        m = _LABEL_RE.match(line)
        if m and (current is None or _GM_LABELS.index(m.group(1)) >= _GM_LABELS.index(current)):
            current = m.group(1)
            fields[current] = [m.group(2)] if m.group(2) else []
            if current == "EXPERIENCE":
                # Some entries give a flat XP value ("1,400 +14/hp"); others break
                # it out per Hit Die or per rank as a little table ("3 HD: 65
                # +2/hp" / "7HD: 1,295 +8/hp" / "Leader (4HD) 145 +3/hp", one row
                # per line, sometimes after a "Varies by HD:" lead-in). Every real
                # row carries the "+N/hp" XP-per-hit-point suffix or opens with a
                # digit; ordinary prose does neither, so that's what ends the
                # table and starts the description.
                i += 1
                while i < len(block_lines) and (
                    re.match(r"^\d", block_lines[i]) or re.search(r"\+\d+/hp", block_lines[i])
                ):
                    fields[current].append(block_lines[i])
                    i += 1
                break
        elif current is not None:
            fields[current].append(line)
        i += 1

    rest = block_lines[i:]
    description_lines: list[str] = []
    abilities: list[dict] = []
    heading = None
    heading_lines: list[str] = []

    def flush():
        if heading is not None and heading_lines:
            abilities.append({"heading": heading, "text": " ".join(heading_lines).strip()})

    for line in rest:
        if line.strip() in _HEADINGS:
            flush()
            heading = "Languages" if line.strip() == "Language" else line.strip()
            heading_lines = []
        elif heading is None:
            description_lines.append(line)
        else:
            heading_lines.append(line)
    flush()

    doc = {"name": name}
    for label in _GM_LABELS:
        key = _FIELD_KEY[label]
        if label in fields:
            doc[key] = " ".join(fields[label]).strip()
    doc["description"] = " ".join(description_lines).strip()
    doc["abilities"] = abilities
    _coerce_types(doc)
    return doc


def _coerce_types(doc: dict) -> None:
    """Bare numbers per the design's schema example (armour_class: 8, morale: 90).
    An armour class with an [ascending] bracket or extra text ("or -1 [21] (see
    below)") is kept as a string so the bracket is never silently dropped - only a
    clean integer collapses to int. frequency/size/alignment/intelligence are
    lower-cased to match the design's schema example (`frequency: very rare`,
    `size: huge`) - the GM Guide prints them Capitalised, the schema doesn't."""
    for key in ("armour_class", "morale"):
        val = doc.get(key, "")
        if re.fullmatch(r"-?\d+", val or ""):
            doc[key] = int(val)
    for key in ("frequency", "size", "alignment", "intelligence"):
        if isinstance(doc.get(key), str):
            doc[key] = doc[key].lower()


def parse_wiki(text: str) -> list[dict]:
    """Split the wiki dump into monster entries, anchored on "Frequency:" lines."""
    lines = normalise(text).splitlines()
    freq_idx = [i for i, l in enumerate(lines) if l.startswith("Frequency:")]

    def find_name(before: int) -> tuple[str, int]:
        j = before - 1
        while j >= 0 and (not lines[j].strip() or _is_furniture(lines[j]) or lines[j].startswith("=== PAGE")):
            j -= 1
        return lines[j].strip(), j

    monsters = []
    for n, start in enumerate(freq_idx):
        name_raw, _ = find_name(start)
        end = find_name(freq_idx[n + 1])[1] if n + 1 < len(freq_idx) else len(lines)
        block = [l for l in lines[start:end] if l.strip() and not _is_furniture(l) and not l.startswith("=== PAGE")]
        monsters.append(_parse_wiki_block(name_raw, block))
    return monsters


_WIKI_KNOWN_LABELS = {
    "frequency", "no. encountered", "size", "move", "armour class", "hit dice",
    "attacks", "damage", "special attacks", "special defences", "magic resistance",
    "lair probability", "intelligence", "alignment", "level/xp", "morale",
}


def _parse_wiki_block(name: str, block_lines: list[str]) -> dict:
    """Every wiki stat line is "Label: value" on ONE line - unlike the GM Guide,
    values here don't wrap - so the block is just "labelled lines, then prose": the
    first line that isn't a recognised label ends the fields and starts the
    description."""
    fields: dict[str, str] = {}
    i = 0
    while i < len(block_lines):
        m = _WIKI_LABEL_RE.match(block_lines[i])
        if not (m and m.group(1).lower() in _WIKI_KNOWN_LABELS):
            break
        fields[m.group(1).lower()] = m.group(2).strip()
        i += 1
    doc = {"name": name, "description": " ".join(block_lines[i:]).strip()}
    for label, key in _WIKI_FIELD_MAP.items():
        if label in fields:
            doc[key] = fields[label]
    attacks = fields.get("attacks", "").strip()
    damage = fields.get("damage", "").strip()
    if attacks or damage:
        doc["melee_attacks"] = f"{attacks} ({damage})".strip() if damage else attacks
    return doc


def cross_check(gm: list[dict], wiki: list[dict]) -> list[dict]:
    """Diff GM-guide vs wiki entries by name (case-insensitive). For every name in
    both, compare each field the wiki has a mapping for. A disagreement is either a
    parse bug or a genuine 2.x->3.0 revision - both get logged, neither is resolved
    here (design §4)."""
    by_name_gm = {m["name"].lower(): m for m in gm}
    fields_to_compare = ["frequency", "no_encountered", "size", "alignment", "move",
                          "armour_class", "hit_dice", "melee_attacks", "lair_chance",
                          "intelligence", "morale", "experience"]
    disagreements = []
    matched = 0
    for w in wiki:
        g = by_name_gm.get(w["name"].lower())
        if g is None:
            continue
        matched += 1
        for f in fields_to_compare:
            gv, wv = g.get(f), w.get(f)
            if gv is None or wv is None:
                continue
            if str(gv).strip().lower() != str(wv).strip().lower():
                disagreements.append({
                    "name": g["name"], "field": f, "gm_guide": gv, "wiki": wv,
                })
    return {
        "gm_count": len(gm), "wiki_count": len(wiki), "matched_by_name": matched,
        "unmatched_wiki_names": sorted(w["name"] for w in wiki if w["name"].lower() not in by_name_gm),
        "disagreements": disagreements,
    }


def write_monsters(monsters: list[dict], out_dir: Path) -> None:
    """One file per monster. A few GM Guide entries share a name after the
    name-detector picks up a shared table-column header instead of the real
    creature name (e.g. two unrelated "giant-sized vermin" rows both parsed as
    "Ordinary Giant") - disambiguated by suffix rather than silently overwritten,
    same approach as tools/extract.py uses for duplicate table captions."""
    import yaml
    out_dir.mkdir(parents=True, exist_ok=True)
    seen: dict[str, int] = {}
    for m in monsters:
        stem = slug(m["name"])
        seen[stem] = seen.get(stem, 0) + 1
        if seen[stem] > 1:
            stem = f"{stem}_{seen[stem]}"
        path = out_dir / f"{stem}.yaml"
        path.write_text(
            yaml.safe_dump(m, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )


def write_cross_check(report: dict, out_dir: Path) -> None:
    import yaml
    (out_dir / "_cross_check.yaml").write_text(
        yaml.safe_dump(report, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    gm_path, wiki_path, out_dir = Path(argv[1]), Path(argv[2]), Path(argv[3])
    gm = parse_gm(gm_path.read_text(encoding="utf-8"))
    wiki = parse_wiki(wiki_path.read_text(encoding="utf-8"))
    write_monsters(gm, out_dir)
    report = cross_check(gm, wiki)
    write_cross_check(report, out_dir)
    print(f"extracted {len(gm)} monsters from {gm_path.name} into {out_dir}")
    print(f"cross-checked against {len(wiki)} wiki entries: {report['matched_by_name']} matched by "
          f"name, {len(report['disagreements'])} field disagreements")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
