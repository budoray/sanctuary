"""Typed access to the committed OSRIC table corpus.

The extractor is dumb on purpose: it stores each table's lines as printed.
Interpretation lives here, so one table's quirks cannot break another's.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"
_DASH = re.compile(r"[–—-]")


@lru_cache(maxsize=None)
def _index() -> dict[str, tuple[Path, ...]]:
    """id -> every file carrying it, in filename order.

    19 ids have MORE THAN ONE file - a table split across pages keeps its id
    and gains a "... CONTINUED" or "... PART 2" name (2.9.1c has two, 2.9.1h
    has four, 1.4.2.3a has three). Mapping id -> a single Path silently keeps
    whichever file globbed last and discards 26 tables.
    """
    out: dict[str, list[Path]] = {}
    for p in sorted(_DIR.glob("*.yaml")):
        out.setdefault(p.name.split("_", 1)[0], []).append(p)
    return {k: tuple(v) for k, v in out.items()}


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parts(table_id: str) -> list[dict]:
    """Every document carrying `table_id`, in order. Use this for a table the
    book split across pages."""
    paths = _index().get(table_id.lower())
    if not paths:
        raise KeyError(f"no table {table_id!r} in {_DIR}")
    return [_read(p) for p in paths]


@lru_cache(maxsize=None)
def load(table_id: str) -> dict:
    """The single document for a table, keyed by its OSRIC number.

    Raises when the id covers several files rather than picking one - a caller
    that wants a split table must say so by calling `parts()`.
    """
    paths = _index().get(table_id.lower())
    if not paths:
        raise KeyError(f"no table {table_id!r} in {_DIR}")
    if len(paths) > 1:
        names = ", ".join(p.name for p in paths)
        raise LookupError(
            f"table {table_id!r} spans {len(paths)} files ({names}); call parts()")
    return _read(paths[0])


def _is_ac_header(fields: list[str]) -> bool:
    """True for a to-hit table's armour-class header row, e.g.
    `10 9 8 7 6 5 4 3 2 1 0 -1 -2 -3 -4 -5 -6 -7 -8 -9 -10`.

    That line starts with a digit like any data row, so the `[<\\d]` check in
    `rows()` keeps it. What makes it a header and not a row is that every
    field is a bare integer and the whole line strictly decreases - a real
    row's label is followed by to-hit numbers that rise (or hold) as the
    target gets easier to hit, never a single unbroken descent end to end.
    """
    try:
        nums = [int(f) for f in fields]
    except ValueError:
        return False
    return len(nums) > 1 and all(a > b for a, b in zip(nums, nums[1:]))


def rows(table_id: str) -> list[list[str]]:
    """Data rows, whitespace-split. Lines that do not begin with a number,
    range or `<` are treated as wrapped headers and dropped, as is the
    armour-class header row some to-hit tables repeat as data-shaped text
    (see `_is_ac_header`)."""
    out = []
    for line in load(table_id)["lines"]:
        if not re.match(r"^\s*[<\d]", line):
            continue
        fields = line.split()
        if _is_ac_header(fields):
            continue
        out.append(fields)
    return out


def in_range(spec: str, value: float) -> bool:
    """Does `value` fall in an OSRIC row label?

    Handles `3`, `4-5`, `4–5`, `18.01–18.50`, `19+`, and `<1-1`.

    Refuses `"N-N"` labels (equal endpoints, e.g. `"1-1"`) with `ValueError`
    rather than guess: OSRIC's hit-dice column overloads the hyphen for two
    things - a genuine range (`"2-3"`) and the "N hit dice minus 1 hit point"
    idiom (`"1-1"`), and a real range is never written with identical
    endpoints (you'd just write the bare value). Reading `"1-1"` as the
    numeric range [1, 1] makes it collapse to `value == 1` and shadow the
    bare `"1"` row before it is ever reached - see `ability_row`. Interpreting
    the hit-dice idiom itself belongs to whichever caller needs it (monster
    hit dice, Chapter 5), not to this generic range parser.
    """
    s = (spec or "").strip()
    if not s:
        return False
    if s.startswith("<"):
        try:
            return value < float(_DASH.split(s[1:], 1)[0])
        except ValueError:
            return False
    open_ended = s.endswith("+")
    s = s.rstrip("+")
    parts = [p for p in _DASH.split(s) if p]
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return False
    if not nums:
        return False
    if open_ended and len(nums) == 1:
        return value >= nums[0]
    if len(nums) == 1:
        return value == nums[0]
    if len(nums) == 2 and nums[0] == nums[1]:
        raise ValueError(
            f"ambiguous row label {spec!r}: an equal-endpoint range is not "
            "distinguishable from OSRIC's hit-dice idiom; interpret it in "
            "the caller that knows which one it means")
    return nums[0] <= value <= nums[-1]


def ability_row(table_id: str, score: float) -> list[str]:
    """The row of an ability table whose first cell covers `score`."""
    for row in rows(table_id):
        if row and in_range(row[0], score):
            return row
    raise LookupError(f"no row in {table_id} covers {score}")
