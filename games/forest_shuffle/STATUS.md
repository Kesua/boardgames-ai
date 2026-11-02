# Forest Shuffle — status

Ported from the original `forrest-shuffle` project (engine, models and records); every step below was redone or
re-checked on this platform.

- [x] ingest-rules: `rules.md` in our own words, rule IDs F1.1–F7.1, from the official base, Woodland Edge and Alpine rulebooks
- [x] build-card-db: `data/cards.json`; field-by-field check against the official card appendix and three independent
      implementations (`data/SOURCES.md`): 2,781 of 2,794 comparisons agree; 3 data errors found and fixed 2026-11-02
- [x] plan-engine: `PLAN.md`
- [x] build-engine: engine on the mechanics kit (Deck, DecisionStack, TextLog, CodecBuilder); 234 tests: every rule ID,
      every one of the 92 species (`tests/test_cards.py`)
- [x] verify-engine: `checks/report.json` 0 problems, 10,000 games per player count (2–5) on the fixed engine, with card
      conservation and the hand limit; independent review in `checks/review.md`
- [x] design-rl: encoder v2 (v1 kept for the legacy models), greedy agent
- [x] train-model: `models/p2-v2fix-15m` finished (2 players); `p2-v1-7.2m` and `p4-v1-6.8m` legacy (trained before
      the recipe, not finished). All three were trained before the European Wildcat fix (see Open).
- [x] run-experiment: `p2-v2fix-15m-mirror`, `p2-v1-7.2m-mirror`, `p2-v2fix-15m-vs-v1-7.2m`, `p4-v1-6.8m-mirror`,
      re-run on the fixed engine 2026-11-02; `--verify 20` matches for all four
- [x] write-notes: `notes.json` (en + cs); `python games/forest_shuffle/check_notes.py` confirms all 94 cited numbers
- [ ] publish-game: publisher notice drafted in the publish-game skill, not sent (the maintainer sends it)

## Open
- A finished 4-player model with the train-model recipe would replace the early `p4-v1-6.8m` (open run + anchored run,
  then a new `p4-…-mirror` experiment).
- Retraining the 2-player model on the fixed engine would remove the remaining doubt about the European Wildcat
  (in 0.4 % of its forests).
