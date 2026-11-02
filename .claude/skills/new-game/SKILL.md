---
name: new-game
description: Start adding a board game to boardgames.ai and lead the whole pipeline (rules, cards, engine, checks, training, experiments, notes, publish). Use when someone asks to add, implement or analyse a new game by name.
---

# New game (lead skill)

## Goal
Turn a game's name into a published, trustworthy analysis on the dashboard: an engine that follows the official
rules exactly, a trained AI strong enough that its games mean something, standard experiments anyone can replay, and
plain-language notes for players. This skill sets up the folder and walks you through the other skills in order;
each step leaves checkable files and an entry in `STATUS.md`.

## Inputs
- The game's name and edition (base game? which expansions?). Default: the base game only.
- Optional: rulebook PDF or link, card list links, photos of cards from the requester.

## Steps
1. **Check fit (10 minutes, before any work).** The platform supports turn-based games for 2+ players with discrete
   choices, ending in finite time. Note in `STATUS.md`: player counts, rough number of distinct cards/pieces, hidden
   information, randomness, any real-time or dexterity element (not supported), any choice too large to number
   (e.g. free placement on a large grid — plan steps for it in plan-engine). If the game does not fit, stop and say why.
2. **Slug:** lowercase with underscores (`ark_nova`). Branch: `game/<slug>`.
3. **Scaffold:** `python tools/new_game.py --slug <slug> --name "<Name>"` copies `games/_template` and points every
   import and the manifest at the new slug (a plain copy would keep testing the template). It brings stubs for
   `STATUS.md`, `PLAN.md`, `RIGHTS.md` (fill in publisher and designer), `data/SOURCES.md`, `checks/review.md` and
   `i18n/en.json`; the manifest keys are explained in `bgai/manifest.schema.json`. Replace the toy rules, engine and
   tests step by step; keep the tests passing.
4. **Keep `games/<slug>/STATUS.md` current** (the stub has this checklist):
   ```
   - [ ] ingest-rules: rules.md with IDs, 2 sources, decisions listed
   - [ ] build-card-db: data/*.json, SOURCES.md, field-by-field check of 2 sources (+ 3rd for disputes)
   - [ ] plan-engine: PLAN.md (state, decisions, action numbering, effects, scoring)
   - [ ] build-engine: engine + tests (every rule ID, every card)
   - [ ] verify-engine: checks report 0 problems, independent review done, findings fixed
   - [ ] design-rl: encoder, greedy, smoke training learns
   - [ ] train-model: open run, anchored run, acceptance → finished model
   - [ ] run-experiment: mirror (+ versus) per player count, --verify passes
   - [ ] write-notes: notes.json (en + other languages)
   - [ ] publish-game: check_repo passes, publisher notice drafted, PR opened
   ```
5. Run the skills in that order. Never start training before verify-engine is done. Run every command from the
   repository root with the project's `.venv` (the `bgai` package is not installed; imports work from the root).

## Done when
All boxes are ticked, `python tools/check_repo.py` and `python -m pytest -q` pass, and the game shows on
`python tools/build_site.py` output with its findings.

## How big is the job? (measured on the games done so far)
| Game | Size | Agent work | Machine time |
|---|---|---|---|
| No Thanks! (dry run) | 33 number cards, 1 decision kind | under 1 hour, ~0.2M tokens, rules to site | checks 30 s; smoke training minutes |
| Wingspan | 180 birds, 30 power types, 31 decision kinds | about a day across several agents (2 rule researchers, card build + 3-source check, engine, audit) | checks ~15 min; training about a day per player count |
| Forest Shuffle (+2 expansions) | 92 species on 230 cards | several days in the original project (1,800-line plan first) | training 10.7 h for the 2-player model on a 22-core CPU + laptop GPU |

## Lessons from earlier games
- Forest Shuffle: the slow part was not code but understanding rules and cards precisely (an implementation plan of
  1,800 lines came first). Budget most of your effort for rules, cards and verification.
- Wingspan: two independent rule researchers agreed on every number but differed on 14 small points (rulings that
  changed over time, typos in card lists); resolving those explicitly is what makes the engine trustworthy.
- An AI trained only against itself can drift (it learns to beat its own habits). The train-model recipe exists
  because of this — follow it.
