---
name: review-game-pr
description: Review a pull request that adds or changes a game — decide whether its rules, cards, engine verification, model strength, experiments and notes are trustworthy enough to publish. Use as a maintainer or as an independent reviewer of another person's or agent's work.
---

# Review a game pull request

## Goal
Decide quickly and fairly whether the work is relevant and worthy: is the engine right, is the AI strong enough for
its numbers to mean something, are the numbers reproducible, and are the notes honest. Every item below points to a
file; a missing file is a "changes requested".

## Start here (5–10 minutes of machine time)
```bash
python tools/review_pr.py --game <slug> --base main
```
It runs the game's tests, the repository rules, shows the check report, replays the first 20 games of every
experiment, prints each strength card, lists files changed outside the game folder, picks 5 rules and 5 cards for
you to compare with the official rulebook and cards, prints one game as text, and suggests a verdict. Then work
through the CHECK lines below (about 30–60 minutes of your time for a large game).

## Checklist (with what "good" looks like)
1. **CI green**: tests, `tools/check_repo.py`, skills in sync.
2. **Rules** (`rules.md`): two independent sources named; every rule has an ID and sources; a decisions table that
   lists real disagreements (a table with none is suspicious for any non-trivial game). Spot-check 5 rules against the
   official rulebook yourself. Fail: any of the 5 is wrong in a way that changes play or scoring.
3. **Cards** (`data/SOURCES.md`): how two sources were compared field by field; how many differences; a third source
   for disputes. Spot-check 5 cards. Fail: any number, cost, icon or effect differs from the printed card.
4. **Engine verification**: `checks/report.json` 0 problems over ≥ 10,000 games for every player count;
   `checks/review.md` by an independent reviewer with findings resolved. Read the printed game for 2 minutes. Fail:
   a move that the rules do not allow, a player who never does something the game requires, scores that cannot be.
5. **Model** (`models/<id>/model.json`): strength card finished — beats an opponent it never trained against by more
   than 2 standard errors and greedy ≥ 95 % over at least 300 games. Training curve sensible: `win_vs_greedy`
   rises and then stays high; a fall by more than 10 points that does not recover is a collapse (ask why).
6. **Experiments**: run `python -m bgai.experiment --game <slug> --id <id> --verify 20` for one experiment yourself.
7. **Notes**: pick 3 numbers in notes.json and find them in the dashboard; no causal claims; caveats present.
   Fail: a number that is not in stats.json, or "X makes you win".
8. **Rights**: RIGHTS.md present; no PDFs, art or copied text (search for long quoted card texts).
9. **Dashboard**: every tab of the game renders in light/dark mode and on a phone width.

## Verdicts
- **Approve:** all items pass.
- **Approve as engine only:** items 1–4 and 8 pass and the pull request has no models or experiments yet. The game
  is listed as "engine ready, AI not trained yet"; training (which needs a strong machine for about a day per player
  count) can come in a later pull request from anyone.
- **Approve as "not finished":** items 1–4, 6, 8 pass, the model is not finished — the dashboard marks it; ask for a
  follow-up training run.
- **Changes requested:** anything in 1–4, 6 or 8 fails.
