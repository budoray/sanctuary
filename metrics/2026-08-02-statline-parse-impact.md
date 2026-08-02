# Bestiary statline parsing — corpus-wide impact

Measured 2026-08-02, over all **303 records** in `data/monsters/`, comparing
`sanctuary/runtime.py` before and after the statline fix.

Re-check by diffing against the pre-fix parser:
`git show 2f15b14:sanctuary/runtime.py` — its `_hd_and_hp_expr`, its
`re.search(r"\d+", experience)` and its `_LEAD_INT.match(armour_class)` are the
three "before" implementations these numbers were taken against.

| Field | Records whose parsed value changed |
|---|---|
| `hit_dice` | **160** |
| `experience` | **91** |
| `armour_class` | **6** |

Experience restored across the corpus: **213,411 xp**.

Largest single corrections — the old parser took the first `\d+`, so a thousands
separator truncated the award at its first digit:

| Monster | before | after |
|---|---|---|
| Kraken | 17 | 17,500 |
| Lich | 10 | 10,000 |
| Pit Fiend (greater Devil) | 7 | 7,900 |
| Efreet | 7 | 7,000 |
| Giant, Storm | 6 | 6,000 |
| Dread Wraith | 9 | 5,900 |
| Aerial Servant | 5 | 5,250 |
| Purple Worm | 5 | 5,000 |

The `hit_dice` count is the one that mattered in play: an unreadable statline
degraded to HD 1 with `1d8` hit points **in silence**, which is what every
dragon, giant, elemental, titan, treant, whale and lich in the book was worth
to a first-level party. Guarded now by
`tests/test_runtime.py::test_no_shipped_monster_silently_becomes_a_one_hit_die_pushover`
and by three scenarios in `features/bestiary.feature`.

Not fixed here, and still counted in the 160: a collapsed multi-creature record
(`black_blue_green_red_white.yaml` holds `8 5+1 6 4+2 7`) resolves to its FIRST
variant's hit dice for every name that reaches it. A black dragon's 8 HD beats
the 1 HD it used to get; a red dragon reaching that same record still gets the
black dragon's. Splitting those records is the open queue item.
