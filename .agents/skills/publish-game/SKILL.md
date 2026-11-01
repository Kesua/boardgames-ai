---
name: publish-game
description: Prepare a finished game for merge — repository checks, rights file and publisher notice draft, dashboard check, and a pull request with the review checklist. Use as the last step of adding a game.
---

# Publish a game

## Goal
Make the game's results public responsibly: everything reproducible, nothing that infringes the publisher's rights,
and a pull request a maintainer can review in minutes because every claim points to evidence.

## Steps
1. `python -m pytest -q`, `python tools/check_repo.py`, `python tools/sync_skills.py --check` all pass.
2. `python tools/build_site.py`; open every tab of the game in a browser (light and dark, phone width). Fix anything
   broken or unclear.
3. `games/<slug>/RIGHTS.md`: publisher, designer, what is and is not in the repository, removal process.
4. Draft the publisher notice (do **not** send it yourself — a human sends it and records date and reply in
   RIGHTS.md):
   > Subject: Fan research project about <Game>
   > Hello, we run boardgames.ai, an open-source, non-commercial research project in which AI agents learn board
   > games and publish which cards and strategies win (https://…). We added <Game>: the repository contains the rules
   > in our own words, card data as numbers (no card text or art) and statistics. It does not let anyone play the
   > game. If you would prefer we remove it or change anything, reply and we will do so within 7 days.
5. Open the PR with this body:
   ```
   ## <Game>
   - Rules: games/<slug>/rules.md (sources A/B, N decisions)
   - Cards: data/SOURCES.md (field-by-field check, third source: …)
   - Engine checks: checks/report.json (N games, 0 problems); review: checks/review.md
   - Model: models/<id>/model.json (strength card: finished yes/no)
   - Experiments: experiments/<ids> (--verify 20 matches)
   - Notes: notes.json (languages)
   - Rights: RIGHTS.md (notice drafted / sent on …)
   ```

## Done when
The PR is open with all checks green, and the maintainer review (review-game-pr skill) has what it needs.
