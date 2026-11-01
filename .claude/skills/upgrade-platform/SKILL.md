---
name: upgrade-platform
description: Change shared platform or kit code (bgai/) safely — run every game's tests and checks and replay every experiment's fingerprint; regenerate or retrain where games changed. Use for any change under bgai/.
---

# Upgrade the platform

## Goal
Every game and every published number depends on `bgai/`. A platform change must not silently change any game's
results; where it intentionally does, every affected experiment is regenerated (and models retrained if they can no
longer play).

## Steps
1. Make the change with tests (`tests/`). Kit parts: golden tests in `tests/test_kit.py` must still pass — if a
   behaviour must change, add a new part (`Deck2`) instead (bgai/kit/README.md rule 4).
2. `python -m pytest -q` (all games) and `python -m bgai.checks --game <slug> --games 2000` for every game.
3. `python tools/regenerate.py --game all --check-only` — first 20 games of every experiment.
4. If fingerprints differ and the change was meant to change games: regenerate all experiments of the affected games
   (`python tools/regenerate.py` refuses; re-run them with `bgai.experiment` using each recipe), update notes if
   numbers moved, and say so in the PR.
5. If the observation or action numbering of a game changed: its models cannot play → retrain (train-model).

## Done when
All tests, checks and fingerprint replays pass, or the PR lists every regenerated experiment and retrained model.
