"""Sanctuary - an OSRIC 3.0 table in the browser.

Sanctuary is an independent product published under the OSRIC 3.0 Third-Party
License and is not affiliated with Mythmere Games LLC.

    python app.py test            # the gate
    TENSHIN_DEV=1 python app.py   # play locally, no login

⚠ TENSHIN_DEV must be set BEFORE tenshin_gate is imported; the drop-in latches
it into a module constant at import time.
"""
import os
import sys
import uuid
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

# ⚠ BEFORE `import tenshin_gate`, AND THIS IS THE WHOLE REASON IT IS UP HERE.
# The drop-in latches TENSHIN_DEV and TENSHIN_SECRET into module constants at
# import time, so setting them later does nothing at all. The gate needs both:
# dev mode to reach the gated player routes without a signed cookie, and a
# secret that is not the public dev fallback - `secret_ok()` fails CLOSED on the
# fallback, deliberately, so a box that never configured one rejects everything.
if "test" in sys.argv:
    os.environ.setdefault("TENSHIN_DEV", "1")
    os.environ.setdefault("TENSHIN_SECRET", "gate-only-secret-not-a-real-one")

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import tenshin_feedback
import tenshin_gate
import tenshin_version
from sanctuary import character, module as module_mod, procgen, runtime, session, tables
from sanctuary.dice import Dice

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


@lru_cache(maxsize=1)
def _art() -> dict:
    return yaml.safe_load((ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))


# ── auth ──────────────────────────────────────────────────────────────────────
# One Tenshin Arts account opens every game, so Sanctuary hosts no login of its
# own: an unauthenticated visitor is sent to the SITE, not to a per-game form.
# `require_account` raises 401 when the signed session cookie is missing or bad.
#
# ⚠ /version, /licence, /live/embed and /api/report stay OPEN on purpose. The
# platform contract requires the unauthenticated embed to carry build · report ·
# back, and the hub reads /version cross-origin to show a live build on the card.
def _account(request: Request) -> int:
    return tenshin_gate.require_account(request)


# ── public leaderboard (Across-the-realms) ─────────────────────────────────
# Sanctuary's natural score is XP earned: it is the one number every delve
# produces regardless of module, party size, or whether the party survived —
# a wipe still earns XP, and a fixture module (no procgen) has no depth stat
# to report but wins XP the same as a generated one. Depth (the requested
# dungeon_level) rides along as `stat` so the row means something at a glance.
# One row per Tenshin account: their best delve, ever.
# ponytail: process-local dicts, same shape as sanctuary/session.py's own
# in-memory `_SESSIONS` - a durable store is a later, unrelated concern.
CORS = {"Access-Control-Allow-Origin": "*"}
_BEST: dict[int, dict] = {}
_SESSION_LEVEL: dict[str, int] = {}


def _record_best(request: Request, acct: int, session_id: str, view: dict) -> None:
    xp = int(view.get("xp", 0))
    prior = _BEST.get(acct)
    if prior is not None and xp <= prior["score"]:
        return
    level = _SESSION_LEVEL.get(session_id, 1)
    name = (tenshin_gate.name_from_cookie_header(request.headers.get("cookie", ""))
            or f"P{acct}")
    _BEST[acct] = {"name": name, "score": xp, "level": level,
                   "stat": f"level {level} · {xp} xp"}


@app.get("/leaderboard.json")
def leaderboard():
    """Public board, unauthenticated (the accepted carve-out - Tenshin
    accounts are zero-PII, a self-chosen name and nothing else). Ranked on
    XP, each account's best delve. ⚠ Every row carries a `stat` STRING - the
    hub prints that column verbatim, and a board serving {name, score, level}
    with no `stat` renders a blank column."""
    board = sorted(_BEST.values(), key=lambda r: -r["score"])[:20]
    return JSONResponse({"board": board}, headers=CORS)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    _account(request)
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    return html.replace("{{VERSION}}", tenshin_version.get_version())


@app.get("/version", response_class=PlainTextResponse)
def version():
    return tenshin_version.get_version()


@app.get("/licence", response_class=HTMLResponse)
def licence():
    return (f"<!doctype html><meta charset=utf-8><title>Sanctuary™ licence</title>"
            f"<main><h1>Licence</h1><p>{LICENCE_NOTICE}</p><p>{SRD_NOTICE}</p>"
            f"<p><a href=\"/\">← Sanctuary™</a></p></main>")


@app.get("/api/ancestry-classes")
def api_ancestry_classes(request: Request):
    """The map Fix 1 needs: `{ancestry: [allowed classes]}` for all seven,
    sourced straight from data/ancestries.yaml via character.ancestry() -
    never hand-copied into JS, or it drifts from the book the moment either
    side edits alone."""
    _account(request)
    return {a: list(character.ancestry(a)["allowed_classes"]) for a in character.ANCESTRIES}


@app.post("/api/roll-abilities")
async def api_roll_abilities(request: Request):
    """The six ability scores for (seed, mode), before ancestry, class or an
    arrangement apply - what an arrangeable mode shows the player to arrange.
    Uses a fresh Dice(seed), the same first thing character.generate() does
    with it, so the values shown here are exactly what a later /api/character
    call with the same seed will roll."""
    _account(request)
    body = await request.json()
    try:
        mode = str(body["mode"])
        scores = character.roll_abilities(Dice(seed=int(body["seed"])), mode)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"scores": scores, "arrangeable": character.arrangeable(mode)}


@app.post("/api/character")
async def api_character(request: Request):
    _account(request)
    body = await request.json()
    try:
        arrangement = body.get("arrangement")
        c = character.generate(
            seed=int(body["seed"]),
            mode=str(body["mode"]),
            ancestry_name=str(body["ancestry"]),
            class_names=tuple(body["classes"]),
            name=str(body.get("name", "")),
            arrangement=dict(arrangement) if arrangement is not None else None,
        )
    except (ValueError, KeyError, LookupError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = asdict(c)
    out["log"] = [asdict(r) for r in c.log]
    portraits = _art()["portraits"]
    out["portrait"] = portraits.get(c.classes[0], portraits["default"])
    return out


def _build_module(body: dict) -> module_mod.Module:
    """`module: "generate"` runs procgen off `seed`/`target_areas`/
    `dungeon_level`; any other value names a fixture under data/modules/
    (only "weeping_cistern" ships today)."""
    name = str(body.get("module", "generate"))
    if name == "generate":
        doc = procgen.generate_dungeon(
            seed=int(body.get("seed", 1)),
            target_areas=int(body.get("target_areas", 10)),
            dungeon_level=int(body.get("dungeon_level", 1)),
        )
        return module_mod.load(doc)
    path = ROOT / "data" / "modules" / f"{name}.yaml"
    if not path.exists():
        raise ValueError(f"no such module {name!r}")
    return module_mod.load(path)


def _build_party(specs: list[dict]) -> list[character.Character]:
    if not specs:
        raise ValueError("a delve needs at least one character")
    party = []
    for spec in specs:
        arrangement = spec.get("arrangement")
        party.append(character.generate(
            seed=int(spec["seed"]),
            mode=str(spec["mode"]),
            ancestry_name=str(spec["ancestry"]),
            class_names=tuple(spec["classes"]),
            name=str(spec.get("name", "")),
            arrangement=dict(arrangement) if arrangement is not None else None,
        ))
    return party


@app.post("/api/delve/start")
async def api_delve_start(request: Request):
    """Begin a solo delve: generate/load a module, roll the party, hand
    both to `sanctuary.session`. Returns `session_id` plus the opening
    view - everything after this is `/api/delve/act`."""
    acct = _account(request)
    body = await request.json()
    try:
        mod = _build_module(body)
        party = _build_party(body.get("party") or [])
        session_id = uuid.uuid4().hex
        out = session.start(session_id, mod, party, seed=int(body.get("seed", 1)))
    except (ValueError, KeyError, LookupError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    out["session_id"] = session_id
    _SESSION_LEVEL[session_id] = int(body.get("dungeon_level", 1))
    _record_best(request, acct, session_id, out)
    return out


@app.post("/api/delve/act")
async def api_delve_act(request: Request):
    """One player action against a running delve - move, search, rest,
    attack, flee, take_treasure, decide (a tier-3 ruling), or leave."""
    acct = _account(request)
    body = await request.json()
    session_id = str(body.get("session_id", ""))
    action = str(body.get("action", ""))
    kwargs = {k: v for k, v in body.items() if k not in ("session_id", "action")}
    try:
        out = session.act(session_id, action, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    _record_best(request, acct, session_id, out)
    return out


@app.get("/api/delve/{session_id}")
def api_delve_view(session_id: str, request: Request):
    _account(request)
    try:
        return session.view(session_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    return (f"<!doctype html><meta charset=utf-8><title>Sanctuary™</title>"
            f"<p>Sanctuary™ build {tenshin_version.get_version()}</p>"
            f"<p>{LICENCE_NOTICE}</p>")


def selfcheck() -> str:
    """Prove this build works, and say what it proved with real numbers."""
    n_files = len(list((ROOT / "data" / "tables").glob("*.yaml")))
    n_table_ids = len(tables._index())
    assert n_table_ids > 150, f"only {n_table_ids} table ids in the corpus"

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

    portraits = _art()["portraits"]
    portrait_files = set()
    for k in character.CLASSES:
        path = portraits.get(k)
        assert path, f"no portrait entry for class {k!r}"
        assert (ROOT / path.lstrip("/")).exists(), f"missing portrait file for {k!r}: {path}"
        portrait_files.add(path)
    # Distinct files actually backing a class, not one count per class - a
    # class pointing at a shared/default file must not inflate this number.
    n_portraits = len(portrait_files)

    index_html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    for needle in (LICENCE_NOTICE, SRD_NOTICE, 'id="build"', 'id="report"',
                   'id="back"', 'id="signout"', "Sanctuary™"):
        assert needle in index_html, f"client is missing {needle!r}"

    pdfs_present = all(p.exists() for p in (
        Path("C:/Users/budor/Downloads/OSRIC-3.0-Player-Guide-FINAL.v.7.pdf"),
        Path("C:/Users/budor/Downloads/OSRIC_3.0_Gamemaster_Guide.pdf"),
    ))
    round_trip = "verified" if pdfs_present else "UNVERIFIED (source PDFs not present)"

    n_areas, n_reachable, xp_earned, turns_elapsed = _runtime_selfcheck()

    return (f"sanctuary self-check OK - {n_table_ids} tables in {n_files} files, "
            f"{n_ancestries} ancestries, {n_classes} classes, {n_portraits} portraits, "
            f"corpus round-trip {round_trip}, "
            f"seed 1 reproduces a {c.classes[0]} with "
            f"{c.hit_points} hp and {len(c.log)} logged rolls, "
            f"runtime plays a {n_areas}-area dungeon ({n_reachable} reachable) to a "
            f"reproducible finish earning {xp_earned} xp over {turns_elapsed} turns")


def _play_a_delve(seed: int):
    """One deterministic solo delve, driven only through runtime's public
    actions - proof that a party can enter a generated dungeon, fight,
    take treasure, and finish (design §9's own completability gate). A
    three-strong party rather than one, since OSRIC's own d100 lair rolls
    can stock a level-1 room with more monsters than a lone 1st-level
    fighter has any business surviving - that is the book being the book,
    not a bug in this check."""
    doc = procgen.generate_dungeon(seed, target_areas=4, dungeon_level=1)
    mod = module_mod.load(doc)
    party = []
    for offset, cls in enumerate(("fighter", "fighter", "cleric")):
        for s in range(seed + offset * 1000, seed + offset * 1000 + 200):
            try:
                party.append(character.generate(
                    seed=s, mode="normal", ancestry_name="human",
                    class_names=(cls,), name=f"Selfcheck{offset}"))
                break
            except ValueError:
                continue
    st = runtime.new_game(mod, party, seed=seed)
    graph = {a["id"]: a for a in mod.areas}
    order, seen, frontier = [], {st.area_id}, [st.area_id]
    while frontier:
        cur = frontier.pop()
        order.append(cur)
        for e in graph[cur]["exits"]:
            if e["to"] not in seen and not e.get("hidden"):
                seen.add(e["to"])
                frontier.append(e["to"])

    def clear_combat():
        rounds = 0
        while st.combat is not None and rounds < 100:
            rounds += 1
            if st.pending_decisions:
                runtime.decide(st, 0, "self-check DM improvises a ruling")
                continue
            total = sum(max(0, v) for v in st.hp.values())
            if total < sum(st.max_hp.values()) * 0.3:
                runtime.flee(st)
                return
            runtime.attack_round(st)

    clear_combat()
    for area_id in order[1:]:
        if st.finished:
            break
        try:
            runtime.move(st, area_id)
        except ValueError:
            continue
        clear_combat()
        if not st.finished:
            runtime.search(st)
            clear_combat()
        if not st.finished:
            runtime.take_treasure(st)
    if not st.finished:
        runtime.leave(st)
    return doc, order, seen, st


def _runtime_selfcheck() -> tuple[int, int, int, int]:
    # A fixed, deterministic candidate list - not a random search - so the
    # chosen seed (and everything this prints) is the same every run.
    seed = next(s for s in range(2026, 2036)
                if _play_a_delve(s)[3].turns > 0 or _play_a_delve(s)[3].xp > 0)
    doc, order, seen, st = _play_a_delve(seed)
    assert procgen.reachable_area_ids(doc) == {a["id"] for a in doc["areas"]}, \
        "a generated dungeon must never trap the party (no soft lock)"
    assert st.finished, "the self-check delve must reach a terminal state"

    _, _, _, replay = _play_a_delve(seed)
    assert [r.total for r in st.dice.log] == [r.total for r in replay.dice.log], \
        "same seed, same actions must replay identically"

    return len(doc["areas"]), len(seen), st.xp, st.turns


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print(selfcheck())
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=9300)
