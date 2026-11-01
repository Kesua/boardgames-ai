---
name: train-model
description: Train a finished AI model for one player count with the standard recipe (open run until gains stop, anchored run against fixed opponents, paired acceptance games) and publish it with its strength card. Use after design-rl; budget ≤ 24 hours per player count.
---

# Train a model (the standard recipe)

## Goal
The published statistics are only as meaningful as the AI that produced them. A model counts as **finished** when it
clearly beats opponents it never trained against and the greedy baseline. The recipe comes from the Forest Shuffle
runs: pure self-play improves fast, then drifts (it learns to beat its own habits and gets weaker against outsiders);
anchoring it to fixed opponents and lowering the learning rate fixes that.

## 1. Open run
```bash
python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/open --timesteps 40000000 --chunk 500000 \
    --envs 10 --eval-workers 3 --hours 9
```
All seats learn; 20 % of games include a frozen older snapshot; random leaves the pool once beaten 95 %. Every 1M
steps the log (`runs/<slug>/open/p2/train_log.csv`) has paired results against the checkpoints 1M and 3M older.
**Plateau:** `win_vs_3m` within 2 standard errors of 50 % (|x − 0.5| ≤ 2·sqrt(0.25/400) ≈ 0.05 for 2p) at two
evaluations in a row. The **open-run best** = the 3M-older checkpoint of the first of those two evaluations.

## 2. Anchored run (from the open-run best)
```bash
python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/anchored --start-from <open best ckpt> \
    --fixed <open best ckpt> greedy --keep-every 2000000 --lr 1e-4 --epochs 4 --reference <open best ckpt> \
    --timesteps 30000000 --chunk 500000 --envs 10 --eval-workers 3 --hours 12
```
Stop when the latest checkpoint wins ≤ 55 % in paired games against the one 2M steps older, twice in a row, or the
budget ends. `ppo_best.zip` = best against the reference.

## 3. Publish and accept
```bash
python -m bgai.models publish --game <slug> --id p2-<name> --players 2 --checkpoint runs/<slug>/anchored/p2/ppo_best.zip \
    --logs runs/<slug>/open/p2/train_log.csv runs/<slug>/anchored/p2/train_log.csv --recipe "<open cmd>" "<anchored cmd>" \
    --hours <h> --hardware "<cpu/gpu>"
python -m bgai.models accept --game <slug> --id p2-<name> \
    --vs greedy <open-run last ckpt> <open-run best ckpt> [<previous finished model id>] \
    --labels "greedy baseline" "open-run checkpoint it never trained against" "open-run best (trained against)" ... \
    --required ">=0.95" beats - beats --deals 750
```
Paired games: each model plays every seat of each deal once. Finished = every `required` row passes
(beats = more than 50 % + 2 standard errors). Not finished within budget → do not publish experiments as "finished";
the dashboard marks unfinished models.

## Pitfalls
- Watch `clipped` in the training printout: above ~0.3 for long means updates are too large (lower lr / epochs).
- Evaluation workers each load torch (~1.7 GB); keep `--eval-workers` small on machines with little memory.
- Training checkpoints go to `runs/` (git-ignored); only the published `model.zip` (~10–30 MB) is committed.
