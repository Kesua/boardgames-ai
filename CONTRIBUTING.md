# Contributing — adding a game

## What you are signing up for
Adding a game means: the rules and cards captured exactly, an engine proven by tests and an independent review, an
AI trained until it is strong, and standard experiments anyone can replay. A coding agent does most of the work by
following the skills; you steer, answer questions only you can answer (which edition? is this ruling right?), and
check the evidence at each step.

You can stop after the engine: an **engine-only pull request** (rules, cards, engine, tests, checks, review) is
welcome and is listed as "engine ready, AI not trained yet". Training needs a strong machine for about a day per
player count and can come later, from you or anyone else.

## What it costs (measured on the games done so far)

| | Small game (No Thanks!, 33 number cards) | Large game (Wingspan, 180 birds with 30 power types) |
|---|---|---|
| Your time (estimate) | 15 minutes: start it, answer questions, review | a few hours over several days: decisions where sources differ, spot checks, review |
| Agent time, rules to engine | under 1 hour, about 0.2M tokens (a dry run, not kept in the repository) | about a day across several agent sessions; tokens not measured |
| Engine checks (10,000 games per player count) | 30 seconds | Wingspan 16 minutes, Forest Shuffle 53 minutes (4 player counts) |
| Training, per player count | under an hour | the 2-player Forest Shuffle model: 10.7 hours (in the original project) |
| Experiment (2,000 games) | seconds | Forest Shuffle 5–9 minutes with 4 worker processes |

Machine used for these numbers: a 22-core laptop CPU, 64 GB memory, an RTX 4070 Laptop GPU (8 GB). Training speed
there: Wingspan about 4M steps per hour with 10 game workers. We have not measured smaller machines; plan for at
least 8 cores and 32 GB memory for training (each evaluation worker loads torch, about 1.7 GB). Without a GPU the
update step runs on the CPU (not measured; expect slower training). Default to training 2 players first.

| Step (skill) | You check |
|---|---|
| new-game | the game fits (turn-based, no dexterity), slug and branch |
| ingest-rules | `rules.md`: two independent sources, every rule an ID, a decisions table |
| build-card-db | `data/SOURCES.md`: field-by-field comparison, disputes settled |
| plan-engine | `PLAN.md` makes sense to you |
| build-engine | tests named by rule ID; one test per card |
| verify-engine | `checks/report.json` 0 problems; `checks/review.md` findings resolved |
| design-rl | smoke training beats random and, in paired games, greedy |
| train-model | the strength card says finished |
| run-experiment | `--verify 20` prints "match" |
| write-notes | every number in notes.json is on the dashboard |
| publish-game | `python tools/review_pr.py` suggests approve |

## The first hour
```bash
git clone <this repository> && cd boardgames-ai
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q && .venv/Scripts/python tools/check_repo.py     # about 30 seconds
git checkout -b game/<slug>
```
Then tell your agent: *"Add the game <Name> (<edition>) to boardgames.ai. Follow AGENTS.md and the new-game skill."*
It scaffolds the folder with `python tools/new_game.py --slug <slug> --name "<Name>"` and works step by step; read
`games/<slug>/STATUS.md` to see where it is. Have ready: which edition and expansions, and a link to the official
rulebook if you have one (some rule sites refuse automated downloads).

## How to judge an agent's (or a person's) work
```bash
python tools/review_pr.py --game <slug> --base main
```
runs the tests, the repository rules, the replays and the strength cards, lists files changed outside the game
folder, picks 5 rules and 5 cards for you to compare with the real rulebook and cards, prints one game as text, and
suggests a verdict. The `review-game-pr` skill explains each item and when it fails. In short, the work is worth
merging when:
1. CI is green (tests, `tools/check_repo.py` — which already requires a test for every rule and card and a fresh
   engine check report).
2. The 5 rules and 5 cards you spot-check match the official ones.
3. The printed game looks like the real game to someone who knows it.
4. The model's strength card says finished and the training curve did not collapse — or it is an engine-only pull
   request.
5. Three numbers from the notes appear on the dashboard; no "X makes you win" claims.
6. No PDFs, art or copied card/rule text; `RIGHTS.md` present.

## Rules of the road
- Never commit rulebooks, card images, copied texts, raw game records or training runs.
- Platform changes (`bgai/`) follow the `upgrade-platform` skill; shared parts the `extract-to-kit` skill.
- Publisher notices are sent by maintainers, never automatically.
- Be kind in reviews; ask for evidence, not effort.
