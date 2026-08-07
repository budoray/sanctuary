"""Structural invariants for the Sanctuary backend."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "app"
DICE_MODULE = APP_ROOT / "engine" / "dice.py"

_RANDOM_DOT = re.compile(r"\brandom\.")


def _app_py_files():
    for path in APP_ROOT.rglob("*.py"):
        if path == DICE_MODULE:
            continue
        yield path


@pytest.mark.parametrize("path", list(_app_py_files()))
def test_no_random_module_usage(path: Path):
    """Python's ``random`` module may only be used inside ``engine/dice.py``."""
    text = path.read_text(encoding="utf-8")
    assert "import random" not in text, f"{path}: contains 'import random'"
    assert "from random" not in text, f"{path}: contains 'from random ...'"
    assert not _RANDOM_DOT.search(text), f"{path}: contains 'random.'"
