"""Drop-in build-version source for Tenshin Arts apps.

Every app reports its build the same way:

    a stamped ``VERSION`` file at the repo root (the git tag, e.g. ``v0.1.0-beta``)
      -> else ``git describe --tags --always`` in a dev checkout
      -> else ``"dev"``

Serve plain text at ``GET /version`` — see website/SSOT.md.
"""
import subprocess
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def get_version() -> str:
    """Build version string: stamped VERSION file → git describe → "dev"."""
    try:
        text = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    try:
        out = subprocess.run(["git", "describe", "--tags", "--always"],
                             cwd=_ROOT, capture_output=True, text=True, timeout=5)
        desc = out.stdout.strip()
        if out.returncode == 0 and desc:
            return desc
    except (OSError, subprocess.SubprocessError):
        pass
    return "dev"


if __name__ == "__main__":
    print(get_version())
