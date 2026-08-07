# Sanctuary — improvements, gotchas and queue

## Architecture snapshot

Sanctuary is an OSRIC 3.0 tactical VTT with two runtimes:

- **Engine-run:** an AI DM moves monsters, resolves morale, and advances turns.
- **DM-run:** a human DM takes the seat, sees everything, and can override.

The same `backend/app/engine/session.py` state machine serves both runtimes.
The same `backend/app/engine/module.py` format is used for tactical modules
and the richer S3 Adventure format.

### Key modules

| File | Responsibility |
|---|---|
| `backend/app/engine/dice.py` | Seeded `Dice` with append-only `Roll` log. The only file allowed to import `random`. |
| `backend/app/engine/character.py` | OSRIC character generation and derived stats. |
| `backend/app/engine/resolve.py` | OSRIC attack, save, morale, turn undead, movement resolution. |
| `backend/app/engine/session.py` | Tactical session state machine. |
| `backend/app/engine/ai_dm.py` | Deterministic monster tactics. |
| `backend/app/instance_manager.py` | Background AI-DM loop for persistent instances. |
| `backend/app/engine/module.py` | Tactical `Module` and S3 `Adventure` format. |
| `backend/app/rulesets/` | OSRIC loader + custom ruleset support. |
| `frontend/static/main.js` | Plain-JS client. |

## Gotchas

- **No second RNG.** `backend/tests/test_invariants.py` fails the build if
  `random` is used outside `dice.py`.
- **Replay determinism.** Same seed + same action sequence must reproduce the
  same roll log. Any non-determinism breaks this.
- **Frontend is static.** No npm, no Vite, no PixiJS. Edit `frontend/static/`
  directly and reload.
- **Deploy is one script.** `ssh root@<ip> 'bash /opt/tenshin/sanctuary/deploy-all.sh'`
  runs `git fetch`, `pip install`, and restarts the service.
- **Migrations are manual.** `cd backend && python -m alembic upgrade head`.

## Queue

- [x] Eliminate second RNG and enforce invariant.
- [x] Fix game-load freeze / splash timeout.
- [x] Fix observer / spectator mode.
- [x] Clean deploy scripts (no npm/PixiJS).
- [x] Scale tokens and add viewport zoom.
- [x] Integrate OSRIC combat resolution.
- [x] Build deterministic AI DM policy.
- [x] Implement S3 Adventure format and validator.
- [x] Persistent instances with AI-DM background loop.
- [ ] DM Workshop visual editor (in progress).
- [ ] Drop-in co-op and AI takeover for absent players (in progress).
- [ ] Adventure/ruleset marketplace and publishing (in progress).
- [ ] Full equipment/weapon system.
- [ ] Spell system with saving throws.
- [ ] Initiative/surprise/segment model.
- [ ] Death threshold: OSRIC −10 vs current ≤−11.
- [ ] Replace placeholder art with PixelLab-generated top-down tiles and tokens.
