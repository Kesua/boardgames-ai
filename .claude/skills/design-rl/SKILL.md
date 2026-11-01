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
Within 400k steps the model must beat random in > 90 % of games. If not: check the mask (illegal answers?), the
reward sign, whether the observation contains the decision context.

## Done when
Encoder and greedy committed with tests (encoder size and range), the smoke run learns, throughput recorded in
`STATUS.md` (steps per hour).
