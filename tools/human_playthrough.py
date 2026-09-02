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
from collections import deque
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8700"


def human_delay(min_ms: int = 400, max_ms: int = 1200):
    time.sleep(random.randint(min_ms, max_ms) / 1000.0)


def think_delay():
    time.sleep(random.randint(1000, 2200) / 1000.0)


def short_pause():
    time.sleep(random.randint(200, 500) / 1000.0)


def log(msg: str):
    print(f"[BOT] {msg}", flush=True)


class HumanBot:
    def __init__(self, page):
        self.page = page
        self.visited_tiles = set()
        self.last_hp = 0

    def run(self):
        self.open_game()
        self.create_character()
        self.play_dungeon()

    def open_game(self):
        log("Opening Sanctuary...")
        self.page.goto(URL)
        self.page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        human_delay()
        self.page.click("#play-now-btn")
        self.page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        log("At character creation.")

    def create_character(self):
        log("Choosing a fighter...")
        self.page.select_option("#char-class", "fighter")
        human_delay()

        # Re-roll until we have a reasonable HP total, then keep that character.
        for attempt in range(10):
            self.page.click("#roll-character-btn")
            self.page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
            hp = self.page.evaluate("""() => playerCharacter?.sheet?.max_hit_points || 0""")
            log(f"Rolled HP: {hp}.")
            if hp >= 6:
                break
            human_delay(300, 700)

        think_delay()
        log("Buying starter kit...")
        self.page.click("#buy-starter-kit")
        self.page.wait_for_timeout(800)

        log("Entering the dungeon.")
        self.page.click("#enter-dungeon-btn")
        self.page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        human_delay()
        self.page.click(".module-card[data-id='crooked_tower']")
        self.page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        self.page.wait_for_selector("text=Round 1", timeout=10000)
        log("Dungeon loaded.")
        think_delay()

    def read_state(self) -> dict | None:
        try:
            return self.page.evaluate("""() => ({
                phase: combatState?.phase || 'player',
                round: combatState?.round || 1,
                acted: combatState?.acted || false,
                attacked: combatState?.attacked || false,
                movementRemaining: combatState?.movementRemaining || 0,
                hp: playerCharacter?.sheet?.hit_points || 0,
                maxHp: playerCharacter?.sheet?.max_hit_points || 1,
                name: playerCharacter?.name || 'Hero',
                playerPos: playerPos,
                monsters: monsters.filter(m => m.alive).map(m => ({x:m.x, y:m.y, hp:m.hp, maxHp:m.maxHp, name:m.name})),
                map: mapData,
                mapW: MAP_W,
                mapH: MAP_H,
                doorsOpened: Array.from(doorsOpened),
                chestsOpened: Array.from(chestsOpened),
                explored: Array.from(explored),
                hint: document.getElementById('action-hint')?.textContent || ''
            })""")
        except Exception as e:
            log(f"Read state failed: {e}")
            return None

    def play_dungeon(self):
        max_rounds = 100
        consecutive_failures = 0
        for _ in range(max_rounds):
            if self.is_game_over():
                title = self.page.locator("#end-title").inner_text()
                msg = self.page.locator("#end-msg").inner_text()
                log(f"Game over: {title} — {msg[:200]}")
                return

            state = self.read_state()
            if not state:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    log("Could not read state multiple times. Stopping.")
                    break
                time.sleep(0.5)
                continue
            consecutive_failures = 0

            log(f"--- Round {state['round']} | {state['name']} HP {state['hp']}/{state['maxHp']} | Move {state['movementRemaining']} | {state['hint'][:55]}...")

            if state["phase"] != "player":
                log("Enemy turn; waiting...")
                self.wait_for_player_phase()
                if self.is_game_over() or (self.read_state() or {}).get("hp", 1) <= 0:
                    if self.is_game_over():
                        title = self.page.locator("#end-title").inner_text()
                        msg = self.page.locator("#end-msg").inner_text()
                        log(f"Game over: {title} — {msg[:200]}")
                    else:
                        log("Character died during enemy turn. Stopping.")
                    return
                continue

            if state["hp"] <= 0:
                log("Character is down. Waiting for resolution.")
                self.wait_for_player_phase()
                if self.is_game_over():
                    title = self.page.locator("#end-title").inner_text()
                    msg = self.page.locator("#end-msg").inner_text()
                    log(f"Game over: {title} — {msg[:200]}")
                else:
                    log("No game-over screen detected after death. Stopping.")
                return

            # Mark current tile as visited at the start of the turn to reduce oscillation.
            px, py = state["playerPos"]["x"], state["playerPos"]["y"]
            self.visited_tiles.add((px, py))

            # Take actions until nothing useful remains.
            for action_count in range(6):
                state = self.read_state()
                if not state or state["phase"] != "player" or state["hp"] <= 0:
                    break
                if not self.take_action(state):
                    break
                if action_count == 5:
                    log("Action limit reached this turn.")

            log("Ending turn.")
            self.end_turn()

        log("Reached max rounds. Stopping playthrough.")

    def is_game_over(self) -> bool:
        try:
            return self.page.locator("#end-modal").is_visible(timeout=300)
        except Exception:
            return False

    def wait_for_player_phase(self):
        dead_ticks = 0
        for _ in range(40):
            if self.is_game_over():
                return
            state = self.read_state()
            if state:
                if state["phase"] == "player":
                    return
                if state["hp"] <= 0:
                    dead_ticks += 1
                    if dead_ticks >= 3:
                        log("Character is dead; waiting for game-over screen.")
                        time.sleep(2)
                        return
            time.sleep(0.5)
        log("Timed out waiting for player phase.")

    def take_action(self, state: dict) -> bool:
        px, py = state["playerPos"]["x"], state["playerPos"]["y"]
        monsters = state["monsters"]
        hp_ratio = state["hp"] / state["maxHp"]

        # 1. Rest if safe and wounded.
        nearby_enemies = [m for m in monsters if self.distance(px, py, m["x"], m["y"]) <= 5]
        if hp_ratio <= 0.5 and not nearby_enemies and self.can_rest():
            log("Wounded and safe — resting.")
            self.page.click("#rest-btn")
            self.wait_state_update(state)
            return True

        # 2. Use potion if available and hurt.
        if hp_ratio <= 0.35 and self.has_potion():
            log("Drinking potion.")
            self.page.click("#use-potion-btn")
            self.wait_state_update(state)
            return True

        # 3. Attack adjacent enemy.
        adjacent = [m for m in monsters if self.distance(px, py, m["x"], m["y"]) == 1]
        if adjacent and not state["attacked"]:
            target = min(adjacent, key=lambda m: m["hp"])
            log(f"Attacking {target['name']}.")
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state)
            return True

        # 4. Open adjacent door.
        door = self.find_adjacent_door(px, py, state)
        if door:
            log(f"Opening door at {door}.")
            self.click_tile(door[0], door[1])
            self.wait_state_update(state)
            return True

        # 5. Move toward nearest interesting tile.
        if state["movementRemaining"] > 0:
            target = self.choose_move_target(state)
            if target:
                log(f"Moving to ({target[0]},{target[1]}).")
                self.click_tile(target[0], target[1])
                self.wait_state_update(state)
                return True

        return False

    def choose_move_target(self, state):
        px, py = state["playerPos"]["x"], state["playerPos"]["y"]
        explored = set(state["explored"])
        map_data = state["map"]
        w, h = state["mapW"], state["mapH"]

        def walkable(x, y):
            if x < 0 or y < 0 or x >= w or y >= h:
                return False
            t = map_data[y][x]
            if t in (".", "E", "C"):
                return True
            if t == "D" and f"{x},{y}" in state["doorsOpened"]:
                return True
            return False

        def value(x, y):
            key = f"{x},{y}"
            t = map_data[y][x]
            if t == "E":
                return 100
            if key not in explored:
                return 50
            if t == "C" and key not in state["chestsOpened"]:
                return 40
            if (x, y) not in self.visited_tiles:
                return 5
            return 0

        queue = deque([(px, py, None)])
        seen = {(px, py)}
        best_step = None
        best_score = -1

        while queue:
            x, y, first_step = queue.popleft()
            score = value(x, y)
            if score > best_score:
                best_score = score
                best_step = first_step
                if score == 100:
                    break
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen or not walkable(nx, ny):
                    continue
                seen.add((nx, ny))
                step = first_step if first_step else (nx, ny)
                queue.append((nx, ny, step))

        return best_step

    def find_adjacent_door(self, px, py, state):
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = px + dx, py + dy
            if 0 <= nx < state["mapW"] and 0 <= ny < state["mapH"]:
                if state["map"][ny][nx] == "D" and f"{nx},{ny}" not in state["doorsOpened"]:
                    return (nx, ny)
        return None

    def click_tile(self, x, y):
        self.page.evaluate(
            """({x, y}) => { if (typeof handleGridClick === 'function') handleGridClick(x, y); }""",
            {"x": x, "y": y},
        )

    def wait_state_update(self, old_state, max_wait: float = 2.5):
        deadline = time.time() + max_wait
        while time.time() < deadline:
            new_state = self.read_state()
            if not new_state:
                break
            if (new_state["playerPos"] != old_state["playerPos"] or
                new_state["movementRemaining"] != old_state["movementRemaining"] or
                new_state["attacked"] != old_state["attacked"] or
                new_state["acted"] != old_state["acted"] or
                new_state["phase"] != old_state["phase"] or
                new_state["hp"] != old_state["hp"] or
                new_state["round"] != old_state["round"]):
                return
            time.sleep(0.15)
        human_delay(300, 700)

    def end_turn(self):
        try:
            btn = self.page.locator("#end-turn-btn")
            if btn.is_enabled(timeout=300):
                btn.click()
                human_delay(600, 1200)
        except Exception as e:
            log(f"End turn failed: {e}")

    def can_rest(self) -> bool:
        try:
            btn = self.page.locator("#rest-btn")
            return btn.count() > 0 and btn.is_enabled(timeout=200)
        except Exception:
            return False

    def has_potion(self) -> bool:
        try:
            btn = self.page.locator("#use-potion-btn")
            return btn.count() > 0 and btn.is_enabled(timeout=200)
        except Exception:
            return False

    def ensure_weapon_equipped(self):
        has_weapon = self.page.evaluate("""() => !!findEquippedMeleeWeapon() || !!findEquippedRangedWeapon()""")
        if not has_weapon:
            log("No weapon equipped; equipping short sword.")
            self.page.locator("#inventory-create .equip-btn[data-id='sword_short']").click()
            self.page.wait_for_timeout(600)

    @staticmethod
    def distance(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)


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
            log("Playthrough finished. Browser stays open for 45 seconds.")
            time.sleep(45)
        except KeyboardInterrupt:
            log("Stopped by user.")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
