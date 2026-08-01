# Sanctuary — for Claude

A seeded-dice tabletop engine: every die in the game comes from `sanctuary/dice.py`,
which keeps an append-only roll log. **Same seed plus the same call sequence produces a
byte-identical log**, which is what makes a generator property-testable, a bug report
reproducible from its seed, and the dice auditable to a player who suspects them.
⚠ **Nothing outside `dice.py` may import `random`** — that rule is the whole guarantee.

Slug `sanctuary`, port **9300** — `registered` in `../Website/app.py`'s `OPS`, which is
the live port map. Believe it over any number in a game document, including this one.
⚠ 9300 was **Titer's**, freed when Titer retired into Pyrogen (2026-08-01). Reissuing a
port is safe only once no name still resolves in front of it: `titer.tenshinarts.com`
was verified NXDOMAIN against 8.8.8.8 before this row took the number.

⚠⚠ **`sanctuary.tenshinarts.com` ALREADY RESOLVES to 104.131.165.79 and nothing is behind
it** (checked against 8.8.8.8, 2026-08-01). That is G8's shape exactly, and it is the one
failure this platform has actually shipped: a name that resolves with no vhost does not
fail fast — Caddy answers with whatever its default host serves, which is how Asymptote
published a cabinet reading *sent an invalid response*. The record existing before the
deploy is fine and necessary; **nothing about this game may be published or lit on the
strength of it**, and `registered` is what keeps it out of the Caddyfile, cc-op,
deploy-all and the units until there is something to serve.

⚠ **REGISTERED, NOT SHIPPED.** `app.py` exists, serves on port 9300, has a self-check
gate, and the client renders a character sheet with portraits — but there is still no
vhost and no unit. The row exists so the platform can SEE it: a game in no registry
cannot fail a parity check, which is how two games once sat pushed-and-undeployed with
every board green.

⚠ **Its gate is GREEN** — `python -m pytest tests/ -q` → 429 passed, `tests/test_corpus.py`
→ 11 passed, and `python app.py test` prints the self-check sentence. Recorded rather than
assumed; a gate someone just ran is worth more than one nobody has checked.

<!-- tenshin:platform:start -->
**Two documents.** Global standards + future work: the SSoT
([`../Website/SSOT.md`](../Website/SSOT.md)) — read its **Platform conventions** first, it
lists the standards every game meets. **Everything specific to this game lives here in
[`IMPROVEMENTS.md`](IMPROVEMENTS.md)** — architecture, gotchas, design record, and this game's queue.
Strike an item there in the same commit that ships it.
⚠ **This replaces the old "do not start a new `.md` here" rule** (Dr. Ray, 2026-07-25): project
specifics were split out of the SSoT per game, so a new `.md` here is now correct, not forbidden.

**Every commit bumps the build** — the patch of `vX.Y.Z-beta` in `VERSION`, staged in that commit.
Dr. Ray alone moves major/minor, and the build restarts at `0` when either does. **No CI/CD** — gates
run locally and through the Command Center; do not add a `.github/` directory.

**The house chrome, in every client:** build · report · back · sign out, same set, same order. `back`
is `← Tenshin Arts` → the site ROOT (not `/games`) and leaves you signed in; `sign out` ends the
session. They are different doors — one account opens every game, so leaving one is navigation. The
unauthenticated `/live/embed` carries the first three and drops sign out.

**Show the BUILD, never a hand-kept number.** Whatever `/version` serves is what every screen shows
and every bug report carries, or the hub's card and the game disagree.

⚠ **Check the CLIENT, not the server.** A route that exists is not a feature a player can reach: a
reporter wired server-side with nothing calling it, a version in the state payload that nothing
renders, and a tutorial with no replay have all shipped here while `app.py` grepped clean. If the
client is a static file or a bundle, the gate must read it.

⚠ **`tenshin_feedback.submit()` returns `(ok, info)` — a tuple.** `bool()` on a 2-tuple is always
True, so `if submit(...)` tells the player "sent" while the report goes nowhere. Unpack it.

⚠ **An assertion that cannot fail is not a test.** Break it three ways before trusting it — the value, the absence, the selector scope.

⚠ **A broken measurement still returns a number.** Make the primitive self-report; guard on OUTPUT not inventory; refuse rather than compute across a mismatched commit/ticks/seed; one draw is not a ranking.

⚠ **Derive, don't migrate.** Display data is derived at READ time; what must persist migrates at the ONE door every load passes — never at a call site, never inside a seed guarded by `if already_seeded: return`.

⚠ **Test the deployed shape, not the convenient one.** Mutate a live row to the old shape, re-run the fix, assert it landed — a fresh-DB test passes for the wrong reason.

⚠ **A self-check prints what it proved, in a sentence, with the numbers** — interpolated from what it computed, never typed in. The gate output IS this platform's behaviour documentation; a literal in a status line is the stale second copy.

⚠ **Results a document quotes go in `metrics/` and are COMMITTED; scratch and sqlite do not.** A claim in a design record you cannot re-check is a claim nobody can revisit.
<!-- tenshin:platform:end -->
## The gate
```bash
python app.py test          # → "sanctuary self-check OK - ..."
python -m pytest tests/ -q
```
⚠ Use the **system** python. Any `.venv` in this tree is a decoy.

## Run
```bash
TENSHIN_DEV=1 python app.py    # http://127.0.0.1:9300/
```

★ **Testing standard, site-wide (Dr. Ray, 2026-08-01).** **BDD features AND TDD tests, both** —
every behaviour gets a Gherkin `.feature` under `features/` bound with `pytest-bdd` (runs inside
pytest, so the gate keeps its shape), alongside the unit tests. **Maximum coverage** via
`pytest-cov`. ⚠ **Every change of the MINOR version triggers a FULL suite run**, green before the
minor moves — a patch bump tests what it touched, a minor bump tests everything. The minor is the
chapter boundary, and a chapter that lands red is one nobody can build on.
⚠ A scenario that restates a unit test in Gherkin is waste. Features describe what a player or GM
would recognise — *"a fighter with exceptional Strength hits harder"* — never *"parse_expr returns
a 4-tuple"*. If it cannot be phrased without naming a Python symbol, it is a unit test.

## Conventions
- **All dice through `sanctuary/dice.py`.** No other module imports `random`, and no `Math.random`
  in `static/`. The animated die renders the number the engine already rolled; it never generates
  one. Guarded by `tests/test_invariants.py`.
- Extracted tables live in `data/`; the extractor is `tools/extract.py`.
- ⚠ **Never hand-edit `data/tables/`.** Fix the extractor and re-extract — the round-trip test
  re-runs extraction and compares, so a hand-edit passes a spot-check and then fails the gate.
- ⚠ **The extractor is dumb on purpose.** It stores each table's lines as printed; typed
  interpretation lives in `sanctuary/tables.py`. Per-line prose-vs-data classification was tried
  and failed in both directions — it leaked 70 lines of narrative into two tables, and the fix
  then discarded genuine rows like `Lieutenant Special as type as type`. Blocks are judged whole.
- ⚠ **19 table ids map to more than one file** — a table the book split across pages keeps its id
  and gains a `CONTINUED`/`PART 2` name. `tables.load()` raises and names the parts; `parts()`
  returns them all. Indexing id → one path silently drops 26 tables with every test still green.
- **The minor version tracks the OSRIC chapter.** `v0.8.0` is the first playable build, and the
  build restarts at `0` when the minor moves. See `docs/superpowers/specs/` §12a.
- ★ **All artwork is PixelLab-generated, top-down, Factorio-styled. NEVER isometric** (Dr. Ray,
  2026-08-01). The OSRIC licence forbids the books' art outright, so there is no fallback.
- ⚠ **Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License and is
  not affiliated with Mythmere Games LLC.** That notice ships in the client AND at `/licence`. The
  licence permits verbatim reuse of **monster, spell and magic-item text only** — never the art,
  never rules prose.
- **A natural 1 to-hit is NOT an automatic miss; a natural 20 is NOT an automatic hit.** That is
  OSRIC's stated rule. A natural 1 on a *saving throw* always fails.
- ⚠ **Round-trip and spot-check are both required** on the corpus. Round-trip alone passes on a
  uniformly mis-parsed corpus.
- **`read_text(encoding="utf-8")` everywhere.** The sources carry en-dashes, curly quotes and
  ligatures; Windows defaults to cp1252.
- **Ligatures (U+FB00–FB06) are normalised at extraction.** Unnormalised, the corpus ships words no
  search will match.
- ⚠ **Assets must be SERVED, not merely present.** `/static` has gone unmounted on this platform
  while client tests read files off disk and passed. Guarded by
  `test_every_portrait_is_actually_served`.
