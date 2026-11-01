# Independent reviews of the Wingspan engine and data

Two reviews by agents that did not write the code, plus the automated checks.

## 1. Card data against a third source (fan wiki, one page per bird)
180 birds checked: 177 agree on every field and the meaning of the power; 3 differences resolved in
`data/SOURCES.md` (2 incomplete wiki pages, 1 open food-cost question kept with the two card lists).

## 2. Engine audit against rules.md
Method: every rule ID W1–W14 and every decision D1–D14 compared with the code; 1,000 random games (2–5 players) with
invariants after every step; a brute-force comparison of every reachable food payment (236 cases, exact match);
scripted scenarios for the trickiest timings; three full game logs read against the rules.

Verdict: no rule bug that changes game results. Findings and resolution:

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | bug (statistics) | Decisions with one legal answer were applied without being recorded (≈ 60 % of bird plays missing from per-card counts) | Forced moves are logged and recorded (`drain_forced`); test `test_forced_moves_are_recorded` |
| 2 | doubtful (W10.10) | Hermit Thrush: the owner must choose which tied player takes a die first | Owner chooses (START_PLAYER among tied players); rules.md updated; test `test_hermit_thrush_owner_chooses_first` |
| 3 | doubtful (W2.4) | Setup choices of earlier seats were visible in later seats' observations | Observation hides others' hand size, food and the discard pile until setup ends; test `test_setup_choices_are_secret_in_observations` |
| 4 | doubtful (encoder) | Opponents' scores in the observation included their secret bonus-card points | Others' bonus points are hidden; test `test_opponent_bonus_points_hidden` |
| 5 | minor | "All players draw from the deck" offered when only tray cards remain | Offered only with deck or discard cards |
| — | notes | "All players gain food" shares are given automatically (never worse to accept); one player's own pink birds resolve in mat order | Kept; documented here |

## 3. Automated checks
See `report.json` (`python -m bgai.checks --game wingspan --games 10000`).
