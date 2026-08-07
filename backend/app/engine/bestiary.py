"""Minimal monster loader for tactical combat.

Loads `*.yaml` from a monsters directory. Only the fields needed for
map/token combat are exposed: hp, ac, to-hit bonus, damage die.
"""
import re
from pathlib import Path

import yaml

_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "monsters"

_HIT_DICE_RE = re.compile(r"^(\d+)(?:\s*-\s*1)?(?:\+\d+)?$")
_AC_RE = re.compile(r"^(\d+)\s*\[\s*(\d+)\s*\]")
_DAMAGE_RE = re.compile(r"(\d+d\d+(?:[+-]\d+)?)")


def _parse_hit_dice(hd: str) -> tuple[int, int]:
    """Return (dice_count, die_faces). '1-1' becomes (1, 8) with a -1 hp adjustment
    applied after rolling."""
    hd = hd.strip().lower()
    if hd.endswith("-1"):
        count = int(hd.split("-")[0])
        return count, 8
    if "+" in hd:
        count = int(hd.split("+")[0])
        return count, 8
    if hd.isdigit():
        return int(hd), 8
    raise ValueError(f"unreadable hit dice: {hd!r}")


def _hp_adjustment(hd: str) -> int:
    hd = hd.strip().lower()
    if hd.endswith("-1"):
        return -1
    if "+" in hd:
        return int(hd.split("+")[1])
    return 0


def _parse_ac(ac: str) -> int:
    """Return descending AC (lower is better)."""
    m = _AC_RE.match(ac.strip())
    if m:
        return int(m.group(1))
    # Fallback: plain number.
    digits = re.findall(r"\d+", ac)
    if digits:
        return int(digits[0])
    raise ValueError(f"unreadable armour class: {ac!r}")


def _parse_damage(melee: str) -> str:
    m = _DAMAGE_RE.search(melee)
    return m.group(1) if m else "1d6"


def load(name: str, monsters_dir: Path | None = None) -> dict:
    """Load a monster by name or slug."""
    directory = monsters_dir or _DEFAULT_DIR
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    path = directory / f"{slug}.yaml"
    if not path.exists():
        raise KeyError(f"no monster {name!r} ({path})")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    hd = str(doc.get("hit_dice", "1"))
    count, faces = _parse_hit_dice(hd)
    return {
        "id": slug,
        "name": doc["name"],
        "hit_dice": hd,
        "hp_dice_count": count,
        "hp_die_faces": faces,
        "hp_adjustment": _hp_adjustment(hd),
        "ac": _parse_ac(str(doc.get("armour_class", "10"))),
        "damage": _parse_damage(str(doc.get("melee_attacks", "1d6"))),
        "description": doc.get("description", ""),
    }


def base_ids(monsters_dir: Path | None = None) -> list[str]:
    directory = monsters_dir or _DEFAULT_DIR
    return sorted(p.stem for p in directory.glob("*.yaml"))
