"""Where the OSRIC source PDFs live.

⚠ The books are NOT in this repo and must never be. `github.com/budoray/sanctuary`
is PUBLIC, and the OSRIC 3.0 Third-Party License permits reusing the text of
monsters, spells and magic items - it does not permit redistributing the books.
Committing the PDFs would republish Mythmere Games' commercial product.

They are the source of the round-trip gate: `tests/test_corpus.py` re-extracts
from them and byte-compares against the committed `data/tables/`, which is what
makes "never hand-edit data/tables/" enforceable rather than aspirational.

⚠ This lookup exists because a hardcoded Downloads path already failed once.
The PDFs were cleaned out of Downloads, the round-trip tests skipped, and the
suite stayed green for several chapters while the corpus was unverifiable - the
platform's own "a broken measurement still returns a number" lesson. Prefer the
stable `_reference` directory beside the game repos; Downloads is a fallback,
not a home.

Override with the SANCTUARY_OSRIC_DIR environment variable.
"""
import os
from pathlib import Path

PLAYER_GUIDE = "OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"
GM_GUIDE = "OSRIC_3.0_Gamemaster_Guide.pdf"

# Searched in order. The first directory holding BOTH books wins.
_CANDIDATES = (
    os.environ.get("SANCTUARY_OSRIC_DIR"),
    Path(__file__).resolve().parent.parent.parent / "_reference" / "osric",
    Path.home() / "Downloads",
)


def osric_dir() -> Path | None:
    """The directory holding both books, or None if neither location has them."""
    for c in _CANDIDATES:
        if not c:
            continue
        d = Path(c)
        if (d / PLAYER_GUIDE).exists() and (d / GM_GUIDE).exists():
            return d
    return None


def source_pdfs() -> list[Path] | None:
    """Both books as paths, or None when they are not present here."""
    d = osric_dir()
    return None if d is None else [d / PLAYER_GUIDE, d / GM_GUIDE]


def searched() -> str:
    """Every location tried, for a skip message that names what was missing."""
    return ", ".join(str(c) for c in _CANDIDATES if c)
