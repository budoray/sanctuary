"""Monster records: the shipped corpus, GM overlays, custom monsters, and monster level.

Loads `data/monsters/*.yaml` (291 OSRIC monsters, extracted by
`tools/extract_monsters.py`). A GM's edits are stored as an OVERLAY, never a mutation of
the shipped file - re-running the extractor can never clobber a GM's work, and the book's
own numbers stay recoverable. See docs/superpowers/specs/2026-08-01-sanctuary-design.md
§7.3.
"""
from pathlib import Path

import yaml

from sanctuary import tables

_DIR = Path(__file__).resolve().parent.parent / "data" / "monsters"
_OVERLAY_DIR = _DIR / "overlays"


def _slug(name: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKC", name).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _base_path(name_or_slug: str) -> Path:
    slug = _slug(name_or_slug)
    path = _DIR / f"{slug}.yaml"
    if not path.exists():
        raise KeyError(f"no monster {name_or_slug!r} in {_DIR}")
    return path


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _overlay_path(slug: str) -> Path:
    return _OVERLAY_DIR / f"{slug}.yaml"


def base_ids() -> list[str]:
    """Every monster slug in the shipped corpus."""
    return sorted(p.stem for p in _DIR.glob("*.yaml") if p.stem != "_cross_check")


def load(name: str) -> dict:
    """A monster's EFFECTIVE record: the shipped base with any GM overlay merged on
    top, field by field. The base file on disk is never touched by this - see
    `edit()`."""
    slug = _slug(name)
    doc = _read(_base_path(slug))
    overlay_path = _overlay_path(slug)
    if overlay_path.exists():
        doc = {**doc, **_read(overlay_path)}
    return doc


def all_monsters() -> list[dict]:
    """Every monster in the corpus, overlays applied."""
    return [load(slug) for slug in base_ids()]


def edit(name: str, **fields) -> dict:
    """Record a GM's edit to one or more fields of a shipped monster, as an overlay.

    Never writes the base file - `data/monsters/<slug>.yaml` stays byte-identical, so
    a fresh `tools/extract_monsters.py` run (or a book errata correction) cannot
    silently discard the GM's work, and the printed values stay recoverable by
    dropping the overlay. Returns the new effective (merged) record.
    """
    slug = _slug(name)
    _base_path(slug)  # raises KeyError if this isn't a real monster
    _OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    path = _overlay_path(slug)
    overlay = _read(path) if path.exists() else {}
    overlay.update(fields)
    path.write_text(yaml.safe_dump(overlay, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return load(slug)


def reset(name: str) -> dict:
    """Drop a monster's overlay, restoring the book's own values."""
    path = _overlay_path(_slug(name))
    path.unlink(missing_ok=True)
    return load(name)


_REQUIRED = (
    "name", "frequency", "size", "alignment", "move", "armour_class", "hit_dice",
    "melee_attacks", "senses", "lair_chance", "intelligence", "morale", "loot",
    "experience", "description",
)


def create(**fields) -> dict:
    """A brand-new custom monster: same 13-field schema, no base to overlay onto.
    `name` is required; every other field defaults to an empty placeholder so the
    record is always shaped like a shipped one (never a KeyError downstream for a
    GM-authored beast). Written straight to the overlay directory, since a custom
    monster has no shipped file to keep separate from."""
    if not fields.get("name"):
        raise ValueError("a custom monster needs a name")
    doc = {k: fields.get(k, "") for k in _REQUIRED}
    doc["abilities"] = fields.get("abilities", [])
    slug = _slug(doc["name"])
    _OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    _overlay_path(slug).write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return doc


def _xp_breakpoints() -> list[tuple[int, int | float]]:
    """[(level, xp_ceiling), ...] from Table 2.11A, read fresh each call rather than
    hand-copied. Each row reads "LEVEL RANGE", e.g. "6 501-1,100" or "10 10,001 or
    higher" - the ceiling is the LAST number in the row (the range's upper bound),
    not every digit in it run together, and "or higher" has no ceiling at all."""
    import re
    doc = tables.load("2.11a")
    breakpoints = []
    for line in doc["lines"]:
        parts = line.split(None, 1)
        if not parts or not parts[0].isdigit():
            continue
        level = int(parts[0])
        if "higher" in parts[1]:
            ceiling = float("inf")
        else:
            numbers = re.findall(r"[\d,]+", parts[1])
            ceiling = int(numbers[-1].replace(",", "")) if numbers else float("inf")
        breakpoints.append((level, ceiling))
    return breakpoints


def monster_level(base_xp: int) -> int:
    """Table 2.11A: base XP -> monster level 1-10, computed fresh from the committed
    table every call rather than typed in - a GM sees a level, not a raw XP number
    they'd otherwise have to eyeball against the book (§7.3)."""
    for level, ceiling in _xp_breakpoints():
        if base_xp <= ceiling:
            return level
    raise AssertionError("unreachable: the top breakpoint has no ceiling")
