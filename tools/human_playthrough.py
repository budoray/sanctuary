"""Human-speed Sanctuary playthrough bot.

Launches a headed browser, creates a fighter, enters the Crooked Tower,
and plays the dungeon at a pace a human can follow. It makes simple,
cautious decisions: explore, fight adjacent enemies, rest when safe, and
retreat if badly wounded. It does not cheat or use hidden state.
"""
from __future__ import annotations

import random
import sys
import time

from playwright.sync_api import sync_playwright

from bot_core import DungeonBot

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8700"


def human_delay(min_ms: int = 400, max_ms: int = 1200):
    time.sleep(random.randint(min_ms, max_ms) / 1000.0)


def think_delay():
    time.sleep(random.randint(1000, 2200) / 1000.0)


def short_pause():
    time.sleep(random.randint(200, 500) / 1000.0)


class HumanBot(DungeonBot):
    def __init__(self, page, class_id: str = "fighter"):
        super().__init__(page, max_rounds=100, class_id=class_id)

    def tiny_wait(self, seconds: float = 0.005):
        # Add a small human-scale pause to every tiny wait so the spectator
        # can follow the action, without making loop polling unbearable.
        time.sleep(seconds + random.uniform(0.15, 0.35))

    def wait_state_update(self, old_state: dict, max_wait: float = 2.5) -> dict | None:
        deadline = time.time() + max_wait
        while time.time() < deadline:
            new_state = self.read_state()
            if not new_state:
                break
            if (
                new_state["playerPos"] != old_state["playerPos"]
                or new_state["movementRemaining"] != old_state["movementRemaining"]
                or new_state["attacked"] != old_state["attacked"]
                or new_state["acted"] != old_state["acted"]
                or new_state["phase"] != old_state["phase"]
                or new_state["hp"] != old_state["hp"]
                or new_state["round"] != old_state["round"]
            ):
                return new_state
            time.sleep(0.15)
        human_delay(300, 700)
        return self.read_state()

    def wait_for_player_phase(self):
        for _ in range(40):
            if self.is_game_over():
                return
            state = self.read_state()
            if state:
                if state["phase"] == "player":
                    return
                if state["hp"] <= 0:
                    return
            time.sleep(0.5)
        print("[BOT] Timed out waiting for player phase.")

    def open_game(self):
        print("[BOT] Opening Sanctuary...")
        self.page.goto(URL)
        self.page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        human_delay()
        self.page.click("#play-now-btn")
        self.page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        print("[BOT] At character creation.")

    def create_character(self, class_id: str = "fighter"):
        print(f"[BOT] Choosing a {class_id}...")
        self.page.select_option("#char-class", class_id)
        human_delay()

        for attempt in range(10):
            self.page.click("#roll-character-btn")
            self.page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
            hp = self.page.evaluate("""() => playerCharacter?.sheet?.max_hit_points || 0""")
            print(f"[BOT] Rolled HP: {hp}.")
            if hp >= 6:
                break
            human_delay(300, 700)

        think_delay()
        print("[BOT] Buying starter kit...")
        self.page.evaluate(
            """async () => {
                const kit = document.getElementById('buy-starter-kit');
                if (typeof buyStarterKit === 'function') await buyStarterKit();
                else if (kit) kit.click();
            }"""
        )
        self.wait_for_weapon_equipped()

    def wait_for_weapon_equipped(self, timeout: float = 5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            has = self.page.evaluate(
                """() => !!(typeof findEquippedMeleeWeapon === 'function' && findEquippedMeleeWeapon()) ||
                         !!(typeof findEquippedRangedWeapon === 'function' && findEquippedRangedWeapon())"""
            )
            if has:
                return
            time.sleep(0.1)
        print("[BOT] Warning: no weapon equipped after buying starter kit; attempting manual equip.")
        self.ensure_weapon_equipped()

    def navigate_to_dungeon(self):
        print("[BOT] Entering town...")
        self.page.evaluate(
            """() => {
                if (playerCharacter && party.length > 1) {
                    party = [playerCharacter];
                    activePartyIndex = 0;
                    if (typeof refreshAfterTransaction === 'function') refreshAfterTransaction();
                }
            }"""
        )
        status = self.page.evaluate(
            """() => typeof partyReadyForDungeon === 'function' ? partyReadyForDungeon() : { ready: true }"""
        )
        if not status.get("ready"):
            print(f"[BOT] Party not ready: {status.get('reason')}; forcing weapon equip.")
            self.ensure_weapon_equipped()
        self.page.evaluate(
            """async () => {
                if (typeof enterDungeon === 'function') await enterDungeon();
                else document.getElementById('enter-dungeon-btn')?.click();
            }"""
        )
        self.page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        human_delay()
        self.page.click("#town-guild")
        self.page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        human_delay()
        self.page.click(".module-card[data-id='crooked_tower']")
        self.page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        human_delay()
        self.page.click("#module-brief-depart")
        self.page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        self.page.wait_for_selector("text=Round 1", timeout=10000)
        print("[BOT] Dungeon loaded.")
        think_delay()

    def play_dungeon(self):
        consecutive_failures = 0
        for _ in range(self.max_rounds):
            if self.is_game_over():
                self.outcome = self.game_over_text()
                print(f"[BOT] Game over: {self.outcome}")
                return

            state = self.read_state()
            if not state:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    self.outcome = "state read failure"
                    print("[BOT] Could not read state multiple times. Stopping.")
                    return
                time.sleep(0.5)
                continue
            consecutive_failures = 0

            print(
                f"[BOT] --- Round {state['round']} | {state['name']} HP {state['hp']}/{state['maxHp']} | "
                f"Move {state['movementRemaining']} | {state['hint'][:55]}..."
            )

            if state["phase"] != "player":
                print("[BOT] Enemy turn; waiting...")
                self.wait_for_player_phase()
                if self.is_game_over():
                    self.outcome = self.game_over_text()
                    print(f"[BOT] Game over: {self.outcome}")
                    return
                continue

            if state["hp"] <= 0:
                print("[BOT] Character is down. Waiting for resolution.")
                self.wait_for_player_phase()
                self.outcome = self.game_over_text() if self.is_game_over() else "died"
                print(f"[BOT] Character died. Outcome: {self.outcome}")
                return

            for action_count in range(6):
                state = self.read_state()
                if not state or state["phase"] != "player" or state["hp"] <= 0:
                    break
                if not self.take_action(state):
                    break
                if action_count == 5:
                    print("[BOT] Action limit reached this turn.")
                short_pause()

            print("[BOT] Ending turn.")
            self.end_turn()

        self.outcome = f"max rounds ({self.max_rounds}) reached"
        print(f"[BOT] Reached {self.max_rounds} rounds.")

    def end_turn(self):
        try:
            btn = self.page.locator("#end-turn-btn")
            if btn.count() and btn.is_enabled(timeout=300):
                btn.click()
                human_delay(600, 1200)
        except Exception as e:
            print(f"[BOT] End turn failed: {e}")

    def on_run_finished(self):
        print("[BOT] Playthrough finished. Browser stays open for 45 seconds.")
        time.sleep(45)


def main():
    print("=" * 60)
    print("Sanctuary Human-Speed Playthrough Bot")
    print("=" * 60)
    print(f"Server: {URL}")
    print("A headed browser will open so you can watch.")
    print("Press Ctrl+C to stop early.")
    print("=" * 60, flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=60)
        page = browser.new_page(viewport={"width": 1500, "height": 950})
        page.on("console", lambda msg: print(f"[PAGE] {msg.type}: {msg.text}", flush=True))

        try:
            bot = HumanBot(page)
            bot.run()
        except KeyboardInterrupt:
            print("[BOT] Stopped by user.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
