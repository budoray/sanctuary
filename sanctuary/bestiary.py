"""Monster records: the shipped corpus, GM overlays, custom monsters, and monster level.

Loads `data/monsters/*.yaml` (291 OSRIC monsters, extracted by
`tools/extract_monsters.py`). A GM's edits are stored as an OVERLAY, never a mutation of
the shipped file - re-running the extractor can never clobber a GM's work, and the book's
own numbers stay recoverable. See docs/superpowers/specs/2026-08-01-sanctuary-design.md
§7.3.
"""
import re
import unicodedata
from pathlib import Path

import yaml

from sanctuary import tables

_DIR = Path(__file__).resolve().parent.parent / "data" / "monsters"
_OVERLAY_DIR = _DIR / "overlays"


def _slug(name: str) -> str:
    s = unicodedata.normalize("NFKC", name).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


# Encounter-table names carry a trailing dice quantity ("Bugbear 1d6", "Bat
# 5d10") that is not part of the monster's name - it's how many are
# encountered, parsed separately by the caller.
_TRAILING_QTY = re.compile(r"\s*\d+d\d+([+-]\d+)?\s*$", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")

# Pure size/age/rarity qualifiers that appear ALONE far too often across the
# corpus to ever safely identify a monster on their own (a 1.0-confidence
# match landing on "the giant one" is still a coin flip on WHICH giant
# thing). Blocked as a single-word resolution key even when it happens to be
# unique today - a new monster added later could silently break the
# uniqueness guarantee.
_STOPWORDS = {
    "giant", "greater", "lesser", "very", "young", "old", "ancient", "huge",
    "large", "small", "normal", "ordinary", "big", "bigger", "biggest",
}


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("ses"):
        return word[:-2]
    if len(word) > 2 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _words(s: str, *, singular: bool = True) -> list[str]:
    """Printed text -> normalised word list: lower-cased, punctuation-blind,
    with the table's trailing dice-quantity suffix and a trailing hyphen
    (`"Sphinx, Hieraco-"`'s line-wrap artefact) stripped. Singularised by
    default (`singular=False` keeps the raw word, needed for the exact-slug
    guess: corpus slugs are the extractor's literal heading text, unfixed by
    this resolver's own plural heuristic - "Cyclops" must stay "cyclops",
    not become the file-less "cyclop")."""
    s = _TRAILING_QTY.sub("", s.strip()).rstrip("-").strip()
    words = _WORD.findall(s.lower())
    return [_singular(w) for w in words] if singular else words


def _candidates(printed_name: str, *, singular: bool = True) -> list[list[str]]:
    """Every normalised word-list worth trying, in order of confidence.

    Handles the GM Guide's two comma conventions - "Frog, Giant" (base
    name, modifier - already in slug order) and "Devil, Assagim" (generic
    category, proper name) - by trying both the literal order AND the
    modifier-first inversion ("Giant Frog"), plus the category dropped
    entirely ("Assagim"). A bare two-word reversal is also tried without a
    comma (`"Spectral Troll"` -> `"Troll Spectral"`), matching the corpus's
    own "base_modifier" slug convention (`troll_spectral`, `troll_giant`).
    """
    s = _TRAILING_QTY.sub("", printed_name.strip()).rstrip("-").strip()
    seen: list[list[str]] = []

    def add(words: list[str]) -> None:
        if words and words not in seen:
            seen.append(words)

    add(_words(s, singular=singular))
    if "," in s:
        cat, _, specific = s.partition(",")
        cat, specific = cat.strip(), specific.strip().rstrip(",").strip()
        if specific:
            add(_words(specific, singular=singular) + _words(cat, singular=singular))  # "Dire Wolf"
            add(_words(specific, singular=singular))                                    # "Assagim"
    words = _words(s, singular=singular)
    if len(words) >= 2:
        add(list(reversed(words)))
    return seen


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


def resolve_name(printed_name: str) -> dict | None:
    """The encounter tables' printed name -> the monster it means, or `None`.

    Two independent mismatches send a generated encounter to "the DM must
    arbitrate" (see runtime.py): the GM Guide's D100 monster tables print
    names in an inverted or category-first form the corpus's own heading
    slugs don't share (`"Wolf, Dire"`, `"Devil, Assagim"`), and a handful of
    the corpus's own files collapse SEVERAL creatures' stat blocks into one
    record (`werebear_wereboar_wererat_weretiger_werewolf.yaml`,
    `normal_dire.yaml` - a wolf/dire-wolf pair the extractor even mislabeled
    with the table's own column headers as the monster's NAME) with no way
    to reach one by name - see `data/monsters/`'s split-out files
    (`werebear.yaml`... now `lycanthrope_werebear.yaml`, `wolf_dire.yaml`,
    `elemental_air.yaml`, ...) for the ones that were worth splitting;
    `test_the_full_corpus_is_303_monsters` explains why.

    Tries, in order: the printed name as its own slug, raw and singularised
    (a slug is the extractor's literal heading text, so the raw form goes
    first - singularising "Cyclops" would guess the file-less "cyclop");
    the comma-inverted and category-dropped forms (`"Devil, Assagim"` ->
    `"Assagim"`); a bare word-order reversal (`"Spectral Troll"` ->
    `troll_spectral`); and last, a UNIQUE contiguous match inside another
    monster's own name field (catches a name landing inside a still-
    collapsed file, or a corpus heading that simply orders words
    differently - `"Mobat"` inside `"Bat, Mobat"`). A stopword-only
    candidate never reaches that last step even if it happens to be a
    unique match today - "Giant" alone matches dozens of files, and a new
    monster added later could just as easily break a lucky one-word
    uniqueness. Some printed names are simply absent from OSRIC 3.0's
    corpus (`"Barghest"`, `"Roper"` - not extraction gaps, verified against
    the raw source) or the book renamed the creature entirely (`"Ape,
    Carnivorous"` is `"Gorilla, Carnivorous, Giant"` here) - those correctly
    return `None` rather than a wrong monster.
    """
    ids = base_ids()
    id_set = set(ids)
    candidates = _candidates(printed_name, singular=False) + _candidates(printed_name)

    for words in candidates:
        slug = "_".join(words)
        if slug in id_set:
            return load(slug)

    index = {slug: _words(load(slug).get("name", "")) for slug in ids}
    for words in _candidates(printed_name):  # singularised, for the index below
        if set(words) <= _STOPWORDS:
            continue
        n = len(words)
        hits = set()
        for slug, nwords in index.items():
            for i in range(0, len(nwords) - n + 1):
                if nwords[i:i + n] == words:
                    hits.add(slug)
                    break
        if len(hits) == 1:
            return load(next(iter(hits)))
    return None


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
