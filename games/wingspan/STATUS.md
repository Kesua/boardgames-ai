# Wingspan — status

Base game only (180 birds, 26 bonus cards, base goal tiles), no expansions, no automa.

- [x] ingest-rules: `rules.md` W1–W14, decisions D1–D14 (section W15); two independent researchers (sources listed in the file)
- [x] build-card-db: `data/birds.json` (180), `data/bonus_cards.json`; two card lists compared field by field,
      third check against the fan wiki (177/180 agree, 3 resolved in `data/SOURCES.md`)
- [x] plan-engine: `PLAN.md`
- [x] build-engine: task-stack engine, 30 power types; 244 tests (every rule ID, one test per bird)
- [x] verify-engine: `checks/report.json` 0 problems (10,000 games, 2–5 players); independent audit in
      `checks/review.md` (no rule bug; 5 findings fixed)
- [x] design-rl: encoder (1,659 floats for 2 players, hides secret information), greedy agent with turn rollouts;
      smoke training learns (beats greedy after ~2.5M steps)
- [x] train-model: `models/p2-28m` (2 players, 28M steps, 6.0 hours): open run, anchored run, two more anchored stages
      (recipe in `model.json`). Strength card: 95.1 % against greedy (bar 95 %, passed narrowly), 90.9 % against an
      open-run checkpoint it never trained against, 89.7 % against the open-run best, 59.7 % against its 16M-step
      predecessor. Finished.
- [x] run-experiment: `experiments/p2-28m-mirror` (2,000 games, seed 1000, 95 seconds with 16 workers; `--verify 20` ok)
- [x] write-notes: `notes.json` (en + cs, 7 findings, known limit); `check_notes.py` recomputes all 43 cited numbers
      per language and 8 data-dependent claims
- [ ] publish-game: publisher notice not sent yet (needs the maintainer's go-ahead)

## Open
- Northern Mockingbird food cost: the two card lists agree, the wiki differs; kept with the card lists (`data/SOURCES.md`).
- 3–5 player models: not trained yet; the engine supports 2–5 players.
- The 2-player AI averages 70 points and passed the greedy bar narrowly; a stronger AI may need a larger network or
  a better encoder (design-rl), not more steps (`win_vs_3m` reached 0.5 at the end).
