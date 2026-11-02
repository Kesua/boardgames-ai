---
name: verify-engine
description: Prove a game engine is correct before training — automated checks over 10,000+ random games, rule and card test coverage, rulebook examples as tests, and an independent review of the code and of game logs against rules.md. Use after build-engine; training may not start until this passes.
---

# Verify the engine

## Goal
Trained agents find and exploit every rule bug, and the dashboard would then present the bug as a "strong card".
This step is the last chance to catch errors cheaply. It has two halves: machines (checks, coverage) and an
independent reviewer who did not write the code.

## Steps
1. **Automated checks:** `python -m bgai.checks --game <slug> --games 10000` — 10,000 random games for EVERY
   supported player count (minutes to an hour). It checks that games end, legal answers are valid, the same seed
   replays the same game, clones are independent, scores equal the breakdown sums, record fields exist, observations
   lie in [0, 1], the greedy agent clearly beats random players (catches inverted scores: `scores()` must be
   higher-is-better) and the game's `invariants` hold (write some: card conservation, limits). Writes
   `games/<slug>/checks/report.json` with the code commit; commit it. Must report 0 problems. Any later engine change
   makes the report stale (`tools/check_repo.py` says so): run it again.
2. **Coverage:** `python tools/check_repo.py` — every rule ID has a test marked `rule("<ID>")`, every catalog item a
   test marked `card("<ID>")` (or one test parametrized over the whole catalog marked `card("*")`), and the
   pipeline files exist.
3. **Rulebook examples:** turn every worked example in the rulebook (setup examples, scoring examples) into a test.
4. **Independent review** — you start it yourself when your tool can (a subagent or a new session); otherwise ask
   the human to start one and hand them the brief. Give the separate agent/session this brief: the goal (a rule bug publishes false insights),
   `rules.md`, the engine files, the two researchers' notes; ask it to check every rule ID against the code, look for
   wrong numbers/timing/optionality/illegal or missing options/effects on the wrong target/stuck states, to reproduce
   suspicions with scripts, to read 3 full game logs (`g.text_state()` + the log) against the rules, and to report
   findings with severity, rule ID, file:line, reproduction and fix. It must not edit files.
5. Fix every bug and every "doubtful" item you agree with; add a test per fix; record items you decide not to change
   in `rules.md` decisions. Re-run step 1.
6. Save the review summary to `games/<slug>/checks/review.md` (findings and how each was resolved).

## Done when
`checks/report.json` shows 0 problems, `checks/review.md` lists all findings resolved, tests and check_repo pass.

## What reviews found on Wingspan (typical classes)
Forced moves not recorded (statistics bias), a power whose owner must choose the starting player, setup choices
visible to later players in the agent's observation, and an opponent's secret bonus-card points leaking into the
observation. None changed game results, all mattered for the published numbers or for fair learning.

## What the card check found on Forest Shuffle (after the engine had passed every check)
One card scored by the wrong type (European Wildcat: per Bird instead of per Woodland Edge card), a setup number wrong
for one option, one timing word ("from now on" vs "from your next turn"). Automated checks cannot see such errors —
only a comparison with independent sources can. Do not skip the two-source card check.
