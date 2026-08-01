# Sanctuary Foundation + Chapter 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `v0.1.0-beta` — a seeded, replayable dice engine, an extracted OSRIC table corpus, and complete character generation for all 7 ancestries and 11 classes, served with the house chrome and the OSRIC licence notice.

**Architecture:** A seeded `Dice` object records every roll to an append-only log, so a whole session replays identically from its seed. A dumb PDF extractor emits one YAML per OSRIC table as raw lines; typed accessors in `tables.py` interpret the tables each chapter actually needs. `character.py` builds characters by rolling through `Dice` and reading through `tables.py`. FastAPI serves it; the client is zero-build HTML/JS.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, PyYAML, itsdangerous, pypdf (dev/extraction only). No bundler, no node, no CDN.

## Global Constraints

- **Repo:** `D:\Tenshin Arts\Sanctuary`, remote `https://github.com/budoray/sanctuary.git`, branch `main`.
- **Slug** `sanctuary`. **Port 9300.** One name per thing: slug == subdomain == systemd unit == data directory == git repo.
- **Every commit bumps the build** — the patch of `vX.Y.Z-beta` in `VERSION`, staged in that same commit. The minor moves only when a chapter lands complete, and the build restarts at `0` when it does. This plan starts at `v0.0.2-beta` and ends at `v0.1.0-beta`.
- **No `.github/` directory.** There is no CI/CD on this platform.
- **`encoding="utf-8"` on every `read_text` / `write_text` without exception.** Windows defaults to cp1252 and every source file here carries en-dashes, curly quotes and ligatures. This rule has bitten twice on this platform, once inside a script written to document it.
- **Every module the entrypoint imports is declared in `requirements.txt`.** A game's own gate cannot catch an omission — it runs where the package is already installed. Two games shipped a 502 this way with every gate green.
- **No third-party requests from a player's browser.** No CDN, no Google Fonts, no remote images.
- **`random.` must appear nowhere outside `sanctuary/dice.py`**, and `Math.random` nowhere in `static/`. Asserted by test.
- **Licence notice, verbatim, in the client and at `/licence`:** `Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License and is not affiliated with Mythmere Games LLC.`
- **House chrome in every client, same set, same order:** build · report · back · sign out. `back` is `← Tenshin Arts` to the site ROOT and leaves you signed in; `sign out` ends the session.
- **`tenshin_feedback.submit()` returns `(ok, info)` — a tuple.** Unpack it. `bool()` on a 2-tuple is always True.
- **The gate reads the CLIENT, not just the routes.** A route that exists is not a feature a player can reach.
- **A self-check prints what it proved, in a sentence, with numbers interpolated from what it computed** — never typed in.
- Source PDFs live in `C:\Users\budor\Downloads\`. Extracted plain text is in the session scratchpad; the extractor reads the **PDFs**, not the scratchpad.

★ **TESTING STANDARD, site-wide (Dr. Ray, 2026-08-01).** Applies to every task from here and to every Tenshin repo:

- **BDD features AND TDD tests, both.** Every behaviour gets a Gherkin `.feature` file under `features/` describing it in the language of the game, bound with `pytest-bdd` (installed, 8.1.0, runs inside pytest — no second runner, the gate stays two commands). The TDD unit tests stay as they are; BDD is added alongside, not instead.
- **Maximum coverage.** `pytest-cov` is installed. Every module carries tests; a new branch without a test is unfinished work.
- ⚠ **Every change of the MINOR version triggers a full test suite run** — `python -m pytest tests/ -q` plus `python app.py test` once it exists, both green, before the minor moves. A patch bump runs the tests covering what it touched; a minor bump runs everything. The minor is the chapter boundary, and a chapter that lands red is a chapter nobody can build on.
- `pytest-bdd` and `pytest-cov` are declared in `requirements.txt` even though `app.py` never imports them — an undeclared test dependency is how a future session's suite fails for no visible reason.

⚠ **A BDD scenario that restates the unit test in Gherkin is waste.** Features describe behaviour a player or GM would recognise — *"a fighter with exceptional Strength hits harder"* — not *"parse_expr returns a 4-tuple"*. If a scenario cannot be phrased without naming a Python symbol, it belongs in the unit tests, not in a feature file.

---

### Task 1: Repo skeleton, drop-ins and dependencies

**Files:**
- Create: `requirements.txt`, `sanctuary/__init__.py`, `tests/__init__.py`
- Create: `tenshin_version.py`, `tenshin_gate.py`, `tenshin_feedback.py` (byte-identical copies from `D:\Tenshin Arts\Website\`)
- Modify: `VERSION`

**Interfaces:**
- Consumes: nothing.
- Produces: `tenshin_version.get_version() -> str`; `tenshin_gate.require_account(request) -> int`; `tenshin_feedback.submit(game, kind, title, body="", username="", meta=None, image="", timeout=6) -> tuple[bool, dict]`.

- [ ] **Step 1: Copy the three drop-ins byte-identically**

These are vendored, canonical in the Website repo. Do not edit them here.

```bash
cd "D:/Tenshin Arts/Sanctuary"
cp "../Website/tenshin_version.py" .
cp "../Website/tenshin_gate.py" .
cp "../Website/tenshin_feedback.py" .
```

- [ ] **Step 2: Verify they are byte-identical**

```bash
for f in tenshin_version.py tenshin_gate.py tenshin_feedback.py; do
  cmp "$f" "../Website/$f" && echo "$f OK"
done
```
Expected: three `OK` lines, no `differ` output.

- [ ] **Step 3: Write `requirements.txt`**

`pypdf` is declared even though `app.py` never imports it — an undeclared dev dependency is how a future session's extraction run dies for no visible reason.

```
fastapi>=0.110
uvicorn>=0.29
PyYAML>=6
itsdangerous>=2
pypdf>=4
```

- [ ] **Step 4: Create package markers**

```bash
mkdir -p sanctuary tests data/tables tools static
printf '"""Sanctuary - an OSRIC 3.0 table in the browser."""\n' > sanctuary/__init__.py
touch tests/__init__.py
```

- [ ] **Step 5: Install and verify the interpreter**

⚠ Use the **system** python. Any `.venv` in this tree is a decoy.

```bash
python -m pip install -r requirements.txt
python -c "import fastapi, uvicorn, yaml, itsdangerous, pypdf; print('deps OK')"
```
Expected: `deps OK`

- [ ] **Step 6: Commit**

```bash
cd "D:/Tenshin Arts/Sanctuary"
printf 'v0.0.3-beta\n' > VERSION
git add requirements.txt sanctuary/__init__.py tests/__init__.py tenshin_version.py tenshin_gate.py tenshin_feedback.py VERSION
git commit -m "Repo skeleton: vendored drop-ins and declared dependencies"
```

---

### Task 2: The dice engine — `Roll` record and expression parsing

**Files:**
- Create: `sanctuary/dice.py`
- Test: `tests/test_dice.py`

**Interfaces:**
- Consumes: nothing. `dice.py` imports nothing of ours, ever.
- Produces:
  - `parse_expr(expr: str) -> tuple[int, int, int, int]` returning `(count, faces, drop_lowest, modifier)`
  - `Roll` frozen dataclass with fields `index: int`, `expr: str`, `faces: tuple[int, ...]`, `kept: tuple[int, ...]`, `mods: int`, `total: int`, `reason: str`, `tags: dict`
  - `Dice(seed: int)` with `.roll(expr, reason="", mods=0, **tags) -> Roll` and `.log -> tuple[Roll, ...]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dice.py`:

```python
import pytest

from sanctuary.dice import Roll, parse_expr


def test_parse_simple():
    assert parse_expr("3d6") == (3, 6, 0, 0)


def test_parse_drop_lowest():
    assert parse_expr("4d6d1") == (4, 6, 1, 0)


def test_parse_modifier():
    assert parse_expr("1d20+3") == (1, 20, 0, 3)
    assert parse_expr("1d8-1") == (1, 8, 0, -1)


def test_parse_drop_and_modifier():
    assert parse_expr("4d6d1+2") == (4, 6, 1, 2)


def test_parse_rejects_nonsense():
    for bad in ["", "d6", "3d", "3x6", "3d6d", "0d6", "3d0", "4d6d4"]:
        with pytest.raises(ValueError):
            parse_expr(bad)


def test_roll_is_frozen():
    r = Roll(index=0, expr="1d6", faces=(4,), kept=(4,), mods=0,
             total=4, reason="", tags={})
    with pytest.raises(Exception):
        r.total = 99
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_dice.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanctuary.dice'`

- [ ] **Step 3: Write the minimal implementation**

Create `sanctuary/dice.py`:

```python
"""Seeded dice with an append-only roll log.

Every die rolled anywhere in Sanctuary comes from here. Same seed plus the same
call sequence produces a byte-identical log, which is what makes a generator
property testable, a bug report reproducible from its seed, and the game
auditable to a player who suspects the dice.

This module imports nothing else from Sanctuary. Nothing else may import
`random`.
"""
import random
import re
from dataclasses import dataclass, field

# NdM, optional dL (drop L lowest), optional +X / -X
_EXPR = re.compile(r"^(\d+)d(\d+)(?:d(\d+))?([+-]\d+)?$")


def parse_expr(expr: str) -> tuple[int, int, int, int]:
    """Parse a dice expression into (count, faces, drop_lowest, modifier)."""
    m = _EXPR.match((expr or "").strip().replace(" ", ""))
    if not m:
        raise ValueError(f"bad dice expression: {expr!r}")
    count = int(m.group(1))
    faces = int(m.group(2))
    drop = int(m.group(3) or 0)
    mods = int(m.group(4) or 0)
    if count < 1:
        raise ValueError(f"need at least one die: {expr!r}")
    if faces < 2:
        raise ValueError(f"a die needs at least two faces: {expr!r}")
    if drop >= count:
        raise ValueError(f"cannot drop {drop} of {count} dice: {expr!r}")
    return count, faces, drop, mods


@dataclass(frozen=True)
class Roll:
    """One roll, with the arithmetic that produced it.

    `faces` is every die as it landed; `kept` is what counted after any drop.
    The client renders the reasoning, not just the number.
    """
    index: int
    expr: str
    faces: tuple[int, ...]
    kept: tuple[int, ...]
    mods: int
    total: int
    reason: str = ""
    tags: dict = field(default_factory=dict)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dice.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.4-beta\n' > VERSION
git add sanctuary/dice.py tests/test_dice.py VERSION
git commit -m "Dice: expression parsing and the immutable Roll record"
```

---

### Task 3: The dice engine — rolling, the log, and replay determinism

**Files:**
- Modify: `sanctuary/dice.py`
- Modify: `tests/test_dice.py`

**Interfaces:**
- Consumes: `parse_expr`, `Roll` from Task 2.
- Produces: `Dice(seed: int)`, `.roll(expr, reason="", mods=0, **tags) -> Roll`, `.log -> tuple[Roll, ...]`, `.seed -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dice.py`:

```python
from sanctuary.dice import Dice


def test_roll_totals_and_records():
    d = Dice(seed=12345)
    r = d.roll("3d6", reason="strength")
    assert len(r.faces) == 3
    assert all(1 <= f <= 6 for f in r.faces)
    assert r.kept == r.faces
    assert r.total == sum(r.faces)
    assert r.reason == "strength"
    assert r.index == 0


def test_drop_lowest_keeps_the_best_three():
    d = Dice(seed=999)
    r = d.roll("4d6d1")
    assert len(r.faces) == 4
    assert len(r.kept) == 3
    assert sorted(r.kept) == sorted(r.faces)[1:]
    assert r.total == sum(r.kept)


def test_modifier_is_added_and_recorded_separately():
    d = Dice(seed=7)
    r = d.roll("1d20", mods=3)
    assert r.mods == 3
    assert r.total == sum(r.kept) + 3


def test_log_is_append_only_and_monotonic():
    d = Dice(seed=1)
    for i in range(5):
        d.roll("1d6", reason=f"r{i}")
    assert [r.index for r in d.log] == [0, 1, 2, 3, 4]
    assert [r.reason for r in d.log] == ["r0", "r1", "r2", "r3", "r4"]


def test_same_seed_same_sequence_is_identical():
    def session(seed):
        d = Dice(seed=seed)
        d.roll("3d6", reason="a")
        d.roll("4d6d1", reason="b")
        d.roll("1d20", mods=2, reason="c")
        return [(r.expr, r.faces, r.kept, r.total) for r in d.log]

    assert session(42) == session(42)
    assert session(42) != session(43)


def test_tags_are_carried():
    d = Dice(seed=5)
    r = d.roll("1d20", reason="attack", kind="attack", actor="ilse")
    assert r.tags == {"kind": "attack", "actor": "ilse"}


def test_log_cannot_be_mutated_through_the_property():
    d = Dice(seed=5)
    d.roll("1d6")
    log = d.log
    assert isinstance(log, tuple)
    assert len(d.log) == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_dice.py -q`
Expected: FAIL — `ImportError: cannot import name 'Dice'`

- [ ] **Step 3: Implement `Dice`**

Append to `sanctuary/dice.py`:

```python
class Dice:
    """A seeded roller with an append-only log.

    One instance per session. `log` is exposed as a tuple so a caller cannot
    append to it behind the engine's back.
    """

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self._log: list[Roll] = []

    @property
    def log(self) -> tuple[Roll, ...]:
        return tuple(self._log)

    def roll(self, expr: str, reason: str = "", mods: int = 0, **tags) -> Roll:
        """Roll `expr`, record it, return the record."""
        count, faces_n, drop, expr_mods = parse_expr(expr)
        faces = tuple(self._rng.randint(1, faces_n) for _ in range(count))
        kept = tuple(sorted(faces)[drop:]) if drop else faces
        total_mods = expr_mods + int(mods)
        roll = Roll(
            index=len(self._log),
            expr=expr,
            faces=faces,
            kept=kept,
            mods=total_mods,
            total=sum(kept) + total_mods,
            reason=reason,
            tags=dict(tags),
        )
        self._log.append(roll)
        return roll
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_dice.py -q`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.5-beta\n' > VERSION
git add sanctuary/dice.py tests/test_dice.py VERSION
git commit -m "Dice: seeded rolling, append-only log, replay determinism"
```

---

### Task 4: The no-second-RNG invariant

**Files:**
- Create: `tests/test_invariants.py`

**Interfaces:**
- Consumes: nothing at runtime — this is a structural test over the source tree.
- Produces: nothing importable.

This is the only thing that actually prevents a second RNG being introduced. An animated die that generates its own number and then eases to the server's value destroys the replay guarantee silently, and no behavioural test catches it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_invariants.py`:

```python
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
```

- [ ] **Step 2: Run it — it should PASS immediately**

Run: `python -m pytest tests/test_invariants.py -q`
Expected: 2 passed

- [ ] **Step 3: Prove the test can fail (an assertion that cannot fail is not a test)**

Temporarily add `import random` to the top of `sanctuary/tables.py`… which does not exist yet, so use `sanctuary/__init__.py`:

```bash
printf 'import random\n' >> sanctuary/__init__.py
python -m pytest tests/test_invariants.py -q
```
Expected: FAIL naming `sanctuary/__init__.py`

- [ ] **Step 4: Revert the deliberate break and re-run**

```bash
git checkout sanctuary/__init__.py
python -m pytest tests/test_invariants.py -q
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.6-beta\n' > VERSION
git add tests/test_invariants.py VERSION
git commit -m "Invariant: no RNG outside dice.py, none in the client"
```

---

### Task 5: The table extractor

**Files:**
- Create: `tools/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: nothing from Sanctuary.
- Produces: `slug(name: str) -> str`; `normalise(text: str) -> str`; `find_tables(text: str) -> list[dict]` where each dict is `{"id": str, "name": str, "lines": list[str]}`; a CLI `python tools/extract.py <pdf> <out_dir>`.

The extractor is deliberately **dumb**: it slices table blocks and stores raw lines. Typed interpretation lives in `tables.py`. A universal table parser is the over-engineering trap here — Table 1.1.2A alone contains the row `18.91–18.99 +2 +5 235 1–4 (1 in 6 extraordinary success) 35`, where one column holds parenthetical prose with spaces.

- [ ] **Step 1: Write the failing test**

Create `tests/test_extract.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.extract import find_tables, normalise, slug

SAMPLE = """
 TABLE 1.1.2A: STRENGTH
STRENGTH TO HIT  DAMAGE
3 -3 -1 0 1 0
4-5 -2 -1 10 1 0
Notes:
- To-hit modifiers apply to your roll.

 TABLE 1.2.0A: REQUIRED ABILITY SCORES
CLASS STR
Fighter 9
"""


def test_normalise_expands_ligatures():
    assert normalise("e\ufb00ect") == "effect"
    assert normalise("su\ufb03cient") == "sufficient"
    assert normalise("\ufb01rst") == "first"


def test_normalise_leaves_en_dashes_alone():
    # En-dashes are meaningful in ranges (4-5, 18.01-18.50); do not mangle them.
    assert "\u2013" in normalise("4\u20135")


def test_slug():
    assert slug("REQUIRED ABILITY SCORES") == "required_ability_scores"
    assert slug("Fighter To-Hit Table") == "fighter_to_hit_table"


def test_find_tables_splits_on_headers():
    tables = find_tables(SAMPLE)
    assert [t["id"] for t in tables] == ["1.1.2a", "1.2.0a"]
    assert tables[0]["name"] == "STRENGTH"
    assert tables[1]["name"] == "REQUIRED ABILITY SCORES"


def test_find_tables_keeps_data_rows_verbatim():
    first = find_tables(SAMPLE)[0]
    assert "3 -3 -1 0 1 0" in first["lines"]
    assert "4-5 -2 -1 10 1 0" in first["lines"]


def test_find_tables_stops_a_block_at_prose():
    first = find_tables(SAMPLE)[0]
    assert not any("To-hit modifiers apply" in ln for ln in first["lines"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_extract.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools'`

- [ ] **Step 3: Implement the extractor**

Create `tools/__init__.py` (empty) and `tools/extract.py`:

```python
"""One-shot OSRIC PDF -> YAML table extractor.

Run manually; never imported by app.py. The committed YAML is the runtime
truth and the PDFs are never read at runtime.

    python tools/extract.py "C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf" data/tables

The output is deliberately raw: each table keeps its lines as printed. Typed
interpretation belongs in sanctuary/tables.py, where one table's quirks cannot
break another's.
"""
import re
import sys
import unicodedata
from pathlib import Path

# TABLE 1.3.4.4A: FIGHTER LEVEL ADVANCEMENT   /   TABLE D-2A: ROOM SIZE
_HEADER = re.compile(r"^\s*TABLE\s+([0-9][0-9.]*[A-Za-z]?|D-\d+[A-Za-z]?)\s*[:.]\s*(.+?)\s*$")
# A data row starts with a number, a range, a die code, or a short label.
_PROSE = re.compile(r"^\s*(Notes?:|[-\u2022*]\s|\*|After |Use this table|This table)")


def normalise(text: str) -> str:
    """Expand typographic ligatures; leave en-dashes and everything else alone.

    The wiki PDFs are set with U+FB00-FB06. Unnormalised, the corpus ships
    words no search will match.
    """
    return unicodedata.normalize("NFKC", text)


def slug(name: str) -> str:
    s = normalise(name).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def find_tables(text: str) -> list[dict]:
    """Slice `text` into table blocks. Each block runs from its TABLE header
    until prose, a blank run, or the next header."""
    out: list[dict] = []
    current: dict | None = None
    blanks = 0
    for raw in normalise(text).splitlines():
        m = _HEADER.match(raw)
        if m:
            if current:
                out.append(current)
            current = {"id": m.group(1).lower(), "name": m.group(2).strip(), "lines": []}
            blanks = 0
            continue
        if current is None:
            continue
        line = raw.rstrip()
        if not line.strip():
            blanks += 1
            if blanks >= 2:
                out.append(current)
                current = None
            continue
        if _PROSE.match(line) or line.startswith("=== PAGE"):
            out.append(current)
            current = None
            continue
        blanks = 0
        current["lines"].append(line.strip())
    if current:
        out.append(current)
    return [t for t in out if t["lines"]]


def pdf_text(path: Path) -> str:
    import pypdf

    reader = pypdf.PdfReader(str(path))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def write_tables(tables: list[dict], out_dir: Path, source: str) -> int:
    import yaml

    out_dir.mkdir(parents=True, exist_ok=True)
    for t in tables:
        doc = {"id": t["id"], "name": t["name"], "source": source, "lines": t["lines"]}
        path = out_dir / f"{t['id']}_{slug(t['name'])}.yaml"
        path.write_text(
            yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000),
            encoding="utf-8",
        )
    return len(tables)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    pdf, out_dir = Path(argv[1]), Path(argv[2])
    tables = find_tables(pdf_text(pdf))
    n = write_tables(tables, out_dir, source=pdf.name)
    print(f"extracted {n} tables from {pdf.name} into {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Run to verify the tests pass**

Run: `python -m pytest tests/test_extract.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.7-beta\n' > VERSION
git add tools/__init__.py tools/extract.py tests/test_extract.py VERSION
git commit -m "Extractor: slice OSRIC PDFs into raw per-table YAML"
```

---

### Task 6: Extract the corpus and gate it

**Files:**
- Create: `data/tables/*.yaml` (committed)
- Test: `tests/test_corpus.py`

**Interfaces:**
- Consumes: `tools.extract.find_tables`, `pdf_text`, `write_tables`.
- Produces: the committed corpus under `data/tables/`.

- [ ] **Step 1: Run the extractor over both books**

```bash
cd "D:/Tenshin Arts/Sanctuary"
python tools/extract.py "C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf" data/tables
python tools/extract.py "C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf" data/tables
ls data/tables | wc -l
```
Expected: a count in the low hundreds. Record the real number — it goes in the gate line.

- [ ] **Step 2: Write the round-trip and spot-check tests**

Round-trip catches a hand-edit diverging from the book. Spot-check catches a parse that is correctly *shaped* and wrong — round-trip alone passes cheerfully on a uniformly mis-parsed corpus.

Create `tests/test_corpus.py`:

```python
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "data" / "tables"


def load(table_id: str) -> dict:
    matches = list(TABLES.glob(f"{table_id}_*.yaml"))
    assert matches, f"no committed table {table_id}"
    return yaml.safe_load(matches[0].read_text(encoding="utf-8"))


def test_corpus_is_committed_and_substantial():
    files = list(TABLES.glob("*.yaml"))
    assert len(files) > 150, f"only {len(files)} tables extracted"


def test_no_ligatures_survived():
    bad = []
    for p in TABLES.glob("*.yaml"):
        text = p.read_text(encoding="utf-8")
        if any(chr(c) in text for c in range(0xFB00, 0xFB07)):
            bad.append(p.name)
    assert bad == [], f"ligatures survived into: {bad}"


def test_spot_check_fighter_advancement():
    t = load("1.3.4.4a")
    assert "FIGHTER" in t["name"].upper()
    joined = " | ".join(t["lines"])
    assert "9 250,000 9" in joined, "fighter L9 should need 250,000 XP"


def test_spot_check_fighter_to_hit():
    t = load("1.3.4.4c")
    rows = [ln for ln in t["lines"] if ln.startswith("1 ")]
    assert rows, "no level-1 row in the fighter to-hit table"
    # Level 1 needs 10 to hit AC 10 - the first number after the level.
    assert rows[0].split()[1] == "10"


def test_spot_check_monster_to_hit_is_from_the_gm_guide():
    t = load("2.1.2a")
    assert "Gamemaster" in t["source"]
    assert any(ln.startswith("8-9+") or ln.startswith("8\u20139+") for ln in t["lines"])


def test_every_table_has_an_id_name_and_lines():
    for p in TABLES.glob("*.yaml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert doc["id"], p.name
        assert doc["name"], p.name
        assert doc["lines"], p.name
```

- [ ] **Step 3: Run the tests**

Run: `python -m pytest tests/test_corpus.py -q`
Expected: 6 passed. If a spot-check fails, the extractor's block boundaries are wrong — fix `_PROSE`/`_HEADER` in `tools/extract.py`, re-extract, and re-run. Do **not** hand-edit the YAML.

- [ ] **Step 4: Add the round-trip test**

Append to `tests/test_corpus.py`:

```python
def test_extraction_round_trips():
    """Re-running the extractor reproduces the committed corpus exactly."""
    import tempfile

    from tools.extract import find_tables, pdf_text, write_tables

    pdfs = {
        "OSRIC-3.0-Player-Guide-FINAL.v.7.pdf": Path(
            "C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"),
        "OSRIC_3.0_Gamemaster_Guide.pdf": Path(
            "C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf"),
    }
    for p in pdfs.values():
        if not p.exists():
            import pytest
            pytest.skip(f"source PDF not present: {p}")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for name, p in pdfs.items():
            write_tables(find_tables(pdf_text(p)), out, source=name)
        fresh = {q.name: q.read_text(encoding="utf-8") for q in out.glob("*.yaml")}

    committed = {q.name: q.read_text(encoding="utf-8") for q in TABLES.glob("*.yaml")}
    assert set(fresh) == set(committed), (
        f"only fresh: {sorted(set(fresh) - set(committed))[:5]}; "
        f"only committed: {sorted(set(committed) - set(fresh))[:5]}")
    differing = [k for k in committed if committed[k] != fresh[k]]
    assert differing == [], f"committed tables diverge from the book: {differing[:5]}"
```

- [ ] **Step 5: Run and commit**

```bash
python -m pytest tests/test_corpus.py -q
printf 'v0.0.8-beta\n' > VERSION
git add data/tables tests/test_corpus.py VERSION
git commit -m "Corpus: extract OSRIC tables, gate with round-trip and spot-checks"
```
Expected: 7 passed

---

### Task 7: The table loader

**Files:**
- Create: `sanctuary/tables.py`
- Test: `tests/test_tables.py`

**Interfaces:**
- Consumes: the committed `data/tables/*.yaml`.
- Produces:
  - `load(table_id: str) -> dict` — the raw `{"id","name","source","lines"}` document
  - `rows(table_id: str) -> list[list[str]]` — whitespace-split data rows, header lines dropped
  - `in_range(spec: str, value: float) -> bool` — `"4–5"`, `"18.01–18.50"`, `"19"`, `"19+"`, `"<1-1"`
  - `ability_row(table_id: str, score: float) -> list[str]` — the row whose first cell contains `score`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tables.py`:

```python
import pytest

from sanctuary import tables


def test_load_returns_the_document():
    t = tables.load("1.1.2a")
    assert "STRENGTH" in t["name"].upper()
    assert t["lines"]


def test_load_unknown_table_raises():
    with pytest.raises(KeyError):
        tables.load("9.9.9z")


def test_a_split_table_refuses_to_load_as_one_and_names_its_parts():
    """1.4.2.3a is three files. Silently returning one of them is how 26
    tables would vanish from a corpus that still round-trips."""
    with pytest.raises(LookupError) as e:
        tables.load("1.4.2.3a")
    assert "1.4.2.3a_general_equipment.yaml" in str(e.value)


def test_parts_returns_every_file_for_a_split_table():
    docs = tables.parts("1.4.2.3a")
    assert len(docs) == 3
    assert all(d["id"] == "1.4.2.3a" for d in docs)
    assert {d["name"] for d in docs} == {
        "GENERAL  EQUIPMENT", "CONTAINERS", "MOUNTS AND PACK ANIMALS"}


def test_parts_of_a_single_file_table_is_a_one_item_list():
    assert len(tables.parts("1.3.4.4a")) == 1


def test_no_committed_table_is_unreachable():
    """Every file in data/tables must be reachable through the index - the
    guard against an id-keying scheme that drops files on the floor."""
    from pathlib import Path as _P
    reachable = {p for group in tables._index().values() for p in group}
    on_disk = set(_P(tables._DIR).glob("*.yaml"))
    assert reachable == on_disk, f"unreachable: {sorted(on_disk - reachable)}"


def test_in_range_handles_single_values():
    assert tables.in_range("3", 3)
    assert not tables.in_range("3", 4)


def test_in_range_handles_en_dash_ranges():
    assert tables.in_range("4\u20135", 4)
    assert tables.in_range("4\u20135", 5)
    assert not tables.in_range("4\u20135", 6)


def test_in_range_handles_hyphen_ranges():
    assert tables.in_range("4-5", 5)


def test_in_range_handles_exceptional_strength():
    assert tables.in_range("18.01\u201318.50", 18.25)
    assert not tables.in_range("18.01\u201318.50", 18.60)
    assert tables.in_range("18.51\u201318.75", 18.75)


def test_in_range_handles_open_ended():
    assert tables.in_range("19+", 25)
    assert tables.in_range("19+", 19)
    assert not tables.in_range("19+", 18)


def test_ability_row_finds_the_strength_row():
    row = tables.ability_row("1.1.2a", 18)
    assert row[0].startswith("18")
    # STRENGTH  TO HIT  DAMAGE  ENCUMBRANCE ...
    assert row[1] == "+1"
    assert row[2] == "+2"


def test_ability_row_finds_an_exceptional_strength_row():
    row = tables.ability_row("1.1.2a", 18.60)
    assert row[0].replace("\u2013", "-") == "18.51-18.75"
    assert row[1] == "+2"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_tables.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanctuary.tables'`

- [ ] **Step 3: Implement the loader**

Create `sanctuary/tables.py`:

```python
"""Typed access to the committed OSRIC table corpus.

The extractor is dumb on purpose: it stores each table's lines as printed.
Interpretation lives here, so one table's quirks cannot break another's.
"""
import re
from functools import lru_cache
from pathlib import Path

import yaml

_DIR = Path(__file__).resolve().parent.parent / "data" / "tables"
_DASH = re.compile(r"[\u2013\u2014-]")


@lru_cache(maxsize=None)
def _index() -> dict[str, tuple[Path, ...]]:
    """id -> every file carrying it, in filename order.

    ⚠ 20 ids have MORE THAN ONE file - a table split across pages keeps its id
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

    Handles `3`, `4-5`, `4\u20135`, `18.01\u201318.50`, `19+`, and `<1-1`.
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_tables.py -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.9-beta\n' > VERSION
git add sanctuary/tables.py tests/test_tables.py VERSION
git commit -m "Tables: typed lookups over the raw corpus"
```

---

### Task 8: Ability score generation — the four modes

**Files:**
- Create: `sanctuary/character.py`
- Test: `tests/test_character.py`

**Interfaces:**
- Consumes: `sanctuary.dice.Dice`, `sanctuary.tables`.
- Produces:
  - `ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")`
  - `GEN_MODES = ("hardest", "difficult", "normal", "flexible")`
  - `roll_abilities(d: Dice, mode: str) -> dict[str, int]` — in-order modes assign directly; arrange modes return the same dict with scores in roll order for the player to rearrange
  - `arrangeable(mode: str) -> bool`

- [ ] **Step 1: Write the failing test**

Create `tests/test_character.py`:

```python
import pytest

from sanctuary.character import ABILITIES, GEN_MODES, arrangeable, roll_abilities
from sanctuary.dice import Dice


def test_all_four_modes_exist():
    assert GEN_MODES == ("hardest", "difficult", "normal", "flexible")


def test_hardest_rolls_3d6_in_order():
    d = Dice(seed=1)
    scores = roll_abilities(d, "hardest")
    assert list(scores) == list(ABILITIES)
    assert all(3 <= v <= 18 for v in scores.values())
    assert [r.expr for r in d.log] == ["3d6"] * 6


def test_normal_rolls_4d6_drop_lowest():
    d = Dice(seed=2)
    scores = roll_abilities(d, "normal")
    assert all(3 <= v <= 18 for v in scores.values())
    assert [r.expr for r in d.log] == ["4d6d1"] * 6


def test_difficult_uses_3d6_and_is_arrangeable():
    d = Dice(seed=3)
    roll_abilities(d, "difficult")
    assert [r.expr for r in d.log] == ["3d6"] * 6
    assert arrangeable("difficult")
    assert not arrangeable("hardest")


def test_flexible_uses_4d6_and_is_arrangeable():
    d = Dice(seed=4)
    roll_abilities(d, "flexible")
    assert [r.expr for r in d.log] == ["4d6d1"] * 6
    assert arrangeable("flexible")
    assert not arrangeable("normal")


def test_every_roll_carries_its_ability_as_the_reason():
    d = Dice(seed=5)
    roll_abilities(d, "normal")
    assert [r.reason for r in d.log] == list(ABILITIES)


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        roll_abilities(Dice(seed=6), "easiest")


def test_generation_is_reproducible_from_the_seed():
    assert roll_abilities(Dice(seed=99), "normal") == roll_abilities(Dice(seed=99), "normal")
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sanctuary.character'`

- [ ] **Step 3: Implement**

Create `sanctuary/character.py`:

```python
"""Character generation: abilities, ancestry, class, derived statistics.

Every random step rolls through `Dice`, so a character is fully reproducible
from (seed, choices). That is also what makes a reroll honest rather than a
slot machine.
"""
from sanctuary.dice import Dice

ABILITIES = ("strength", "dexterity", "constitution",
             "intelligence", "wisdom", "charisma")

# OSRIC 3.0 names four generation modes. This is a player-facing choice,
# not a configuration value.
GEN_MODES = ("hardest", "difficult", "normal", "flexible")

_MODE_EXPR = {
    "hardest": "3d6",     # 3d6 in order
    "difficult": "3d6",   # 3d6, arrange to taste
    "normal": "4d6d1",    # 4d6 drop lowest, in order
    "flexible": "4d6d1",  # 4d6 drop lowest, arrange
}
_ARRANGEABLE = {"difficult", "flexible"}


def arrangeable(mode: str) -> bool:
    """May the player rearrange the rolled scores across abilities?"""
    return mode in _ARRANGEABLE


def roll_abilities(d: Dice, mode: str) -> dict[str, int]:
    """Roll the six ability scores. Arrange modes return them in roll order;
    rearranging is the player's move, made later against this result."""
    if mode not in GEN_MODES:
        raise ValueError(f"unknown generation mode: {mode!r}")
    expr = _MODE_EXPR[mode]
    return {name: d.roll(expr, reason=name).total for name in ABILITIES}
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_character.py -q`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.10-beta\n' > VERSION
git add sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: the four OSRIC ability generation modes"
```

---

### Task 9: Exceptional Strength

**Files:**
- Modify: `sanctuary/character.py`
- Modify: `tests/test_character.py`

**Interfaces:**
- Consumes: `roll_abilities`, `Dice`, `tables.ability_row`.
- Produces: `EXCEPTIONAL_CLASSES = ("fighter", "paladin", "ranger")`; `roll_exceptional_strength(d: Dice, score: int, cls: str) -> float` returning `18.xx`, `19.0`, or the score unchanged.

⚠ A d100 of `00` (100) means Strength **19**, not 18.00. Only fighters, paladins and rangers roll at all — for everyone else an 18 is a plain 18.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_character.py`:

```python
from sanctuary.character import EXCEPTIONAL_CLASSES, roll_exceptional_strength


def test_only_fighters_paladins_and_rangers_roll():
    assert set(EXCEPTIONAL_CLASSES) == {"fighter", "paladin", "ranger"}


def test_non_eligible_class_keeps_a_plain_18():
    d = Dice(seed=1)
    assert roll_exceptional_strength(d, 18, "thief") == 18
    assert d.log == ()


def test_score_below_18_never_rolls():
    d = Dice(seed=1)
    assert roll_exceptional_strength(d, 17, "fighter") == 17
    assert d.log == ()


def test_eligible_18_rolls_d100_and_returns_a_decimal():
    d = Dice(seed=1)
    result = roll_exceptional_strength(d, 18, "fighter")
    assert d.log[0].expr == "1d100"
    assert 18.01 <= result <= 19.0


def test_percentile_100_means_nineteen():
    from sanctuary.dice import Roll

    class FixedRoller:
        """Duck-typed stand-in - a percentile of 00 (100) must give 19."""
        log = ()

        def roll(self, expr, reason="", mods=0, **tags):
            return Roll(index=0, expr=expr, faces=(100,), kept=(100,),
                        mods=0, total=100, reason=reason, tags=tags)

    assert roll_exceptional_strength(FixedRoller(), 18, "fighter") == 19.0


def test_exceptional_strength_reads_the_right_table_row():
    from sanctuary import tables
    # 18.51-18.75 gives +2 to hit, +3 damage per Table 1.1.2A.
    row = tables.ability_row("1.1.2a", 18.60)
    assert row[1] == "+2" and row[2] == "+3"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ImportError: cannot import name 'EXCEPTIONAL_CLASSES'`

- [ ] **Step 3: Implement**

Append to `sanctuary/character.py`:

```python
# Only these classes roll percentile strength. For everyone else an 18 is an 18.
EXCEPTIONAL_CLASSES = ("fighter", "paladin", "ranger")


def roll_exceptional_strength(d: Dice, score: int, cls: str) -> float:
    """Percentile strength for an eligible 18.

    Returns 18.01-18.99 as a decimal, or 19.0 on a percentile roll of 00 (100).
    Returns `score` unchanged when the character is not eligible - and rolls no
    dice at all in that case, so the log stays honest.
    """
    if int(score) != 18 or cls not in EXCEPTIONAL_CLASSES:
        return score
    pct = d.roll("1d100", reason="exceptional strength", kind="chargen").total
    if pct >= 100:
        return 19.0
    return round(18 + pct / 100, 2)
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_character.py -q`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.11-beta\n' > VERSION
git add sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: exceptional Strength for fighters, paladins and rangers"
```

---

### Task 10: Ancestry data and eligibility

**Files:**
- Create: `data/ancestries.yaml`
- Modify: `sanctuary/character.py`, `tests/test_character.py`

**Interfaces:**
- Consumes: `tables.load("1.2.0a")`.
- Produces: `ANCESTRIES` (7 names); `ancestry(name) -> dict`; `meets_ancestry_minimums(scores: dict, name: str) -> bool`; `apply_ancestry(scores: dict, name: str) -> dict`.

Ancestry minimums come from Table 1.2.0A. Bonuses and adjustments are transcribed into `data/ancestries.yaml` because only three ancestries (dwarf, gnome, halfling) have bonus *tables*; the rest are prose, which the licence does not permit us to reproduce and which we do not need — only the mechanics.

- [ ] **Step 1: Transcribe the ancestry data**

Create `data/ancestries.yaml`. Read Table 1.2.0A from `data/tables/1.2.0a_*.yaml` and the ancestry sections of the Player Guide (§1.2.1–1.2.7) for the adjustments, then fill in the real values. The structure:

```yaml
dwarf:
  ability_adjustments: {constitution: 1, charisma: -1}
  minimums: {strength: 8, constitution: 12}
  maximums: {dexterity: 17}
  infravision_ft: 60
  allowed_classes: [assassin, cleric, fighter, thief]
  level_limits: {cleric: 8, fighter: 9, thief: 12, assassin: 9}
elf:
  ability_adjustments: {dexterity: 1, constitution: -1}
  minimums: {intelligence: 8, dexterity: 7}
  maximums: {}
  infravision_ft: 60
  allowed_classes: [assassin, cleric, fighter, magic-user, thief]
  level_limits: {cleric: 7, fighter: 7, magic-user: 11, thief: 0, assassin: 10}
gnome:
  # Same shape as dwarf and elf above. Values from Player Guide §1.2.3 and
  # Table 1.2.0A; the Stalwart bonuses are Table 1.2.3.2A.
  ability_adjustments: {}
  minimums: {}
  maximums: {}
  infravision_ft: 60
  allowed_classes: []
  level_limits: {}
half-elf:   # §1.2.4 - no bonus table, adjustments are in the prose
  ability_adjustments: {}
  minimums: {}
  maximums: {}
  infravision_ft: 60
  allowed_classes: []
  level_limits: {}
halfling:   # §1.2.5, Stalwart bonuses Table 1.2.5.2A
  ability_adjustments: {}
  minimums: {}
  maximums: {}
  infravision_ft: 60
  allowed_classes: []
  level_limits: {}
half-orc:   # §1.2.6 - no bonus table
  ability_adjustments: {}
  minimums: {}
  maximums: {}
  infravision_ft: 60
  allowed_classes: []
  level_limits: {}
human:
  ability_adjustments: {}
  minimums: {}
  maximums: {}
  infravision_ft: 0
  allowed_classes: [assassin, cleric, druid, fighter, illusionist, magic-user, monk, paladin, ranger, thief]
  level_limits: {}
```

⚠ `level_limits` of `0` means unlimited. Humans have no limits at all, which is the trade for having no adjustments — do not model this as a missing key on some ancestries and a zero on others; be consistent.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_character.py`:

```python
from sanctuary.character import (ANCESTRIES, ancestry, apply_ancestry,
                                 meets_ancestry_minimums)


def test_seven_ancestries():
    assert set(ANCESTRIES) == {
        "dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human"}


def test_every_ancestry_has_the_full_shape():
    for name in ANCESTRIES:
        a = ancestry(name)
        for key in ("ability_adjustments", "minimums", "maximums",
                    "allowed_classes", "level_limits"):
            assert key in a, f"{name} missing {key}"
        assert a["allowed_classes"], f"{name} allows no classes"


def test_humans_have_no_adjustments_and_no_limits():
    a = ancestry("human")
    assert a["ability_adjustments"] == {}
    assert a["level_limits"] == {}
    assert len(a["allowed_classes"]) == 10


def test_apply_ancestry_adjusts_scores():
    scores = {k: 10 for k in ABILITIES}
    adjusted = apply_ancestry(scores, "dwarf")
    assert adjusted["constitution"] == 11
    assert adjusted["charisma"] == 9
    assert scores["constitution"] == 10, "apply_ancestry must not mutate its input"


def test_minimums_are_checked_after_adjustment():
    low = {k: 6 for k in ABILITIES}
    assert not meets_ancestry_minimums(low, "dwarf")
    ok = {k: 14 for k in ABILITIES}
    assert meets_ancestry_minimums(ok, "dwarf")


def test_humans_accept_any_scores():
    assert meets_ancestry_minimums({k: 3 for k in ABILITIES}, "human")
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ImportError: cannot import name 'ANCESTRIES'`

- [ ] **Step 4: Implement**

Append to `sanctuary/character.py`:

```python
from functools import lru_cache
from pathlib import Path

import yaml

_DATA = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def _ancestries() -> dict:
    return yaml.safe_load((_DATA / "ancestries.yaml").read_text(encoding="utf-8"))


ANCESTRIES = ("dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human")


def ancestry(name: str) -> dict:
    a = _ancestries().get(name)
    if a is None:
        raise KeyError(f"unknown ancestry: {name!r}")
    return a


def apply_ancestry(scores: dict, name: str) -> dict:
    """Ancestral adjustments applied to a copy of `scores`."""
    out = dict(scores)
    for k, delta in ancestry(name)["ability_adjustments"].items():
        out[k] = out.get(k, 0) + delta
    return out


def meets_ancestry_minimums(scores: dict, name: str) -> bool:
    """Table 1.2.0A minimums, checked AFTER ancestral adjustments."""
    a = ancestry(name)
    if any(scores.get(k, 0) < v for k, v in a["minimums"].items()):
        return False
    return not any(scores.get(k, 0) > v for k, v in a["maximums"].items())
```

- [ ] **Step 5: Run and commit**

```bash
python -m pytest tests/test_character.py -q
printf 'v0.0.12-beta\n' > VERSION
git add data/ancestries.yaml sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: seven ancestries, adjustments, minimums and class access"
```
Expected: 20 passed

---

### Task 11: Classes — eligibility, hit dice and hit points

**Files:**
- Create: `data/classes.yaml`
- Modify: `sanctuary/character.py`, `tests/test_character.py`

**Interfaces:**
- Consumes: `ancestry`, `tables`, `Dice`.
- Produces: `CLASSES` (11 names); `game_class(name) -> dict`; `eligible_classes(scores: dict, ancestry_name: str) -> list[str]`; `roll_hit_points(d: Dice, cls: str, level: int, con_bonus: int) -> int`.

- [ ] **Step 1: Transcribe class data**

Create `data/classes.yaml`, one entry per class, reading the requirements from each class's section and the hit die from its level-advancement table (`1.3.N.4a`). Structure:

```yaml
fighter:
  hit_die: d10
  prime_requisites: [strength]
  minimums: {strength: 9, constitution: 7}
  advancement_table: "1.3.4.4a"
  saving_throw_table: "1.3.4.4b"
  to_hit_table: "1.3.4.4c"
  fixed_hp_after_level_9: 3
  spell_list: null
cleric:
  hit_die: d8
  prime_requisites: [wisdom]
  minimums: {wisdom: 9}
  advancement_table: "1.3.2.4a"
  saving_throw_table: "1.3.2.4b"
  to_hit_table: "1.3.2.4c"
  fixed_hp_after_level_9: 2
  spell_list: clerical
```

All eleven: assassin, cleric, druid, fighter, illusionist, magic-user, monk, paladin, ranger, thief. Multi- and dual-classing are Task 13, not entries here.

⚠ `fixed_hp_after_level_9` is the flat per-level hit points once hit dice stop. The fighter's own table says `+3` and notes Constitution adjustments also stop. Do not apply a Constitution bonus past that point.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_character.py`:

```python
from sanctuary.character import (CLASSES, eligible_classes, game_class,
                                 roll_hit_points)


def test_eleven_classes():
    assert set(CLASSES) == {
        "assassin", "cleric", "druid", "fighter", "illusionist", "magic-user",
        "monk", "paladin", "ranger", "thief"}


def test_every_class_names_its_three_tables():
    for name in CLASSES:
        c = game_class(name)
        for key in ("advancement_table", "saving_throw_table", "to_hit_table"):
            from sanctuary import tables
            tables.load(c[key])  # raises if the table is not in the corpus


def test_eligibility_respects_class_minimums():
    weak = {k: 6 for k in ABILITIES}
    assert "fighter" not in eligible_classes(weak, "human")
    strong = {k: 16 for k in ABILITIES}
    assert "fighter" in eligible_classes(strong, "human")


def test_eligibility_respects_ancestry_class_access():
    strong = {k: 16 for k in ABILITIES}
    assert "paladin" not in eligible_classes(strong, "dwarf")
    assert "paladin" in eligible_classes(strong, "human")


def test_hit_points_use_the_class_hit_die():
    d = Dice(seed=1)
    roll_hit_points(d, "fighter", level=1, con_bonus=0)
    assert d.log[0].expr == "1d10"
    d2 = Dice(seed=1)
    roll_hit_points(d2, "magic-user", level=1, con_bonus=0)
    assert d2.log[0].expr == "1d4"


def test_constitution_bonus_applies_per_level():
    d = Dice(seed=3)
    hp = roll_hit_points(d, "fighter", level=3, con_bonus=2)
    rolled = sum(r.total for r in d.log)
    assert hp == rolled + 6


def test_hit_points_never_drop_below_one_per_level():
    d = Dice(seed=4)
    assert roll_hit_points(d, "magic-user", level=2, con_bonus=-3) >= 2
```

- [ ] **Step 3: Run to verify it fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ImportError: cannot import name 'CLASSES'`

- [ ] **Step 4: Implement**

Append to `sanctuary/character.py`:

```python
@lru_cache(maxsize=1)
def _classes() -> dict:
    return yaml.safe_load((_DATA / "classes.yaml").read_text(encoding="utf-8"))


CLASSES = ("assassin", "cleric", "druid", "fighter", "illusionist",
           "magic-user", "monk", "paladin", "ranger", "thief")


def game_class(name: str) -> dict:
    c = _classes().get(name)
    if c is None:
        raise KeyError(f"unknown class: {name!r}")
    return c


def eligible_classes(scores: dict, ancestry_name: str) -> list[str]:
    """Classes this character may take: allowed by ancestry AND meeting the
    class's own ability minimums."""
    allowed = set(ancestry(ancestry_name)["allowed_classes"])
    out = []
    for name in CLASSES:
        if name not in allowed:
            continue
        if any(scores.get(k, 0) < v for k, v in game_class(name)["minimums"].items()):
            continue
        out.append(name)
    return out


def roll_hit_points(d: Dice, cls: str, level: int, con_bonus: int) -> int:
    """Hit points for `level` levels of `cls`.

    Past the level where hit dice stop, the class gains flat hit points and
    Constitution adjustments no longer apply - the fighter's table says so
    explicitly and the same shape holds for every class.
    """
    c = game_class(cls)
    die = c["hit_die"]
    cap = 9
    total = 0
    for lvl in range(1, int(level) + 1):
        if lvl <= cap:
            rolled = d.roll(f"1{die}", reason=f"{cls} hp level {lvl}", kind="chargen").total
            total += max(1, rolled + con_bonus)
        else:
            total += c["fixed_hp_after_level_9"]
    return total
```

- [ ] **Step 5: Run and commit**

```bash
python -m pytest tests/test_character.py -q
printf 'v0.0.13-beta\n' > VERSION
git add data/classes.yaml sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: eleven classes, eligibility and hit points"
```
Expected: 27 passed

---

### Task 12: The derived block

**Files:**
- Modify: `sanctuary/character.py`, `tests/test_character.py`

**Interfaces:**
- Consumes: `tables.ability_row`, `tables.rows`, `game_class`.
- Produces: `ability_modifiers(scores: dict) -> dict`; `saving_throws(cls: str, level: int) -> dict`; `to_hit_target(cls: str, level: int, armour_class: int) -> int`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_character.py`:

```python
from sanctuary.character import ability_modifiers, saving_throws, to_hit_target


def test_strength_modifiers_come_from_the_table():
    mods = ability_modifiers({**{k: 10 for k in ABILITIES}, "strength": 18})
    assert mods["hit"] == 1
    assert mods["damage"] == 2


def test_exceptional_strength_modifiers():
    mods = ability_modifiers({**{k: 10 for k in ABILITIES}, "strength": 18.60})
    assert mods["hit"] == 2
    assert mods["damage"] == 3


def test_average_scores_give_no_modifiers():
    mods = ability_modifiers({k: 10 for k in ABILITIES})
    assert mods["hit"] == 0
    assert mods["damage"] == 0


def test_fighter_saving_throws_at_level_one():
    saves = saving_throws("fighter", 1)
    # Table 1.3.4.4B, row 1-2: 16 / 17 / 14 / 15 / 17
    assert saves["aimed_magic_items"] == 16
    assert saves["breath_weapons"] == 17
    assert saves["death_paralysis_poison"] == 14
    assert saves["petrifaction_polymorph"] == 15
    assert saves["spells"] == 17


def test_fighter_saving_throws_improve_with_level():
    assert saving_throws("fighter", 13)["spells"] < saving_throws("fighter", 1)["spells"]


def test_fighter_to_hit_targets():
    # Table 1.3.4.4C: level 1 needs 10 vs AC 10, and 20 vs AC 1.
    assert to_hit_target("fighter", 1, 10) == 10
    assert to_hit_target("fighter", 1, 1) == 19


def test_higher_level_hits_more_easily():
    assert to_hit_target("fighter", 9, 4) < to_hit_target("fighter", 1, 4)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ImportError: cannot import name 'ability_modifiers'`

- [ ] **Step 3: Implement**

Append to `sanctuary/character.py`:

```python
from sanctuary import tables

SAVE_CATEGORIES = ("aimed_magic_items", "breath_weapons",
                   "death_paralysis_poison", "petrifaction_polymorph", "spells")

# Descending armour classes, as printed across the to-hit tables.
_AC_COLUMNS = list(range(10, -11, -1))


def _int(cell: str) -> int:
    return int(str(cell).replace("+", "").replace("\u2212", "-"))


def ability_modifiers(scores: dict) -> dict:
    """Combat-relevant modifiers derived from the ability tables."""
    strength_row = tables.ability_row("1.1.2a", scores["strength"])
    return {
        "hit": _int(strength_row[1]),
        "damage": _int(strength_row[2]),
        "encumbrance_lbs": _int(strength_row[3]),
    }


def saving_throws(cls: str, level: int) -> dict:
    """The five saving-throw targets for a class at a level."""
    table_id = game_class(cls)["saving_throw_table"]
    for row in tables.rows(table_id):
        if tables.in_range(row[0], level) and len(row) >= 6:
            return dict(zip(SAVE_CATEGORIES, (_int(c) for c in row[1:6])))
    raise LookupError(f"no saving-throw row for {cls} level {level}")


def to_hit_target(cls: str, level: int, armour_class: int) -> int:
    """The d20 result needed to hit `armour_class`.

    A natural 1 is NOT an automatic miss and a natural 20 is NOT an automatic
    hit - that is OSRIC's stated rule, not a bug. Comparison against this
    target is the whole of it.
    """
    table_id = game_class(cls)["to_hit_table"]
    col = _AC_COLUMNS.index(int(armour_class))
    for row in tables.rows(table_id):
        if tables.in_range(row[0], level):
            return _int(row[1 + col])
    raise LookupError(f"no to-hit row for {cls} level {level}")
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_character.py -q`
Expected: 34 passed. If `to_hit_target` misreads a column, print `tables.rows(...)` for the table and check whether the extractor kept the two header lines (the AC row and the bracketed ascending-AC row) — both must be dropped by the `^\s*[<\d]` filter, and the bracketed line starts with `[`, so it is.

- [ ] **Step 5: Commit**

```bash
printf 'v0.0.14-beta\n' > VERSION
git add sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: derived modifiers, saving throws and to-hit targets"
```

---

### Task 13: Assembling a character, multi-class and dual-class

**Files:**
- Modify: `sanctuary/character.py`, `tests/test_character.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `Character` frozen dataclass with `name, ancestry, classes (tuple[str, ...]), levels (dict[str,int]), scores, hit_points, armour_class, saves, seed`; `generate(seed, mode, ancestry_name, class_names, name="") -> Character`; `is_legal_multiclass(ancestry_name, class_names) -> bool`.

⚠ Multi-classing splits hit dice between classes and is restricted by ancestry; dual-classing is human-only and sequential. Model them differently — a tuple of concurrent classes for multi, a sequence with a switch level for dual.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_character.py`:

```python
from sanctuary.character import (SAVE_CATEGORIES, Character, generate,
                                 is_legal_multiclass)


def test_generate_produces_a_complete_character():
    c = generate(seed=1234, mode="normal", ancestry_name="human",
                 class_names=("fighter",), name="Ilse")
    assert isinstance(c, Character)
    assert c.name == "Ilse"
    assert c.ancestry == "human"
    assert c.classes == ("fighter",)
    assert c.levels == {"fighter": 1}
    assert set(c.scores) == set(ABILITIES)
    assert c.hit_points >= 1
    assert set(c.saves) == set(SAVE_CATEGORIES)
    assert c.seed == 1234


def test_generation_is_reproducible():
    a = generate(seed=77, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=77, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert a == b


def test_different_seeds_give_different_characters():
    a = generate(seed=1, mode="normal", ancestry_name="human", class_names=("fighter",))
    b = generate(seed=2, mode="normal", ancestry_name="human", class_names=("fighter",))
    assert a.scores != b.scores or a.hit_points != b.hit_points


def test_humans_may_not_multiclass():
    assert not is_legal_multiclass("human", ("fighter", "magic-user"))


def test_elves_may_multiclass_fighter_magic_user():
    assert is_legal_multiclass("elf", ("fighter", "magic-user"))


def test_multiclass_must_be_allowed_by_ancestry():
    assert not is_legal_multiclass("dwarf", ("fighter", "magic-user"))


def test_single_class_is_always_legal_for_an_allowed_class():
    assert is_legal_multiclass("human", ("fighter",))


def test_generate_rejects_an_illegal_combination():
    with pytest.raises(ValueError):
        generate(seed=1, mode="normal", ancestry_name="human",
                 class_names=("fighter", "magic-user"))
```

- [ ] **Step 2: Add multiclass data**

Add a `multiclass_combinations` key per ancestry in `data/ancestries.yaml`, transcribed from §1.3.11. Humans get `[]`. For example:

```yaml
elf:
  multiclass_combinations:
    - [fighter, magic-user]
    - [fighter, thief]
    - [magic-user, thief]
    - [fighter, magic-user, thief]
```

- [ ] **Step 3: Run to verify the test fails**

Run: `python -m pytest tests/test_character.py -q`
Expected: FAIL — `ImportError: cannot import name 'Character'`

- [ ] **Step 4: Implement**

Append to `sanctuary/character.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Character:
    name: str
    ancestry: str
    classes: tuple[str, ...]
    levels: dict
    scores: dict
    hit_points: int
    armour_class: int
    saves: dict
    modifiers: dict
    seed: int
    log: tuple = field(default=(), compare=False)


def is_legal_multiclass(ancestry_name: str, class_names) -> bool:
    """One class is always legal if the ancestry allows it. More than one must
    appear in that ancestry's multiclass combinations - humans have none, and
    dual-classing is a different mechanism entirely."""
    names = list(class_names)
    allowed = set(ancestry(ancestry_name)["allowed_classes"])
    if not set(names) <= allowed:
        return False
    if len(names) == 1:
        return True
    combos = [sorted(c) for c in ancestry(ancestry_name).get("multiclass_combinations", [])]
    return sorted(names) in combos


def generate(seed: int, mode: str, ancestry_name: str, class_names,
             name: str = "") -> Character:
    """Roll a complete first-level character. Fully reproducible from
    (seed, mode, ancestry, classes)."""
    class_names = tuple(class_names)
    if not is_legal_multiclass(ancestry_name, class_names):
        raise ValueError(
            f"{ancestry_name} may not be {'/'.join(class_names)}")

    d = Dice(seed=seed)
    scores = apply_ancestry(roll_abilities(d, mode), ancestry_name)
    primary = class_names[0]
    scores["strength"] = roll_exceptional_strength(d, scores["strength"], primary)

    mods = ability_modifiers(scores)
    con_bonus = 0  # Constitution hp adjustment lands with Chapter 3.
    # Multi-class hit points average across the classes' dice.
    per_class = [roll_hit_points(d, c, 1, con_bonus) for c in class_names]
    hit_points = max(1, sum(per_class) // len(per_class))

    return Character(
        name=name,
        ancestry=ancestry_name,
        classes=class_names,
        levels={c: 1 for c in class_names},
        scores=scores,
        hit_points=hit_points,
        armour_class=10,  # armour lands with Chapter 3.
        saves=saving_throws(primary, 1),
        modifiers=mods,
        seed=seed,
        log=d.log,
    )
```

- [ ] **Step 5: Run and commit**

```bash
python -m pytest tests/ -q
printf 'v0.0.15-beta\n' > VERSION
git add data/ancestries.yaml sanctuary/character.py tests/test_character.py VERSION
git commit -m "Chargen: assemble a character, multi-class legality"
```
Expected: 42 passed

---

### Task 14: The server and the client — licence, house chrome, character sheet, dice tray

**Files:**
- Create: `app.py`, `static/index.html`, `static/app.css`, `static/app.js`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `sanctuary.character.generate`, `tenshin_version`, `tenshin_gate`, `tenshin_feedback`.
- Produces: routes `GET /`, `GET /version`, `GET /licence`, `POST /api/character`, `POST /api/report`, `GET /live/embed`; and `selfcheck() -> str`; plus the client the gate reads.

⚠ Server and client are **one task** because neither is independently testable without the other — `GET /` and `selfcheck()` both read `static/index.html`. Write both, then run the suite once at the end.

- [ ] **Step 1: Write the failing test**

Create `tests/test_app.py`:

```python
from fastapi.testclient import TestClient

import app as sanctuary_app

NOTICE = ("Sanctuary is an independent product published under the OSRIC 3.0 "
          "Third-Party License and is not affiliated with Mythmere Games LLC.")

client = TestClient(sanctuary_app.app)


def test_version_is_plain_text():
    r = client.get("/version")
    assert r.status_code == 200
    assert r.text.strip().startswith("v")
    assert "text/plain" in r.headers["content-type"]


def test_licence_route_carries_the_exact_notice():
    r = client.get("/licence")
    assert r.status_code == 200
    assert NOTICE in r.text


def test_licence_route_carries_the_srd_notice():
    assert "SRD 5.1" in client.get("/licence").text


def test_the_client_itself_carries_the_notice():
    """A route that exists is not a feature a player can reach."""
    assert NOTICE in client.get("/").text


def test_the_client_carries_the_house_chrome_in_order():
    body = client.get("/").text
    positions = [body.find(x) for x in
                 ('id="build"', 'id="report"', 'id="back"', 'id="signout"')]
    assert all(p >= 0 for p in positions), f"missing chrome: {positions}"
    assert positions == sorted(positions), "house chrome out of order"


def test_back_goes_to_the_site_root_not_games():
    body = client.get("/").text
    assert "tenshinarts.com/\"" in body or "tenshinarts.com'" in body
    assert "/games" not in body


def test_the_client_carries_the_trademark():
    assert "Sanctuary\u2122" in client.get("/").text


def test_character_api_returns_a_reproducible_character():
    payload = {"seed": 4242, "mode": "normal",
               "ancestry": "human", "classes": ["fighter"], "name": "Ilse"}
    a = client.post("/api/character", json=payload).json()
    b = client.post("/api/character", json=payload).json()
    assert a == b
    assert a["name"] == "Ilse"
    assert len(a["log"]) >= 6


def test_character_api_rejects_an_illegal_combination():
    r = client.post("/api/character", json={
        "seed": 1, "mode": "normal", "ancestry": "human",
        "classes": ["fighter", "magic-user"]})
    assert r.status_code == 400


def test_selfcheck_reports_real_numbers():
    line = sanctuary_app.selfcheck()
    assert line.startswith("sanctuary self-check OK")
    import re
    assert re.search(r"\d+ tables", line)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_app.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement `app.py`**

```python
"""Sanctuary - an OSRIC 3.0 table in the browser.

Sanctuary is an independent product published under the OSRIC 3.0 Third-Party
License and is not affiliated with Mythmere Games LLC.
"""
import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import tenshin_feedback
import tenshin_version
from sanctuary import character, tables

ROOT = Path(__file__).resolve().parent
GAME = "sanctuary"

LICENCE_NOTICE = (
    "Sanctuary is an independent product published under the OSRIC 3.0 "
    "Third-Party License and is not affiliated with Mythmere Games LLC.")
SRD_NOTICE = (
    "This work includes material taken from the System Reference Document 5.1 "
    "(\"SRD 5.1\") by Wizards of the Coast LLC and available at: "
    "https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 "
    "is licensed under the Creative Commons Attribution 4.0 International "
    "License available at: https://creativecommons.org/licenses/by/4.0/legalcode.")

app = FastAPI(title="Sanctuary")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    return html.replace("{{VERSION}}", tenshin_version.get_version())


@app.get("/version", response_class=PlainTextResponse)
def version():
    return tenshin_version.get_version()


@app.get("/licence", response_class=HTMLResponse)
def licence():
    return (f"<!doctype html><meta charset=utf-8><title>Sanctuary\u2122 licence</title>"
            f"<main><h1>Licence</h1><p>{LICENCE_NOTICE}</p><p>{SRD_NOTICE}</p>"
            f"<p><a href=\"/\">\u2190 Sanctuary\u2122</a></p></main>")


@app.post("/api/character")
async def api_character(request: Request):
    body = await request.json()
    try:
        c = character.generate(
            seed=int(body["seed"]),
            mode=str(body["mode"]),
            ancestry_name=str(body["ancestry"]),
            class_names=tuple(body["classes"]),
            name=str(body.get("name", "")),
        )
    except (ValueError, KeyError, LookupError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = asdict(c)
    out["log"] = [asdict(r) for r in c.log]
    return out


@app.post("/api/report")
async def api_report(request: Request):
    body = await request.json()
    # NEVER `if submit(...)` - it returns a 2-tuple, which is always truthy.
    ok, info = tenshin_feedback.submit(
        game=GAME,
        kind=str(body.get("kind", "bug")),
        title=str(body.get("title", "")),
        body=str(body.get("body", "")),
        username=str(body.get("username", "")),
        image=str(body.get("image", "")),
    )
    return {"ok": ok, "info": info}


@app.get("/live/embed", response_class=HTMLResponse)
def live_embed():
    return (f"<!doctype html><meta charset=utf-8><title>Sanctuary\u2122</title>"
            f"<p>Sanctuary\u2122 build {tenshin_version.get_version()}</p>"
            f"<p>{LICENCE_NOTICE}</p>")


def selfcheck() -> str:
    """Prove this build works, and say what it proved with real numbers."""
    n_tables = len(list((ROOT / "data" / "tables").glob("*.yaml")))
    assert n_tables > 150, f"only {n_tables} tables in the corpus"

    c = character.generate(seed=1, mode="normal",
                           ancestry_name="human", class_names=("fighter",))
    again = character.generate(seed=1, mode="normal",
                               ancestry_name="human", class_names=("fighter",))
    assert c == again, "generation is not reproducible from its seed"
    assert c.hit_points >= 1

    n_ancestries = len(character.ANCESTRIES)
    n_classes = len(character.CLASSES)
    for a in character.ANCESTRIES:
        assert character.ancestry(a)["allowed_classes"]
    for k in character.CLASSES:
        tables.load(character.game_class(k)["to_hit_table"])

    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    for needle in (LICENCE_NOTICE, 'id="build"', 'id="report"',
                   'id="back"', 'id="signout"', "Sanctuary\u2122"):
        assert needle in index_html, f"client is missing {needle!r}"

    return (f"sanctuary self-check OK - {n_tables} tables, {n_ancestries} ancestries, "
            f"{n_classes} classes, seed 1 reproduces a {c.classes[0]} with "
            f"{c.hit_points} hp and {len(c.log)} logged rolls")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print(selfcheck())
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=9300)
```

- [ ] **Step 4: Do not run the tests yet — the client does not exist**

`GET /` and `selfcheck()` both read `static/index.html`. The server is only half of this task; write the client in the next steps, then run the suite once at the end. ⚠ The animated die renders the number the engine already rolled. `Math.random` must not appear in `static/` — Task 4's test enforces it.

- [ ] **Step 5: Write `static/index.html`**

House chrome in order: build · report · back · sign out. `back` goes to the site ROOT.

```html
<!doctype html>
<meta charset="utf-8">
<title>Sanctuary™</title>
<link rel="stylesheet" href="/static/app.css">
<header class="chrome">
  <h1>Sanctuary™</h1>
  <nav>
    <span id="build">{{VERSION}}</span>
    <button id="report" type="button">report</button>
    <a id="back" href="https://tenshinarts.com/">← Tenshin Arts</a>
    <a id="signout" href="https://tenshinarts.com/signout">sign out</a>
  </nav>
</header>

<main>
  <section id="forge">
    <h2>Roll a character</h2>
    <label>Mode
      <select id="mode">
        <option value="hardest">Hardest — 3d6 in order</option>
        <option value="difficult">Difficult — 3d6, arrange</option>
        <option value="normal" selected>Normal — 4d6 drop lowest</option>
        <option value="flexible">Flexible — 4d6 drop lowest, arrange</option>
      </select>
    </label>
    <label>Ancestry <select id="ancestry"></select></label>
    <label>Class <select id="klass"></select></label>
    <label>Name <input id="name" type="text" placeholder="Ilse"></label>
    <button id="roll" type="button">Roll</button>
  </section>

  <section id="sheet" hidden>
    <h2 id="who"></h2>
    <dl id="scores"></dl>
    <p id="vitals"></p>
    <h3>Saving throws</h3>
    <dl id="saves"></dl>
  </section>

  <section id="tray">
    <h2>Dice</h2>
    <ol id="log"></ol>
  </section>
</main>

<footer>
  <p id="licence">Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License and is not affiliated with Mythmere Games LLC.</p>
  <p><a href="/licence">Full licence</a></p>
</footer>
<script src="/static/app.js"></script>
```

- [ ] **Step 6: Write `static/app.js`**

```js
"use strict";

const ANCESTRIES = ["dwarf", "elf", "gnome", "half-elf", "halfling", "half-orc", "human"];
const CLASSES = ["assassin", "cleric", "druid", "fighter", "illusionist",
                 "magic-user", "monk", "paladin", "ranger", "thief"];

function fill(id, values) {
  const el = document.getElementById(id);
  el.innerHTML = "";
  for (const v of values) {
    const o = document.createElement("option");
    o.value = v; o.textContent = v;
    el.appendChild(o);
  }
}
fill("ancestry", ANCESTRIES);
fill("klass", CLASSES);
document.getElementById("ancestry").value = "human";
document.getElementById("klass").value = "fighter";

// The seed is the character. A new one per roll, shown in the log so any
// character can be reproduced exactly.
function newSeed() {
  return Date.now() % 2147483647;
}

function renderSheet(c) {
  document.getElementById("sheet").hidden = false;
  document.getElementById("who").textContent =
    `${c.name || "Unnamed"} — ${c.ancestry} ${c.classes.join("/")}`;

  const scores = document.getElementById("scores");
  scores.innerHTML = "";
  for (const [k, v] of Object.entries(c.scores)) {
    scores.insertAdjacentHTML("beforeend", `<dt>${k}</dt><dd>${v}</dd>`);
  }

  document.getElementById("vitals").textContent =
    `${c.hit_points} hp · AC ${c.armour_class} · to hit ${c.modifiers.hit >= 0 ? "+" : ""}${c.modifiers.hit}` +
    ` · damage ${c.modifiers.damage >= 0 ? "+" : ""}${c.modifiers.damage} · seed ${c.seed}`;

  const saves = document.getElementById("saves");
  saves.innerHTML = "";
  for (const [k, v] of Object.entries(c.saves)) {
    saves.insertAdjacentHTML("beforeend", `<dt>${k.replace(/_/g, " ")}</dt><dd>${v}</dd>`);
  }
}

// The die FACE comes from the server. This animation only reveals a number
// that was already rolled - it never generates one.
function animate(el, finalFaces) {
  const frames = 8;
  let i = 0;
  const tick = () => {
    // Cycle through the real faces rather than inventing values.
    el.textContent = finalFaces[i % finalFaces.length];
    if (++i < frames) {
      setTimeout(tick, 40);
    } else {
      el.textContent = finalFaces.join(" ");
    }
  };
  tick();
}

function renderLog(rolls) {
  const log = document.getElementById("log");
  log.innerHTML = "";
  for (const r of rolls) {
    const li = document.createElement("li");
    const faces = document.createElement("b");
    li.appendChild(faces);
    const modText = r.mods ? ` ${r.mods > 0 ? "+" : ""}${r.mods}` : "";
    li.insertAdjacentHTML("beforeend",
      ` <code>${r.expr}</code>${modText} = <strong>${r.total}</strong>` +
      (r.reason ? ` <em>${r.reason}</em>` : ""));
    log.appendChild(li);
    animate(faces, r.faces);
  }
}

document.getElementById("roll").addEventListener("click", async () => {
  const payload = {
    seed: newSeed(),
    mode: document.getElementById("mode").value,
    ancestry: document.getElementById("ancestry").value,
    classes: [document.getElementById("klass").value],
    name: document.getElementById("name").value,
  };
  const res = await fetch("/api/character", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    document.getElementById("who").textContent = `Cannot roll that: ${err.detail}`;
    document.getElementById("sheet").hidden = false;
    return;
  }
  const c = await res.json();
  renderSheet(c);
  renderLog(c.log);
});

document.getElementById("report").addEventListener("click", async () => {
  const title = prompt("What went wrong?");
  if (!title) return;
  const res = await fetch("/api/report", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind: "bug", title, body: location.href }),
  });
  const out = await res.json();
  alert(out.ok ? "Report sent." : "Could not send the report.");
});
```

- [ ] **Step 7: Write `static/app.css`**

Keep it small and readable; no CDN, no remote fonts.

```css
:root { color-scheme: light dark; --ink: #1a1c22; --paper: #f7f5ef; --rule: #c9c3b4; }
@media (prefers-color-scheme: dark) { :root { --ink: #e7e3d8; --paper: #16171b; --rule: #3a3d46; } }
body { margin: 0; font: 16px/1.5 Georgia, "Times New Roman", serif; color: var(--ink); background: var(--paper); }
.chrome { display: flex; justify-content: space-between; align-items: baseline;
          gap: 1rem; padding: .75rem 1.25rem; border-bottom: 2px solid var(--rule); }
.chrome h1 { font-size: 1.25rem; margin: 0; letter-spacing: .04em; }
.chrome nav { display: flex; gap: 1rem; align-items: baseline; font-size: .85rem; }
main { display: grid; gap: 2rem; padding: 1.25rem; grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr)); }
section { border: 1px solid var(--rule); padding: 1rem; }
h2 { margin-top: 0; font-size: 1rem; text-transform: uppercase; letter-spacing: .08em; }
label { display: block; margin: .5rem 0; }
select, input, button { font: inherit; padding: .3rem; }
dl { display: grid; grid-template-columns: auto 1fr; gap: .1rem .75rem; margin: 0; }
dt { text-transform: capitalize; opacity: .75; }
dd { margin: 0; font-variant-numeric: tabular-nums; }
#log { font-size: .9rem; padding-left: 1.25rem; }
#log b { font-variant-numeric: tabular-nums; }
footer { padding: 1.25rem; border-top: 1px solid var(--rule); font-size: .78rem; opacity: .8; }
```

- [ ] **Step 8: Run the full suite**

```bash
python -m pytest tests/ -q
python app.py test
```
Expected: all tests pass; the self-check prints a sentence with real numbers, e.g. `sanctuary self-check OK - 239 tables, 7 ancestries, 10 classes, seed 1 reproduces a fighter with 6 hp and 7 logged rolls`

- [ ] **Step 9: Verify it runs and looks right**

```bash
TENSHIN_DEV=1 python app.py
```
Then open the preview at `http://127.0.0.1:9300/`, roll a character, and confirm the sheet, the dice log and the licence footer all render. Use the browser tools rather than asking anyone to check by hand.

- [ ] **Step 10: Commit**

```bash
printf 'v0.0.16-beta\n' > VERSION
git add app.py tests/test_app.py static/ VERSION
git commit -m "Server and client: routes, licence, house chrome, character sheet, dice tray"
```

---

### Task 15: Character portraits from PixelLab

**Files:**
- Create: `static/art/portraits/<ancestry>-<class>.png`
- Create: `data/art.yaml`
- Modify: `static/app.js`, `static/app.css`, `app.py` (`selfcheck`), `tests/test_app.py`

**Interfaces:**
- Consumes: the PixelLab MCP tools.
- Produces: `data/art.yaml` mapping `"<ancestry>/<class>" -> "/static/art/portraits/<file>.png"`, and a portrait rendered on the character sheet.

★ **Standing platform art direction: TOP-DOWN, in the artwork style of Factorio. Never isometric.** Dr. Ray restated this for Sanctuary on 2026-08-01: use PixelLab artwork, no isometric tiles. Portraits are the one exception to *top-down* framing — a portrait is a face, not a floor — but nothing in Sanctuary is ever drawn isometric, and the dungeon tilesets in Chapter 4 are strictly top-down.

⚠ The OSRIC licence forbids using the books' art entirely. Every image in this repo is generated or drawn for Sanctuary.

- [ ] **Step 1: Generate a first portrait and confirm the look before batching**

Use `mcp__pixellab__create_portrait_character`. One portrait first — settle the style before spending generations on a matrix.

Prompt shape (adjust the subject per portrait, keep the style clause identical across all of them or the set will not read as one game):

```
a human fighter, chainmail and open helm, weathered face, three-quarter bust portrait,
muted earth palette, flat shading, crisp pixel art, dark neutral background
```

⚠ **`credits: $0.00` is normal and misleading** — generations come from the subscription pool. Read `generations_remaining` instead.

- [ ] **Step 2: Generate the portrait set, staggered**

⚠ **Eight in-flight jobs, ACCOUNT-WIDE** — not per session, not per repo. Fire two, poll `mcp__pixellab__get_image`, fire two more. ⚠ **A rate-limited job was never queued — re-issue it unchanged.** Do not rewrite a prompt that was fine on the strength of an error that was about traffic.

Start with one portrait per **class** (10), on a human subject, rather than the full 7×10 = 70 ancestry×class matrix. The matrix is the trap here: 70 generations before anyone has played the game, when a class silhouette carries almost all of the recognition. Ancestry variants are a later pass if they earn it.

- [ ] **Step 3: Download the images**

⚠ Fetch within **8 hours** — the object auto-deletes. Download with `curl --ssl-no-revoke` (an AV root in the Windows store breaks Python's chain verification).

```bash
mkdir -p "D:/Tenshin Arts/Sanctuary/static/art/portraits"
# one per returned URL:
curl --ssl-no-revoke -o "static/art/portraits/fighter.png" "<url>"
```

- [ ] **Step 4: Write `data/art.yaml` and the failing test**

```yaml
portraits:
  default: /static/art/portraits/fighter.png
  fighter: /static/art/portraits/fighter.png
  cleric: /static/art/portraits/cleric.png
  # ... one per class in sanctuary.character.CLASSES
```

Append to `tests/test_app.py`:

```python
def test_every_class_has_a_portrait_file_on_disk():
    import yaml
    from pathlib import Path

    from sanctuary.character import CLASSES

    root = Path(__file__).resolve().parent.parent
    art = yaml.safe_load((root / "data" / "art.yaml").read_text(encoding="utf-8"))
    missing = []
    for cls in CLASSES:
        rel = art["portraits"].get(cls)
        if not rel or not (root / rel.lstrip("/")).exists():
            missing.append(cls)
    assert missing == [], f"classes with no portrait: {missing}"


def test_every_portrait_is_actually_served():
    """Assets must be SERVED, not merely present - /static has gone unmounted
    on this platform while tests read files off disk and passed."""
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    art = yaml.safe_load((root / "data" / "art.yaml").read_text(encoding="utf-8"))
    for rel in set(art["portraits"].values()):
        r = client.get(rel)
        assert r.status_code == 200, f"{rel} is not served"
        assert r.content[:8] == bytes.fromhex("89504e470d0a1a0a"), f"{rel} is not a PNG"


def test_the_client_renders_a_portrait():
    assert 'id="portrait"' in client.get("/").text
```

- [ ] **Step 5: Run to verify the tests fail**

Run: `python -m pytest tests/test_app.py -q`
Expected: FAIL — no `data/art.yaml`, no `id="portrait"` in the client.

- [ ] **Step 6: Serve the portrait and render it**

Add to `app.py` inside `api_character`, just before `return out`:

```python
    import yaml as _yaml
    _art = _yaml.safe_load((ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))
    out["portrait"] = _art["portraits"].get(c.classes[0], _art["portraits"]["default"])
```

Add to `selfcheck()`, before the return, so the gate covers art too:

```python
    import yaml as _yaml
    _art = _yaml.safe_load((ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))
    n_portraits = len(set(_art["portraits"].values()))
    for _cls in character.CLASSES:
        _rel = _art["portraits"].get(_cls)
        assert _rel and (ROOT / _rel.lstrip("/")).exists(), f"no portrait for {_cls}"
```

and interpolate `n_portraits` into the returned sentence.

Add to `static/index.html`, inside `<section id="sheet">` above `<h2 id="who">`:

```html
    <img id="portrait" alt="" width="192" height="192">
```

Add to `renderSheet` in `static/app.js`, after the `hidden = false` line:

```js
  const portrait = document.getElementById("portrait");
  portrait.src = c.portrait;
  portrait.alt = `${c.ancestry} ${c.classes.join("/")}`;
```

Add to `static/app.css`:

```css
#portrait { display: block; image-rendering: pixelated; border: 1px solid var(--rule); margin-bottom: .75rem; }
```

- [ ] **Step 7: Run the suite and look at it**

```bash
python -m pytest tests/ -q
python app.py test
TENSHIN_DEV=1 python app.py
```
Open `http://127.0.0.1:9300/`, roll a character of each class, and confirm the portrait changes and renders crisply. ⚠ **A string gate proves wiring exists, never that it is live** — look at the rendered page, do not trust the assertion alone.

- [ ] **Step 8: Commit**

```bash
printf 'v0.0.17-beta\n' > VERSION
git add static/art data/art.yaml static/index.html static/app.js static/app.css app.py tests/test_app.py VERSION
git commit -m "Art: PixelLab class portraits on the character sheet"
```

---

### Task 16: Repo documentation and the v0.1.0 release

**Files:**
- Modify: `CLAUDE.md` (⚠ **already exists** — Dr. Ray created it in `794fb3c`, 2026-08-01)
- Create: `IMPROVEMENTS.md`
- Modify: `VERSION`

**Interfaces:**
- Consumes: nothing.
- Produces: the two documents every Tenshin repo carries.

⚠⚠ **`CLAUDE.md` EXISTS. Do not create or overwrite it.** Dr. Ray wrote it while this plan was being executed, along with vendoring `tenshin_client.py` — a drop-in this plan's Task 1 missed entirely, caught by `dropins.sh check`. All four drop-ins are now present and byte-identical to the Website copies.

Its current shape: a `# Sanctuary — for Claude` heading, the canonical block between `<!-- tenshin:platform:start -->` (line 33) and `<!-- tenshin:platform:end -->` (line 73), then `## The gate` and `## Conventions`.

- [ ] **Step 1: ADD the load-bearing rules to the existing `CLAUDE.md`**

⚠ **Never touch the lines between `<!-- tenshin:platform:start -->` and `<!-- tenshin:platform:end -->`.** That block is vendored, guarded by `deploy/dropins.sh check`, and editing it here makes this repo diverge from every other game.

Read the file first. Add the game-specific rules below the end marker, merging with the existing `## The gate` and `## Conventions` sections rather than duplicating them. Only add rules not already stated. The list to merge in:

```markdown
# Sanctuary — for Claude

A browser OSRIC 3.0 table: seeded dice, generated characters, procedural dungeons, and
campaigns Game Masters can build and run. Slug `sanctuary`, port **9300**.

⚠ **Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License
and is not affiliated with Mythmere Games LLC.** That notice ships in the client AND at
`/licence`, and the gate asserts both. The licence permits verbatim reuse of **monster,
spell and magic-item text only** — never the books' art, never rules prose.

<!-- tenshin:platform:start -->
(copy from ../Website/deploy/claude-platform.md)
<!-- tenshin:platform:end -->

## The gate
​```bash
python app.py test          # → "sanctuary self-check OK - ..."
python -m pytest tests/ -q
​```
⚠ Use the **system** python. Any `.venv` in this tree is a decoy.

## Run
​```bash
TENSHIN_DEV=1 python app.py    # http://127.0.0.1:9300/
​```

## Rules that are load-bearing
- **`random.` appears nowhere outside `sanctuary/dice.py`**, and `Math.random` nowhere in
  `static/`. Every die comes from the seeded engine or the replay guarantee is gone.
  Guarded by `tests/test_invariants.py`.
- **The animated die renders the number the engine already rolled.** It never generates one.
- **A natural 1 to-hit is NOT an automatic miss; a natural 20 is NOT an automatic hit.**
  That is OSRIC's stated rule. A natural 1 on a *saving throw* always fails.
- **The extractor is dumb on purpose.** `tools/extract.py` stores each table's lines as
  printed; typed interpretation lives in `sanctuary/tables.py`. A universal table parser
  breaks on rows like Table 1.1.2A's `18.91–18.99 … 1–4 (1 in 6 extraordinary success) 35`.
- **Never hand-edit `data/tables/`.** Fix the extractor and re-extract; the round-trip test
  compares the committed corpus against the book.
- **Round-trip and spot-check are both required.** Round-trip alone passes on a uniformly
  mis-parsed corpus.
- **`read_text(encoding="utf-8")` everywhere.** The sources carry en-dashes, curly quotes
  and ligatures; Windows defaults to cp1252.
- **Ligatures (U+FB00–FB06) are normalised at extraction.** Unnormalised, the corpus ships
  words no search will match.
- **The minor version tracks the OSRIC chapter** — see the design record §12a. `v0.8.0` is
  the first playable build, and the build restarts at `0` when the minor moves.
- ★ **All artwork is PixelLab-generated, TOP-DOWN, Factorio-styled. NEVER isometric**
  (Dr. Ray, 2026-08-01). The licence forbids the books' art outright, so there is no
  fallback — every image here is made for Sanctuary.
- **Assets must be SERVED, not merely present.** `/static` has gone unmounted on this
  platform while client tests read files off disk and passed. Guarded by
  `test_every_portrait_is_actually_served`.
```

- [ ] **Step 2: Write `IMPROVEMENTS.md`**

```markdown
# Sanctuary — architecture, gotchas and queue

Design record: [`docs/superpowers/specs/2026-08-01-sanctuary-design.md`](docs/superpowers/specs/2026-08-01-sanctuary-design.md)
Build plan: [`docs/superpowers/plans/`](docs/superpowers/plans/)

## Architecture
One-way dependency chain, asserted by test:
`dm → runtime → module → {procgen, bestiary, treasure} → {character, resolve} → tables`,
and everything → `dice`. `dice.py` imports nothing of ours.

## PixelLab
Sanctuary needs art in four places and the licence forbids using the books':
character portraits by ancestry and class (ships with Ch.1), monster portraits (291, phased
by encounter frequency with `common` first — Ch.5), dungeon tilesets (Ch.4), and the dice
tray and map chrome. Top-down, Factorio-styled, per the platform standing order.
⚠ For floors use `create_tiles_pro` with `outline_mode: "segmentation"` and a numbered list
of floors — not `create_topdown_tileset`, which composes a scene when asked for a transition.

## Queue
- [ ] Ch.2 Spells → `v0.2.0`
- [ ] Ch.3 How to Play → `v0.3.0`
- [ ] Ch.4 Dungeons, Towns and Wildernesses → `v0.4.0`
- [ ] Ch.5 Monsters → `v0.5.0`
- [ ] Ch.6 Treasure → `v0.6.0`
- [ ] Campaign format and authoring → `v0.7.0`
- [ ] First playable → `v0.8.0`
- [ ] Constitution hit-point adjustment (deferred from Ch.1; lands with Ch.3)
- [ ] Armour class from equipment (deferred from Ch.1; lands with Ch.3)
- [ ] Thief skills and spell slots on the sheet (needs Ch.2 and Ch.3 tables)
- [ ] Dual-classing (human-only, sequential — distinct from multi-classing)
```

- [ ] **Step 3: Run the whole gate one final time**

```bash
python -m pytest tests/ -q
python app.py test
```
Expected: all green.

- [ ] **Step 4: Move the minor to v0.1.0 — Chapter 1 is complete**

The build restarts at `0` when the minor moves.

```bash
printf 'v0.1.0-beta\n' > VERSION
```

- [ ] **Step 5: Commit and push**

```bash
git add CLAUDE.md IMPROVEMENTS.md VERSION
git commit -m "Chapter 1 complete: character generation, v0.1.0-beta

Seven ancestries, eleven classes, four generation modes, exceptional
Strength, derived saving throws and to-hit targets, all rolled through the
seeded engine and reproducible from a seed."
git push -u origin main
```

⚠ A session's job ends at `git push`. Do not SSH the Droplet — local keys are deliberately
not authorised on it. Report what is ready and stop.

---

## Deferred from this plan, deliberately

These belong to later chapters and are recorded in `IMPROVEMENTS.md` rather than half-built here:

- **Constitution hit-point adjustment** — Table 1.1.4A. Needs Chapter 3's combat context; `roll_hit_points` already takes `con_bonus` and is passed `0`.
- **Armour class from equipment** — Chapter 3. `Character.armour_class` is `10` (unarmoured).
- **Thief skills, spell slots, encumbrance and movement** — the tables are extracted and committed; the accessors land with Chapters 2 and 3.
- **Dual-classing** — human-only and sequential, a different mechanism from multi-classing. Modelling it as a class tuple would be wrong.
- **Monster attack matrix and monster saving throws** — extracted (`2.1.2a`, `2.1.3a`) and gated, but unused until Chapter 5.
