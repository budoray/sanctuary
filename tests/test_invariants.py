"""Structural invariants. Each of these has a real failure behind it."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The only module allowed to touch a second source of randomness.
_ALLOWED = ROOT / "sanctuary" / "dice.py"

# Directories excluded from the scan: tests exercise randomness-adjacent
# fixtures (duck-typed rollers, seeded stand-ins) and tools/ is one-off
# extraction tooling, neither of which is on the game's dice path.
_EXCLUDED_DIRS = {"tests", "tools"}


def _python_sources():
    for p in sorted(ROOT.rglob("*.py")):
        if p == _ALLOWED:
            continue
        rel = p.relative_to(ROOT)
        if rel.parts[0] in _EXCLUDED_DIRS:
            continue
        if "__pycache__" in rel.parts:
            continue
        yield p


def _random_offenses(source: str) -> list[str]:
    """AST-level offenses: an Import/ImportFrom of `random`, `secrets`, or
    `os.urandom`, or an attribute access on a name bound to the `random`
    module or to `os.urandom`. A substring match on "random." or "import
    random" (the previous version of this test) misses `from random import
    randint`, `from os import urandom`, `import secrets`, and any alias that
    doesn't happen to contain the word "random" in the matched text - all
    four are probed and proven to be caught below (test_evasions_are_all_caught
    is the standing proof; this docstring just states the contract)."""
    tree = ast.parse(source)
    random_aliases = set()
    os_aliases = set()
    offenses = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                bound = alias.asname or top
                if top == "random":
                    offenses.append(f"import {alias.name}")
                    random_aliases.add(bound)
                elif top == "secrets":
                    offenses.append(f"import {alias.name}")
                elif top == "os":
                    os_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            names = ", ".join(a.name for a in node.names)
            if top == "random":
                offenses.append(f"from {node.module} import {names}")
            elif top == "secrets":
                offenses.append(f"from {node.module} import {names}")
            elif top == "os" and any(a.name == "urandom" for a in node.names):
                offenses.append("from os import urandom")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id in random_aliases:
                offenses.append(f"{node.value.id}.{node.attr}")
            elif node.value.id in os_aliases and node.attr == "urandom":
                offenses.append(f"{node.value.id}.urandom")

    return offenses


def test_random_is_confined_to_the_dice_module():
    offenders = {}
    for p in _python_sources():
        offenses = _random_offenses(p.read_text(encoding="utf-8"))
        if offenses:
            offenders[str(p.relative_to(ROOT))] = offenses
    assert offenders == {}, (
        f"a second source of randomness outside dice.py: {offenders}. Every "
        "die in Sanctuary comes from sanctuary.dice, or the replay guarantee "
        "is gone."
    )


# The one-way dependency chain from the design record (docs/superpowers/specs/
# 2026-08-01-sanctuary-design.md §5). Each element is a rank; modules in the
# same rank are siblings introduced together. A module may only import
# something from a STRICTLY LATER rank (or `dice`, which every rank may use)
# - never a sibling, never anything to its own left. Encoded as data so a
# module landing in a later chapter (spells, resolve, bestiary, procgen, ...)
# slots in by adding it to a rank here, with no change to the walk below.
DEPENDENCY_CHAIN = (
    ("dm", "session"),
    ("runtime",),
    ("module",),
    ("procgen", "bestiary", "treasure"),
    ("resolve",),
    ("character",),
    ("spells",),
    ("tables",),
    ("dice",),
)

_RANK_OF = {name: rank for rank, names in enumerate(DEPENDENCY_CHAIN) for name in names}


def _sanctuary_imports(source: str) -> list[str]:
    """Every `sanctuary.<name>` module this file imports, in any of the three
    import spellings (`import sanctuary.x`, `import sanctuary.x as y`,
    `from sanctuary import x`, `from sanctuary.x import y`)."""
    tree = ast.parse(source)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "sanctuary" and len(parts) > 1:
                    names.append(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sanctuary":
                names.extend(a.name for a in node.names)
            elif node.module and node.module.startswith("sanctuary."):
                names.append(node.module.split(".")[1])
    return names


def test_dependency_chain_is_one_way():
    """§5: dm -> runtime -> module -> {procgen, bestiary, treasure} ->
    {character, resolve} -> tables -> dice. A module may import only
    strictly later ranks; importing a sibling or anything leftward collapses
    the chain into a ball of mud one module at a time."""
    violations = []
    for p in sorted((ROOT / "sanctuary").glob("*.py")):
        module = p.stem
        if module not in _RANK_OF:
            continue  # not yet part of the chain; nothing to enforce
        own_rank = _RANK_OF[module]
        for imported in _sanctuary_imports(p.read_text(encoding="utf-8")):
            their_rank = _RANK_OF.get(imported)
            if their_rank is not None and their_rank <= own_rank:
                violations.append(
                    f"{module}.py imports sanctuary.{imported}, which breaks the "
                    f"§5 chain: {module} (rank {own_rank}) may only import ranks "
                    f"after its own, not {imported} (rank {their_rank})")
    assert violations == [], "\n".join(violations)


def test_client_has_no_second_rng():
    """Scans every file under static/ that can be decoded as text - not a
    fixed extension allowlist - so a script hidden in an .svg, .mjs, .json,
    or any future asset type is still caught. Binary assets (portraits, etc.)
    raise UnicodeDecodeError and are skipped rather than exempted by name."""
    static = ROOT / "static"
    if not static.exists():
        return
    offenders = []
    for p in static.rglob("*"):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "Math.random" in text:
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], (
        f"Math.random in the client: {offenders}. The animated die renders the "
        "number the engine already rolled; it never generates one."
    )
