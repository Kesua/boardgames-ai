---
name: add-metric
description: Add a new statistic to the shared summaries or a game's summary.py, bump the stats schema version, regenerate every affected experiment (proving the games did not change) and show it on the dashboard. Use when the dashboard should show something new.
---

# Add a metric

## Goal
New questions come up after experiments exist. Because raw records are not kept, a new metric means replaying the
experiments — cheap (minutes each, no training) and it doubles as a reproducibility check.

## Steps
1. Decide where it belongs: every game → `bgai/summary/` (generic, uses manifest terms only); one game →
   `games/<slug>/summary.py` as a standard shape (`bgai/summary/SHAPES.md`): table, bars (+ win-rate line, one axis),
   grid, facts.
2. Implement with a test on a small recorded fixture (`--keep-raw` keeps a raw file to develop against).
3. Bump `SCHEMA_VERSION` in `bgai/experiment.py` if the shared stats change shape.
4. Regenerate: `python tools/regenerate.py --game all` (or one game). It refuses to replace stats when the games differ.
5. Dashboard: shared metrics need a view in `dashboard/app.js`; game shapes render automatically. Add labels to
   `dashboard/i18n/*.json` or the game's `i18n/*.json` (`sections`).
6. `python tools/build_site.py`, look at it in light and dark mode and at phone width.

## Done when
Tests pass, every experiment regenerated with the same fingerprint, the new metric shows with labels in every language.
