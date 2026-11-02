---
name: design-rl
description: Design what a game's AI agent observes (encoder), its greedy baseline and reward, and run a short smoke training to prove learning works before a full training run. Use after verify-engine.
---

# Design the learning setup

## Goal
The agent can only learn what it can see, and training time is the scarcest resource. A compact, informative
observation and a sane greedy baseline make the difference between a strong AI in hours and a weak one in days.

## The encoder (`games/<slug>/encoder.py`, class with `size`, `version`, `encode(game, seat)`)
- A float32 vector in [0, 1] from the deciding player's view. Typical blocks: global state (round, supply, market as
  counts per card id), the **decision context** (decision kind one-hot, the card or piece the decision is about,
  amounts left), own private state (hand as counts per card id, resources, own board as per-slot features), each
  other player's **public** state (clockwise from self), score breakdown and lead.
- **Hide what is hidden:** other hands, secret cards, choices made in secret; scores that include secret points.
  Information a player with perfect memory could rebuild from public events (chips taken in front of everyone, cards
  revealed earlier) counts as public, even when table custom keeps it face down.
- Static card features (cost, points, icons, effect type one-hot) precomputed once per card id.
- Use `bgai.kit.add_counts` / `one_hot`. Typical sizes: 1,500–4,500 floats.
- If you later extend the observation, append to the end and register older versions in `SPEC.encoder_versions` so
  old models still play.

## The greedy baseline (`agents.py`)
Not a strong player — a sanity check and an early training opponent. Judge big choices by playing out the current
turn in a `clone()` with simple rules and comparing (own score − best other score + small resource values).

## Reward
The default (win ±1, ties count as wins, + margin/100) works; change it only with evidence.

## Smoke training
```bash
python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/smoke --timesteps 1000000 --chunk 200000 \
    --envs 8 --eval-workers 3
```
Use 2 players for the smoke run when the game allows it; otherwise its smallest player count. Pass rule:
`win_vs_random` above 0.9 for 2 players (for n players: clearly above 1/n, e.g. ≥ 0.8) within 400k steps, AND a paired
check against greedy shows learning:
```bash
python -m bgai.rl.h2h --game <slug> --players 2 --a runs/<slug>/smoke/p2/ppo_<last>.zip --b greedy --seeds 150
```
(the training log's greedy column uses only `--greedy-games` games and moves in coarse steps). If it does not learn:
check the mask (illegal answers?), the reward sign (`scores()` higher-is-better?), whether the observation contains
the decision context.

## Done when
Encoder and greedy committed with tests (encoder size; the [0, 1] range is also checked by `bgai.checks`), the
smoke run learns, throughput recorded in `STATUS.md` (steps per hour).
