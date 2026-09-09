# Sanctuary Gap Analysis

This document compares Sanctuary's current feature set to mature web, board, and CRPG
dungeon crawlers. The goal is to identify concrete, high-value improvements for the
autonomous improvement loop.

## Current Sanctuary Snapshot (verified 2025)

- **Core loop:** create a character, buy a starter kit, enter a module, explore a
  procedurally generated 22×16 dungeon, fight monsters, open doors/chests, avoid
  traps, reach the exit, optionally descend.
- **Combat:** turn-based OSRIC initiative; melee, ranged, and spell attacks;
  death saves; short rest healing; potions.
- **Progression:** XP from kills/loot, level-ups via `/api/osric/level-up`,
  ability rolls, equipment/inventory, THAC0, saving throws, spell slots.
- **Meta:** town with shop and mercenary roster, campaign gold, save/load,
  multiple dungeon modules (`crooked_tower`, etc.).
- **Tooling:** headless benchmark with Pixi ticker → web-second conversion,
  human-speed spectator bot, shared `DungeonBot` core, pytest suite.  High
  ticker speeds (60×) can overwhelm the headless Chromium GPU process on some
  Windows hosts, so reliable benchmarking uses a lower ticker speed (20×) and
  a 25-round cap.
- **Level 1 balance pass (latest):**
  - Monster melee attacks now use each monster's natural damage expression
    instead of a default 1d4 club.
  - Level 1 monsters have 60 % HP, one smaller damage die, and AC worsened by 1
    (descending AC +1), making the tutorial band more forgiving.
  - Level 1 characters are guaranteed a 16+ prime requisite score (e.g., Strength
    for fighters) and at least 14 Constitution, so the starter party has good
    to-hit, damage, and HP. They also receive a +2 tutorial to-hit bonus on
    level 1 to reduce miss-streak deaths.
  - Wandering monsters are disabled entirely on level 1, so the Crooked Tower is
    deterministic and first-time players are not punished by chase loops.
  - On level 1, resting is allowed whenever no enemy is adjacent (instead of
    requiring the whole area to be clear), so a wounded party can recover
    between encounters.
  - Fighter starter kit now includes three potions of healing and enough starting
    gold (260 gp minimum) to afford the expanded kit.
  - The level 1 encounter table is limited to kobold, goblin, and giant rat;
    orc and skeleton are removed.
  - Locked doors and iron keys add a light progression gate: the Crooked Tower
    seals its shrine (and thus the exit route) behind a locked door, and the
    matching key is guaranteed in the first chest. Monsters can bash through
    locked doors, but players must find or carry a key.
  - The Crooked Tower boss (Grik) uses the normal weakened damage expression
    and a 1.25× HP multiplier instead of an extra damage die.
- **Monster AI pass:**
  - Melee attacks now use the monster's own damage expression.
  - From dungeon level 2 onward, most non-boss monsters start **asleep** and do
    not act until the player gets within 3 tiles or line of sight; waking one
    alerts nearby sleeping monsters. The Crooked Tower (level 1) keeps monsters
    awake so first-time players learn the combat loop without a stealth wall.
  - From level 2 onward, melee monsters use **pack tactics** (+1 to hit per
    adjacent ally, capped at +2) and ranged monsters **kite** by keeping their
    distance when they have line of sight.
- **Ranged cover:**
  - Targets adjacent to walls, creatures, or obstacles receive a **+1 AC cover
    bonus** against ranged attacks, rewarding flanking and punishing shooting
    through doorways. Melee attacks ignore cover.
- **Class-balance snapshot (Level 1 Crooked Tower, headless bot, post-fix):**
  - Fighter: 9/10 wins (90 %)
  - Thief: 3/5 wins (60 %) — extra potion and a fade-after-backstab tactic
    raised the thief from 0 %, but fights are still long without a ranged
    option.
  - Cleric: 3/5 wins (60 %) — the morning star upgrade and smarter healing
    timing closed the Grik damage gap.
  - Magic-User: 3/5 wins (60 %) — Magic Missile alpha-strike is strong, but
    the d4 HP mage still dies to a single hit if initiative is lost.
- **Headless benchmark pass (2025-01-09, 40-round web-second conversion):**
  - Fighter: 6/10 wins (60 %), 4 UNKNOWN (max rounds reached)
  - Cleric: 1/5 wins (20 %), 4 UNKNOWN
  - Thief: 3/5 wins (60 %), 1 UNKNOWN, 1 defeat
  - Magic-User: 1/5 wins (20 %), 4 UNKNOWN
  - Diagnosis: fragile ranged classes were retreating to the far end of the
    map and then ping-ponging back into melee, burning rounds instead of
    finishing fights. Mercenary generation also occasionally failed at the
    old 20-attempt server retry limit.
- **Improvements in flight:**
  - Server-side mercenary retry increased from 20 to 100 attempts; client
    now falls back to the unrestricted Human ancestry after a few failures.
  - Ranged-kiting bot logic rewritten to retreat to the nearest safe firing
    position instead of the furthest corner, and to avoid walking straight
    back into the tile it just retreated from in the same turn.
  - Bot spell logic widened: Bless fires against 2+ visible enemies (was 3+),
    and Sleep can be cast on a single visible target instead of requiring a
    cluster.
  - Starting-gold minimums raised for fighter (310 gp), cleric (190 gp),
    magic-user (190 gp), and thief (260 gp) so every level-1 hero can afford
    at least one mercenary after buying their kit.
  - Fighter starter kit regained a second potion of healing while staying
    mercenary-affordable thanks to the higher gold floor.
  - Synthesized Web Audio SFX added for attacks, spells, doors, chests,
    footsteps, rest, and victory, with a mute toggle.
  - Bot headless loop fixed so mercenary turns no longer consume the
    `max_rounds` budget; the counter now only advances on the hero's own
    completed turns.
  - Bot mercenary hiring scoring fixed so front-line tanks/healers are
    preferred over fragile casters regardless of the player character class.
  - Mercenary front-line guarantee narrowed to `fighter` and `cleric`;
    `paladin` and `ranger` were failing their high ability-score rolls so
    often that the guaranteed slot came up empty, leaving fragile classes
    with two magic-user hirelings.
  - Static asset cache busting added to `index.html` so JS/CSS changes are
    picked up by browsers without a hard refresh.
  - Headless benchmark viewport reduced and ticker speed lowered for
    reliability on hosts where Chromium's GPU process crashes under the
    original 60× ticker.
- **Headless benchmark reliability pass:**
  - Town-guild and module-depart clicks now use JavaScript `click()` instead
    of Playwright pointer events, avoiding intercepted-pointer timeouts on
    smaller viewports.
  - `benchmark_all.py` retries a run once when the Chromium page/browser
    closes unexpectedly.
- **Hall of Fame scoring and streaks:**
  - Each recorded run now computes a score from HP remaining, dungeon level,
    rounds taken, rooms visited, and a hardcore multiplier.
  - The Hall of Fame modal shows wins, losses, current streak, best streak,
    and best score, plus per-run score badges.
  - The end-of-delve victory modal displays the run score.
- **Monster healer role:**
  - New `healer` AI role casts a 2d6-ish heal on the most wounded ally within
    6 tiles before acting offensively.
  - Added `Kobold Shaman` and `Goblin Shaman` templates; shamans appear in
    level 2+ encounter tables and in the Goblin Warren module.
- **Monster tactical UI:**
  - HP bars now appear beneath monster tokens so players can prioritize
    targets at a glance.
  - Healer shamans are marked with a green "+" badge and use a green fallback
    token colour.
- **Room events:**
  - Entering a new room has a 15 % chance to trigger a small environmental
    event: an abandoned cache (gold), an old shrine (party heal), corpse loot
    (identify a consumable), a hidden niche (XP), or an ominous sigil (flavour).
  - Events are tracked per room and do not repeat.
- **Victory clarity:**
  - The "Exit Open" modal now displays the module's story reward and the name
    of the next unlocked module.
- **Economy / town fixes:**
  - Removed a duplicate `townRest()` that made inn rest free; resting now
    correctly charges `innCost()` gold per party level.

## Comparables

### NetHack ([Wikipedia](https://en.wikipedia.org/wiki/NetHack))

- 50+ persistent, procedurally generated dungeon levels with special branches,
  fixed-layout quest levels, and shops/altars/fountains/pools/sinks.
- Deep item interaction: blessed/uncursed/cursed status, identification mini-game,
  scrolls, potions, wands, rings, amulets, tools, keys, lamps.
- Pet system, taming, monster polymorphing, intrinsic resistances, conducts.
- Permadeath, bones files (levels where other players died), scoreboards,
  post-mortem item identification.
- Huge bestiary with complex AI and ecological interactions.

### Dungeon Crawl Stone Soup / DCSS ([Wikipedia](https://en.wikipedia.org/wiki/Dungeon_Crawl_Stone_Soup))

- 27 species × 26 backgrounds, a pantheon of 26 gods with piety/anger mechanics.
- Skill-based advancement through use (weapons, spells, evocations, stealth, etc.).
- Auto-explore, auto-travel, regex item search, webtiles online play.
- Branches with rune objectives, portal vaults, manual vault fragments, sprint
  modes.
- Strong UI affordances: mouse interaction, graphical tiles, deterministic seeding.

### Gloomhaven ([Wikipedia](https://en.wikipedia.org/wiki/Gloomhaven))

- Campaign-driven, 95 scenarios, 17 classes, legacy stickers/envelopes, branching
  narrative.
- Card-driven action selection (two cards per turn, top+bottom actions), no dice.
- Hex grid, line-of-sight, obstacles, traps, loot, loot deck, scenario goals.
- Persistent character progression: perks, item unlocks, city/road events,
  retirement and new characters.
- Cooperative 1–4 players, digital adaptation with multiplayer.

### Dungeon'JS / web dungeon crawlers ([GitHub](https://github.com/Zusoy/dungeonjs))

- Browser-first 3D multiplayer experience with socket.io.
- Room generation on entry, dice-based combat, keys/chests, treasure victory
  scoring, boss enemy.

## Priority Gaps

### High Impact

1. **Dungeon depth and variety**
   - Sanctuary has one 22×16 map per level with a single exit. NetHack/DCSS offer
     dozens of levels, branches, and special rooms. Even a second exit branch or
     a "downstairs" that preserves map state would add replayability.
2. **Meaningful monster AI and variety** ✅ *Partially implemented*
   - Monsters currently move toward the player and attack. Add roles: ranged
     kiting, healers, pack tactics, fleeing at low HP, patrol routes, sleeping
     guards. Gloomhaven's monster ability decks are a good model.
   - Implemented: role-based AI cards (brute, skirmisher, archer, healer, boss),
     pack tactics, ranged kiting, low-HP morale/fleeing, sleeping guards,
     door-bashing, and boss rally. Healer shamans are the newest addition.
3. **Item identification and consumable depth** ✅ *Implemented*
   - Potions and scrolls use an unknown-appearance system: each type gets a
     random label ("Potion (red)", "Scroll (ivory)") until used or identified.
   - Potion types: healing, extra healing, poison. Scroll types: identify,
     mapping, teleport.
   - Chests can contain both potions and scrolls independently, giving players
     a reason to seek out loot beyond gold.
4. **Auto-explore / auto-travel** ✅ *Implemented*
   - DCSS's auto-explore removes tedium. Sanctuary now exposes an **Auto-Explore**
     button in the action bar and an `E` keyboard shortcut. It walks toward the
     nearest unexplored frontier, opens adjacent doors, and stops when a monster
     is spotted, movement runs out, or the path is blocked. The headless
     benchmark can exercise it with `--auto-explore`.
5. **Victory and failure clarity** ✅ *Implemented for level 1*
   - Added a live **enemies-remaining / exit-open** badge in the top bar, updated
     every turn. Stepping on the exit tile now reports how many enemies remain if it
     is warded, and clearly announces when it opens. The headless benchmark can
     now reliably clear the Crooked Tower as a level 1 fighter.

### Medium Impact

6. **Environmental interactions beyond traps** ✅ *Implemented*
   - Locked doors requiring iron keys now gate optional/exit routes on dungeon
     modules. Monsters can bash through them, and keys are placed in chests.
   - **Ranged cover** is implemented: walls, creatures, and obstacles grant +1
     AC to adjacent targets against ranged attacks.
   - **Barrels / crates** block movement and ranged line of sight, can be pushed
     (moving into the vacated tile) or destroyed, and provide cover.
   - **Difficult terrain** (water/mud pools) costs double movement.
   - **Room events** add small interactive discoveries (shrines, caches, corpse
     loot, hidden niches, ominous sigils) when entering new rooms.
   - Still missing: fire, levers, secret walls, persistent fountains/altars.
     NetHack's sink/fountain/altar interactions are a benchmark.
7. **Spell and class identity** ✅ *Partially implemented*
   - The bot now uses cleric heals, magic-user Magic Missile, and thief sneak /
     backstab, giving each class a distinct loop.
   - Still missing: functional buff/debuff spells (Bless, Shield, Sleep) and
     mage crowd-control targeting in the bot.
8. **Mercenary AI usefulness**
   - Mercenaries are present but the smoke test only checks that they act. Make
     them tactically valuable: flanking, focus fire, healing allies.
9. **Score / leaderboard / permadeath option** ✅ *Implemented*
   - A local Hall of Fame records the last 50 runs (victory/defeat, module,
     character, level, final HP, rounds, date, score) and is viewable from town.
   - **Hardcore mode**: a character-creation toggle makes death permanent and
     tracks hardcore runs separately in the Hall of Fame.
   - **Bestiary**: tracks monsters encountered and slain across a campaign,
     viewable from town. Records are persisted in localStorage.
   - **Scoring and streaks**: runs are scored by HP%, level, speed, rooms
     explored, and hardcore mode. The Hall of Fame tracks current streak,
     best streak, and best score.
   - Still missing: online leaderboards and class/build rankings.
10. **Accessibility and UI polish**
    - DCSS invests heavily in mouse support, tooltips, and auto-pilot helpers.
    - Add keyboard shortcuts, action undo within a turn, movement path preview,
      and clearer combat log.

### Lower Impact / Long-term

11. **Multiplayer / async co-op**
    - Dungeon'JS shows browser multiplayer is a genre expectation. Sanctuary's
      turn-based structure is well-suited to async or hot-seat co-op.
12. **Narrative campaign events**
    - Gloomhaven's city/road events and branching story. Sanctuary modules have
      text intros but no in-dungeon narrative choices.
13. **Sound, music, and graphical tile variety**
    - Presentation lags behind commercial CRPGs; audio and varied tiles improve
      perceived quality.
14. **Modding / custom modules**
    - Allow JSON/Lua module definitions so players can add maps, monsters, and
      items without touching engine code.

## Recommended Next Steps

1. **Close the level-1 class-balance gap (current focus).**
   - Ranged-kiters need to finish fights before the round limit; verify the
     nearest-safe-firing-position retreat fixes cleric/magic-user win rates.
   - If win rates stay low, give fragile classes a guaranteed fighter/cleric
     mercenary at hire time and/or start them with an extra potion.
2. **Expand environmental interactions.** Add pushable/destroyable barrels and
   difficult terrain (water/mud) that alter movement and ranged line of sight.
3. **Improve monster AI further.** Add fleeing at low HP, patrol routes, or a
   simple monster ability deck so combat stops feeling like a uniform charge.
4. **Expand item consumables.** Add 2–3 unidentified potions/scrolls and a simple
   identify-by-use loop, like NetHack's early-game discovery.
5. **Introduce a second dungeon branch.** A locked door requiring a key from a
   chest, leading to a harder mini-level, tests persistence and branching.
6. **Add a hall of fame / run history.** Track victories, defeats, and key stats
   so the meta-loop has stakes beyond a single delve.
7. **Level-1 class-balance gap — earlier pass.** ✅ *Implemented*
   - Thief kit now includes a short bow and arrows, plus two potions of healing.
   - Bot thief fades away after stabbing and uses ranged attacks when equipped.
   - Cleric starter kit uses a morning star for better damage.
   - Mage and cleric now cast Shield / Bless pre-buffs and Sleep crowd-control.
   - Backend combat resolution now applies active spell bonuses (Bless +1 to hit,
     Shield +1 AC).
   - Latest multi-class benchmark before the kite fix: Fighter 60 %, Thief 60 %,
     Cleric 20 %, Magic-User 20 %.

## Sources

- NetHack: https://en.wikipedia.org/wiki/NetHack
- Dungeon Crawl Stone Soup: https://en.wikipedia.org/wiki/Dungeon_Crawl_Stone_Soup
- Gloomhaven: https://en.wikipedia.org/wiki/Gloomhaven
- Dungeon'JS: https://github.com/Zusoy/dungeonjs
