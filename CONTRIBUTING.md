# Contributing — adding a game

## What you are signing up for
Adding a game means: the rules and cards captured exactly, an engine proven by tests and an independent review, an
AI trained until it is strong, and standard experiments anyone can replay. A coding agent does most of the work by
following the skills; you steer, answer questions only you can answer, and check the evidence at each step.

| Step (skill) | Typical effort | You check |
|---|---|---|
| new-game | minutes | the game fits (turn-based, no dexterity), slug and branch |
| ingest-rules | hours | `rules.md`: two sources, every rule an ID, a decisions table |
| build-card-db | hours | `data/SOURCES.md`: field-by-field comparison, disputes settled |
| plan-engine | an hour | `PLAN.md` makes sense to you |
| build-engine | hours–days | tests named by rule ID; one test per card |
| verify-engine | hours | `checks/report.json` 0 problems; `checks/review.md` findings resolved |
| design-rl | an hour | smoke training beats random |
| train-model | ≤ 24 h per player count (machine time) | strength card says finished |
| run-experiment | minutes–an hour | `--verify 20` prints "match" |
| write-notes | an hour | every number in notes.json is on the dashboard |
| publish-game | an hour | PR checklist complete |

Hardware: one desktop; a GPU halves training time but is not required. Agents' token use is moderate when they
follow `AGENTS.md` §6 (scripts instead of reading whole files).

## How to start
```bash
git checkout -b game/<slug>
# then tell your agent: "Add the game <Name> (<edition>) to boardgames.ai. Follow AGENTS.md and the new-game skill."
```

## How to judge an agent's (or a person's) work
Use the `review-game-pr` skill — it is the maintainers' checklist. In short:
1. CI green (tests, `tools/check_repo.py`).
2. Spot-check 5 rules and 5 cards against the official rulebook and cards yourself.
3. Read one random game log for two minutes: does it look like the real game?
4. The model's strength card says finished; the training curve did not collapse.
5. Replay one experiment: `python -m bgai.experiment --game <slug> --id <id> --verify 20`.
6. Three numbers from the notes appear on the dashboard; no "X makes you win" claims.
7. No PDFs, art or copied card/rule text; `RIGHTS.md` present.

## Rules of the road
- Never commit rulebooks, card images, copied texts, raw game records or training runs.
- Platform changes (`bgai/`) follow the `upgrade-platform` skill; shared parts the `extract-to-kit` skill.
- Publisher notices are sent by maintainers, never automatically.
- Be kind in reviews; ask for evidence, not effort.
