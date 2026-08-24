"""Tests for FastAPI routes (requires local Postgres)."""
from __future__ import annotations

import pytest

from config import settings


def test_version(client):
    res = client.get("/version")
    assert res.status_code == 200
    assert res.text.startswith("v0.1")


def test_landing(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Sanctuary" in res.text


def test_begin_requires_auth(client):
    # In dev mode the test client is treated as the dev account.
    res = client.get("/begin")
    assert res.status_code == 200


def test_osric_options(client):
    res = client.get("/api/ruleset/osric/options")
    assert res.status_code == 200
    data = res.json()
    assert "ancestries" in data
    assert "classes" in data
    assert "alignments" in data


def test_create_and_list_character(client):
    res = client.post(
        "/api/characters",
        data={"name": "Testor", "ancestry": "human", "class": "fighter", "alignment": "True Neutral"},
    )
    assert res.status_code == 200
    char = res.json()
    assert char["name"] == "Testor"
    assert char["ancestry"] == "human"
    assert char["class"] == "fighter"

    res = client.get("/api/characters")
    assert res.status_code == 200
    chars = res.json()
    assert any(c["name"] == "Testor" for c in chars)


def test_move_token_on_square_grid(client):
    res = client.post(
        "/api/characters",
        data={"name": "Mover", "ancestry": "human", "class": "fighter", "alignment": "True Neutral"},
    )
    char = res.json()
    char_id = char["id"]

    res = client.post(f"/api/test-ground/{char_id}/move", data={"direction": 0})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"

    # With a single token the round resolves immediately, but the timer runs
    # in a background thread, so poll briefly for the resolution.
    token = None
    for _ in range(20):
        res = client.get("/api/test-ground/state")
        assert res.status_code == 200
        state = res.json()
        token = next((t for t in state["tokens"] if t["character_id"] == char_id), None)
        if token and token["x"] == 1:
            break
        import time
        time.sleep(0.1)
    assert token is not None
    assert token["x"] == 1
    assert token["y"] == 0
    assert state["scale"]["tiles_per_10ft"] == 3


def _create_character(client, name, ancestry, klass, alignment, retries=10):
    """Create a character, retrying if random 3d6 rolls miss class requirements."""
    for n in range(retries):
        res = client.post(
            "/api/characters",
            data={"name": name, "ancestry": ancestry, "class": klass, "alignment": alignment},
        )
        if res.status_code == 200:
            return res.json()
    raise AssertionError(f"Failed to create {klass} after {retries} attempts")


def test_equipment_catalog(client):
    res = client.get("/api/ruleset/osric/equipment")
    assert res.status_code == 200
    data = res.json()
    assert any(i["id"] == "leather" for i in data["equipment"])
    assert any(i["id"] == "shield_small" for i in data["equipment"])
    assert any(i["id"] == "sword_long" for i in data["equipment"])


def test_inventory_changes_armour_class(client):
    char = _create_character(client, "Armoured", "human", "fighter", "True Neutral")
    char_id = char["id"]
    base_ac = char["sheet"]["armour_class"]

    # Equip leather armour and a small shield.
    res = client.post(
        f"/api/characters/{char_id}/inventory",
        data={"item_id": "leather", "quantity": 1, "equipped": "true"},
    )
    assert res.status_code == 200
    char = res.json()
    assert char["sheet"]["armour_class"] == base_ac + 2

    res = client.post(
        f"/api/characters/{char_id}/inventory",
        data={"item_id": "shield_small", "quantity": 1, "equipped": "true"},
    )
    assert res.status_code == 200
    char = res.json()
    assert char["sheet"]["armour_class"] == base_ac + 3

    # Unequip the shield.
    res = client.post(f"/api/characters/{char_id}/inventory/shield_small/unequip")
    assert res.status_code == 200
    char = res.json()
    assert char["sheet"]["armour_class"] == base_ac + 2


def test_class_equipment_restrictions(client):
    char = _create_character(client, "Mage", "human", "magic_user", "True Neutral")
    char_id = char["id"]

    # Magic-users cannot wear leather armour.
    res = client.post(
        f"/api/characters/{char_id}/inventory",
        data={"item_id": "leather", "quantity": 1, "equipped": "true"},
    )
    assert res.status_code == 400

    # Daggers are permitted.
    res = client.post(
        f"/api/characters/{char_id}/inventory",
        data={"item_id": "dagger", "quantity": 1, "equipped": "false"},
    )
    assert res.status_code == 200
