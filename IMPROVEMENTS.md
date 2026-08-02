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
frequency, `common` first), dungeon tilesets (Ch.4), map chrome.
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
- [ ] First playable → `v0.8.0` (runtime + solo driver + client wiring shipped this
      chapter at `v0.7.x`; Dr. Ray moves the minor at the chapter boundary)
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
- [ ] Only `bat_mobat` was audited for the hyphen/multi-tier data landmine
      above; a full corpus sweep for other `hit_dice`/`experience` fields
      that parse but mean something else wasn't done - `resolve_name`
      making more of the corpus reachable will keep surfacing these.
