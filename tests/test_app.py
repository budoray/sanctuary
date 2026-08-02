import os
from pathlib import Path

# ⚠ BEFORE `import app`, which imports `tenshin_gate` - the drop-in latches
# TENSHIN_DEV into a module constant at import time, so setting it inside a
# test does nothing at all. Every route this suite hits unauthenticated needs
# dev mode to reach it without a signed session cookie.
os.environ.setdefault("TENSHIN_DEV", "1")

import yaml
from fastapi.testclient import TestClient

import app as sanctuary_app
from sanctuary import character

NOTICE = ("Sanctuary is an independent product published under the OSRIC 3.0 "
          "Third-Party License and is not affiliated with Mythmere Games LLC.")

PNG_MAGIC = bytes.fromhex("89504e470d0a1a0a")
ROOT = Path(__file__).resolve().parent.parent

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


def test_the_client_itself_carries_the_srd_notice():
    # Both notices ship in both places (the design record's own words) -
    # /licence had the SRD notice, the client index did not.
    assert "SRD 5.1" in client.get("/").text


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
    assert "Sanctuary™" in client.get("/").text


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


def test_roll_abilities_api_returns_the_six_rolled_scores():
    r = client.post("/api/roll-abilities", json={"seed": 13, "mode": "flexible"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["scores"]) == set(character.ABILITIES)
    assert body["arrangeable"] is True


def test_roll_abilities_api_matches_the_character_api_for_the_same_seed():
    # The whole point: what the player arranges is exactly what generate()
    # would have rolled anyway - roll-abilities never gets its own dice draws.
    rolled = client.post("/api/roll-abilities", json={"seed": 13, "mode": "flexible"}).json()
    c = client.post("/api/character", json={
        "seed": 13, "mode": "flexible", "ancestry": "human", "classes": ["fighter"],
    }).json()
    assert rolled["scores"] == c["scores"]


def test_roll_abilities_api_reports_non_arrangeable_modes():
    r = client.post("/api/roll-abilities", json={"seed": 13, "mode": "normal"})
    assert r.json()["arrangeable"] is False


def test_character_api_accepts_an_arrangement_for_an_arrangeable_mode():
    rolled = client.post("/api/roll-abilities", json={"seed": 13, "mode": "flexible"}).json()["scores"]
    arrangement = dict(zip(character.ABILITIES, sorted(rolled.values(), reverse=True)))
    r = client.post("/api/character", json={
        "seed": 13, "mode": "flexible", "ancestry": "human", "classes": ["fighter"],
        "arrangement": arrangement,
    })
    assert r.status_code == 200
    assert r.json()["scores"]["strength"] == max(rolled.values())


def test_character_api_rejects_an_arrangement_for_a_non_arrangeable_mode():
    rolled = client.post("/api/roll-abilities", json={"seed": 13, "mode": "normal"}).json()["scores"]
    arrangement = dict(zip(character.ABILITIES, sorted(rolled.values(), reverse=True)))
    r = client.post("/api/character", json={
        "seed": 13, "mode": "normal", "ancestry": "human", "classes": ["fighter"],
        "arrangement": arrangement,
    })
    assert r.status_code == 400
    assert "normal" in r.json()["detail"]


def test_character_api_rejects_a_bad_arrangement_with_a_useful_message():
    r = client.post("/api/character", json={
        "seed": 13, "mode": "flexible", "ancestry": "human", "classes": ["fighter"],
        "arrangement": {**{k: 10 for k in character.ABILITIES}, "strength": 99},
    })
    assert r.status_code == 400
    assert "permutation" in r.json()["detail"]


# ── Fix 1: ancestry->class access is known before any dice roll ─────────────
def test_ancestry_classes_endpoint_covers_all_seven_ancestries():
    body = client.get("/api/ancestry-classes").json()
    assert set(body) == set(character.ANCESTRIES)


def test_ancestry_classes_endpoint_reflects_the_data_not_a_hardcoded_map():
    body = client.get("/api/ancestry-classes").json()
    assert "monk" not in body["half-elf"]
    assert "monk" in body["human"]
    assert body["half-elf"] == character.ancestry("half-elf")["allowed_classes"]


# ── Fix 2: a 400 must never render as though it were a character sheet ─────
def test_a_rejected_roll_does_not_produce_a_rendered_sheet():
    """The client's error path must exist as markup - a distinct error
    region, not the #who name field re-purposed to carry the message. A
    string check here would pass on the broken version (the message DID
    render, just in the wrong place)."""
    html = client.get("/").text
    assert 'id="forge-error"' in html
    assert 'id="who"' in html
    # The error region and the character name are not the same element.
    assert html.index('id="forge-error"') != html.index('id="who"')


def test_begin_a_delve_is_disabled_until_a_character_exists():
    html = client.get("/").text
    import re
    m = re.search(r'<button id="begin-delve"[^>]*>', html)
    assert m and "disabled" in m.group(0)


def test_selfcheck_reports_real_numbers():
    line = sanctuary_app.selfcheck()
    assert line.startswith("sanctuary self-check OK")
    import re
    assert re.search(r"\d+ tables", line)


def test_selfcheck_portrait_count_is_distinct_files_not_one_per_class():
    # A portrait count computed by incrementing once per class always equals
    # len(CLASSES) - even if two classes shared one file, or all ten did.
    # This pins that the number in the sentence is a distinct-file count by
    # checking it against the same set the sentence is supposed to describe.
    import re
    portraits = sanctuary_app._art()["portraits"]
    distinct = len({portraits[k] for k in character.CLASSES})
    line = sanctuary_app.selfcheck()
    m = re.search(r"(\d+) portraits", line)
    assert m and int(m.group(1)) == distinct


def test_selfcheck_states_whether_the_round_trip_is_verified():
    line = sanctuary_app.selfcheck()
    assert "round-trip" in line
    assert "verified" in line or "UNVERIFIED" in line


def _art():
    return yaml.safe_load((ROOT / "data" / "art.yaml").read_text(encoding="utf-8"))


def test_every_class_has_a_portrait_entry_and_file():
    portraits = _art()["portraits"]
    for k in character.CLASSES:
        path = portraits.get(k)
        assert path, f"no portrait entry for {k!r}"
        assert (ROOT / path.lstrip("/")).exists(), f"portrait file missing: {path}"


def test_every_portrait_is_actually_served():
    portraits = _art()["portraits"]
    for k, path in portraits.items():
        r = client.get(path)
        assert r.status_code == 200, f"{path} did not serve (class {k!r})"
        assert r.content[:8] == PNG_MAGIC, f"{path} is not a PNG"


def test_the_client_carries_a_portrait_element():
    assert 'id="portrait"' in client.get("/").text


def test_selfcheck_sentence_reports_unique_ids_and_files():
    from sanctuary import tables
    n_files = len(list((ROOT / "data" / "tables").glob("*.yaml")))
    n_ids = len(tables._index())
    line = sanctuary_app.selfcheck()
    assert f"{n_ids} tables in {n_files} files" in line


# ── auth (JOB 1) ─────────────────────────────────────────────────────────────
# The no-cookie-gets-401 / platform-routes-stay-open matrix is proved properly
# in tests/test_auth.py, in a SUBPROCESS with TENSHIN_DEV stripped - DEV_MODE
# is a module constant latched at import time, so it cannot be toggled mid
# process. This suite only needs to prove the OTHER half: that dev mode, once
# on, actually lets a guarded route through.
def test_tenshin_dev_bypasses_the_gate():
    assert sanctuary_app.tenshin_gate.DEV_MODE is True, \
        "the rest of this suite depends on dev mode being on"
    assert client.get("/").status_code == 200
    assert client.get("/leaderboard.json").status_code == 200


# ── leaderboard (JOB 2) ───────────────────────────────────────────────────────
# ── client wiring: exits must be real, reachable controls ────────────────────
# A test asserting "the word 'passage' appears" passes on a bare <li> just as
# easily as on a working <button> - it has to grab the block that builds
# #exits from view.exits and assert the control and its wiring, not the text.
def _exits_render_block() -> str:
    import re
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    m = re.search(r"view\.exits\.forEach\(\(e\) => \{(.*?)\}\);", js, re.S)
    assert m, "no view.exits.forEach block found in static/app.js"
    return m.group(1)


def test_exits_render_as_a_focusable_button_carrying_the_target_area_id():
    block = _exits_render_block()
    assert 'createElement("button")' in block, \
        "an exit must be a real <button> - a bare <li> is not focusable or keyboard-operable"
    assert "dataset.to" in block, \
        "the exit's target area id must live in a data-to attribute, not be parsed back out of the label"


def test_exit_buttons_are_disabled_while_a_decision_is_pending():
    block = _exits_render_block()
    assert "decisionPending" in block, \
        "movement must be visibly disabled while a decision is pending, not silently inert"


def test_leaderboard_gains_a_row_after_a_delve_and_ranks_it_by_xp():
    r = client.post("/api/delve/start", json={
        "module": "weeping_cistern",
        "party": [{"seed": 777, "mode": "normal", "ancestry": "human",
                   "classes": ["fighter"], "name": "Boardtest"}],
    })
    assert r.status_code == 200
    board = client.get("/leaderboard.json").json()["board"]
    assert board, "a completed delve start left no row on the board"
    row = board[0]
    assert {"name", "score", "level", "stat"} <= set(row)
    assert isinstance(row["stat"], str) and row["stat"].strip()
    assert board == sorted(board, key=lambda r: -r["score"]), \
        "the board is not ranked on score"
