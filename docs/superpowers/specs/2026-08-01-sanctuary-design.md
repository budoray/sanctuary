# Sanctuary™ — design

**Date:** 2026-08-01 · **Status:** design, approved in outline, not yet planned
**Slug:** `sanctuary` · **Port:** 9300 · **Repo:** https://github.com/budoray/sanctuary.git

---

## 1. What Sanctuary is

Sanctuary is a complete OSRIC 3.0 table in the browser: it generates characters, rolls
every die in the open, runs dungeons, and lets Game Masters build and run their own
campaigns.

It is one system with two runtimes over one campaign format:

- **Engine-run** — a module plays unattended. Solo or party. The engine referees.
- **DM-run** — the same module opened as a live table, with a human in the DM seat who
  can override anything.

Every other decision in this document follows from that sentence. The campaign format is
the spine; the authoring surfaces are views onto it; the play modes are session drivers
over it. Design either runtime as an afterthought and the format ends up serving one of
them and getting retrofitted for the other.

## 2. Licence and attribution — load-bearing

Sanctuary is published under the **OSRIC Third-Party License version 1.1**, which is
printed in the back matter of the OSRIC 3.0 Player Guide. What it grants and withholds
decides real scope, so it is written out here rather than referenced:

| | |
|---|---|
| Rules and game mechanics | ✅ free use — every table in this document |
| Names of beings, locations, spells, items | ✅ free use |
| **Verbatim text of monsters, spells and magic items** | ✅ **explicitly excepted — may be reproduced** |
| Verbatim text of anything else (rules prose, GM advice) | ❌ implement the mechanic, never paste the essay |
| **The books' art** | ❌ **never.** All Sanctuary art is generated or drawn for it |

This is why S2 is a parse job and not a writing job: the 291 monster descriptions and 414
spell texts ship as written. It is also an independent reason the art must be ours, on top
of the platform's standing top-down/Factorio art direction.

**Required notice, verbatim and non-negotiable:**

> Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License
> and is not affiliated with Mythmere Games LLC.

Included as good practice, per the licence's own recommendation:

> This work includes material taken from the System Reference Document 5.1 ("SRD 5.1") by
> Wizards of the Coast LLC and available at:
> https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is licensed
> under the Creative Commons Attribution 4.0 International License available at:
> https://creativecommons.org/licenses/by/4.0/legalcode.

Both notices live in the client chrome **and** at `/licence`, and the gate asserts the
client carries them — not merely that the route exists. The house lesson applies with
force here: a route that exists is not a feature a player can reach, and an unshipped
licence notice is a licence breach rather than a missing feature.

⚠ Sanctuary must never imply affiliation with, or endorsement by, Mythmere Games. "OSRIC"
appears only in compatibility statements. The game's own name carries the ™, per house
convention — **Sanctuary™**, never "OSRIC Sanctuary".

## 3. Platform placement

Standard Tenshin game. Python + FastAPI, zero-build HTML/JS client, no bundler, no node on
the deploy path, no third-party requests from a player's browser.

- Slug `sanctuary` == subdomain == systemd unit == data directory == git repo.
- Port **9300** — Titer's retired slot. Reissue condition re-verified 2026-08-01 against
  8.8.8.8: `titer.tenshinarts.com` and `corpus.tenshinarts.com` both NXDOMAIN. Re-run the
  lookup rather than trusting this line.
- `sanctuary.tenshinarts.com` already resolves to 104.131.165.79. ⚠ This is the G11 shape
  — a name in front of nothing bound. Expected, since the A record was placed ahead of the
  deploy, but until the unit exists the subdomain serves the box's default vhost.
- House chrome in every client, same set, same order: **build · report · back · sign out**.
  `back` is `← Tenshin Arts` to the site ROOT and leaves you signed in; `sign out` ends the
  session. Version readout from `tenshin_version.py`. Reporting via `tenshin_feedback.py`
  to the shared hub — Sanctuary never stores its own reports.
- ⚠ `tenshin_feedback.submit()` returns `(ok, info)`. Unpack it. `bool()` on a 2-tuple is
  always truthy, which reports success while the report goes nowhere.
- `/live`, `/live/embed`, `/live/stream`, `/live/agents` — agents only, never a real player.
- At most **two** AI players (`BOT_COUNT` env var, default 2).
- Every commit bumps the patch of `vX.Y.Z-beta` in `VERSION`, staged in that commit. No
  `.github/` directory — there is no CI/CD on this platform.
- Every module the entrypoint imports is declared in `requirements.txt`. A game's own gate
  cannot catch an omission; the site's `python app.py check` is what catches it.

## 4. Source corpus

Five sources, all in hand. Nothing in this design depends on material we do not have.

| Source | Contents | Role |
|---|---|---|
| OSRIC 3.0 Player Guide (264pp) | 67 tables, 7 ancestries, 11 classes, equipment, combat | S1 authority |
| OSRIC 3.0 Gamemaster Guide (330pp) | 172 tables, **291 monsters**, 24 dungeon-generation tables (D-1…D-24), 34 magic-item tables, treasure, traps | S2/S3 authority |
| OSRIC wiki ch.1–6 (642pp) | **414 spells**, 286 monsters, character/play/dungeon/treasure chapters | Spell authority; bestiary cross-check |
| The Hyqueous Vaults (20pp) | A real 67-area OSRIC module | Format reference for S3 — not ingested |

Two independent monster transcriptions (291 in the GM guide, 286 on the wiki) are treated
as a feature: the parser is gated by **diffing them against each other**. A field that
disagrees is either a parse bug or a genuine 2.x→3.0 revision, and both deserve a human
look rather than silent entry into the corpus.

⚠ **Ligatures.** The wiki PDFs are set with typographic ligatures — `eﬀect` (U+FB00),
`suﬃcient` (U+FB03), `ﬁrst` (U+FB01). Unnormalised, the corpus ships words no search will
match. Normalisation is a parser requirement with its own test, not a cleanup pass.

⚠ **Encoding.** `read_text(encoding="utf-8")` and `write_text(encoding="utf-8")` on every
file operation in this repo, without exception. The sources are set in en-dashes, curly
quotes and ligatures; Windows defaults to cp1252. This rule has bitten twice on this
platform, once inside a script written to document it.

---

## 5. Architecture

```
sanctuary/
  dice.py         seeded roller, append-only roll log        [S1]
  tables.py       loads data/tables/*.yaml, lookups          [S1]
  character.py    ability gen, ancestry, class, derived      [S1]
  resolve.py      attack · save · turn · morale · skills     [S1]
  bestiary.py     monster records, custom monsters, effects  [S2]
  effects.py      the tier-2 verb vocabulary                 [S2]
  module.py       campaign format: load, validate, save      [S3]
  procgen.py      D-1…D-24 dungeon generator                 [S3]
  treasure.py     loot classes, gems, jewellery, magic items [S3]
  runtime.py      the play state machine                     [S4]
  session.py      session drivers: solo · party · async      [S4]
  dm.py           DM seat: overrides, reveals, adjudication  [S5]
tools/
  extract.py      PDF → YAML, one-shot, off the runtime path
data/
  tables/*.yaml   239 rules tables
  monsters/*.yaml 291 monsters
  spells/*.yaml   414 spells
  items/*.yaml    magic items
static/           zero-build client
tests/
app.py            routes, gate, house chrome
```

Dependency direction is one-way and enforced by test:

```
dm → runtime → module → {procgen, bestiary, treasure} → {character, resolve} → tables
                                    ↓
                              everything → dice
```

`dice.py` imports nothing of ours. `tables.py` imports only `dice`. No module imports
anything to its left in that chain. The test that enforces this is cheap and prevents the
slow collapse into a ball of mud that a project this size otherwise reaches by S4.

---

## 6. S1 — Rules core

The load-bearing slice. Everything above it is wrong if this is wrong, and nothing above it
is testable until this exists.

### 6.1 The dice engine

One `Dice(seed)` per session. Every roll in the entire system goes through it, and it
returns a record rather than a bare integer:

```python
Roll(
    index   = 47,                       # monotonic, per-session
    expr    = "1d20",
    faces   = [14],                     # what each die actually showed
    mods    = +3,
    total   = 17,
    reason  = "Ilse attacks orc, AC 6",
    tags    = {"kind": "attack", "actor": "ilse", "target": "orc-2"},
)
```

The log is append-only. Same seed plus same call sequence produces a byte-identical log.
That single property buys three things at once: generator properties become testable, a
bug report becomes reproducible from its seed, and the game becomes auditable to a player
who suspects the dice.

**Rules encoded here, because each has been "corrected" by someone who half-remembered it:**

- A natural 1 on a to-hit roll is **not** an automatic miss. A natural 20 is **not** an
  automatic hit. This is OSRIC's stated rule and it is not a bug.
- A natural 1 on a saving throw **always** fails.
- Natural 20 auto-succeeding a save is explicitly house-rulable — a flag, defaulting off.

⚠ **The animated die renders the number the engine already rolled. It never generates one.**
A client that rolls its own d20 and then eases to the server's value is fine; one that
treats its own animation as the roll is a second RNG, and the replay guarantee is gone the
moment it ships. Enforced structurally: `random.` and `Math.random` appear nowhere outside
`dice.py`, asserted by test. That test is the only thing that actually prevents this.

### 6.2 The table corpus

`tools/extract.py` slices the PDFs on `TABLE <n>: <NAME>` headers and emits one YAML per
table, keyed by OSRIC's own numbering:

```
data/tables/1.3.4.4a_fighter_level_advancement.yaml
data/tables/2.1.2a_monster_to_hit.yaml
data/tables/d-05_number_of_exits.yaml
```

The YAML is committed and is the runtime truth. The PDFs are never read at runtime.
`pypdf` is declared in `requirements.txt` even though `app.py` never imports it — an
undeclared dev dependency is how a future session's extraction run dies for no visible
reason.

Two gates, because they fail differently and neither catches the other:

- **Round-trip** — re-running the extractor reproduces the committed YAML exactly. Catches
  a hand-edit silently diverging from the book.
- **Spot-check** — asserts known values: fighter L9 = 250,000 XP; fighter L1 needs 10 to
  hit AC 10; cleric turning ladder; monster to-hit for 8-9+ HD vs AC 3 = 9. Catches a parse
  that is correctly *shaped* and wrong. Round-trip alone passes cheerfully on a uniformly
  mis-parsed corpus.

### 6.3 Character generation

Four generation modes, a player-facing choice rather than a config value:

| Mode | Method |
|---|---|
| Hardest | 3d6 in order |
| Difficult | 3d6, arrange to taste |
| Normal | 4d6 drop lowest, in order |
| Flexible | 4d6 drop lowest, arrange |

Then exceptional Strength (d100 percentile, **fighter/paladin/ranger only** — a plain 18
for everyone else), ancestry minimums from Table 1.2.0A, class eligibility, HP by hit die,
and the derived block: AC, saving-throw ladder, to-hit row, thief skills, spell slots,
encumbrance and movement rate. Multi-classing and dual-classing per §1.3.11–1.3.12.

All 7 ancestries, all 11 classes: assassin, cleric, druid, fighter, illusionist,
magic-user, monk, paladin, ranger, thief, plus multi/dual.

Every random step is a `Roll` in the log, so a character is fully reproducible from
`(seed, choices)`. That is also what makes a reroll honest rather than a slot machine.

### 6.4 Resolution

`attack` · `save` · `turn_undead` · `morale` · `thief_skill` · `item_save` ·
`encumbrance`. Each looks up its table, applies modifiers, rolls through `dice`, and
returns a record carrying both the outcome and the arithmetic that produced it — the
client renders the reasoning, not just the number.

Monsters resolve on their own ladders: Table 2.1.2A (monster to-hit by hit dice) and
Table 2.1.3A (monster saving throws by hit dice), both from the GM guide.

### 6.5 S1 client

Thin but real: a character sheet, a dice tray rendering the roll log, and the house chrome.
The gate reads this client, not just the routes.

---

## 7. S2 — Bestiary

### 7.1 The schema

All 291 monsters carry the same 13 fields, and the consistency is near-total (`NO.
ENCOUNTERED` is the one genuine optional, present on 253):

```yaml
name: Achaiyerai
frequency: very rare          # unique|very rare|rare|uncommon|common
no_encountered: "1d6"
size: huge                    # tiny|small|medium|large|huge|gigantic
alignment: chaotic evil
move: "180ft"
armour_class: 8               # descending, with [ascending] preserved
hit_dice: "10"
melee_attacks: "1 bite (1d10 piercing) and 2 claws (1d8 slashing)"
senses: "Infravision 120ft"
lair_chance: "5%"
intelligence: "average (8-10)"
morale: 90
loot: "Hoard 6"
experience: "1,400 +14/hp"
description: |                # verbatim, licence-permitted
  ...
abilities:                    # see 7.2
  - ...
```

### 7.2 Effects — the tiered model

This is the hardest problem in the project and the place where it could drown. A general
effects DSL capable of expressing every OSRIC ability is a research project, not a slice.
The resolution is to tier it and to make the bottom tier *honest* rather than silent:

| Tier | What | Resolved by |
|---|---|---|
| **1** | The 13 stat fields — AC, HD, attacks, damage, morale, saves | Engine, always |
| **2** | A verb vocabulary for what recurs across many monsters: save-or-die, energy drain, poison, paralysis, breath weapon, regeneration, magic resistance, swallow whole, level drain, charm, fear, petrification | Engine |
| **3** | Everything else, held as prose | DM if present; otherwise **surfaced as a decision** |

⚠ **The engine never silently drops an ability.** A monster whose Toxic Cloud is not
modelled says so and asks, rather than quietly fighting without it. This is what permits
shipping with tier 2 half-filled and growing it, instead of blocking on a complete DSL
nobody finishes.

The Hyqueous Vaults proves tier 3 is structural rather than a shortcut. That module invents
spectral candles and prime rods — an interacting tangibility system existing nowhere in
OSRIC. No general engine will ever execute "touching a lit spectral candle with a prime rod
cancels its plane-bending effect." Module-invented mechanics *must* fall to prose plus
adjudication.

### 7.3 Custom and edited monsters

The user-facing requirement: create new beasts, adjust existing values.

- Every field of the 291 is editable. Edits are stored as an **overlay**, never a mutation
  of the shipped corpus — so the book's values remain recoverable and a corpus re-parse
  does not clobber a DM's work.
- New monsters are the same schema with no base.
- Difficulty is **computed and shown**, not typed: Table 2.11A maps base XP to monster
  level 1–10, which then drives encounter placement. OSRIC's entire Chapter Eleven is that
  one table, so Sanctuary is doing more than the book here — the form computes what a DM
  would otherwise eyeball.
- Custom monsters are module-scoped by default and promotable to a DM's personal library.

### 7.4 Spells and magic items

414 spells on a fixed header schema — `Level · Range · Duration · Area of Effect ·
Components · Casting Time · Saving Throw` plus verbatim text. Same tiering as monsters:
slots and memorisation are engine-executed from S1; individual spell *effects* enter tier 2
by vocabulary, and everything else is tier 3.

Magic items from GM ch.13 (34 tables: potions, scrolls, rods/staves/wands, armour, swords,
miscellaneous, rings, cursed items, artifacts).

---

## 8. S3 — Campaign format and procgen

### 8.1 The format

Derived from what a real module actually contains, using the Hyqueous Vaults as the
reference shape:

```yaml
module:
  title: ...
  version: ...
  party_guidance: {size: [6, 8], total_levels: [20, 24]}
  background: |  ...
  start: |  ...

regions:                        # wandering-monster scope
  - id: south
    areas: [1, 37]
    check: {chance: "1-in-6", every: "3 turns"}
    table:  {die: d8, entries: [...]}

areas:
  - id: 1
    name: Clearing
    description: |  ...
    exits: [{to: 2, kind: trail, hidden: false}, ...]
    contents: [...]
    monsters: [...]
    treasure: [...]
    discoveries:                # probabilistic, tied to time or action
      - what: "black iron key (area 28)"
        trigger: {action: search, scope: "fire ring"}
      - what: "leather skullcap, dagger, hawk feathers"
        trigger: {action: search, scope: trees, chance: "1-in-6", per: hour}

monsters: [...]                 # module-local, extends the bestiary
items:    [...]                 # module-local magic items
mechanics: [...]                # module-local, tier 3 by definition
```

Four features fall out of the Hyqueous analysis and none are optional:

1. **Region-scoped wandering tables** with their own check cadence — not one global table.
2. **Module-local monsters.** Eel-men, ur-ameboid, vodyanoy and the Necromantess exist only
   in that module. This is the same mechanism as S2's custom monsters, which is why S2
   comes first.
3. **Module-local items and mechanics**, tier 3.
4. **Probabilistic discoveries gated on action and elapsed time** — "1-in-6 per hour of
   searching" is a mechanic the runtime must actually implement, not flavour.

### 8.2 Procgen

The GM guide's §2.7.1 is a literal algorithm across 24 tables (D-1…D-24), and Sanctuary
implements it as written:

```
1. Starting area           D-1
2. Room/chamber shape+size D-2a / D-2b → D-3 special → D-4 unusual sizing
3. Number of exits         D-5   (keyed on room area, not a flat roll)
4. Exit locations          D-6
5. Passage direction       D-7   / beyond-the-door D-20
6. Room contents           D-8   + sub-tables
7. Corridor continues 30ft, then D-18
```

Plus traps and tricks (§2.7.2), random encounters (§2.7.3), and treasure (ch.12: loot
classes, coin, gems, jewellery, maps; ch.13: magic items).

**Procgen emits the S3 format.** It is not a parallel representation — the generator writes
a module file, which is what makes "generate then edit" a one-line feature rather than a
second product. This is the single most important structural decision in S3.

⚠ The book instructs the GM to "freely fudge" impossible results — a room that will not fit
gets resized or rerolled. The generator must do the same, and must **log** each fudge to
the roll log rather than silently re-rolling. A generator that hides its retries cannot be
debugged from a seed.

⚠ **Reachability, per the platform's hard-won rule:** generation must prove an
empty-handed party can reach every area, using progressive reach — not
`reachable(world, everything)`. The item that bypasses a hazard can sit behind that hazard.
Re-roll rather than ship a soft-lock.

### 8.3 Authoring surfaces

All four requested, and affordable only because each is a **view over the one format**:

| Surface | What it is |
|---|---|
| **Import** | The format itself. Upload YAML/JSON, validate, report errors by area. |
| **Structured forms** | Generated UI over the schema. Area-by-area: description, exits, contents, monsters, discoveries and their odds. |
| **Generate then edit** | Procgen writes a module, forms open it. No blank page. |
| **Visual map editor** | Graphical view of the same areas and exits. Drag rooms, draw corridors, drop monsters and treasure. |

Build order is exactly that order — each is strictly more UI over the same validated
substrate, and the map editor is last because it is the only one that cannot be built
cheaply. If the schema is right, four surfaces are affordable. If it is wrong, they are
four products.

---

## 9. S4 — Play runtime

`runtime.py` is a state machine over a loaded module: party position, time (turns, hours,
days — the wandering and discovery mechanics need real elapsed time), light and vision,
encumbrance and movement rate, initiative and combat rounds, morale, treasure, XP and
levelling.

`session.py` supplies drivers, and the runtime does not know which is in use:

| Driver | Ships | Notes |
|---|---|---|
| **Solo** | **first** | One player against the engine. The test case, per the build order. |
| **Party (real-time)** | second | Sockets, house pattern. ⚠ Keyed by player name, never join order — index pairing desyncs on reconnect. |
| **Async** | third | Long campaigns on players' own schedules. The shared async turn engine's canonical home is **Vested**, and `engine/` is vendored, not ours to fork. |

Tier-3 abilities in engine-run play surface as a decision to the party rather than being
skipped — the honest degradation from §7.2, exercised here.

⚠ **Every item must be obtainable in play.** A platform-proven failure mode: a game shipped
with 131 passing tests where no player could place anything, because every test set state
by hand. Guard with a test that completes an act using only in-game actions.

---

## 10. S5 — DM seat

The same module, same runtime, plus a human with authority. The DM seat can:

- See everything — full map, unrevealed areas, monster stats, remaining HP, upcoming
  wandering checks.
- Reveal and conceal.
- **Override any roll**, with the override recorded in the roll log as an override. A DM
  fudge is a legitimate part of running a table; an *invisible* one breaks replay. Both
  facts are respected by logging it honestly.
- Adjudicate every tier-3 ability, which is what the tier exists for.
- Move monsters, adjust HP, award XP and treasure ad hoc, insert an unplanned encounter.
- Pause, rewind to a prior roll index, and branch.

⚠ The DM seat is a **role on a session, not a separate application**. It is the same
runtime with a privileged view. Building it as its own client is how the two runtimes drift
apart and the format ends up serving only one.

---

## 11. Art

Not a slice — a thread landing per-slice. Platform standing order: **top-down, in the
artwork style of Factorio.** ★ **Dr. Ray, 2026-08-01, for Sanctuary specifically: use
PixelLab artwork, and NO ISOMETRIC TILES.** That is stronger than the platform's "prefer
top-down" — here isometric is not a fallback, it is excluded. Licence reinforces the whole
thread: the books' art is explicitly off-limits, so every image is made for Sanctuary.

Portraits are framed as portraits — a face is not a floor — but no *tile, map or scene* in
Sanctuary is ever drawn isometric.

| Lands with | Work |
|---|---|
| S1 | Character portraits by ancestry and class; a character sheet that reads as an artifact rather than a form; the dice tray and roll log |
| S2 | Monster portraits. 291 is the largest single art job on the platform — phase it by encounter frequency, `common` first, `unique` last |
| S3 | Dungeon tilesets: floors, walls, doors, stairs, water, rubble |
| S4/S5 | Map rendering, tokens, the DM's overview |

Operational notes carried from the platform's expensive lessons:

- ⚠ For a **floor**, do not reach for `create_topdown_tileset`. The Wang-transition model
  returns corrugated banding and composes a scene when asked for a transition. Use
  `create_tiles_pro` with `outline_mode: "segmentation"` and a numbered list of floors.
- ⚠ **Eight in-flight jobs, account-wide** — not per session, not per repo. Stagger: fire
  two, poll `get_image`, fire two more.
- ⚠ **`credits: $0.00` is normal and misleading.** Generations come from the subscription
  pool. Read `generations_remaining`.
- ⚠ **A rate-limited job was never queued.** Re-issue it unchanged; do not "fix" a prompt
  that was fine.
- Fetch within 8 hours before the object auto-deletes. Download with `curl --ssl-no-revoke`.
- A fill must read as a **surface, not a scene** — ground only, no horizon, no focal point.
- Anything carrying **state** (a lit vs unlit area, a revealed vs hidden room) is drawn
  procedurally, because a tile has no state. Tiled fills are otherwise encouraged.
- ⚠ **Assets must be SERVED, not merely present.** `/static` has gone unmounted on this
  platform while client tests read files off disk and passed.

---

## 12. Gates and tests

```bash
python app.py test          # → "sanctuary self-check OK — 239 tables, 291 monsters, 414 spells, ..."
python -m pytest tests/ -q
```

⚠ Numbers in that line are **interpolated from what the check computed**, never typed. The
gate output is this platform's behaviour documentation; a literal in a status line is a
stale second copy.

Structural invariants, each of which has a real failure behind it somewhere on this
platform:

- **`random.` / `Math.random` nowhere outside `dice.py`.** The only real guard against a
  second RNG.
- **Replay determinism** — same seed, identical log, across a full generated delve.
- **Table round-trip and spot-check** (§6.2).
- **Bestiary cross-source diff** — GM guide vs wiki, disagreements reported not swallowed.
- **Ligature normalisation** — no U+FB00–FB06 survives into the corpus.
- **Import direction** — no module imports leftward in the §5 chain.
- **Reachability** — no generated dungeon soft-locks an empty-handed party.
- **Completable using only in-game actions** — no hand-set state.
- **Licence notice present in the CLIENT**, both notices, plus `/licence`.
- **Every asset the client requests is actually served.**
- ⚠ **A single-seed gate cannot prove a generator property.** `app.py test` proves *this
  build* is playable; the suite proves *the generator* is sound across seeds. Keep the
  split — do not loop seeds inside `app.py test`.
- ⚠ **A string gate proves wiring exists, never that it is live.** Liveness is a browser
  question; sample the canvas.

---

## 12a. Versioning — minor tracks chapters

★ **Dr. Ray, 2026-08-01:** the minor version tracks the OSRIC chapter being ingested, and
**`v0.8.0` is the first playable build.** This is an explicit authorisation — the platform
rule is that Dr. Ray alone moves major and minor, and this is that instruction given in
advance for this repo.

| Version | Chapter | Ships |
|---|---|---|
| `v0.0.x` | — | Foundation: dice engine, table extraction, house chrome |
| `v0.1.0` | Ch.1 Creating a Character | 7 ancestries, 11 classes, 4 generation modes, derived stats |
| `v0.2.0` | Ch.2 Spells | 414 spells, slots, memorisation |
| `v0.3.0` | Ch.3 How to Play | Combat, time, movement, saves, morale, turning undead |
| `v0.4.0` | Ch.4 Dungeons, Towns and Wildernesses | D-1…D-24 procgen, encounters, traps |
| `v0.5.0` | Ch.5 Monsters | 291 bestiary, custom and edited beasts, effect tiers |
| `v0.6.0` | Ch.6 Treasure | Loot classes, coin, gems, jewellery, magic items |
| `v0.7.0` | — | Campaign format and authoring surfaces |
| **`v0.8.0`** | — | **First playable — solo runtime over all of the above** |

⚠ **The build restarts at `0` when the minor moves** (`v0.1.7-beta` → `v0.2.0-beta`), per
the platform rule. Every commit still bumps the build; the minor moves only when a chapter
lands complete.

⚠ This cuts across the S1–S5 slicing rather than replacing it. The slices are the
*architecture*; the chapters are the *delivery order*. Where they disagree the chapter
order wins for sequencing, because it is what Dr. Ray will see land — but the dependency
direction in §5 still holds, which is why the dice engine and table corpus must precede
`v0.1.0` rather than being a chapter of their own.

## 13. Platform changes

Shipping a game means the platform changes too. None optional, each missed at least once
before:

- Games page gets Sanctuary's card and stage.
- Copyright/trademark list updated **everywhere** it appears — it lives in four files.
- Joins Across-the-realms: serves `/leaderboard.json`, adds its `REALMS` row.
- Deploy registry, vhost, systemd unit.
- Row added to the SSoT's `| repo | gate |` table.
- `CLAUDE.md` with the vendored `<!-- tenshin:platform:start/end -->` block, plus
  `IMPROVEMENTS.md` for Sanctuary-specific architecture, gotchas and queue.
- Drop-ins vendored byte-identical: `tenshin_gate.py`, `tenshin_version.py`,
  `tenshin_client.py`, `tenshin_feedback.py`.

**Separate work, not Sanctuary's:** the site must state that most artwork across the
platform is generated using PixelLab. That is a `Website` repo change spanning all
eighteen games — attribution on the site, not a per-game notice — and it is tracked
independently of this spec.

---

## 14. Risks and open questions

| Risk | Handling |
|---|---|
| **Effects scope** — tier 2's vocabulary could grow without limit | Tier 3 is always a legitimate answer. Ship tier 2 partial; grow it from actual play. The failure mode is treating tier 2 as something to complete. |
| **291 monster portraits** | Phased by frequency; the game is playable before the art is finished. |
| **Format churn** | S3's format is the spine and S4/S5 depend on it. It should be exercised by loading Hyqueous-shaped content before S4 begins. |
| **Table extraction accuracy** | Round-trip plus spot-check plus cross-source diff. Three independent gates because a wrong number in a to-hit table is invisible in play. |
| **Scale** | Five slices is a large project. Each gets its own plan and its own build; this document is the shape, not the schedule. |

**Open, needs a decision before S3 is planned:** whether DM-authored campaigns are private
to their author, shareable by link, or published to a library visible to all Sanctuary
players. This affects storage, moderation and the account model, and it does not block S1
or S2.

---

*Sanctuary is an independent product published under the OSRIC 3.0 Third-Party License and
is not affiliated with Mythmere Games LLC.*
