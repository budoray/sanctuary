import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Tests run with auth bypassed so we don't need real Tenshin cookies.
os.environ.setdefault("TENSHIN_DEV", "1")
os.environ.setdefault("TENSHIN_DEV_ACCOUNT", "1")

# Keep tests fast and independent of a local Ollama instance.
os.environ["OLLAMA_ENABLED"] = "false"
os.environ.setdefault("OLLAMA_TIMEOUT", "0.1")
