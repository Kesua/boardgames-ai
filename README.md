# boardgames.ai

**What does an AI learn when it plays a board game millions of times against itself?**

AI agents learn modern board games here only by playing against copies of themselves. Every finished AI then plays
thousands of games, and the dashboard shows what the winners did differently: which cards, combinations and habits
go with winning — with the uncertainty of every number, and the recipe to replay every game.

| Game | Players analysed | AI | Highlights |
|---|---|---|---|
| Forest Shuffle (+ Woodland Edge, Alpine) | 2, 4 | 15M-step AI (2 players, finished), earlier AI (4 players) | Gentian with butterflies wins most; real trees beat saplings; the first player wins 55 % |
| Wingspan (base game) | 2 | see the Lab tab | rules from two independent sources, 180 birds checked against three |

**Dashboard:** `python tools/build_site.py && python -m http.server -d site 8000` → http://127.0.0.1:8000
(also published to GitHub Pages on every merge).

## Why the numbers can be trusted
- **Rules:** written in own words with an ID per rule, from at least two independent sources; every disagreement is
  decided in the open (`games/<slug>/rules.md`).
- **Cards:** built by a script from two sources compared field by field, disputes settled by a third
  (`games/<slug>/data/SOURCES.md`).
- **Engine:** a test for every rule ID and every card; 10,000+ random games with conservation checks; an independent
  review before any training (`games/<slug>/checks/`).
- **AI strength:** every model has a strength card — paired games against opponents it never trained against and
  against a greedy baseline (`games/<slug>/models/<id>/model.json`).
- **Reproducible:** every experiment is a recipe (`experiment.json`); the same code, model and seed replay the same
  games. CI replays the first 20 games of every experiment and compares a fingerprint.

## Add a game
Open a branch and ask your coding agent (Claude Code, Codex, Grok, Cursor …) to *"add the game <name>"*. The agent
follows `AGENTS.md` and the step-by-step skills in `.agents/skills/` — rules, cards, engine, verification, training,
experiments, notes — and every step leaves files you can check. See [CONTRIBUTING.md](CONTRIBUTING.md) for what to
expect, how long it takes and how to judge the result.

## Repository layout
```
AGENTS.md            instructions for coding agents (CLAUDE.md imports it)
.agents/skills/      step-by-step skills (copied to .claude/skills/ by tools/sync_skills.py)
bgai/                shared platform: game contract, mechanics kit, agents, training, experiments, statistics
games/<slug>/        one game: rules, card data, engine, tests, models, experiments, notes, rights
games/_template/     a tiny complete game to start from
dashboard/           static dashboard pages; tools/build_site.py builds site/
tools/               repository checks, site build, regeneration, skill sync
```

## Development
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.lock   # Windows; use bin/ elsewhere
python -m pytest -q
python tools/check_repo.py
```
Training uses the GPU for the update when torch sees one (CUDA build of torch); everything works on CPU.

## Licences and rights
Code: MIT (`LICENSE`). Statistics, notes, rules summaries and model weights: CC BY 4.0 (`LICENSE-DATA`). Game names,
card names and card data belong to their publishers (`NOTICE.md`, `games/<slug>/RIGHTS.md`); this is an unofficial,
non-commercial research project and removes a game on the rights holder's request.
