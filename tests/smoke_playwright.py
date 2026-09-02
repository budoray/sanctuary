"""Smoke test: load Sanctuary, create characters, verify UI elements.

Ignores expected backend 400 responses from /api/osric/character when the
rolled scores do not meet class requirements (the UI handles these and
offers re-roll / arrange-to-taste).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8700"

EXPECTED_400_URLS = {"/api/osric/character"}


def run() -> int:
    errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))

        def on_response(resp):
            if resp.status >= 400 and not any(resp.url.endswith(u) for u in EXPECTED_400_URLS):
                errors.append(f"unexpected bad response: {resp.url} -> {resp.status}")

        page.on("response", on_response)

        page.goto(URL)
        page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        page.click("#play-now-btn")
        page.wait_for_selector("#create-modal", state="visible", timeout=10000)

        # Create a fighter and enter dungeon quickly to verify core flow.
        page.select_option("#char-class", "fighter")
        page.click("#roll-character-btn")
        page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
        page.click("#buy-starter-kit")
        page.wait_for_timeout(500)
        page.click("#enter-dungeon-btn")
        page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        page.click("#town-guild")
        page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        page.click(".module-card[data-id='crooked_tower']")
        page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        page.click("#module-brief-depart")
        page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        # Restart and create a cleric using arrange-to-taste to meet requirements.
        page.goto(URL)
        page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        page.click("#play-now-btn")
        page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        page.select_option("#char-class", "cleric")
        page.select_option("#roll-method", "arrange_to_taste")
        page.click("#roll-character-btn")
        page.wait_for_selector("#ability-pool:not(.hidden)", timeout=10000)
        page.click("#auto-arrange-btn")
        page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
        page.click("#buy-starter-kit")
        page.wait_for_timeout(500)
        page.click("#enter-dungeon-btn")
        page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        page.click("#town-guild")
        page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        page.click(".module-card[data-id='crooked_tower']")
        page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        page.click("#module-brief-depart")
        page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        page.wait_for_timeout(1000)

        if not page.locator("#turn-undead-btn").count():
            errors.append("Turn Undead button not found for cleric")
        else:
            print("Turn Undead button present for cleric")

        # Restart as fighter, buy a bow and arrows, equip bow to verify ammo UI.
        page.goto(URL)
        page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        page.click("#play-now-btn")
        page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        page.select_option("#char-class", "fighter")
        page.click("#roll-character-btn")
        page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
        page.click("#buy-starter-kit")
        page.wait_for_timeout(500)

        # Restart as thief to verify Sneak / Find Traps buttons appear.
        page.goto(URL)
        page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        page.click("#play-now-btn")
        page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        page.select_option("#char-class", "thief")
        page.select_option("#roll-method", "arrange_to_taste")
        page.click("#roll-character-btn")
        page.wait_for_selector("#ability-pool:not(.hidden)", timeout=10000)
        page.click("#auto-arrange-btn")
        page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
        page.click("#buy-starter-kit")
        page.wait_for_timeout(500)
        page.click("#enter-dungeon-btn")
        page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        page.click("#town-guild")
        page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        page.click(".module-card[data-id='crooked_tower']")
        page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        page.click("#module-brief-depart")
        page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        page.wait_for_selector("text=Round 1", timeout=10000)
        page.wait_for_timeout(1000)

        if not page.locator("#sneak-btn").count():
            errors.append("Sneak button not found for thief")
        else:
            print("Sneak button present for thief")
        if not page.locator("#search-traps-btn").count():
            errors.append("Search Traps button not found for thief")
        else:
            print("Search Traps button present for thief")

        # Restart as fighter, buy a bow and arrows, equip bow to verify ammo UI.
        page.goto(URL)
        page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        page.click("#play-now-btn")
        page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        page.select_option("#char-class", "fighter")
        page.click("#roll-character-btn")
        page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
        page.click("#buy-starter-kit")
        page.wait_for_timeout(500)

        page.click(".shop-open-btn")
        page.wait_for_selector("#shop-catalog", state="visible", timeout=10000)
        page.click(".shop-tab[data-cat='weapons']")
        page.wait_for_timeout(300)
        page.locator(".shop-modal-row[data-id='bow_short']").dblclick()
        page.click(".shop-tab[data-cat='gear']")
        page.wait_for_timeout(300)
        page.locator(".shop-modal-row[data-id='arrows']").dblclick()
        page.click("#buy-cart-btn")
        page.wait_for_timeout(500)
        page.click("#close-shop-btn")
        page.wait_for_timeout(300)

        # Ensure the bow is equipped before entering the dungeon.
        def ensure_bow_equipped():
            state = page.evaluate("""() => ({
                bow: playerCharacter.sheet.inventory.items.find(i => i.item_id === 'bow_short')?.equipped,
                arrows: playerCharacter.sheet.inventory.items.find(i => i.item_id === 'arrows')?.quantity
            })""")
            return state

        state = ensure_bow_equipped()
        if not state["bow"]:
            page.locator("#inventory-create .equip-btn[data-id='bow_short']").click()
            page.wait_for_timeout(800)
        state = ensure_bow_equipped()
        if not state["bow"]:
            errors.append(f"Could not equip bow: {state}")
        else:
            print("Bow equipped, arrows:", state["arrows"])

        inv = page.locator("#inventory-create").inner_text()
        if "arrows" not in inv.lower():
            errors.append(f"Arrows not listed after buying bow: {inv[:400]!r}")
        else:
            print("Creation inventory shows arrows")

        page.click("#enter-dungeon-btn")
        page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        page.click("#town-guild")
        page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        page.click(".module-card[data-id='crooked_tower']")
        page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        page.click("#module-brief-depart")
        page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        page.wait_for_selector("text=Round 1", timeout=10000)
        page.wait_for_timeout(1000)

        # Make sure no unexpected console/page errors after entering dungeon with bow.
        hint = page.locator("#action-hint").inner_text()
        print("Action hint with bow:", repr(hint))
        if "shoot" not in hint.lower() and "out of ammo" not in hint.lower():
            errors.append(f"Unexpected action hint for bow fighter: {hint!r}")

        browser.close()

    if errors:
        print("FAILURES:")
        for e in errors:
            print(" -", e)
        return 1

    print("Smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
