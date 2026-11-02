# AGENTS.md — instructions for coding agents (Claude Code, Codex, Grok, Cursor, …)

This is the single source of instructions for every agent working here. `CLAUDE.md` only imports this file.
Skills (step-by-step guides) live in `.agents/skills/<name>/SKILL.md`; `.claude/skills/` is a generated copy.
Read this file fully once; then read only the skill for the step you are doing.

## 1. What this repository is for (read this first — every decision follows from it)

**Goal:** show players of modern board games which cards, combinations and habits win — learned by AI agents that
taught themselves each game by playing against copies of themselves (millions of moves, tens of thousands of games),
and measured over thousands of recorded games. The public dashboard (static site built from `games/*/`) is the product. Everything else exists
to make its numbers **correct, reproducible and honest**:

- **Correct**: an engine bug becomes a false "insight" read by thousands of players. Rules come from at least two
  independent sources, every rule has an ID and a test, every card has a test, and an independent review happens
  before any training.
- **Reproducible**: anyone can replay any experiment exactly from its recipe (`experiment.json`) and the stored
  model; CI replays the first 20 games of every experiment and compares a fingerprint.
- **Honest**: numbers are correlations from one AI's games, shown with uncertainty; small samples are greyed; the
  AI's strength is shown on a strength card; written notes say what is shown, not why.

**Non-goals:** no way to play or watch games; no raw game records in git (they are regenerated from recipes); no
copied rulebook or card text, no art (rights, see `games/<slug>/RIGHTS.md`).

## 2. Repository map

| Path | What it is |
|---|---|
| `bgai/game.py` | **The contract** between the platform and a game (`GameSpec`, `Game` protocol). Read it before writing an engine. |
| `bgai/kit/` | Shared mechanics: `Deck`, `Rng`, `DecisionStack`, `CodecBuilder`, `winners/ranks`, `TextLog`, encoding helpers. Read `bgai/kit/README.md`. |
| `bgai/agents.py` | Random and trained (policy) agents, `play_game`. |
| `bgai/rl/` | Self-play PPO trainer (`train.py`, `selfplay.py`) and paired head-to-head evaluation (`h2h.py`). |
| `bgai/checks.py` | Automated engine checks per player count (ends, legality, determinism, clone, scores, records, encoder range, greedy beats random, invariants). |
| `bgai/show.py` | Prints one game as text (`python -m bgai.show --game <slug>`), for reading a game against the rules. |
| `bgai/manifest.schema.json` | Every `manifest.json` key explained; `check_repo` validates against it. |
| `bgai/experiment.py` | Runs an experiment → `experiment.json` + `stats.json` (+ `--verify`). |
| `bgai/models.py` | Publishes a model and measures its strength card. |
| `bgai/summary/` | Shared statistics (items, tags, archetypes, length, play style, samples); shapes for game sections in `SHAPES.md`. |
| `games/<slug>/` | One game: `__init__.py` (SPEC), engine, `rules.md`, `data/`, `manifest.json`, `i18n/`, `tests/`, `models/`, `experiments/`, `notes.json`, `RIGHTS.md`, `PLAN.md`, `STATUS.md`. |
| `games/_template/` | A tiny complete game: copy it to start (new-game skill). |
| `games/wingspan/` | The reference example of a full game done with these skills (rules from 2 sources, 3-source card check, audit). |
| `dashboard/` | Static pages; `tools/build_site.py` builds `site/` from all games. |
| `tools/` | `check_repo.py` (CI gate), `new_game.py` (scaffold), `review_pr.py` (review helper), `sync_skills.py`, `build_site.py`, `regenerate.py`, `import_records.py`. |
| `tests/` | Platform tests (kit golden tests, toy-game experiments, site build). |

## 3. How a game gets in (the pipeline) — one skill per step

```
new-game → ingest-rules → build-card-db → plan-engine → build-engine → verify-engine
        → design-rl → train-model → run-experiment → write-notes → publish-game
```
Each step leaves files a human can check and updates `games/<slug>/STATUS.md`. Do not skip ahead: training on an
unverified engine wastes many hours and produces false numbers.

Keeping the repository healthy: `reproduce-experiment`, `add-metric`, `upgrade-platform`, `extract-to-kit`,
`retire-model`, `review-game-pr`, `handle-takedown`.

## 4. Non-negotiable rules

1. **Never commit** rulebook PDFs, card art, copied card or rule text, raw game records (`raw/`, `*.jsonl`), training
   runs (`runs/`), or any file over 50 MB. Downloads go to `inbox/` (git-ignored).
2. **Two independent sources** for rules and for card data; write rules in your own words with IDs (`W4.2`); list
   every disagreement and its resolution in `rules.md` ("Decisions where sources differed").
3. **Every rule ID and every card has a test** (`@pytest.mark.rule("X4.2")`, `@pytest.mark.card("<item id>")`).
   `tools/check_repo.py` fails on an untested rule ID or catalog item.
4. **Engines are deterministic**: all randomness from the game's seeded `Rng`; the same seed and answers give the same
   game. Never use `random` module functions directly, time, dict ordering of sets, or hash order.
5. **The action numbering is frozen** once models exist (it is part of every model); change it = retrain.
6. **Scores are higher-is-better.** Winners, ranks and the training reward take the maximum; for a lowest-score-wins
   game return negated scores (and say so in rules.md and the intro). `bgai.checks` catches an inverted score.
7. **No statistic without its experiment**: dashboard numbers come only from `stats.json` built by `bgai.experiment`.
8. **Hidden information stays hidden** in the encoder (other players' hands, secret cards, secret choices).
9. **Platform code never names a game.** Game-specific needs go into the game folder or the manifest; shared needs
   into `bgai/` only when a second game needs them (see `bgai/kit/README.md`).
10. **Budget:** one desktop, ≤ 24 h of training per player count, GPU optional. Say so if a game cannot fit.
11. Ask a human before anything outward-facing (publisher notices, publishing the site, pushing to a remote).

## 4b. Platform notes that save time

- When a decision has exactly one legal answer the engine should apply it itself and report it through
  `drain_forced()` so it is still recorded (contract in `bgai/game.py`, example `games/wingspan/engine.py::_ask`) —
  otherwise per-card statistics miss forced plays.
- The meaning of every recorded field (`card`, `item`, `group`, `slot`, `host`, `points`, `tags`, `extra`) is in the
  `bgai/game.py` docstring; the manifest keys are explained in `bgai/manifest.schema.json`.
- Fixed game length (every game the same number of turns)? Set `rounds` in the SPEC to a constant: the length section
  is skipped automatically.
- `max_steps` in the SPEC caps decisions per game; a random game must end well below it.
- Old models keep working when a new observation version extends the old one as a prefix (`encoder_versions`).
- Experiments are fixed: never merge runs; more games = re-run with a larger `--games`.

## 5. Commands

Run every command from the repository root with the project's `.venv` (`bgai` is not installed as a package; on
Windows `.venv/Scripts/python`, elsewhere `.venv/bin/python`). Call that Python directly, one command at a time —
agent tools often refuse shell variables and `cd … &&` chains.
```bash
python tools/new_game.py --slug <slug> --name "<Name>"   # scaffold a game folder from the template
python -m pytest -q                                   # all tests (add -m slow for long checks)
python -m bgai.checks --game <slug> --games 10000     # 10,000 games per player count, writes checks/report.json
python -m bgai.show --game <slug> --seed 1            # one game as text
python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/open --timesteps 40000000 --hours 9
python -m bgai.rl.h2h --game <slug> --players 2 --a <ckpt> --b <ckpt|greedy> --seeds 750
python -m bgai.models publish --game <slug> --id <model id> --players 2 --checkpoint <ckpt> --logs <csv>...
python -m bgai.models accept --game <slug> --id <model id> --vs greedy <ckpt> --required ">=0.95" beats
python -m bgai.experiment --game <slug> --id p2-<model>-mirror --players 2 --seats <model id> --games 2000 --seed 1000
python -m bgai.experiment --game <slug> --id <experiment id> --verify 20
python tools/check_repo.py                            # the CI gate
python tools/review_pr.py --game <slug>               # the mechanical part of a review, with a suggested verdict
python tools/build_site.py && python -m http.server -d site 8000
python tools/sync_skills.py                           # after editing .agents/skills
```
Use the project's virtual environment (`.venv`); dependencies are pinned in `requirements.lock`.

## 6. Working efficiently (tokens and time)

- Read `bgai/game.py`, `bgai/kit/README.md`, the skill for your step and `games/_template/` — that is enough context
  to build a game. Read `games/wingspan/` files only as examples when a skill points you there.
- Prefer scripts over reading: parse sources with small Python scripts, compare data programmatically, let tests
  find problems. Never paste whole rulebooks or card lists into the conversation.
- Long jobs (training, 2,000-game experiments) run in the background; keep working on the next step meanwhile.
- Record progress and open questions in `games/<slug>/STATUS.md` so another agent or person can continue.
- When an independent review is required, give it to a separate agent/session with the files to read and the goal;
  do not review your own work in the same breath.

## 7. How work is judged (what reviewers and the CI check)

- `python tools/check_repo.py` and `python -m pytest -q` pass.
- `games/<slug>/checks/report.json` shows 0 problems over ≥ 10,000 random games for every supported player count,
  made on the current engine (check_repo fails when the engine changed after it).
- `rules.md` cites two sources per rule and lists decisions; `data/SOURCES.md` shows the field-by-field comparison.
- The model's strength card shows it is finished (train-model skill) — or the dashboard marks it as not finished,
  or the pull request is engine-only (no models or experiments yet; review-game-pr skill).
- Every experiment replays (`--verify 20`); notes follow the write-notes rules (no causal claims, numbers from stats).
