---
name: build-card-db
description: Build games/<slug>/data/ (cards, components, effects as structured data) from two independent card lists, compare them field by field with a script, settle disputes with a third source, and document it in data/SOURCES.md. Use after ingest-rules.
---

# Build the card database

## Goal
Every statistic on the dashboard is "per card". A wrong cost, point value or effect silently skews everything. The
card data must therefore be built by a script from sources, checked field by field against an independent second
source, and every disagreement settled and written down. Effects are stored as **structured data** the engine runs,
never as copied card text.

## Steps
1. **Find two sources**: community card databases (apps' data files, BoardGameGeek spreadsheets), fan wikis, open-source
   implementations of the game on GitHub (their data files and scoring code are precise), the publisher's card
   appendix, the requester's photos of their own cards. Prefer machine-readable files. Download to `inbox/`.
   Two copies of one list are one source. A deck of plain number cards (no effects) needs no database: build it from
   the rule that defines it, compare the range and counts with the second rules source, and give each card a test.
2. **Design the schema** (`data/<things>.json`): stable integer `id`, `name`, every number and icon that rules refer to,
   and `effect`/`power` as a small dict with a `type` and parameters. List all distinct effect texts first
   (a script that groups identical texts); each group becomes one effect type. Wingspan: 180 birds → 30 types.
3. **Write `data/build_cards.py`** that reads both sources, normalises names, builds the JSON, and **fails** on any
   difference not listed in an explicit `OVERRIDES` / `EXPECTED_DIFFS` with a reason. Parse effect texts of **both**
   sources with the same parser: if the two wordings give different structured effects, that is a finding.
4. **Third source for disputes** (and ideally a full independent check): e.g. one page per card on a fan wiki,
   compared by a separate agent with a script. Example result: `games/wingspan/data/SOURCES.md` (177/180 agree; the
   3 differences explained).
5. **Pin totals in a test** (`tests/test_data.py`): counts by type, colour, cost, points distribution, etc., so an
   accidental data change fails loudly.
6. Short own-words descriptions for the dashboard: generate them from the structured effect (`describe.py`), or
   write them yourself — never copy the printed text.

## Done when
`build_cards.py` runs clean on the downloaded sources, `SOURCES.md` lists sources, method and every resolved
difference, and `tests/test_data.py` passes.

## Pitfalls
- Two "independent" community lists often descend from one spreadsheet — then they share its errors. A third,
  differently made source is what catches them.
- Names differ in hyphens and case ("Black-Bellied Whistling-Duck"); normalise before joining.
- Expansion content hides in "core" lists (Swift-Start promo birds; expansion words in bonus-card flags).
- Typos in published lists exist (overlapping tiers "5–6: 3; 6+: 6"). Decide with the rules sources and record it.
