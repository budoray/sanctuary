"""Step definitions for features/client.feature."""
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

import app as sanctuary_app

scenarios("../features/client.feature")

NOTICE = ("Sanctuary is an independent product published under the OSRIC 3.0 "
          "Third-Party License and is not affiliated with Mythmere Games LLC.")


@given("a player opens Sanctuary", target_fixture="page")
def open_sanctuary():
    client = TestClient(sanctuary_app.app)
    r = client.get("/")
    assert r.status_code == 200
    return {"client": client, "body": r.text}


@then("the page carries the OSRIC licence notice")
def page_carries_notice(page):
    assert NOTICE in page["body"]


@then("the game's name carries the trademark symbol")
def name_carries_trademark(page):
    assert "Sanctuary™" in page["body"]


@then("the house chrome appears in the order build, report, back, sign out")
def chrome_in_order(page):
    body = page["body"]
    positions = [body.find(x) for x in
                 ('id="build"', 'id="report"', 'id="back"', 'id="signout"')]
    assert all(p >= 0 for p in positions), f"missing chrome: {positions}"
    assert positions == sorted(positions), "house chrome out of order"


@then("the back door leads to the Tenshin Arts site root, not the games list")
def back_door_is_root(page):
    body = page["body"]
    assert "tenshinarts.com/\"" in body
    assert "/games" not in body


@when("the player rolls a human fighter", target_fixture="rolled")
def roll_human_fighter(page):
    res = page["client"].post("/api/character", json={
        "seed": 4242, "mode": "normal", "ancestry": "human",
        "classes": ["fighter"], "name": "Ilse"})
    assert res.status_code == 200
    return res.json()


@then("the character sheet shows the character's name and ancestry")
def sheet_shows_name(rolled):
    assert rolled["name"] == "Ilse"
    assert rolled["ancestry"] == "human"


@then("the dice tray shows every die that made the character")
def tray_shows_dice(rolled):
    # Six ability scores plus at least one hit-die roll.
    assert len(rolled["log"]) >= 7
    for entry in rolled["log"]:
        assert "faces" in entry and entry["faces"]


@then("the character sheet shows a portrait of their calling")
def sheet_shows_portrait(page, rolled):
    assert rolled["portrait"], "no portrait on the character payload"
    r = page["client"].get(rolled["portrait"])
    assert r.status_code == 200
    assert r.content[:8] == bytes.fromhex("89504e470d0a1a0a")


@when("the player rolls the same character twice with the same seed",
      target_fixture="two_rolls")
def roll_twice(page):
    payload = {"seed": 99, "mode": "normal", "ancestry": "human",
               "classes": ["fighter"], "name": "Twin"}
    a = page["client"].post("/api/character", json=payload).json()
    b = page["client"].post("/api/character", json=payload).json()
    return a, b


@then("both rolls produce the exact same character")
def rolls_match(two_rolls):
    a, b = two_rolls
    assert a == b


@when("the player rolls a human fighter and magic-user", target_fixture="rejected")
def roll_illegal_combo(page):
    return page["client"].post("/api/character", json={
        "seed": 1, "mode": "normal", "ancestry": "human",
        "classes": ["fighter", "magic-user"]})


@then("Sanctuary refuses the combination instead of crashing")
def refuses_gracefully(rejected):
    assert rejected.status_code == 400


@when("the player follows the full licence link", target_fixture="licence_page")
def follow_licence_link(page):
    r = page["client"].get("/licence")
    assert r.status_code == 200
    return r.text


@then("the licence page carries the OSRIC notice and the SRD 5.1 notice")
def licence_page_carries_both(licence_page):
    assert NOTICE in licence_page
    assert "SRD 5.1" in licence_page
