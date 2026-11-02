# <Game name> — status

Edition modelled: <base game / expansions>. Keep this file current; it is how another agent or person continues.

Fit check (new-game step 1): player counts, number of distinct cards/pieces, hidden information, randomness, anything
real-time or dexterity-based, any choice too large to number.

- [ ] ingest-rules: rules.md with IDs, 2 independent sources, decisions listed
- [ ] build-card-db: data/*.json, data/SOURCES.md, field-by-field check of 2 sources (+ 3rd for disputes)
      (a deck of plain number cards needs no database: say so in data/SOURCES.md with the rule that defines it)
- [ ] plan-engine: PLAN.md (state, decisions, action numbering, effects, scoring)
- [ ] build-engine: engine + tests (every rule ID, every card)
- [ ] verify-engine: checks/report.json 0 problems (10,000 games per player count), independent review in checks/review.md
- [ ] design-rl: encoder, greedy, smoke training learns
- [ ] train-model: open run, anchored run, acceptance -> finished model
- [ ] run-experiment: mirror (+ versus) per player count, --verify passes
- [ ] write-notes: notes.json (en + other languages)
- [ ] publish-game: check_repo passes, publisher notice drafted, PR opened

## Open questions
