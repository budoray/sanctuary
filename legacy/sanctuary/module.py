"""The module/campaign format: load, validate, save.

A module is the spine the runtime plays: regions with their own wandering
tables, numbered areas with exits, module-local monsters/items/mechanics.
The shape is fixed by docs/superpowers/specs/2026-08-01-sanctuary-design.md
§8.1 - this file parses and checks it, never redesigns it.

⚠ `validate()` reports EVERY problem it finds, not the first one - a GM
fixing a 67-area module needs the whole list, not a scavenger hunt.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

from sanctuary import dice

# Required keys, by shape. A value that is a dict names its own nested
# requirements; a value that is None means "just check the key is present".
_MODULE_REQUIRED = ("title", "version", "party_guidance", "background", "start")
_PARTY_GUIDANCE_REQUIRED = ("size", "total_levels")
_REGION_REQUIRED = ("id", "areas", "check", "table")
_CHECK_REQUIRED = ("chance", "every")
_TABLE_REQUIRED = ("die", "entries")
_AREA_REQUIRED = ("id", "name", "description")
_EXIT_REQUIRED = ("to", "kind", "hidden")
_DISCOVERY_REQUIRED = ("what", "trigger")
_TRIGGER_REQUIRED = ("action", "scope")


@dataclass(frozen=True)
class Problem:
    """One validation failure. `where` names the area/region it belongs to,
    e.g. "area 5" or "region south" or "module" for a top-level problem."""
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


class ModuleError(ValueError):
    """Raised by `load` when `validate` found problems. Carries the full
    list so a caller can report every one, not just the first."""

    def __init__(self, problems: list[Problem]):
        self.problems = problems
        super().__init__("\n".join(str(p) for p in problems))


def _missing(doc: dict, required: tuple, where: str, problems: list[Problem]) -> None:
    for key in required:
        if key not in doc:
            problems.append(Problem(where, f"missing required key '{key}'"))


def _die_faces(die: str) -> int | None:
    """`table.die` is written like "d8", not a full dice expression. Reuse
    dice.parse_expr by spelling it as one die of that size."""
    try:
        _, faces, _, _ = dice.parse_expr(f"1{die}")
        return faces
    except ValueError:
        return None


def validate(doc: dict) -> list[Problem]:
    """Check a module document against the §8.1 contract. Returns every
    problem found - callers that want a hard failure should raise on a
    non-empty list (see `load`), not stop here."""
    problems: list[Problem] = []
    if not isinstance(doc, dict):
        return [Problem("module", "document is not a mapping")]

    mod = doc.get("module")
    if not isinstance(mod, dict):
        problems.append(Problem("module", "missing required key 'module'"))
    else:
        _missing(mod, _MODULE_REQUIRED, "module", problems)
        pg = mod.get("party_guidance")
        if isinstance(pg, dict):
            _missing(pg, _PARTY_GUIDANCE_REQUIRED, "module.party_guidance", problems)
        elif "party_guidance" in mod:
            problems.append(Problem("module", "party_guidance is not a mapping"))

    areas = doc.get("areas")
    if not isinstance(areas, list):
        problems.append(Problem("module", "missing required key 'areas'"))
        areas = []

    area_ids: list[int] = []
    for i, area in enumerate(areas):
        where = f"area {area.get('id', i) if isinstance(area, dict) else i}"
        if not isinstance(area, dict):
            problems.append(Problem(where, "area is not a mapping"))
            continue
        _missing(area, _AREA_REQUIRED, where, problems)
        if "id" in area:
            area_ids.append(area["id"])
        for exit_ in area.get("exits") or []:
            if not isinstance(exit_, dict):
                problems.append(Problem(where, f"exit is not a mapping: {exit_!r}"))
                continue
            _missing(exit_, _EXIT_REQUIRED, where, problems)
            # existence of exit.to checked below, once every area id is known
        for disc in area.get("discoveries") or []:
            if not isinstance(disc, dict):
                problems.append(Problem(where, f"discovery is not a mapping: {disc!r}"))
                continue
            _missing(disc, _DISCOVERY_REQUIRED, where, problems)
            trigger = disc.get("trigger")
            if not isinstance(trigger, dict):
                if "trigger" in disc:
                    problems.append(Problem(where, "discovery trigger is not a mapping"))
                continue
            _missing(trigger, _TRIGGER_REQUIRED, where, problems)
            if trigger.get("chance") and not trigger.get("per"):
                problems.append(Problem(
                    where,
                    f"discovery {disc.get('what', '?')!r} has a chance but no 'per'"))

    dupes = {a for a in area_ids if area_ids.count(a) > 1}
    if dupes:
        problems.append(Problem("module", f"duplicate area ids: {sorted(dupes)}"))
    area_id_set = set(area_ids)

    for i, area in enumerate(areas):
        if not isinstance(area, dict):
            continue
        where = f"area {area.get('id', i)}"
        for exit_ in area.get("exits") or []:
            if isinstance(exit_, dict) and "to" in exit_ and exit_["to"] not in area_id_set:
                problems.append(Problem(
                    where, f"exit points to non-existent area {exit_['to']!r}"))

    regions = doc.get("regions")
    if not isinstance(regions, list):
        problems.append(Problem("module", "missing required key 'regions'"))
        regions = []

    for i, region in enumerate(regions):
        where = f"region {region.get('id', i) if isinstance(region, dict) else i}"
        if not isinstance(region, dict):
            problems.append(Problem(where, "region is not a mapping"))
            continue
        _missing(region, _REGION_REQUIRED, where, problems)

        area_range = region.get("areas")
        if isinstance(area_range, list) and len(area_range) == 2:
            lo, hi = area_range
            if not any(lo <= a <= hi for a in area_ids):
                problems.append(Problem(
                    where, f"area range [{lo}, {hi}] covers no area in the module"))
        elif "areas" in region:
            problems.append(Problem(where, "areas is not a [lo, hi] range"))

        check = region.get("check")
        if isinstance(check, dict):
            _missing(check, _CHECK_REQUIRED, where, problems)
        elif "check" in region:
            problems.append(Problem(where, "check is not a mapping"))

        table = region.get("table")
        if isinstance(table, dict):
            _missing(table, _TABLE_REQUIRED, where, problems)
            die, entries = table.get("die"), table.get("entries")
            if die is not None and entries is not None:
                faces = _die_faces(die)
                if faces is None:
                    problems.append(Problem(where, f"table die is unreadable: {die!r}"))
                elif len(entries) != faces:
                    problems.append(Problem(
                        where,
                        f"table die {die} needs {faces} entries, has {len(entries)}"))
        elif "table" in region:
            problems.append(Problem(where, "table is not a mapping"))

    return problems


def load(path_or_dict) -> "Module":
    """Parse and validate a module. Accepts a path (str/Path) to a YAML
    file, or an already-parsed dict. Raises ModuleError with every problem
    found if the document is invalid."""
    if isinstance(path_or_dict, dict):
        doc = path_or_dict
    else:
        doc = yaml.safe_load(Path(path_or_dict).read_text(encoding="utf-8"))
    problems = validate(doc)
    if problems:
        raise ModuleError(problems)
    return Module(doc)


def save(module: "Module", path) -> Path:
    """Write a module back out as YAML, returning `path` so that
    `load(save(m)) == m` round-trips."""
    path = Path(path)
    path.write_text(
        yaml.safe_dump(module.doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


@dataclass(frozen=True)
class Module:
    """A validated module document. Equality and everything else is
    structural over the underlying dict - the format IS the model."""
    doc: dict

    @property
    def title(self) -> str:
        return self.doc["module"]["title"]

    @property
    def areas(self) -> list[dict]:
        return self.doc["areas"]

    @property
    def regions(self) -> list[dict]:
        return self.doc["regions"]

    def area(self, area_id: int) -> dict:
        for a in self.areas:
            if a["id"] == area_id:
                return a
        raise KeyError(f"no area {area_id} in module {self.title!r}")
