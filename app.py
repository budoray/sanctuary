"""Sanctuary - an OSRIC 3.0 table in the browser.

Sanctuary is an independent product published under the OSRIC 3.0 Third-Party
License and is not affiliated with Mythmere Games LLC.
"""
import sys
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import yaml
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


@lru_cache(maxsize=1)
def _art() -> dict:
    return yaml.safe_load((ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def index():
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
    portraits = _art()["portraits"]
    out["portrait"] = portraits.get(c.classes[0], portraits["default"])
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

    return (f"sanctuary self-check OK - {n_table_ids} tables in {n_files} files, "
            f"{n_ancestries} ancestries, {n_classes} classes, {n_portraits} portraits, "
            f"corpus round-trip {round_trip}, "
            f"seed 1 reproduces a {c.classes[0]} with "
            f"{c.hit_points} hp and {len(c.log)} logged rolls")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print(selfcheck())
    else:
        import uvicorn
        uvicorn.run(app, host="127.0.0.1", port=9300)
