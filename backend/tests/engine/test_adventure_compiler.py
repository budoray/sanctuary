import pytest

from backend.app.engine import adventure_compiler
from backend.app.engine.module import Adventure, AdventureData


def _sample_adventure(**area_overrides):
    data = {
        "module": {
            "title": "Entity Compile Test",
            "version": "1.0",
            "start": "start",
        },
        "regions": [],
        "areas": [
            {
                "id": "start",
                "name": "Starting Area",
                "width": 4,
                "height": 4,
                "tiles": ["1111", "1001", "1001", "1111"],
                "start_x": 1,
                "start_y": 1,
                "exits": [{"to": "hall", "kind": "passage"}],
                "entities": [],
            },
            {
                "id": "hall",
                "name": "Grand Hall",
                "width": 6,
                "height": 6,
                "tiles": ["111111", "100001", "100001", "100001", "100001", "111111"],
                "start_x": 1,
                "start_y": 1,
                "entities": [
                    {"type": "monster", "x": 2, "y": 2, "key": "goblin", "count": 2},
                    {"type": "trap", "x": 4, "y": 2, "key": "spike", "damage": "1d6"},
                    {"type": "treasure", "x": 3, "y": 3, "value": 10},
                ],
            },
        ],
        "monsters": [],
        "items": [],
        "mechanics": [],
    }
    for area in data["areas"]:
        area.update(area_overrides.get(area["id"], {}))
    return Adventure(
        id="entity_compile_test",
        ruleset="osric",
        data=AdventureData.model_validate(data),
    )


def test_compile_converts_entities_to_spawns_and_events():
    adv = _sample_adventure()
    mod = adventure_compiler.compile(adv)

    assert mod.name == "Entity Compile Test"
    assert mod.map.width > 0
    assert mod.map.height > 0

    goblins = [m for m in mod.monsters if m.monster == "goblin"]
    assert len(goblins) == 2
    assert goblins[0].x >= 0 and goblins[0].y >= 0

    traps = [e for e in mod.events if "triggers" in e.message.lower()]
    assert traps
    assert traps[0].choices == {"ok": "trap:1d6"}

    treasures = [e for e in mod.events if "treasure" in e.message.lower()]
    assert treasures


def test_compile_ignores_out_of_bounds_entities():
    adv = _sample_adventure(hall={"entities": [{"type": "monster", "x": 50, "y": 50, "key": "goblin"}]})
    mod = adventure_compiler.compile(adv)
    assert not any(m.monster == "goblin" for m in mod.monsters)


def test_compile_falls_back_to_default_tiles_when_missing():
    adv = _sample_adventure(start={"tiles": None, "width": 4, "height": 4})
    mod = adventure_compiler.compile(adv)
    assert mod.map.width > 0
    assert mod.map.height > 0
