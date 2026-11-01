---
name: handle-takedown
description: Remove a game from the repository and the public site when its publisher or rights holder asks, within 7 days, and record it. Use when a removal request arrives.
---

# Handle a takedown request

## Goal
Respect rights holders promptly; the project's credibility depends on it.

## Steps
1. Record the request (who, when, what) in a private note for maintainers; reply to acknowledge within 2 days.
2. Branch `takedown/<slug>`: `git rm -r games/<slug>`; remove links to it from README and notes of other games.
3. `python tools/check_repo.py && python -m pytest -q && python tools/build_site.py`.
4. Merge; the site rebuilds without the game. Confirm to the requester with the date.
5. Note: git history keeps earlier files. If the request covers history, maintainers decide on a history rewrite
   (`git filter-repo`) — it breaks every clone, so it needs a human decision.
