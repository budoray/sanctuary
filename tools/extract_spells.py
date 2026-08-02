"""Extract Chapter 2 spell records from the saved OSRIC wiki text."""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import yaml


CATEGORY_CLASSES = {
    "Clerical": "cleric",
    "Druidic": "druid",
    "Arcane": "magic-user",
    "Phantasmal": "illusionist",
    # "Arcane Spells, Level 1" (an illusionist 7th-level spell that lets the
    # caster swap in 1st-level magic-user spells) is filed under the school
    # "Various" rather than one of the four standard prefixes - a genuine
    # source quirk. Its Level line always names the class explicitly
    # ("Illusionist 7"), so this entry is never used to INFER a class - it
    # exists only so _entry_start recognises the line as a category at all.
    "Various": None,
}
FIELD_ANCHORS = (
    ("range", "Range:"),
    ("duration", "Duration:"),
    ("area_of_effect", "Area of Effect:"),
    ("components", "Components:"),
    ("casting_time", "Casting Time:"),
    ("saving_throw", "Saving Throw:"),
)
FURNITURE = tuple(
    re.compile(pattern)
    for pattern in (
        r"^=== PAGE \d+ ===$",
        r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2} \d+/191 Chapter 2: Spells$",
        r"^Wiki and Other Goodies - https://osricwiki\.presgas\.name/$",
        r"^https://osricwiki\.presgas\.name/ Printed on .*$",
        r"^Last update: .*osricwiki\.presgas\.name.*$",
        r"^From:$",
        r"^https://osricwiki\.presgas\.name/ - Wiki and Other Goodies$",
        r"^Permanent link:$",
        r"^https://osricwiki\.presgas\.name/doku\.php\?id=osric:chapter2$",
    )
)
LIGATURES = set(chr(codepoint) for codepoint in range(0xFB00, 0xFB07))


def normalise(value: str) -> str:
    """Apply the one permitted textual transformation to source content."""
    return unicodedata.normalize("NFKC", value)


def _nonblank(lines: list[str], start: int) -> int | None:
    for index in range(start, len(lines)):
        if lines[index].strip():
            return index
    return None


def _entry_start(lines: list[str], index: int) -> tuple[int, int] | None:
    """Return category and level-line indexes if ``index`` begins an entry."""
    if not lines[index].strip():
        return None
    category_index = _nonblank(lines, index + 1)
    if category_index is None:
        return None
    category = lines[category_index].strip()
    if not any(category.startswith(prefix) for prefix in CATEGORY_CLASSES):
        return None
    level_index = _nonblank(lines, category_index + 1)
    if level_index is None or not re.match(r"^Level:?\s", lines[level_index].strip()):
        return None
    return category_index, level_index


_STRAY_DIGIT_PREFIX = re.compile(r"^\d+(?=[A-Za-z])")


def _degarble(stripped: str) -> str:
    """Strip a stray leading page-number digit glued onto a field label by
    the wiki scrape, e.g. "6Area of Effect: See below" (Transport via
    Plants, source line ~71) - the "6" is scrape noise, not spell content.
    Only strips when what follows is a letter, so a real value that happens
    to start with a digit (e.g. "0" for Range) is never touched."""
    return _STRAY_DIGIT_PREFIX.sub("", stripped)


def _field(lines: list[str], start: int, anchor: str, next_anchor: str | None) -> tuple[str, int]:
    # Case-insensitive anchor match: one spell in the source ("Fire Storm")
    # has "Area of effect:" (lowercase e) instead of "Area of Effect:" - a
    # real inconsistency in the wiki source, not a parser bug, so tolerate
    # it rather than special-case one spell by name.
    index = _nonblank(lines, start)
    if index is None or not _degarble(lines[index].strip()).lower().startswith(anchor.lower()):
        found = "end of input" if index is None else repr(lines[index])
        raise ValueError(f"expected {anchor!r}, found {found}")
    value = _degarble(lines[index].strip())[len(anchor):].strip()
    index += 1
    if next_anchor is None:
        # Saving Throw, the last field: always a single line in this corpus.
        return value, index

    # Every other field's value may wrap onto following lines (e.g. Heat
    # Metal's Area of Effect spans two lines even though the first has
    # content) - fold every line up to the next field's anchor, whether or
    # not this field's own line already had a value.
    folded = [value] if value else []
    while index < len(lines):
        stripped = _degarble(lines[index].strip())
        if stripped.lower().startswith(next_anchor.lower()):
            break
        if stripped:
            folded.append(stripped)
        index += 1
    return " ".join(folded), index


def _body(lines: list[str], start: int, end: int) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def parse(source: str, source_name: str) -> list[dict]:
    lines = normalise(source).splitlines()
    lines = [line for line in lines if not any(pattern.match(line) for pattern in FURNITURE)]
    starts = [index for index in range(len(lines)) if _entry_start(lines, index)]
    records: list[dict] = []

    for number, start in enumerate(starts):
        category_index, level_index = _entry_start(lines, start)  # type: ignore[misc]
        title = lines[start].strip()
        reversible = title.endswith(" (Reversible)")
        name = title.removesuffix(" (Reversible)")
        school = lines[category_index].strip()
        category_class = next(
            class_name for prefix, class_name in CATEGORY_CLASSES.items() if school.startswith(prefix)
        )
        match = re.fullmatch(
            r"Level:?\s*(?:(Cleric|Druid|Magic user|Illusionist)\s+)?(\d+)",
            lines[level_index].strip(),
        )
        if not match:
            raise ValueError(f"malformed level line {lines[level_index]!r} for {name}")
        named_class, level_text = match.groups()
        class_name = {
            "Cleric": "cleric",
            "Druid": "druid",
            "Magic user": "magic-user",
            "Illusionist": "illusionist",
            None: category_class,
        }[named_class]
        if named_class and category_class is not None and class_name != category_class:
            print(
                f"warning: {name}: level class {class_name} disagrees with category {category_class}"
            )

        values: dict[str, str] = {}
        cursor = level_index + 1
        for field_number, (key, anchor) in enumerate(FIELD_ANCHORS):
            next_anchor = (
                FIELD_ANCHORS[field_number + 1][1]
                if field_number + 1 < len(FIELD_ANCHORS)
                else None
            )
            values[key], cursor = _field(lines, cursor, anchor, next_anchor)

        end = starts[number + 1] if number + 1 < len(starts) else len(lines)
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        records.append(
            {
                "name": name,
                "slug": slug,
                "reversible": reversible,
                "class": class_name,
                "level": int(level_text),
                "school": school,
                **values,
                "text": _body(lines, cursor, end),
                "source": source_name,
            }
        )
    return records


def write(records: list[dict], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("*.yaml"):
        old_file.unlink()
    written: list[Path] = []
    used: set[str] = set()
    for record in records:
        stem = f"{record['slug']}__{record['class']}"
        candidate = stem
        suffix = 2
        while candidate in used:
            candidate = f"{stem}_{suffix}"
            suffix += 1
        used.add(candidate)
        path = output_dir / f"{candidate}.yaml"
        path.write_text(
            yaml.safe_dump(record, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    raw = args.source.read_text(encoding="utf-8")
    records = parse(raw, args.source.name)
    written = write(records, args.output_dir)
    casting_times = len(re.findall(r"^Casting Time:", normalise(raw), flags=re.MULTILINE))
    if not (len(records) == len(written) == casting_times):
        raise AssertionError(
            f"count mismatch: parsed={len(records)}, written={len(written)}, "
            f"Casting Time anchors={casting_times}"
        )
    for path in written:
        if LIGATURES.intersection(path.read_text(encoding="utf-8")):
            raise AssertionError(f"ligature survived in {path}")
    print(
        f"count reconciliation: {len(records)} parsed == {len(written)} YAML files "
        f"== {casting_times} Casting Time anchors"
    )


if __name__ == "__main__":
    main()
