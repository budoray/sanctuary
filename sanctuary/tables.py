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

    20 ids have MORE THAN ONE file - a table split across pages keeps its id
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


def rows(table_id: str) -> list[list[str]]:
    """Data rows, whitespace-split. Lines that do not begin with a number,
    range or `<` are treated as wrapped headers and dropped."""
    out = []
    for line in load(table_id)["lines"]:
        if not re.match(r"^\s*[<\d]", line):
            continue
        out.append(line.split())
    return out


def in_range(spec: str, value: float) -> bool:
    """Does `value` fall in an OSRIC row label?

    Handles `3`, `4-5`, `4–5`, `18.01–18.50`, `19+`, and `<1-1`.
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
    return nums[0] <= value <= nums[-1]


def ability_row(table_id: str, score: float) -> list[str]:
    """The row of an ability table whose first cell covers `score`."""
    for row in rows(table_id):
        if row and in_range(row[0], score):
            return row
    raise LookupError(f"no row in {table_id} covers {score}")
