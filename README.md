# boardgames.ai

**What does an AI learn when it plays a board game against itself — and what can players learn from it?**

Here AI agents learn modern board games only by playing against copies of themselves: millions of moves, tens of
thousands of games, no strategy taught. A finished AI then plays 2,000 recorded games, every final board is scored
piece by piece, and a public dashboard shows what the winners did differently — which cards, combinations and habits
go with winning — with the uncertainty of every number and the recipe to replay every game.

## What a player sees on the dashboard
- **Discoveries** — the main findings in a few sentences, each with its numbers and a chart.
- **Strategy** — the winning plan in plain words, what to avoid, how much going first matters.
- **Cards** — every card: how often it is played, the points it brings, how much more often its owners win.
- **Boards** (forests, player mats) — example final boards and which overall plans win.
- **Play style** and **Game length** — what the AI does on its turns and how the length changes things.
- **Lab** — how each AI was trained and tested, and the exact command that replays each experiment.
- **How to read** — every measure explained in plain words.

These are patterns in the AI's own games: they show what winners have more of, not always why, and how an AI wins
against an equally strong copy of itself — not a proven best strategy.

**See it:** the site is published to GitHub Pages from `main`. Locally:
`python tools/build_site.py && python -m http.server -d site 8000` → http://127.0.0.1:8000

## Games

| Game | State | Examples of what the AI's games show |
|---|---|---|
| Forest Shuffle (base + Woodland Edge + Alpine) | **2 players:** finished AI (15M training steps), 2,000 games. **4 players:** finished AI (9M training steps), 2,000 games. | With 2 players combinations win (butterflies with Gentian, cloven-hoofed animals with a Wolf); with 4 players games are short and cards that score at once win (Steinbock, Fallow Deer, Common Raven); forests of the Stone Pine symbol win most with both. |
| Wingspan (base game) | **2 players:** finished AI (28M training steps), 2,000 games. 3–5 players: not trained yet. | Winners gain most on round goals, eggs and tucked cards, not on the birds' printed points; birds that tuck cards from your hand go with winning; mats built mainly in the forest win less often. |

## Why you can trust the numbers — and how far

| Evidence | Forest Shuffle | Wingspan |
|---|---|---|
| Rules in own words, an ID and a test per rule | `rules.md` F1–F7, from the three official rulebooks | `rules.md` W1–W14, two independent researchers, 14 decisions where sources differed |
| Card data checked field by field | against the official card appendix and three independent implementations; 3 errors found and fixed (`data/SOURCES.md`) | two card lists compared field by field, a fan wiki as third source: 177/180 agree, 3 settled (`data/SOURCES.md`) |
| A test for every card | all 92 species | all 180 birds |
| Automated engine checks | 10,000 random games per player count (`checks/report.json`) | 10,000 random games per player count |
| Independent review | card check, and the port replayed the original project's games identically (`checks/review.md`) | audit of code against rules: 5 findings, all fixed (`checks/review.md`) |
| AI strength card: paired games against opponents it never trained against and a simple greedy player | 2 players: wins 98.6 % against an earlier AI and 95.9 % against a checkpoint from another training run (1,500 games each), 100 % against the greedy player (400 games). 4 players (equal strength = 25 %): 84.0 % against a checkpoint from another run and 84.2 % against an earlier AI (3,000 games each), 99.6 % against the greedy player (2,000 games) | 2 players: wins 90.9 % against a checkpoint from another training run (1,500 games), 95.1 % against the greedy player (1,000 games; bar 95 %, passed narrowly) |
| Reproducible | every experiment is a recipe (code, model, seeds); CI replays its first 20 games and compares their final scores | same |

`tools/check_repo.py` (run by CI on every pull request) fails when a rule or card has no test, when the engine
changed after its check report, or when a pipeline file is missing.

Known limit: the Forest Shuffle models were trained before an independent card check corrected one card's scoring
(European Wildcat) on 2026-11-02. All experiments were re-run on the corrected engine; the models themselves were not
retrained (the card is in 0.4 % of the 2-player forests and 1.2 % of the 4-player forests).

The Wingspan AI averages 70 points a game and passed the greedy bar narrowly: a sound player, not an expert; its
findings show what works at that level.

## Add a game
Open a branch and ask your coding agent (Claude Code, Codex, Grok, Cursor …) to *"add the game <name>"*. The agent
follows `AGENTS.md` and the step-by-step skills in `.agents/skills/` — rules, cards, engine, verification, training,
experiments, notes — and every step leaves files you can check. [CONTRIBUTING.md](CONTRIBUTING.md) says what it costs
in your time, agent time and machine time, how to start, and how to judge the result
(`python tools/review_pr.py --game <slug>` does the mechanical part of a review).

## Install
Python 3.10 or newer. Run every command from the repository root.
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock     # Windows; on Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q                            # about 30 seconds
.venv/Scripts/python tools/check_repo.py
```
Training uses an NVIDIA GPU for the update step when torch sees one. On Windows, add the CUDA build after the line
above: `pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cu126` (on Linux the default torch
already includes CUDA). Everything also works on the CPU, more slowly.

## Repository layout
```
AGENTS.md            instructions for coding agents (CLAUDE.md imports it)
.agents/skills/      step-by-step skills (copied to .claude/skills/ by tools/sync_skills.py)
bgai/                shared platform: game contract, mechanics kit, agents, training, experiments, statistics
games/<slug>/        one game: rules, card data, engine, tests, checks, models, experiments, notes, rights
games/_template/     a tiny complete game to start from (tools/new_game.py copies it)
dashboard/           static dashboard pages; tools/build_site.py builds site/
tools/               repository checks, review helper, site build, regeneration, skill sync
```

## Contact
Questions, errors in a game or ideas: open a GitHub issue. Rights holders who want a game changed or removed: open an
issue titled "Rights: <game>", or contact the maintainer privately through the e-mail on the repository owner's
GitHub profile; we act within 7 days (`.agents/skills/handle-takedown/SKILL.md`).

## Licences and rights
Code: MIT (`LICENSE`). Statistics, notes, rules summaries and model weights: CC BY 4.0 (`LICENSE-DATA`). Game names,
card names and card data belong to their publishers (`NOTICE.md`, `games/<slug>/RIGHTS.md`); this is an unofficial,
non-commercial research project and removes a game on the rights holder's request.
