---
name: review-game-pr
description: Review a pull request that adds or changes a game — decide whether its rules, cards, engine verification, model strength, experiments and notes are trustworthy enough to publish. Use as a maintainer or as an independent reviewer of another person's or agent's work.
---

# Review a game pull request

## Goal
Decide quickly and fairly whether the work is relevant and worthy: is the engine right, is the AI strong enough for
its numbers to mean something, are the numbers reproducible, and are the notes honest. Every item below points to a
file; a missing file is a "changes requested".

## Checklist (with what "good" looks like)
1. **CI green**: tests, `tools/check_repo.py`, skills in sync.
2. **Rules** (`rules.md`): two independent sources named; every rule has an ID and sources; a decisions table that
   lists real disagreements (a table with none is suspicious for any non-trivial game). Spot-check 5 rules against the
   official rulebook yourself.
3. **Cards** (`data/SOURCES.md`): how two sources were compared field by field; how many differences; a third source
   for disputes. Spot-check 5 cards.
4. **Engine verification**: `checks/report.json` 0 problems over ≥ 10,000 games for every player count;
   `checks/review.md` by an independent reviewer with findings resolved. Read one random game log
   (`text_state()` of a random game) yourself for 2 minutes.
5. **Model** (`models/<id>/model.json`): strength card finished — beats an opponent it never trained against by more
   than 2 standard errors and greedy ≥ 95 %. Training curve sensible (no collapse).
6. **Experiments**: run `python -m bgai.experiment --game <slug> --id <id> --verify 20` for one experiment yourself.
7. **Notes**: pick 3 numbers in notes.json and find them in the dashboard; no causal claims; caveats present.
8. **Rights**: RIGHTS.md present; no PDFs, art or copied text (search for long quoted card texts).
9. **Dashboard**: every tab of the game renders in light/dark mode and on a phone width.

## Verdicts
- Approve: all items pass.
- Approve as "not finished": items 1–4, 6, 8 pass, the model is not finished — the dashboard marks it; ask for a
  follow-up training run.
- Changes requested: anything in 1–4, 6 or 8 fails.
