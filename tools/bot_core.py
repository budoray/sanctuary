"""Shared dungeon bot core for Sanctuary playthrough tools.

This module contains the navigation and combat decision logic used by both the
human-speed spectator bot and the headless benchmark bot. Subclasses override
timing methods to control pacing.
"""
from __future__ import annotations

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")


def log(msg: str):
    print(f"[BOT] {msg}", flush=True)


class DungeonBot:
    """Reusable delve autopilot. Only visible game state is used."""

    def __init__(self, page, max_rounds: int = 100, class_id: str = "fighter"):
        self.page = page
        self.max_rounds = max_rounds
        self.class_id = class_id
        self.blocked_tiles: set[tuple[int, int]] = set()
        self.visited_tiles: set[tuple[int, int]] = set()
        self.warded_exits: set[tuple[int, int]] = set()
        self.known_monster_spawns: list[tuple[int, int]] = []
        self.visited_spawns: set[tuple[int, int]] = set()
        self.last_monster_positions: dict[tuple[int, int], str] = {}
        self.last_pos: tuple[int, int] | None = None
        self.actions_taken = 0
        self.sneaked_this_turn = False
        self.outcome = "unknown"
        self.spells_cast_this_turn: set[str] = set()

    # ------------------------------------------------------------------
    # Timing hooks (override in subclasses)
    # ------------------------------------------------------------------
    def tiny_wait(self, seconds: float = 0.005):
        time.sleep(seconds)

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

    def end_turn(self):
        try:
            btn = self.page.locator("#end-turn-btn")
            if btn.count() and btn.is_enabled(timeout=300):
                btn.click()
                self.tiny_wait(0.05)
        except Exception as e:
            log(f"End turn failed: {e}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def run(self):
        self.open_game()
        self.create_character(self.class_id)
        self.navigate_to_dungeon()
        self.on_dungeon_loaded()
        self.play_dungeon()
        self.on_run_finished()

    def on_dungeon_loaded(self):
        """Hook for subclasses to set up measurement hooks."""

    def on_run_finished(self):
        """Hook for subclasses to print reports."""

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def open_game(self):
        log("Opening Sanctuary...")
        self.page.goto(self.url())
        self.page.wait_for_selector("#play-now-btn", state="visible", timeout=10000)
        self.page.click("#play-now-btn")
        self.page.wait_for_selector("#create-modal", state="visible", timeout=10000)
        log("At character creation.")

    def url(self) -> str:
        return "http://127.0.0.1:8700"

    def create_character(self, class_id: str = "fighter"):
        log(f"Choosing a {class_id}...")
        self.page.select_option("#char-class", class_id)
        self.tiny_wait()

        # Fragile classes (d4 HD) cannot reach 6 HP at level 1 even with +1 CON.
        min_hp = 4 if class_id in ("magic_user", "illusionist") else 6
        for attempt in range(10):
            self.page.click("#roll-character-btn")
            self.page.wait_for_selector("#rolled-abilities .ability-grid", state="visible", timeout=10000)
            hp = self.page.evaluate("""() => playerCharacter?.sheet?.max_hit_points || 0""")
            log(f"Rolled HP: {hp}.")
            if hp >= min_hp:
                break
            self.tiny_wait()

        log("Buying starter kit...")
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
            self.tiny_wait(0.05)
        log("Warning: no weapon equipped after buying starter kit; attempting manual equip.")
        self.ensure_weapon_equipped()

    def ensure_weapon_equipped(self):
        has_weapon = self.page.evaluate(
            """() => !!(typeof findEquippedMeleeWeapon === 'function' && findEquippedMeleeWeapon()) ||
                     !!(typeof findEquippedRangedWeapon === 'function' && findEquippedRangedWeapon())"""
        )
        if has_weapon:
            return
        item_id = self.page.evaluate(
            """() => {
                const items = playerCharacter?.sheet?.inventory?.items || [];
                const weapon = items.find(i => {
                    const it = osricOptions?.equipment?.find(e => e.id === i.item_id);
                    return it?.category === 'weapons';
                });
                return weapon?.item_id || null;
            }"""
        )
        if item_id:
            log(f"No weapon equipped; equipping {item_id}.")
            self.page.locator(f"#inventory-create .equip-btn[data-id='{item_id}']").click()
            self.page.wait_for_timeout(500)
        else:
            log("No weapon found in inventory.")

    def close_blocking_modals(self):
        """Close any visible message/confirm modal that blocks interaction."""
        try:
            for modal_id in ["message-modal", "confirm-modal"]:
                modal = self.page.locator(f"#{modal_id}")
                if modal.count() and modal.is_visible(timeout=200):
                    close = modal.locator(".modal-close, button").first
                    if close.count() and close.is_visible(timeout=200):
                        close.click()
                    else:
                        self.page.evaluate(f"() => {{ const m = document.getElementById('{modal_id}'); if (m) m.classList.add('hidden'); }}")
        except Exception:
            pass

    def hire_mercenaries(self):
        """Hire complementary mercenaries directly through JS game state."""
        try:
            # Ensure the mercenary pool is populated without touching the DOM.
            self.page.evaluate("""async () => {
                if (typeof ensureMercenaries === 'function') await ensureMercenaries();
            }""")

            state = self.page.evaluate(
                r"""() => {
                    const pcClass = playerCharacter?.class || 'fighter';
                    // Strong front-line classes first; fragile casters only if nothing better is available.
                    const desired = ['fighter', 'cleric', 'paladin', 'ranger', 'thief', 'magic_user', 'illusionist'];
                    const isFrontLine = (id) => ['fighter', 'paladin', 'ranger', 'cleric'].includes(id);
                    const isFragilePC = ['magic_user', 'illusionist'].includes(pcClass);
                    const mercs = availableMercenaries.map((m, idx) => ({
                        idx,
                        classId: m.class || '',
                        level: m.sheet?.level || 1,
                        cost: (m.dailyWage || 2) * 7,
                    }));

                    let gold = campaign?.campaign_gold || 0;
                    const hired = [];
                    // Hire up to two mercenaries, prioritising front-line tanks/healers.
                    while (hired.length < 2 && gold > 0) {
                        let best = null, bestScore = -Infinity;
                        for (const m of mercs) {
                            if (hired.some(h => h.idx === m.idx)) continue;
                            if (m.cost > gold) continue;
                            if (party.length + hired.length >= 5) break;
                            let score = desired.indexOf(m.classId);
                            if (score < 0) score = -100;
                            // Front-line mercs are always preferred; fragile PCs need them even more.
                            if (isFrontLine(m.classId)) score += 100;
                            if (isFragilePC && isFrontLine(m.classId)) score += 50;
                            score += m.level * 10 - m.cost / 10;
                            if (score > bestScore) { bestScore = score; best = m; }
                        }
                        if (!best) break;
                        if (typeof hireMercenary === 'function') hireMercenary(best.idx);
                        hired.push(best);
                        gold -= best.cost;
                    }
                    return {
                        gold: campaign?.campaign_gold || 0,
                        partySize: party.length,
                        mercCount: availableMercenaries.length,
                        hired: hired.map(h => ({ classId: h.classId, level: h.level, cost: h.cost })),
                    };
                }"""
            )
            if state["hired"]:
                log(f"Hired mercenaries: {state['hired']}")
            else:
                log(f"No mercenaries hired. gold={state['gold']}, party={state['partySize']}, available={state['mercCount']}")
            self.tiny_wait(0.3)
        except Exception as e:
            log(f"Mercenary hiring failed: {e}")
        finally:
            # Always close any stray modal.
            self.close_blocking_modals()

    def navigate_to_dungeon(self):
        log("Entering town...")
        # Roll retries may leave multiple unarmed characters in the party; keep only the active one.
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
            log(f"Party not ready: {status.get('reason')}; forcing weapon equip.")
            self.ensure_weapon_equipped()
        self.page.evaluate(
            """async () => {
                if (typeof enterDungeon === 'function') await enterDungeon();
                else document.getElementById('enter-dungeon-btn')?.click();
            }"""
        )
        self.page.wait_for_selector("#town-screen", state="visible", timeout=10000)
        self.tiny_wait(0.5)
        self.hire_mercenaries()
        self.tiny_wait(0.2)
        self.page.evaluate("() => document.getElementById('town-guild')?.click()")
        self.page.wait_for_selector("#module-list .module-card", state="visible", timeout=10000)
        self.page.evaluate("() => document.querySelector(\".module-card[data-id='crooked_tower']\")?.click()")
        self.page.wait_for_selector("#module-brief-modal", state="visible", timeout=10000)
        self.page.evaluate("() => document.getElementById('module-brief-depart')?.click()")
        self.page.wait_for_selector("#board-canvas canvas", state="visible", timeout=10000)
        self.page.wait_for_selector("text=Round 1", timeout=10000)
        mod_info = self.page.evaluate(
            """() => ({
                module: dungeonModuleName,
                exitTile: mapData?.[3]?.[18],
                monsters: monsters.map(m => ({name: m.name, x: m.x, y: m.y}))
            })"""
        )
        self.known_monster_spawns = [(m["x"], m["y"]) for m in mod_info.get("monsters", [])]
        log(f"Dungeon loaded: {mod_info}")

    def read_state(self) -> dict | None:
        try:
            return self.page.evaluate("""() => ({
                phase: combatState?.phase || 'player',
                round: combatState?.round || 1,
                acted: combatState?.acted || false,
                attacked: combatState?.attacked || false,
                movementRemaining: combatState?.movementRemaining || 0,
                activePartyIndex: (typeof activePartyIndex !== 'undefined' ? activePartyIndex : 0),
                hp: playerCharacter?.sheet?.hit_points || 0,
                maxHp: playerCharacter?.sheet?.max_hit_points || 1,
                name: playerCharacter?.name || 'Hero',
                playerPos: playerPos,
                monsters: monsters.filter(m => m.alive).map(m => ({x:m.x, y:m.y, hp:m.hp, maxHp:m.maxHp, name:m.name})),
                map: mapData,
                mapW: MAP_W,
                mapH: MAP_H,
                doorsOpened: Array.from(doorsOpened),
                doorsLocked: Array.from(doorsLocked),
                chestsOpened: Array.from(chestsOpened),
                chestsWithKey: Array.from(chestsWithKey),
                inventory: playerCharacter?.sheet?.inventory?.items || [],
                explored: Array.from(explored),
                hint: document.getElementById('action-hint')?.textContent || ''
            })""")
        except Exception as e:
            log(f"Read state failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Dungeon loop
    # ------------------------------------------------------------------
    def play_dungeon(self):
        consecutive_failures = 0
        hero_turns = 0
        while hero_turns < self.max_rounds:
            if self.is_game_over():
                self.outcome = self.game_over_text()
                log(f"Game over: {self.outcome}")
                return

            state = self.read_state()
            if not state:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    self.outcome = "state read failure"
                    log("Could not read state multiple times. Stopping.")
                    return
                self.tiny_wait(0.1)
                continue
            consecutive_failures = 0

            if state["hp"] <= 0:
                # Unconscious, not necessarily dead. Try to bind wounds / rest if safe.
                for _ in range(20):
                    if self.is_game_over():
                        break
                    if self.can_rest():
                        try:
                            self.page.click("#rest-btn")
                            self.wait_state_update(state, max_wait=1.0)
                            log("Bind wounds while unconscious.")
                            break
                        except Exception as e:
                            log(f"Rest while down failed: {e}")
                    self.tiny_wait(0.05)
                if self.is_game_over():
                    self.outcome = self.game_over_text()
                    log(f"Game over: {self.outcome}")
                    return
                # If rest did not wake the character, wait for the enemy phase / death
                # saves to resolve instead of spinning through the outer loop.
                self.wait_for_player_phase()
                continue

            if state["phase"] != "player":
                self.wait_for_player_phase()
                if self.is_game_over():
                    self.outcome = self.game_over_text()
                    log(f"Game over: {self.outcome}")
                    return
                continue

            # When mercenaries are auto-piloted, the game cycles through the
            # party. Only act on the hero's turn (party index 0); wait out
            # mercenary turns so we do not click hero actions onto a hireling.
            if state.get("activePartyIndex", 0) != 0:
                log(f"Mercenary turn active ({state.get('activePartyIndex', 0)}); waiting.")
                self.tiny_wait(0.2)
                continue

            self.blocked_tiles.clear()
            self.sneaked_this_turn = False
            self.spells_cast_this_turn.clear()
            self.retreated_this_turn = False
            all_fled = state["monsters"] and all(not m.get("alive") or m.get("fled") for m in state["monsters"])
            if not state["monsters"] or all_fled:
                self.warded_exits.clear()
                self.last_monster_positions.clear()
                self.retreated_from = None
            else:
                self.last_monster_positions = {
                    (m["x"], m["y"]): m["name"] for m in state["monsters"]
                }
                # Once the threat is visible again (or the enemy has closed),
                # clear the ranged-kite guard so the hero can shoot or re-position.
                visible_enemy = self.page.evaluate(
                    """() => monsters.some(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))"""
                )
                if visible_enemy:
                    self.retreated_from = None
            self.last_pos = (state['playerPos']['x'], state['playerPos']['y'])
            log(f"Turn start: round {state['round']}, hp {state['hp']}/{state['maxHp']}, pos ({state['playerPos']['x']},{state['playerPos']['y']}), mov {state['movementRemaining']}, attacked {state['attacked']}, monsters {len(state['monsters'])}")

            for _ in range(6):
                if self.is_game_over():
                    self.outcome = self.game_over_text()
                    log(f"Game over: {self.outcome}")
                    return
                state = self.read_state()
                if not state or state["phase"] != "player" or state["hp"] <= 0:
                    break
                if state.get("activePartyIndex", 0) != 0:
                    break
                if not self.take_action(state):
                    break

            if self.is_game_over():
                self.outcome = self.game_over_text()
                log(f"Game over: {self.outcome}")
                return
            self.end_turn()
            hero_turns += 1

        self.outcome = f"max rounds ({self.max_rounds}) reached"
        log(f"Reached {self.max_rounds} hero turns.")

    def is_game_over(self) -> bool:
        try:
            return self.page.locator("#end-modal").is_visible(timeout=200)
        except Exception:
            return False

    def game_over_text(self) -> str:
        try:
            title = self.page.locator("#end-title").inner_text(timeout=500)
            msg = self.page.locator("#end-msg").inner_text(timeout=500)
            return f"{title} — {msg[:200]}"
        except Exception as e:
            return f"unknown ({e})"

    def take_action(self, state: dict) -> bool:
        if self.is_game_over():
            return False
        px, py = state["playerPos"]["x"], state["playerPos"]["y"]
        monsters = state["monsters"]
        hp_ratio = state["hp"] / state["maxHp"]

        visible_enemy = self.page.evaluate(
            """() => monsters.some(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))"""
        )
        adjacent_enemy = [m for m in monsters if self.distance(px, py, m["x"], m["y"]) == 1 and not m.get("fled")]
        in_danger = adjacent_enemy or visible_enemy

        # Ranged enemies can chip away while we rest; treat them as a rest hazard
        # if they are visible and in range.
        ranged_hazard = self.page.evaluate(
            """() => monsters.some(m => m.alive && !m.fled && m.ranged && isVisibleToPlayer(m.x, m.y) &&
                (Math.abs(m.x - playerPos.x) + Math.abs(m.y - playerPos.y)) <= Math.floor(m.ranged.range / 10))"""
        )

        # Class-specific emergency actions.
        if not state["attacked"]:
            # Crowd control first: Sleep trivialises level-1 mobs. A single
            # Sleep can neutralise an entire Crooked Tower pull, so it is almost
            # always a better opener than Magic Missile.
            if self.cast_sleep(state):
                self.actions_taken += 1
                return True
            # Magic Missile is a guaranteed-hit alpha strike for mages.
            if self.cast_magic_missile(state):
                self.actions_taken += 1
                return True
            # Cleric healing is an action, so use it before the fight gets out
            # of hand. A wounded cleric standing in melee will not survive.
            if self.cast_cleric_heal(state):
                self.actions_taken += 1
                return True
            # Defensive pre-buff only when already threatened; at level 1 the
            # slot is usually better spent on Sleep/Magic Missile.
            if self.cast_shield(state):
                self.actions_taken += 1
                return True
            # Bless is only worth an action if the cleric is healthy and facing
            # a swarm; otherwise just attack.
            if self.cast_bless(state):
                self.actions_taken += 1
                return True
            if self.try_ranged_attack(state):
                self.actions_taken += 1
                return True

        # Use potions earlier when threatened so the bot does not enter a death spiral.
        if hp_ratio <= (0.70 if in_danger else 0.40) and self.has_potion():
            log("Drinking potion.")
            try:
                self.page.locator("#use-potion-btn").click(timeout=500)
            except Exception as e:
                log(f"Potion click failed: {e}")
                return False
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        # Rest to full when it is genuinely safe and worthwhile. Resting while
        # enemies are nearby burns the whole turn; only do it when clearly
        # wounded and not immediately threatened.
        rest_threshold = 0.50 if in_danger else 0.85
        if (
            monsters
            and not adjacent_enemy
            and not ranged_hazard
            and self.can_rest()
            and hp_ratio <= rest_threshold
        ):
            log(f"Wounded ({state['hp']}/{state['maxHp']}) — resting.")
            try:
                self.page.click("#rest-btn")
            except Exception:
                return False
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        # Thief: sneak only when there is a visible target worth backstabbing
        # nearby. Sneaking every turn wastes the action and slows the whole run.
        if (
            self.is_thief()
            and not adjacent_enemy
            and not self.sneaked_this_turn
            and not self.is_stealthed()
            and self.can_sneak()
        ):
            nearby_visible = self.page.evaluate(
                """() => monsters.filter(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))
                             .map(m => ({x:m.x, y:m.y, hp:m.hp, name:m.name}))"""
            )
            close_enough = any(
                self.distance(px, py, m["x"], m["y"]) <= 5 for m in nearby_visible
            )
            if close_enough:
                log("Sneaking.")
                self.page.click("#sneak-btn")
                self.wait_state_update(state, max_wait=1.0)
                self.sneaked_this_turn = True
                self.actions_taken += 1
                return True

        adjacent = [m for m in monsters if self.distance(px, py, m["x"], m["y"]) == 1 and not m.get("fled")]

        # Survival retreat for fragile classes. Fighters can stand and fight;
        # clerics, mages, and thieves with ranged weapons should kite instead of
        # trading melee blows.
        fragile_class = self.player_class() in ("cleric", "magic_user", "illusionist", "thief")
        has_ranged = self.has_ranged_weapon(state)
        retreat_reason = None
        if fragile_class and adjacent and state["movementRemaining"] > 0:
            if hp_ratio <= 0.35:
                retreat_reason = "low_hp"
            elif len(adjacent) >= 2:
                retreat_reason = "outnumbered"
            elif any("Grik" in m.get("name", "") for m in adjacent):
                retreat_reason = "boss"
            elif has_ranged and not self.is_thief():
                retreat_reason = "ranged_kite"
            elif self.is_thief() and hp_ratio <= 0.50:
                retreat_reason = "thief_wounded"
            elif self.is_thief() and any(m.get("ranged") for m in adjacent):
                retreat_reason = "thief_ranged"
        if retreat_reason:
            prefer_range = retreat_reason == "ranged_kite"
            weapon_range = self.ranged_weapon_range(state) if prefer_range else 0
            retreat = self.find_retreat_tile(state, prefer_range=prefer_range, weapon_range=weapon_range)
            if retreat:
                # Never retreat back and forth in the same turn.
                if getattr(self, "retreated_from", None) == (retreat["x"], retreat["y"]):
                    log(f"Already retreated to {retreat}; standing ground.")
                else:
                    log(f"Retreating to ({retreat['x']},{retreat['y']}) [{retreat_reason}].")
                    self.retreated_from = (px, py)
                    # Fragile ranged classes that kited should not immediately walk
                    # back into the danger tile in the same turn; doing so creates
                    # the (12,12) <-> (13,12) oscillation that wastes whole rounds.
                    if prefer_range:
                        self.retreated_this_turn = True
                    self.click_tile(retreat["x"], retreat["y"])
                    self.wait_state_update(state, max_wait=0.5)
                    self.actions_taken += 1
                    return True

        if adjacent and not state["attacked"]:
            target = min(adjacent, key=lambda m: m["hp"])
            log(f"Attacking {target['name']}.")
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        # Thief hit-and-run: after an attack, only fade if actually threatened.
        # Otherwise the loop wastes movement and never finishes a wounded foe.
        if (
            state["attacked"]
            and self.is_thief()
            and state["movementRemaining"] > 0
            and (
                hp_ratio <= 0.50
                or len(adjacent) >= 2
                or any(m.get("ranged") for m in adjacent)
            )
        ):
            retreat = self.find_retreat_tile(state)
            if retreat:
                log(f"Thief fading away to ({retreat['x']},{retreat['y']}).")
                self.click_tile(retreat["x"], retreat["y"])
                self.wait_state_update(state, max_wait=0.5)
                self.actions_taken += 1
                return True

        # Don't try to move while adjacent to an enemy; it often leads to
        # invalid move attempts onto the monster's tile.
        if adjacent:
            return False

        door = self.find_adjacent_door(px, py, state)
        if door:
            log(f"Opening door at {door}.")
            self.click_tile(door[0], door[1])
            self.wait_state_update(state, max_wait=1.0)
            self.actions_taken += 1
            return True

        if state["movementRemaining"] > 0:
            self.visited_tiles.add((px, py))
            step = self.decide_move(state)
            if step:
                target = (step["x"], step["y"])
                # Fragile ranged classes should not walk into melee range.
                # Stop one tile short and shoot on the next turn instead.
                if fragile_class and has_ranged:
                    would_be_adjacent = self.page.evaluate(
                        """(args) => monsters.some(m => m.alive && !m.fled &&
                            Math.abs(m.x - args.x) + Math.abs(m.y - args.y) === 1)""",
                        {"x": target[0], "y": target[1]},
                    )
                    if would_be_adjacent:
                        log(f"Avoiding melee walk-in to ({target[0]},{target[1]}).")
                        return False
                # Avoid immediate backtrack only when it would cause a chase ping-pong.
                # Progression tiles (exit, chests, doors, spawns) are always reachable,
                # and backtracking is fine when the dungeon is safe.
                is_exit = state["map"][target[1]][target[0]] == "E"
                is_door = state["map"][target[1]][target[0]] in ("D", "L")
                is_chest = state["map"][target[1]][target[0]] == "C"
                is_spawn = target in self.known_monster_spawns
                safe_to_leave = not monsters
                retreated_from = getattr(self, "retreated_from", None)
                if (
                    self.last_pos
                    and target == self.last_pos
                    and in_danger
                    and not (is_exit and safe_to_leave)
                    and not is_door
                    and not is_chest
                    and not is_spawn
                ):
                    log(f"Skipping backtrack to {target}.")
                    return False
                # Do not walk straight back into the tile we just retreated from.
                # For ranged-kiters this applies for the rest of the turn even
                # when no enemy is currently visible, preventing (12,12) <-> (13,12)
                # loops where the hero keeps stepping into a newly-adjacent foe.
                if retreated_from and target == retreated_from and (in_danger or getattr(self, "retreated_this_turn", False)):
                    log(f"Skipping re-approach to retreated tile {target}.")
                    return False
                log(f"Moving to ({target[0]},{target[1]}).")
                self.click_tile(target[0], target[1])
                new_state = self.wait_state_update(state, max_wait=0.3)
                new_pos = (
                    new_state["playerPos"]["x"],
                    new_state["playerPos"]["y"],
                ) if new_state else None
                if new_pos == target:
                    self.visited_tiles.add(target)
                    self.last_pos = (px, py)
                    if target in self.known_monster_spawns:
                        self.visited_spawns.add(target)
                    # If we stood on an exit and the game did not end, the exit is warded.
                    if (
                        new_state
                        and new_state["map"][target[1]][target[0]] == "E"
                        and not self.is_game_over()
                    ):
                        self.warded_exits.add(target)
                        log(f"Exit at {target} is warded; looking for remaining enemies.")
                    self.actions_taken += 1
                    return True
                # Move failed (blocked, monster moved onto tile, etc.).
                self.blocked_tiles.add(target)
                log(f"Move to {target} failed; blocking tile this turn.")
                return True

            # Fallback: if pathfinding is stuck (no frontier/enemy visible), backtrack
            # to the last position. This prevents ranged classes from retreating into
            # dead-ends and then being unable to leave.
            if state["movementRemaining"] > 0 and self.last_pos:
                lx, ly = self.last_pos
                if abs(lx - px) + abs(ly - py) == 1:
                    log(f"Pathfinding stuck; backtracking to ({lx},{ly}).")
                    self.click_tile(lx, ly)
                    self.wait_state_update(state, max_wait=0.3)
                    self.actions_taken += 1
                    return True

        return False

    def decide_move(self, state: dict) -> dict | None:
        """Use in-game pathfinding to pick the next step toward the exit or frontier."""
        blocked = [f"{x},{y}" for x, y in self.blocked_tiles]
        visited = [f"{x},{y}" for x, y in self.visited_tiles]
        warded = [f"{x},{y}" for x, y in self.warded_exits]
        has_key = any(i.get("item_id") == "iron_key" and (i.get("quantity") or 1) > 0 for i in state.get("inventory", []))
        try:
            result = self.page.evaluate(
                """(args) => {
                    const blockedSet = new Set(args.blocked);
                    const visitedSet = new Set(args.visited);
                    const wardedSet = new Set(args.warded);

                    function isBotWalkable(x, y) {
                        if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return false;
                        const t = mapData[y][x];
                        if (t === TILE.WALL || t === TILE.SECRET_DOOR) return false;
                        if (t === TILE.LOCKED_DOOR && !doorsOpened.has(`${x},${y}`) && !args.hasKey) return false;
                        // Barrels can be pushed/destroyed; water is difficult but walkable.
                        return true;
                    }

                    function findPath(to) {
                        const queue = [{ x: playerPos.x, y: playerPos.y, path: [] }];
                        const seen = new Set([`${playerPos.x},${playerPos.y}`]);
                        let head = 0;
                        while (head < queue.length) {
                            const cur = queue[head++];
                            if (cur.x === to.x && cur.y === to.y) {
                                return cur.path[0] || null;
                            }
                            for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                                const nx = cur.x + dx, ny = cur.y + dy;
                                const key = `${nx},${ny}`;
                                if (seen.has(key)) continue;
                                if (!isBotWalkable(nx, ny)) continue;
                                if (monsterAt(nx, ny)) continue;
                                seen.add(key);
                                queue.push({ x: nx, y: ny, path: [...cur.path, { x: nx, y: ny }] });
                            }
                        }
                        return null;
                    }

                    function candidateStep(target, reason) {
                        if (!target) return null;
                        let step = findPath(target);
                        // If the target tile is occupied (monster, closed door),
                        // pathfind to the nearest adjacent tile instead.
                        if (!step) {
                            let best = null, bestDist = Infinity;
                            for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                                const ax = target.x + dx, ay = target.y + dy;
                                if (ax < 0 || ay < 0 || ax >= MAP_W || ay >= MAP_H) continue;
                                const tt = mapData[ay][ax];
                                if (tt === TILE.WALL || tt === TILE.SECRET_DOOR) continue;
                                if (tt === TILE.DOOR && !doorsOpened.has(`${ax},${ay}`)) continue;
                                if (tt === TILE.LOCKED_DOOR && !doorsOpened.has(`${ax},${ay}`)) continue;
                                const s = findPath({ x: ax, y: ay });
                                if (!s) continue;
                                const d = distance(playerPos, { x: ax, y: ay });
                                if (d < bestDist) { bestDist = d; best = s; }
                            }
                            step = best;
                        }
                        if (!step) return null;
                        if (blockedSet.has(`${step.x},${step.y}`)) return null;
                        return { step, target, reason };
                    }

                    let choice = null;

                    // 1. Approach the nearest visible enemy so fights are finished before wandering.
                    let nearestEnemy = null, nearestDist = Infinity;
                    for (const m of monsters) {
                        if (!m.alive || m.fled) continue;
                        if (!isVisibleToPlayer(m.x, m.y)) continue;
                        const d = distance(playerPos, { x: m.x, y: m.y });
                        if (d < nearestDist) { nearestDist = d; nearestEnemy = m; }
                    }
                    if (nearestEnemy) {
                        choice = candidateStep({ x: nearestEnemy.x, y: nearestEnemy.y }, 'enemy');
                    }

                    const safeToLeave = monsters.every(m => !m.alive || m.fled);

                    // 2. If enemies remain but none are visible, move toward the
                    // last known position of any living monster. This prevents
                    // ranged classes from retreating into dead-ends and losing
                    // track of the fight.
                    if (!choice && !safeToLeave && args.lastMonsters.length) {
                        let nearestLast = null, nearestLastDist = Infinity;
                        for (const m of args.lastMonsters) {
                            const d = distance(playerPos, { x: m.x, y: m.y });
                            if (d < nearestLastDist) { nearestLastDist = d; nearestLast = m; }
                        }
                        if (nearestLast) {
                            choice = candidateStep(nearestLast, 'last-known');
                        }
                    }

                    // 3. If enemies remain but none are visible, sweep the known
                    // monster spawn points so sleeping or hidden foes are found.
                    if (!choice && !safeToLeave && args.spawns.length) {
                        const spawnSeen = new Set(args.visitedSpawns || []);
                        let nearestSpawn = null, nearestSpawnDist = Infinity;
                        for (const s of args.spawns) {
                            const key = `${s.x},${s.y}`;
                            if (spawnSeen.has(key)) continue;
                            const d = distance(playerPos, s);
                            if (d < nearestSpawnDist) { nearestSpawnDist = d; nearestSpawn = s; }
                        }
                        if (nearestSpawn) {
                            choice = candidateStep(nearestSpawn, 'spawn');
                        }
                    }

                    // 3. Loot any unopened chests once the dungeon is clear.
                    if (!choice && safeToLeave) {
                        let nearestChest = null, nearestChestDist = Infinity;
                        for (let y = 0; y < MAP_H; y++) {
                            for (let x = 0; x < MAP_W; x++) {
                                if (mapData[y][x] === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
                                    const d = distance(playerPos, { x, y });
                                    if (d < nearestChestDist) { nearestChestDist = d; nearestChest = { x, y }; }
                                }
                            }
                        }
                        if (nearestChest) {
                            choice = candidateStep(nearestChest, 'chest');
                        }
                    }

                    // Infer locked doors from the map in case the caller did not
                    // pass them. A locked door without a key means the key chest
                    // is the only way forward.
                    const anyLockedDoor = (args.doorsLocked?.length > 0) || (() => {
                        for (let y = 0; y < MAP_H; y++) {
                            for (let x = 0; x < MAP_W; x++) {
                                if (mapData[y][x] === TILE.LOCKED_DOOR && !doorsOpened.has(`${x},${y}`)) return true;
                            }
                        }
                        return false;
                    })();

                    // 4. If a locked door blocks progress and we lack a key, loot
                    // the key chest first. If the explicit key-chest list is empty,
                    // fall back to any unopened chest.
                    if (!choice && anyLockedDoor && !args.hasKey) {
                        let nearestKeyChest = null, nearestKeyChestDist = Infinity;
                        const keySources = (args.chestsWithKey?.length ? args.chestsWithKey : []);
                        for (const key of keySources) {
                            const [x, y] = key.split(',').map(Number);
                            if (chestsOpened.has(`${x},${y}`)) continue;
                            const d = distance(playerPos, { x, y });
                            if (d < nearestKeyChestDist) { nearestKeyChestDist = d; nearestKeyChest = { x, y }; }
                        }
                        if (!nearestKeyChest) {
                            for (let y = 0; y < MAP_H; y++) {
                                for (let x = 0; x < MAP_W; x++) {
                                    if (mapData[y][x] === TILE.CHEST && !chestsOpened.has(`${x},${y}`)) {
                                        const d = distance(playerPos, { x, y });
                                        if (d < nearestKeyChestDist) { nearestKeyChestDist = d; nearestKeyChest = { x, y }; }
                                    }
                                }
                            }
                        }
                        if (nearestKeyChest) {
                            choice = candidateStep(nearestKeyChest, 'key-chest');
                        }
                    }

                    // 5. Head for the known exit when no visible enemies remain.
                    if (!choice) {
                        for (let y = 0; y < MAP_H && !choice; y++) {
                            for (let x = 0; x < MAP_W; x++) {
                                if (mapData[y][x] === TILE.EXIT && explored.has(`${x},${y}`) && (safeToLeave || !wardedSet.has(`${x},${y}`))) {
                                    choice = candidateStep({ x, y }, 'exit');
                                    if (choice) break;
                                }
                            }
                        }
                    }

                    // When only a few monsters remain and none are visible, do a
                    // full sweep: ignore the visited-set so we do not loop in one
                    // corner of the map while a straggler hides elsewhere.
                    const sweepMode = !safeToLeave && monsters.filter(m => m.alive && !m.fled).length <= 2;

                    // 3. Closed doors adjacent to explored tiles are high-priority
                    // frontiers: opening them is required to reach new areas and
                    // stragglers like the boss in Crooked Tower.
                    if (!choice) {
                        let best = null, bestDist = Infinity;
                        for (const key of explored) {
                            const [x, y] = key.split(',').map(Number);
                            for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                                const nx = x + dx, ny = y + dy;
                                if (nx < 0 || ny < 0 || nx >= MAP_W || ny >= MAP_H) continue;
                                const tt = mapData[ny][nx];
                                const isClosedDoor = tt === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`);
                                const isLockedDoor = tt === TILE.LOCKED_DOOR && !doorsOpened.has(`${nx},${ny}`);
                                if (!isClosedDoor && !isLockedDoor) continue;
                                if (isLockedDoor && !args.hasKey) continue;
                                if (blockedSet.has(`${nx},${ny}`)) continue;
                                const d = distance(playerPos, { x: nx, y: ny });
                                if (d < bestDist) { bestDist = d; best = { x: nx, y: ny }; }
                            }
                        }
                        if (best) choice = candidateStep(best, 'door-frontier');
                    }

                    // 4. Otherwise explore the nearest open frontier.
                    if (!choice) {
                        let best = null, bestDist = Infinity;
                        for (const key of explored) {
                            const [x, y] = key.split(',').map(Number);
                            for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                                const nx = x + dx, ny = y + dy;
                                if (nx < 0 || ny < 0 || nx >= MAP_W || ny >= MAP_H) continue;
                                if (explored.has(`${nx},${ny}`)) continue;
                                if (!sweepMode && visitedSet.has(`${nx},${ny}`)) continue;
                                const tt = mapData[ny][nx];
                                if (tt === TILE.WALL || tt === TILE.SECRET_DOOR) continue;
                                if (tt === TILE.DOOR && !doorsOpened.has(`${nx},${ny}`)) continue;
                                if (tt === TILE.LOCKED_DOOR && !doorsOpened.has(`${nx},${ny}`)) continue;
                                if (monsterAt(nx, ny)) continue;
                                if (blockedSet.has(`${nx},${ny}`)) continue;
                                const d = distance(playerPos, { x: nx, y: ny });
                                if (d < bestDist) { bestDist = d; best = { x: nx, y: ny }; }
                            }
                        }
                        choice = candidateStep(best, best ? 'frontier' : 'no-frontier');
                    }

                    if (!choice) return { step: null, target: null, reason: 'no-path' };
                    return choice;
                }""",
                {"blocked": blocked, "visited": visited, "warded": warded,
                 "hasKey": has_key,
                 "doorsLocked": state.get("doorsLocked", []),
                 "chestsWithKey": state.get("chestsWithKey", []),
                 "spawns": [{"x": x, "y": y} for x, y in self.known_monster_spawns],
                 "visitedSpawns": [f"{x},{y}" for x, y in self.visited_spawns],
                 "lastMonsters": [{"x": x, "y": y, "name": name} for (x, y), name in self.last_monster_positions.items()]},
            )
            if not result or not result.get("step"):
                log(f"decide_move: no step (reason={result.get('reason')}, target={result.get('target')})")
                return None
            return result["step"]
        except Exception as e:
            log(f"decide_move failed: {e}")
            return None

    def find_adjacent_door(self, px, py, state):
        has_key = any(i.get("item_id") == "iron_key" and (i.get("quantity") or 1) > 0 for i in state.get("inventory", []))
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = px + dx, py + dy
            if 0 <= nx < state["mapW"] and 0 <= ny < state["mapH"]:
                t = state["map"][ny][nx]
                closed = t == "D" and f"{nx},{ny}" not in state["doorsOpened"]
                locked = t == "L" and f"{nx},{ny}" not in state["doorsOpened"]
                if closed or (locked and has_key):
                    return (nx, ny)
        return None

    def click_tile(self, x, y):
        self.page.evaluate(
            """({x, y}) => { if (typeof handleGridClick === 'function') handleGridClick(x, y); }""",
            {"x": x, "y": y},
        )

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

    def has_ranged_weapon(self, state: dict) -> bool:
        """Return True if the hero has a real ranged weapon (range >= 2 tiles) and ammo."""
        return self.ranged_weapon_range(state) >= 20

    def ranged_weapon_range(self, state: dict) -> int:
        """Return the equipped ranged weapon's range in feet (0 if none)."""
        try:
            return self.page.evaluate(
                """() => {
                    const weapon = typeof findEquippedRangedWeapon === 'function' ? findEquippedRangedWeapon() : null;
                    if (!weapon) return 0;
                    return weapon.range || 0;
                }"""
            ) or 0
        except Exception:
            return 0

    def has_active_spell(self, spell_id: str) -> bool:
        """Check whether a buff/debuff spell is currently active on the hero.

        The state update is asynchronous, so we retry a few times before
        concluding the spell is absent.
        """
        try:
            for _ in range(10):
                has = self.page.evaluate(
                    f"""() => (playerCharacter?.sheet?.active_spells || []).some(s => s.spell_id === '{spell_id}')"""
                )
                if has:
                    return True
                self.tiny_wait(0.02)
            return False
        except Exception:
            return False

    def player_class(self) -> str:
        try:
            return self.page.evaluate("""() => playerCharacter?.class || ''""") or ""
        except Exception:
            return ""

    def is_thief(self) -> bool:
        return self.player_class() == "thief"

    def is_stealthed(self) -> bool:
        try:
            return self.page.evaluate("""() => typeof playerStealthed !== 'undefined' && playerStealthed""")
        except Exception:
            return False

    def can_sneak(self) -> bool:
        try:
            btn = self.page.locator("#sneak-btn")
            return btn.count() > 0 and btn.is_enabled(timeout=200)
        except Exception:
            return False

    def cast_cleric_heal(self, state: dict) -> bool:
        if self.player_class() != "cleric":
            return False
        if "cure_light_wounds" in self.spells_cast_this_turn:
            return False
        if state["hp"] >= state["maxHp"]:
            return False
        hp_ratio = state["hp"] / state["maxHp"]
        if hp_ratio > 0.75:
            return False
        try:
            btn = self.page.locator("#spell-btn-cure_light_wounds")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            log(f"Casting Cure Light Wounds ({state['hp']}/{state['maxHp']}).")
            btn.click()
            self.wait_state_update(state, max_wait=1.0)
            self.spells_cast_this_turn.add("cure_light_wounds")
            return True
        except Exception:
            return False

    def cast_magic_missile(self, state: dict) -> bool:
        if self.player_class() not in ("magic_user", "illusionist"):
            return False
        if "magic_missile" in self.spells_cast_this_turn:
            return False
        monsters = state["monsters"]
        if not monsters:
            return False
        try:
            btn = self.page.locator("#spell-btn-magic_missile")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            visible = self.page.evaluate(
                """() => monsters.filter(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))
                             .map(m => ({x:m.x, y:m.y, hp:m.hp, name:m.name}))"""
            )
            if not visible:
                return False
            target = min(visible, key=lambda m: m["hp"])
            log(f"Casting Magic Missile at {target['name']}.")
            btn.click()
            self.tiny_wait(0.05)
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state, max_wait=1.0)
            self.spells_cast_this_turn.add("magic_missile")
            return True
        except Exception:
            return False

    def cast_shield(self, state: dict) -> bool:
        """Mage defensive buff: cast as soon as a fight starts."""
        if self.player_class() not in ("magic_user", "illusionist"):
            return False
        if "shield" in self.spells_cast_this_turn or self.has_active_spell("shield"):
            return False
        try:
            btn = self.page.locator("#spell-btn-shield")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            visible = self.page.evaluate(
                """() => monsters.some(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))"""
            )
            if not visible:
                return False
            log("Casting Shield.")
            btn.click()
            self.wait_state_update(state, max_wait=1.0)
            self.spells_cast_this_turn.add("shield")
            return True
        except Exception:
            return False

    def cast_bless(self, state: dict) -> bool:
        """Cleric pre-buff: only burn the action against a real swarm."""
        if self.player_class() != "cleric":
            return False
        if "bless" in self.spells_cast_this_turn or self.has_active_spell("bless"):
            return False
        hp_ratio = state["hp"] / state["maxHp"]
        if hp_ratio <= 0.80:
            return False
        try:
            btn = self.page.locator("#spell-btn-bless")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            visible = self.page.evaluate(
                """() => monsters.filter(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y)).length"""
            )
            if visible < 2:
                return False
            log("Casting Bless.")
            btn.click()
            self.wait_state_update(state, max_wait=1.0)
            self.spells_cast_this_turn.add("bless")
            return True
        except Exception:
            return False

    def cast_sleep(self, state: dict) -> bool:
        """Mage crowd control: put the nearest visible threat to sleep."""
        if self.player_class() not in ("magic_user", "illusionist"):
            return False
        if "sleep" in self.spells_cast_this_turn:
            return False
        try:
            btn = self.page.locator("#spell-btn-sleep")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            visible = self.page.evaluate(
                """() => monsters.filter(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))
                             .map(m => ({x:m.x, y:m.y, hp:m.hp, name:m.name}))"""
            )
            if not visible:
                return False
            target = min(visible, key=lambda m: m["hp"])
            log(f"Casting Sleep on {target['name']}.")
            btn.click()
            self.tiny_wait(0.05)
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state, max_wait=1.0)
            self.spells_cast_this_turn.add("sleep")
            return True
        except Exception:
            return False

    def try_ranged_attack(self, state: dict) -> bool:
        """Fire a ranged weapon at the weakest visible target if one is available."""
        if state["attacked"]:
            return False
        try:
            result = self.page.evaluate(
                """() => {
                    const weapon = typeof findEquippedRangedWeapon === 'function' ? findEquippedRangedWeapon() : null;
                    const hasAmmo = typeof hasAmmoForRangedAttack === 'function' ? hasAmmoForRangedAttack() : false;
                    if (!weapon || !hasAmmo) return { reason: weapon ? 'no_ammo' : 'no_weapon' };
                    const maxTiles = Math.floor((weapon.range || 0) / 10);
                    if (maxTiles < 2) return { reason: 'short_range', weapon: weapon.name };
                    let best = null, bestHp = Infinity;
                    for (const m of monsters) {
                        if (!m.alive || m.fled) continue;
                        if (!isVisibleToPlayer(m.x, m.y)) continue;
                        const d = Math.abs(m.x - playerPos.x) + Math.abs(m.y - playerPos.y);
                        if (d <= 1 || d > maxTiles) continue;
                        if (!hasRangedLineOfSight(playerPos, { x: m.x, y: m.y })) continue;
                        if (m.hp < bestHp) { bestHp = m.hp; best = { x: m.x, y: m.y, name: m.name }; }
                    }
                    if (!best) return { reason: 'no_target', weapon: weapon.name, range: maxTiles };
                    return { target: best, weapon: weapon.name };
                }"""
            )
            if not result or not result.get("target"):
                log(f"Ranged attack unavailable: {result.get('reason')} ({result.get('weapon')} range {result.get('range')}).")
                return False
            target = result["target"]
            log(f"Shooting {target['name']} with {result.get('weapon')} at ({target['x']},{target['y']}).")
            self.click_tile(target["x"], target["y"])
            self.wait_state_update(state, max_wait=1.0)
            return True
        except Exception as e:
            log(f"try_ranged_attack failed: {e}")
            return False

    def find_retreat_tile(
        self, state: dict, *, prefer_range: bool = False, weapon_range: int = 0
    ) -> dict | None:
        """Find a reachable tile that is not adjacent to any enemy.

        When prefer_range is set (fragile ranged classes kiting), prefer the
        nearest safe tile from which the hero can still shoot a visible enemy.
        Falling back to the nearest safe tile keeps the party in the fight
        instead of running to the far end of the map and getting stuck.
        """
        monsters = state["monsters"]
        movement = state["movementRemaining"]
        max_tiles = max(2, weapon_range // 10) if weapon_range else 0
        try:
            result = self.page.evaluate(
                """(args) => {
                    const enemyPositions = new Set(args.monsters.map(m => `${m.x},${m.y}`));
                    const reachable = new Map();
                    const queue = [{ x: playerPos.x, y: playerPos.y, cost: 0 }];
                    reachable.set(`${playerPos.x},${playerPos.y}`, {
                        x: playerPos.x, y: playerPos.y, cost: 0, first: null
                    });
                    let head = 0;
                    while (head < queue.length) {
                        const cur = queue[head++];
                        const curInfo = reachable.get(`${cur.x},${cur.y}`);
                        for (const [dx, dy] of [[0,1],[0,-1],[1,0],[-1,0]]) {
                            const nx = cur.x + dx, ny = cur.y + dy;
                            const key = `${nx},${ny}`;
                            if (reachable.has(key)) continue;
                            if (!isWalkable(nx, ny)) continue;
                            if (monsterAt(nx, ny)) continue;
                            const cost = cur.cost + movementCost(nx, ny);
                            if (cost > args.movement) continue;
                            const first = curInfo.first || { x: nx, y: ny };
                            reachable.set(key, { x: nx, y: ny, cost, first });
                            queue.push({ x: nx, y: ny, cost });
                        }
                    }

                    const maxTiles = args.maxTiles;
                    let best = null, bestScore = -Infinity;
                    for (const tile of reachable.values()) {
                        if (tile.x === playerPos.x && tile.y === playerPos.y) continue;
                        if (enemyPositions.has(`${tile.x},${tile.y}`)) continue;
                        let minEnemyDist = Infinity;
                        for (const m of args.monsters) {
                            const d = Math.abs(m.x - tile.x) + Math.abs(m.y - tile.y);
                            if (d < minEnemyDist) minEnemyDist = d;
                        }
                        if (minEnemyDist <= 1) continue;

                        let score;
                        if (args.preferRange) {
                            let bestShotDist = Infinity;
                            for (const m of args.monsters) {
                                if (!m.alive || m.fled) continue;
                                const d = Math.abs(m.x - tile.x) + Math.abs(m.y - tile.y);
                                if (d <= maxTiles && hasRangedLineOfSight(tile, { x: m.x, y: m.y })) {
                                    if (d < bestShotDist) bestShotDist = d;
                                }
                            }
                            if (bestShotDist !== Infinity) {
                                // Keep the closest safe firing position.
                                score = 1000 - bestShotDist * 10 - tile.cost;
                            } else {
                                // No shot: stay as close to the enemy as safety allows.
                                score = minEnemyDist * 2 - tile.cost;
                            }
                        } else {
                            score = minEnemyDist * 10 - tile.cost;
                        }
                        if (score > bestScore) { bestScore = score; best = tile; }
                    }
                    return best ? best.first : null;
                }""",
                {"monsters": monsters, "movement": movement, "preferRange": prefer_range, "maxTiles": max_tiles},
            )
            return result
        except Exception as e:
            log(f"find_retreat_tile failed: {e}")
            return None

    def auto_explore(self) -> bool:
        """Trigger the in-game auto-explore and wait for it to finish.

        Returns True if the button was available and clicked, False otherwise.
        The JS autoExplore stops on its own when it hits a monster, runs out of
        movement, or has nowhere left to explore.
        """
        try:
            btn = self.page.locator("#auto-explore-btn")
            if not btn.count() or not btn.is_enabled(timeout=200):
                return False
            self.page.evaluate("""async () => {
                if (typeof autoExplore === 'function') await autoExplore();
            }""")
            self.tiny_wait(0.05)
            return True
        except Exception as e:
            log(f"auto_explore failed: {e}")
            return False

    def try_auto_explore(self, state: dict) -> bool:
        """Let the in-game auto-explorer handle safe movement to save rounds.

        Only used when no enemies are visible and the hero is not wounded
        enough to need resting, so it does not charge blindly into danger.
        """
        monsters = state["monsters"]
        hp_ratio = state["hp"] / state["maxHp"]
        if state["attacked"] or state["movementRemaining"] <= 0:
            return False
        if monsters:
            visible = self.page.evaluate(
                """() => monsters.some(m => m.alive && !m.fled && isVisibleToPlayer(m.x, m.y))"""
            )
            if visible:
                return False
        rest_threshold = 0.85
        if hp_ratio <= rest_threshold and self.can_rest():
            return False
        old_pos = (state["playerPos"]["x"], state["playerPos"]["y"])
        if not self.auto_explore():
            return False
        new_state = self.wait_state_update(state, max_wait=3.0)
        if not new_state:
            return False
        new_pos = (new_state["playerPos"]["x"], new_state["playerPos"]["y"])
        if new_pos != old_pos:
            log(f"Auto-explored to ({new_pos[0]},{new_pos[1]}).")
            self.actions_taken += 1
            return True
        return False

    @staticmethod
    def distance(x1, y1, x2, y2):
        return abs(x1 - x2) + abs(y1 - y2)
