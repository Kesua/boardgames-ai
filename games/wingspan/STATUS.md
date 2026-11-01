# Wingspan — status

Base game only (180 birds, 26 bonus cards, base goal tiles), no expansions, no automa.

- [x] ingest-rules: `rules.md` W1–W15, decisions D1–D14; two independent researchers (sources listed in the file)
- [x] build-card-db: `data/birds.json` (180), `data/bonus_cards.json`; two card lists compared field by field,
      third check against the fan wiki (177/180 agree, 3 resolved in `data/SOURCES.md`)
- [x] plan-engine: `PLAN.md`
- [x] build-engine: task-stack engine, 30 power types; 244 tests (every rule ID, one test per bird)
- [x] verify-engine: `checks/report.json` 0 problems (10,000 games, 2–5 players); independent audit in
      `checks/review.md` (no rule bug; 5 findings fixed)
- [x] design-rl: encoder (1,659 floats for 2 players, hides secret information), greedy agent with turn rollouts;
      smoke training learns (beats greedy after ~2.5M steps)
- [ ] train-model: open run started 2026-11-02 00:25 (`runs/wingspan/open`), anchored run and acceptance to follow
- [ ] run-experiment: `p2-<model>-mirror` (2,000 games, seed 1000)
- [ ] write-notes: `notes.json` (en + cs)
- [ ] publish-game: publisher notice not sent yet (needs the maintainer's go-ahead)

## Open
- Northern Mockingbird food cost: the two card lists agree, the wiki differs; kept with the card lists (`data/SOURCES.md`).
- 3–5 player models: not trained yet; the engine supports 2–5 players.
