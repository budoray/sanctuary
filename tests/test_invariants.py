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


def test_client_has_no_second_rng():
    static = ROOT / "static"
    if not static.exists():
        return
    offenders = [
        str(p.relative_to(ROOT))
        for p in static.rglob("*")
        if p.is_file() and p.suffix in (".js", ".html", ".css")
        and "Math.random" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"Math.random in the client: {offenders}. The animated die renders the "
        "number the engine already rolled; it never generates one."
    )
