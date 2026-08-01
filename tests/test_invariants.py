"""Structural invariants. Each of these has a real failure behind it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _python_sources():
    for p in (ROOT / "sanctuary").rglob("*.py"):
        yield p
    for name in ("app.py",):
        p = ROOT / name
        if p.exists():
            yield p


def test_random_is_confined_to_the_dice_module():
    offenders = []
    for p in _python_sources():
        if p.name == "dice.py":
            continue
        text = p.read_text(encoding="utf-8")
        if "random." in text or "import random" in text:
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], (
        f"`random` used outside dice.py: {offenders}. Every die in Sanctuary "
        "comes from sanctuary.dice, or the replay guarantee is gone."
    )


def test_client_has_no_second_rng():
    static = ROOT / "static"
    if not static.exists():
        return
    offenders = [
        str(p.relative_to(ROOT))
        for p in static.rglob("*")
        if p.is_file() and p.suffix in (".js", ".html")
        and "Math.random" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        f"Math.random in the client: {offenders}. The animated die renders the "
        "number the engine already rolled; it never generates one."
    )
