# Sanctuary — for Claude

A web-based OSRIC 3.0 tabletop engine. Every die in the game comes from
`backend/app/engine/dice.py`, which keeps an append-only roll log. **Same seed
plus the same call sequence produces a byte-identical log**, which is what makes
a generator property-testable, a bug report reproducible from its seed, and the
dice auditable to a player who suspects them.

⚠ **Nothing outside `backend/app/engine/dice.py` may import `random`.** That
rule is enforced by `backend/tests/test_invariants.py`.

Slug `sanctuary`, port **9300**. One name per thing: slug == subdomain ==
systemd unit == data directory == git repo.

## Quick start

```bash
cd "D:/Tenshin Arts/Sanctuary"
pip install -r requirements.txt
cd backend && python -m alembic upgrade head
cd ..
python app.py
```

Open `http://127.0.0.1:9300`.

## Gate

```bash
cd backend && python -m pytest tests -q
python app.py test
```

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, python-socketio.
- **Frontend:** Plain HTML + CSS + JavaScript in `frontend/static/`.
- **Persistence:** SQLite locally, PostgreSQL in production.
- **Rulesets:** YAML manifest + Python adapter; OSRIC ships first.

<!-- tenshin:platform:start -->
**Two documents.** Global standards + future work: the SSoT
(`../Website/SSOT.md`) — read its **Platform conventions** first. **Everything
specific to this game lives here in
[`IMPROVEMENTS.md`](IMPROVEMENTS.md)** — architecture, gotchas, design record,
and this game's queue. Strike an item there in the same commit that ships it.

**Every commit bumps the build** — the patch of `vX.Y.Z-beta` in `VERSION`,
staged in that commit. Dr. Ray alone moves major/minor, and the build restarts at
`0` when either does. **No CI/CD** — gates run locally; do not add a `.github/`
directory.

**The house chrome, in every client:** build · report · back · sign out, same
set, same order. `back` is `← Tenshin Arts` → the site ROOT and leaves you
signed in; `sign out` ends the session.

**Show the BUILD, never a hand-kept number.** Whatever `/version` serves is what
every screen shows and every bug report carries.

⚠ **Check the CLIENT, not the server.** A route that exists is not a feature a
player can reach.

⚠ **A LINK IS NOT A FEATURE — ITS TARGET IS.** Follow every control to what it
hits.

⚠ **`tenshin_feedback.submit()` returns `(ok, info)` — a tuple.** Unpack it.
`bool()` on a 2-tuple is always True.

⚠ **An assertion that cannot fail is not a test.** Break it three ways before
trusting it.

⚠ **A broken measurement still returns a number.** Guard on OUTPUT, not
inventory.

⚠ **Derive, don't migrate.** Display data is derived at READ time; what must
persist migrates at the ONE door every load passes.

⚠ **Test the deployed shape, not the convenient one.**

⚠ **A self-check prints what it proved, in a sentence, with the numbers**
interpolated from what it computed, never typed in.
<!-- tenshin:platform:end -->
