# Independent reviews of the Forest Shuffle engine and data

## 1. Port from the original project
The engine was ported from the original `forrest-shuffle` project onto the platform's mechanics kit. Before any rule
fix, the first 40 games of each of the four original record files replayed identically (same final scores, same
decisions), and the summary numbers matched the original analysis to within 5e-7.

## 2. Card data against independent sources (2026-11-02)
An agent that did not build the data compared every field of every card with the official card appendix, the
rulebooks and three independent implementations (`data/SOURCES.md`). Findings:

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | bug (scores) | European Wildcat scored 1 per Bird instead of 1 per Woodland Edge card | data fixed; `test_wildcat_counts_woodland_edge_cards`; experiments re-run |
| 2 | bug (option) | base-game-only setup removed 10 cards too many (F2.1) | rule fixed; `test_removal_counts` |
| 3 | timing (rare) | Black Trumpet works from the moment it is placed, not from the next turn (F4.6) | fixed; `test_black_trumpet_works_in_the_turn_it_is_placed` |

## 3. Tests
Every rule ID (F1.1–F7.1) has a test; every one of the 92 species has a test marked with its card id, with expected
values computed by hand from the card's rule (`tests/test_cards.py`, guarded by `test_every_species_has_a_card_test`).
Writing these tests found no other disagreement between engine and card rules.

## 4. Automated checks
`report.json` (`python -m bgai.checks --game forest_shuffle --games 10000`): 10,000 random games per player count,
including card conservation, the hand limit, the encoder range and greedy-beats-random.

## Known limits
- The trained models learned with the old Wildcat value (1 per Bird). The card was in 0.4 % of the 2-player and 6 % of
  the 4-player forests, so the 2-player AI's play hardly depends on it; the 4-player AI may undervalue it. Findings
  about the Wildcat itself are therefore tentative until a model is retrained on the fixed engine.
