# Forest Shuffle card data — sources and checks

`cards.json` covers the base game, Woodland Edge and Alpine: 92 species, 368 card faces, 230 physical deck cards
(233 with the 3 winter cards). It was first built from the BoardGameArena card sheets and the base-game reference
cards (see `card_catalog.md`), then checked field by field against independent sources on 2026-11-02 by an agent that
did not build it.

| # | Source | What it covers | Why independent |
|---|---|---|---|
| S1 | [soldag/forest-shuffle-scoring](https://github.com/soldag/forest-shuffle-scoring) (commit f701696) | types, cost, every card face with copy count, full scoring code | hand-entered TypeScript scoring app, no BGA code |
| S2 | [lem-solutions/mischwald](https://github.com/lem-solutions/mischwald) (commit 4e61804) | every physical card as a pair of halves with tree symbols; cost, types, effects, bonuses, scoring | German-language Rust engine, own card order |
| S3 | Lookout's official card appendix (EN, version 2025-02-19) | per species: position, copies, cost, effect, bonus, permanent effect, scoring with worked examples | the publisher's own text |
| S4 | the official base, Woodland Edge and Alpine rulebooks | component counts, setup removal, winter cards, clearing, cave, ties | the publisher's own text |
| S5 | [NINI1988/ForestDetector](https://github.com/NINI1988/ForestDetector) (commit cefac19) | every distinct card face with its tree colour | built from photos of real cards |

No source text, image or PDF is stored in this repository; the sources were read in a scratch folder.

## Result
2,794 single comparisons: 2,781 agree. Card faces vs S1 368/368; physical cards vs S2 229/229 (S2 lacks one Alpine
card; S5's card order confirms the pairing); distinct faces vs S5 265/265; copies per species 92/92 against S1, S2
and S3; position 92/92 against all; types 92/92 against S1 and S2.

| Difference | Data | Sources | Verdict |
|---|---|---|---|
| European Wildcat scoring | was 1 per Bird | S1, S2, S3 (with a worked example): 1 per Woodland Edge card, itself included | **data was wrong, fixed 2026-11-02**; all experiments re-run on the fixed engine (models were trained with the old value; the card was in 0.4 % of the 2-player and 6 % of the 4-player forests) |
| Setup removal, base game only | removed 10 extra cards | S4: the extra 10 only with an expansion | **rule was wrong, fixed** (no effect on the default all-expansions setup used everywhere) |
| Black Trumpet timing | worked from the next turn | S3: "from now on" (the other mushrooms: from the next turn) | **fixed**; matters only when another Alps card is placed later in the same turn |
| Horse Chestnut, Wood Ant, Crane Fly, Gentian cost | 1, 1, 1, 0 | S1 differs; S2 and S3 agree with the data | data right |
| Penny Bun trigger, Blueberry effect, Digitalis table, Roe Deer / Chamois symbol | as in the data | S2 differs (copy errors); S1/S3 agree with the data | data right |

Not verifiable from text: type and tree-symbol icons in S3 (images); they rest on S1, S2 and S5, which agree.
