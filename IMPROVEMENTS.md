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
- [ ] Ch.2 Spells → `v0.2.0`
- [ ] Ch.3 How to Play → `v0.3.0`
- [ ] Ch.4 Dungeons, Towns and Wildernesses → `v0.4.0`
- [ ] Ch.5 Monsters → `v0.5.0`
- [ ] Ch.6 Treasure → `v0.6.0`
- [ ] Campaign format and authoring → `v0.7.0`
- [ ] First playable → `v0.8.0`
- [ ] Constitution hit-point adjustment (deferred from Ch.1; lands with Ch.3)
- [ ] Armour class from equipment (deferred from Ch.1; lands with Ch.3)
- [ ] Thief skills and spell slots on the sheet (needs Ch.2 and Ch.3 tables)
- [ ] Dual-classing (human-only, sequential — a different mechanism from multi-classing)
- [ ] Extractor's sub-numbered id artefact: `TABLE 1.4.2.3A.1` becomes id `1.4.2.3a` with name
      `"1: CONTAINERS"`. Fix is to allow `(?:\.\d+)?` in the id group, then re-extract (Ch.6 work).
- [ ] Ability-conditioned level limits — `data/ancestries.yaml` stores best-case ceilings only;
      Ch.3 levelling must also check the relevant ability score.
