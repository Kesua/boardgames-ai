---
name: reproduce-experiment
description: Replay a stored experiment from its recipe to prove its statistics — quick (first 20 games against the fingerprint) or complete (all games, compare the whole fingerprint). Use when checking someone's results, after an environment change, or when CI's fingerprint replay fails.
---

# Reproduce an experiment

## Goal
Trust comes from anyone being able to get exactly the same games. This skill proves (or disproves) that the code and
model in the repository produce the stored numbers.

## Quick
```bash
python -m bgai.experiment --game <slug> --id <experiment id> --verify 20
```
Checks the model files' sha256 against the recipe, replays the first 20 games, compares final scores.

## Complete
```bash
python tools/regenerate.py --game <slug> --id <experiment id> --workers 6
```
Replays all games; replaces stats.json only if the whole fingerprint matches.

## When it does not match
1. `MODEL CHANGED`: the model file differs from the recipe — restore it from git history.
2. First differing game is printed. Check what changed since `experiment.json`'s `code_commit`
   (`git log <commit>..HEAD -- games/<slug> bgai`). An engine or kit change that alters games requires regenerating
   all experiments of that game (upgrade-platform skill) — and, if the action numbering or observation changed,
   retraining.
3. Same code, different machine: compare `environment` (OS, Python, numpy, torch). Rare floating-point differences
   between platforms can flip a near-tie decision. Report it with both environments; do not loosen the check.
