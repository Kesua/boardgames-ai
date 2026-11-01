---
name: extract-to-kit
description: Move a mechanic that a second game needs (same behaviour) from a game into the shared kit bgai/kit/, with golden tests, switching both games over without changing a single game. Use when two games implement the same mechanic.
---

# Extract a part to the kit

## Goal
Shared parts make new engines faster and less buggy — but only parts that mean exactly the same thing in every game.
A wrong abstraction (a part with options for each game) is worse than duplication. This skill moves a proven part,
never designs one up front.

## When it qualifies
A second game needs **the same behaviour**, not something similar. Markets that refill at different times, dice with
different faces, effects with game-specific meaning: keep them in the games.

## Steps
1. Copy the working code from the first game into `bgai/kit/<part>.py`; no options for game-specific behaviour.
2. Golden tests in `tests/test_kit.py`: fixed seeds/inputs → exact outputs.
3. Switch both games to the kit part.
4. Prove nothing changed: all game tests pass and every experiment's fingerprint replays
   (`python tools/regenerate.py --game all --check-only`).
5. Add the part to the table in `bgai/kit/README.md` (behaviour, users).

## Done when
Both games use the part, golden tests pass, every fingerprint replays, README updated.
