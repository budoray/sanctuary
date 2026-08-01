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

⚠ **REGISTERED, NOT SHIPPED.** There is no `app.py`, no server, no vhost and no unit —
this repo is a corpus extractor and a dice engine, not yet a Tenshin app. The row exists
so the platform can SEE it: a game in no registry cannot fail a parity check, which is
how two games once sat pushed-and-undeployed with every board green.

⚠ **Its gate is currently RED** — `tests/test_corpus.py` has two failures in the
extraction round-trip, from work in progress. Recorded rather than hidden; a gate that is
red for a known reason is worth more than one nobody has run.

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
python -m pytest -q
```

## Conventions
- **All dice through `sanctuary/dice.py`.** No other module imports `random`.
- Extracted tables live in `data/`; the extractor is `tools/extract.py`.
