# Forest Shuffle — status

Ported from the original `forrest-shuffle` project (engine, models and records); every step below was redone or
re-checked on this platform.

- [x] ingest-rules: `rules.md` in our own words, rule IDs F1.1–F7.1; tests are marked with the IDs
- [x] build-card-db: `data/` (card list from the original project, checked card by card while building it; see `card_catalog.md`)
- [x] plan-engine: `PLAN.md`
- [x] build-engine: engine on the mechanics kit (Deck, DecisionStack, TextLog, CodecBuilder); 136 tests
- [x] verify-engine: `checks/report.json` 0 problems (2,000 games, 2–5 players); the first 40 games of all four
      original record files replay identically after the port
- [x] design-rl: encoder v2 (v1 kept for the legacy models), greedy agent
- [x] train-model: `models/p2-v2fix-15m` finished (main); `p2-v1-7.2m`, `p4-v1-6.8m` legacy (no anchored run)
- [x] run-experiment: `p2-v2fix-15m-mirror`, `p2-v1-7.2m-mirror`, `p2-v2fix-15m-vs-v1-7.2m`, `p4-v1-6.8m-mirror`;
      `--verify 20` matches for all four
- [x] write-notes: `notes.json` (en + cs)
- [ ] publish-game: check_repo passes; publisher notice not sent yet (needs the maintainer's go-ahead)

## Open
- 4-player model is a legacy model trained before the train-model recipe existed; a finished 4p model would replace
  `p4-v1-6.8m` (open run + anchored run, then a new `p4-…-mirror` experiment).
