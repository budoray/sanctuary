# Sanctuary — architecture, gotchas and queue

Design record: [`docs/superpowers/specs/2026-08-01-sanctuary-design.md`](docs/superpowers/specs/2026-08-01-sanctuary-design.md)
Build plan: [`docs/superpowers/plans/`](docs/superpowers/plans/)

## Architecture
One-way dependency chain, asserted by `tests/test_invariants.py`:
`character → tables → dice`. `dice.py` imports nothing of ours.

## PixelLab
Ten class portraits ship with Chapter 1 (top-down/Factorio-styled, per the platform standing
order — never isometric; the OSRIC licence forbids the books' art outright, so there is no
fallback for any of these). Still needed: monster portraits (291, Ch.5 — phase by encounter
frequency, `common` first), map chrome. Dungeon tilesets SHIPPED: twelve
top-down tiles in `static/art/tiles/` (manifest `data/art_tiles.yaml`), wired
into the delve's canvas map — `water.png` was later replaced with a procedural
pool (`v0.9.37-beta`); the PixelLab original was a flat fill.
⚠ For dungeon floors use `create_tiles_pro` with `outline_mode: "segmentation"` and a numbered
list of floors — **not** `create_topdown_tileset`, which composes a scene when what's wanted is
a transition.
⚠ **Style-drift lesson.** PixelLab's portrait model drifts hard between calls — the first three
class portraits came back in three different styles (painterly bust, bright lineart, anime).
Fix: designate one reference image up front and generate one portrait at a time, comparing each
new one against the reference before moving to the next.
Also worth remembering: up to 8 in-flight jobs account-wide; `credits: $0.00` is normal, read
`generations_remaining` instead; a rate-limited job is never queued, so re-issue it unchanged
rather than assuming it's in a backlog; fetch results within 8 hours, and use
`curl --ssl-no-revoke` when doing so.

## Gotchas earned in this build
- **Never hand-edit `data/tables/`.** Fix the extractor and re-extract — the round-trip test
  compares the committed corpus against a fresh extraction, so a hand-edit fails the gate.
- **The extractor is dumb on purpose.** Per-line prose-vs-data classification was tried and
  failed in both directions: it leaked 70 lines of narrative into two tables, and the tightened
  version then discarded genuine rows like `Lieutenant Special as type as type`. Blocks are
  judged whole.
- **19 table ids map to several files.** `tables.load()` raises and names the parts;
  `tables.parts()` returns them all. Indexing id → one path silently drops 26 tables with every
  test still green.
- **`rows()` must strip the 21-field armour-class header** — it starts with a digit, so a
  level-10 lookup once matched the HEADER instead of the level-10 row.
- **OSRIC's own footnotes contradict its tables twice**: magic-user hit dice stop at 11
  (footnote says 10), ranger at 10 (footnote says "after 11th"). The tables plus the general
  Constitution rule are authoritative. The ranger's 2d8 start makes its hit-dice count run one
  ahead of level, which is why the wrong footnote looks right.
- **Multi-class hit points divide PER CLASS ROLL, not once on the sum** — §1.3.11's Erix Uncle
  example divides one class's roll. The two readings disagree on 22% of seeds.
- **The brief/plan's own worked examples were wrong three times**, with tests that locked the
  error in. Transcription tasks need a data audit against the book, separate from the code
  review.

## Queue
- [x] Ch.2 Spells → `v0.2.0`
- [x] Ch.3 How to Play → `v0.3.0`
- [x] Ch.4 Dungeons, Towns and Wildernesses → `v0.4.0`
- [x] Ch.5 Monsters → `v0.5.0`
- [x] Ch.6 Treasure → `v0.6.0`
- [x] Campaign format and authoring → `v0.7.0`
- [x] First playable → `v0.8.0` (runtime + solo driver + client wiring shipped this
      chapter at `v0.7.x`; Dr. Ray moves the minor at the chapter boundary).
      Chapter closed at `v0.9.0-beta` (Dr. Ray, 2026-08-02) — the corpus-wide
      statline sweep below was the last item in it.
- [ ] Party (real-time, sockets, keyed by player name) and async drivers over the
      same `runtime.State` - `session.py` was written so `runtime` stays ignorant
      of which driver is in use
- [ ] Light and encumbrance in the runtime - skipped this chapter as not cheap;
      movement between areas is currently a flat 1 turn regardless of distance
- [ ] Tier-2 ability vocabulary in `runtime.py` is a keyword match over monster
      prose (`_TIER2_KEYWORDS`), not a real parser - grows as real play surfaces
      false positives/negatives
- [ ] `runtime._instantiate_monster`'s `hd_notation`/`hp_expr` split
      (`_hd_and_hp_expr`) defaults an HD-notation-only monster (no dice-shaped
      `hit_dice` field) to d8 per HD; add a `hit_die` schema field if a monster
      needs a different one
- [ ] `runtime.leave()` is callable from any area, not only the start area - a
      one-way chute/stairs can strand a party unable to retrace its steps, and
      forcing `leave` to happen only at area 1 would make that a soft lock

## Gotchas earned in this chapter (S4 - the play runtime)
- **A generated dungeon's own monster stock can flatten a fresh party.**
  OSRIC's d100 lair-count rolls (Table 2.7.3.2x) aren't scaled to the
  dungeon's stated party size - a level-1 room can come back with 15
  bugbears. `app.py`'s self-check tries a small fixed range of seeds and
  picks the first where the party survives its first encounter, rather
  than asserting against whichever seed happens to be unlucky.
- **`leave()` had to move off "only from area 1"** - a party funnelled
  through a one-way exit with no way back would otherwise never reach a
  terminal state, which is exactly the soft lock this platform has been
  burned by before.
- **Tier-3 surfacing is a keyword match over free-text ability/attack
  prose**, not a parser of the corpus's actual grammar - it is honest
  (never silently drops an ability) but will mis-tier things the
  vocabulary hasn't seen yet. Extend `_TIER2_KEYWORDS` as real play finds
  gaps, per design §7.2's own "ship with tier 2 half-filled and grow it."
- [ ] Constitution hit-point adjustment (deferred from Ch.1; lands with Ch.3)
- [ ] Armour class from equipment (deferred from Ch.1; lands with Ch.3)
- [ ] Thief skills and spell slots on the sheet (needs Ch.2 and Ch.3 tables)
- [ ] Dual-classing (human-only, sequential — a different mechanism from multi-classing)
- [ ] Extractor's sub-numbered id artefact: `TABLE 1.4.2.3A.1` becomes id `1.4.2.3a` with name
      `"1: CONTAINERS"`. Fix is to allow `(?:\.\d+)?` in the id group, then re-extract (Ch.6 work).
- [ ] Ability-conditioned level limits — `data/ancestries.yaml` stores best-case ceilings only;
      Ch.3 levelling must also check the relevant ability score.

## Gotchas earned fixing the encounter-resolution defect (S4, `v0.8.x`)
- **The GM Guide's D100 monster tables and the bestiary's own heading slugs
  never agreed on name order.** `bestiary.resolve_name()` now sits between
  a printed table name (`"Wolf, Dire"`, `"Devil, Assagim"`) and the corpus,
  trying the comma-inverted and category-dropped forms, a bare word
  reversal, and last a UNIQUE contiguous match inside another monster's own
  name field - never a fuzzy guess. `runtime._find_monster_record` is the
  only caller; it used to catch `bestiary.load()`'s `KeyError` directly.
- **`normal_dire.yaml` was the flagship bug, hiding in plain sight.** The
  extractor had mislabeled a genuine Wolf/Dire-Wolf collapsed entry with
  the source table's own column headers ("Normal"/"Dire") AS the monster's
  `name` field - so even a human skimming `data/monsters/` would read past
  it as unrelated. Split into `wolf.yaml` / `wolf_dire.yaml`.
- **A handful of `data/monsters/` files collapse SEVERAL creatures' stat
  blocks into one record** (`werebear_wereboar_wererat_weretiger_werewolf.yaml`
  and 5 others) - the extractor's per-line prose/data judgement runs on the
  whole block (see the "extractor is dumb on purpose" gotcha above), so a
  page with several breeds side by side becomes one record with none of
  them reachable by name. Split where the source gives genuinely separate
  combat stats per variant (hit_dice/armour_class/melee_attacks/experience);
  left collapsed - and matched by any of its names via `resolve_name`'s
  substring fallback - where the book prints one stat block for several
  breeds and splitting would mean inventing numbers. Split variants carry
  `abilities: []` - the source text interleaves several creatures' special
  abilities with no clean per-creature boundary; a follow-up could recover
  them by slicing on the embedded ALL-CAPS creature-name markers the same
  way `description` was recovered.
- **A resolvable name can still carry unparsable stats.** Two more corpus
  quirks surfaced only once `resolve_name` made them reachable: `bat_mobat`'s
  `hit_dice: "4-6"` parsed as HD 4 with a **-6 hit-point modifier** (the
  same hyphen-overload `tables.in_range` already documents, but
  `runtime._hd_and_hp_expr`'s own regex has the identical landmine and had
  never been exercised), and its `experience` field's "4HD: ... 5HD: ...
  6HD: ..." text handed `_instantiate_monster` the literal number `4` as
  the monster's XP. Fixed at the data layer (`hit_dice: '4'`, a single
  clean `experience` value) rather than in `runtime.py`, which is out of
  this fix's file scope - worth an audit of the rest of the corpus for the
  same pattern if it recurs.
- [x] Only `bat_mobat` was audited for the hyphen/multi-tier data landmine
      above; a full corpus sweep for other `hit_dice`/`experience` fields
      that parse but mean something else wasn't done - `resolve_name`
      making more of the corpus reachable will keep surfacing these.
      **Swept, `v0.8.16-beta`** - see below and
      [`metrics/2026-08-02-statline-parse-impact.md`](metrics/2026-08-02-statline-parse-impact.md).

## Gotchas earned in the living-map redesign (`v0.9.x`, 2026-08-02)
- **A generated dungeon can strand the party BY DESIGN.** One-way doors are
  real table output: a room whose own exit record is empty is a pocket, not
  a bug. Build the map's move controls from the CURRENT room's own exits —
  deriving them from other rooms' reverse exits renders doors the party
  cannot walk back through. The sealed room's copy owns the situation:
  "Search for a hidden way, or leave the delve."
- **Full re-render + CSS entrance animations = everything dances on every
  beat.** The dice ledger and the chronicle rebuild their lists each
  render; without the `prevRollsLen`/`prevDelveLogLen` sentinels marking
  only the new lines, every hit-point tick replays every entrance. Derive
  NOVELTY, not just content — and reset the sentinels at every fresh
  start, or a same-length new ledger dances nothing at all.
- **Verification is a driven browser, not a grep.** Each cycle shipped
  against Playwright-driven Chromium (probes in `scratchpad_dl/`,
  gitignored): click/tap-to-move, arrow- and number-key walking, decision
  locks, the guttering-torch epilogue were verified on pixels and console
  errors, never on markup. `#roll` 400s on ability minimums about half the
  time — re-roll loops are normal, not a failure.
- **The map is canvas, drawn from explored rooms only** (`renderMap` in
  `static/app.js`): 64px tiles, corridor memory light, rubble seals where
  one-way doors collapse. Hover, click, arrows and 1-9 all route through
  the same `act("move")` as the rail buttons — one door, four hands.

## Gotchas earned in the client redesign (`v0.9.1-beta`)
- **⚠⚠ `[hidden]` is ONLY `display: none` in the UA stylesheet, so any author
  rule setting `display` on the same element WINS.** `#forge { display: flex }`
  beat it, so `app.js`'s `forge.hidden = true` did nothing visible and the
  character-creation form stayed on screen for the whole delve — 976px tall,
  shoving the map to y=880 on a 720px viewport. **Every test passed**: they
  checked the `.hidden` property and the HTML source, neither of which knows
  what the cascade did. This is the platform's "check the CLIENT, not the
  server" lesson one layer deeper — checking the client's *markup* is still not
  checking what a player sees. Guarded now by
  `[hidden] { display: none !important }` once, globally, plus
  `test_hiding_an_element_actually_hides_it`.
- **Measure the rendered page, not the stylesheet.** The audit that found this
  read as three layout opinions until the numbers came back: map at y=880,
  page 4.24 screens, actions in a 398px gutter beside a 795px column holding
  one static SVG. Drive the real client and read `getBoundingClientRect`.
- **The delve's actions now live in the WIDE column** (`#party-status` moved
  from `#instruments` into `#stage`). `app.js` reaches every node by id and
  never by parent, so moving nodes between containers is free — worth knowing
  before the next layout change.
- **Combat now changes the page** via `main:has(#combat:not([hidden]))`, read
  off the `hidden` flag `app.js` already sets. No new markup, no new JS. Before
  this, a party mid-ambush saw a page pixel-identical to an empty corridor.
- **Two real faces, reused not re-sourced.** Source Serif 4 + IBM Plex Mono
  were already licensed and shipped at `../static/fonts`; copied into this
  game's own `/static` so the vhost never depends on another game's mount.
  `--font-display` and `--font-body` had been byte-identical `system-ui`.
- ⚠ **The browser pane caches `static/` hard.** Two verification passes read
  the OLD tokens.css and reported the fonts as not loading. `fetch(url,
  {cache:'reload'})` then re-navigate before believing a negative result.

## Gotchas earned in the corpus-wide statline sweep (`v0.8.16-beta`)
The sweep found the landmine was not two records, it was **160 hit dice, 91
experience awards and 6 armour classes** - 213,411 xp missing corpus-wide.
- **An unreadable statline degraded to HD 1 / `1d8` IN SILENCE.** Every dragon,
  giant, elemental, titan, treant, whale and lich in the book instantiated as a
  first-level chump, and nothing anywhere said so. The fix that matters is not
  the parser, it is that `_hd_and_hp_expr`'s output is now asserted against the
  corpus's own famous monsters, per the platform's "guard on OUTPUT, not
  inventory".
- **Fixed in the PARSER, not in `data/`** - reversing the earlier `bat_mobat`
  precedent deliberately. `data/monsters/` belongs to the extractor and the
  round-trip test re-extracts it, so 250 hand-edits would be clobbered on the
  next run. The book genuinely prints `"9 to 11"`, `"12 or more"` and
  `"1,400 +14/hp"`; reading those leniently is the reader's job.
- **⚠ The book's dashes are EN DASHES (U+2013), not hyphens** - `"17–22"`,
  `"–3 [23]"`. Every `[+-]` and `-?\d+` pattern misses them, which is how a pit
  fiend's AC −3 became AC 10, the easiest target in the book. The corpus is
  CORRECT here and the round-trip proves it; normalise on read, never in data.
  ⚠ Do not trust a terminal's rendering of these - a console that cannot encode
  U+2013 prints it as `�`, which reads exactly like extractor corruption
  and sent this fix chasing a bug that did not exist.
- **`"N+M"` hit dice are N dice plus M HIT POINTS.** The modifier was being
  dropped, so a troll rolled `6d8` rather than `6d8+6` - along with the whole
  demon, devil and giant shelf.
- **The `experience` field is not a number.** It carries thousands separators
  (`"1,400 +14/hp"` → the old `\d+` search returned **1**), per-HD tiers
  (`"4 HD: 75 +4/hp"` → returned **4**, the HD count) and HD/XP pairs
  (`"9/5,900"` → returned **9**).
- **Hit POINTS appear in the hit-dice field** (`"1 hit point"`, `"50 hp"`).
  `Dice.roll` cannot express a constant, so `_hd_and_hp_expr` returns a third
  `fixed_hp` value - rolling `50d8` for a clay golem is worse than not rolling.
- **`app.py`'s self-check was asking a HARDCODED Downloads path** whether the
  OSRIC PDFs existed - months after commit `638d9cd` replaced that lookup with
  `sanctuary/sources.py` for exactly this reason. It fixed `tests/` and
  `tools/` and missed `app.py`. The books were in `_reference/osric` the whole
  time; the gate printed `round-trip UNVERIFIED` at every run, and the test
  guarding that sentence accepted the *word* "UNVERIFIED" anywhere in it, so
  the lie was load-bearing. **When a lookup moves, grep for the old literal.**
