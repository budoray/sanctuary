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
