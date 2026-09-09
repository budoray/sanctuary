"""Headless Sanctuary playthrough benchmark.

Runs the delve bot as fast as the browser allows, but reports elapsed time
converted to "normal web" seconds using the PixiJS ticker frame count at a
target frame rate (default 60 FPS). This makes headless runs comparable to a
real player watching the game in a browser.
"""
from __future__ import annotations

import argparse
import sys
import time

from playwright.sync_api import sync_playwright

from bot_core import DungeonBot

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8700"
DEFAULT_TARGET_FPS = 60.0


class HeadlessBot(DungeonBot):
    def __init__(
        self,
        page,
        target_fps: float = DEFAULT_TARGET_FPS,
        max_rounds: int = 200,
        ticker_speed: float = 1.0,
        class_id: str = "fighter",
        use_auto_explore: bool = False,
    ):
        super().__init__(page, max_rounds=max_rounds, class_id=class_id)
        self.target_fps = target_fps
        self.ticker_speed = ticker_speed
        self.use_auto_explore = use_auto_explore
        self.start_time = 0.0
        self.end_time = 0.0
        self.start_ticks = 0.0
        self.end_ticks = 0.0
        self.start_fps = 0.0
        self.end_fps = 0.0

    def on_dungeon_loaded(self):
        self.start_time = time.perf_counter()
        self.capture_frame_start()

    def on_run_finished(self):
        self.capture_frame_end()
        self.end_time = time.perf_counter()
        self.report()

    def tiny_wait(self, seconds: float = 0.005):
        time.sleep(seconds)

    def wait_for_player_phase(self):
        dead_ticks = 0
        for _ in range(300):
            if self.is_game_over():
                return
            state = self.read_state()
            if state:
                if state["phase"] == "player":
                    return
                if state["hp"] <= 0:
                    dead_ticks += 1
                    if dead_ticks >= 3:
                        return
            self.tiny_wait(0.02)
        log("Timed out waiting for player phase.")

    def wait_state_update(self, old_state: dict, max_wait: float = 2.0) -> dict | None:
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
            self.tiny_wait(0.03)
        return self.read_state()

    def take_action(self, state: dict) -> bool:
        if not self.use_auto_explore:
            return super().take_action(state)

        px, py = state["playerPos"]["x"], state["playerPos"]["y"]
        monsters = state["monsters"]
        hp_ratio = state["hp"] / state["maxHp"]

        adjacent = [m for m in monsters if self.distance(px, py, m["x"], m["y"]) == 1]
        if adjacent and not state["attacked"]:
            target = min(adjacent, key=lambda m: m["hp"])
            print(f"[BOT] Attacking {target['name']}.")
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True
        if adjacent:
            return False

        if hp_ratio <= 0.5 and not any(m for m in monsters if self.distance(px, py, m["x"], m["y"]) <= 5) and self.can_rest():
            print("[BOT] Wounded and safe — resting.")
            self.page.click("#rest-btn")
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        if hp_ratio <= 0.35 and self.has_potion():
            print("[BOT] Drinking potion.")
            self.page.click("#use-potion-btn")
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        door = self.find_adjacent_door(px, py, state)
        if door:
            print(f"[BOT] Opening door at {door}.")
            self.click_tile(door[0], door[1])
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        # When monsters are visible, fall back to the base pathing logic so the
        # bot can approach or flank instead of auto-explore repeatedly stopping.
        nearby_visible = [m for m in monsters if m["hp"] > 0]
        if nearby_visible and state["movementRemaining"] > 0:
            return super().take_action(state)

        if state["movementRemaining"] > 0:
            if self.auto_explore():
                self.wait_state_update(state, max_wait=2.0)
                self.actions_taken += 1
                return True
        return False

    def capture_frame_start(self):
        info = self.page.evaluate(
            """(speed) => {
                window.__gameTicks = 0;
                const t = app?.ticker;
                if (t) {
                    t.speed = speed;
                    t.add((delta) => { window.__gameTicks = (window.__gameTicks || 0) + delta; });
                }
                return { fps: t?.FPS || 0 };
            }""",
            self.ticker_speed,
        )
        self.start_ticks = 0.0
        self.start_fps = info.get("fps", 0.0)
        print(f"[BOT] Ticker speed set to {self.ticker_speed}. Initial FPS: {self.start_fps:.1f}")

    def capture_frame_end(self):
        info = self.page.evaluate(
            """() => {
                const t = app?.ticker;
                return { ticks: window.__gameTicks || 0, fps: t?.FPS || 0 };
            }"""
        )
        self.end_ticks = info.get("ticks", 0.0)
        self.end_fps = info.get("fps", 0.0)

    def report(self):
        wall_seconds = self.end_time - self.start_time
        ticks = max(0.0, self.end_ticks - self.start_ticks)
        web_seconds = ticks / self.target_fps if self.target_fps else 0.0
        state = self.read_state()
        final_hp = state["hp"] if state else 0
        final_round = state["round"] if state else 0

        print("\n" + "=" * 60)
        print("HEADLESS PLAYTHROUGH REPORT")
        print("=" * 60)
        print(f"Outcome:        {self.outcome}")
        print(f"Final HP:       {final_hp}")
        print(f"Rounds reached: {final_round}")
        print(f"Actions taken:  {self.actions_taken}")
        print(f"Ticker speed:   {self.ticker_speed}x")
        print(f"Observed FPS:   start={self.start_fps:.1f}, end={self.end_fps:.1f}")
        print(f"Game ticks:     {ticks:.2f}")
        print(f"Wall-clock:     {wall_seconds:.3f}s")
        print(f"Web-equivalent ({self.target_fps:.0f} FPS): {web_seconds:.3f}s")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Headless Sanctuary playthrough benchmark")
    parser.add_argument("--url", default=URL, help="Sanctuary base URL")
    parser.add_argument("--class", dest="class_id", default="fighter", help="Character class to play")
    parser.add_argument("--rounds", type=int, default=200, help="Maximum rounds to play")
    parser.add_argument("--fps", type=float, default=DEFAULT_TARGET_FPS, help="Target FPS for time conversion")
    parser.add_argument(
        "--ticker-speed",
        type=float,
        default=1.0,
        help="Pixi ticker speed multiplier (higher = faster headless)",
    )
    parser.add_argument("--headed", action="store_true", help="Run headed (for debugging)")
    parser.add_argument("--auto-explore", action="store_true", help="Use the in-game auto-explore button for movement")
    args = parser.parse_args()

    print("=" * 60)
    print("Sanctuary Headless Playthrough")
    print("=" * 60)
    print(f"Server:      {args.url}")
    print(f"Class:       {args.class_id}")
    print(f"Max rounds:  {args.rounds}")
    print(f"Target FPS:  {args.fps}")
    print(f"Ticker speed: {args.ticker_speed}x")
    print(f"Auto-explore: {args.auto_explore}")
    print("=" * 60, flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not args.headed,
            args=[
                "--disable-frame-rate-limit",
                "--disable-gpu-vsync",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda msg: print(f"[PAGE] {msg.type}: {msg.text}", flush=True))

        try:
            bot = HeadlessBot(
                page,
                target_fps=args.fps,
                max_rounds=args.rounds,
                ticker_speed=args.ticker_speed,
                class_id=args.class_id,
                use_auto_explore=args.auto_explore,
            )
            bot.run()
        except KeyboardInterrupt:
            print("[BOT] Stopped by user.")
        except Exception as e:
            print(f"[BOT] Unhandled error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
