from pathlib import Path

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


def test_selfcheck_reports_real_numbers():
    line = sanctuary_app.selfcheck()
    assert line.startswith("sanctuary self-check OK")
    import re
    assert re.search(r"\d+ tables", line)


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
