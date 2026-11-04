---
name: train-model
description: Train a finished AI model for one player count with the standard recipe (open run until gains stop, anchored run against fixed opponents, paired acceptance games) and publish it with its strength card. Use after design-rl; budget ≤ 24 hours per player count.
---

# Train a model (the standard recipe)

**Which player counts:** 2 players first — it is the one most players ask about and the cheapest to train. Every
further player count is optional and gets its own model, experiments and featured entry; the dashboard shows only
player counts that have a featured experiment. A pull request may stop before training (an engine-only pull request,
review-game-pr skill).

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
**Plateau:** `win_vs_3m` within 2 standard errors of even play at two evaluations in a row. The model takes one seat
against players − 1 older copies, so even play is e = 1/players and the band is |x − e| ≤ 2·sqrt(e(1 − e)/n) with
n = deals × players games: 2p 0.5 ± 0.05 (200 deals), 3p 0.333 ± 0.054, 4p 0.25 ± 0.043 (100 deals). Comparing a 4p
run against 50 % never ends the run (Through the Ages 4p, 2026-11-03). The **open-run best** = the 3M-older checkpoint of the first of those two evaluations.

## 2. Anchored run (from the open-run best)
```bash
python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/anchored --start-from <open best ckpt> \
    --fixed <open best ckpt> greedy --keep-every 2000000 --lr 1e-4 --epochs 4 --reference <open best ckpt> \
    --timesteps 30000000 --chunk 500000 --envs 10 --eval-workers 3 --hours 12 \n    --patience 3 --min-gain 0.02 --min-steps 6000000 --rebase-at 0.8
```
Every 1M steps the log adds `win_vs_ref` (paired games against the reference on 750 deals); a checkpoint that
beats the best result so far is copied to `ppo_best.zip`. When the win rate against the reference reaches 0.8
(`--rebase-at 0.8`), the best checkpoint becomes the new, stronger reference and the learning rate halves — without
this, gains against a weak reference become too small to measure while the model still improves (Wingspan: stopped
at 8M steps although 8M still beat 5M 59 %). The trainer stops by itself after three evaluations in a row without a
gain of 0.02 against the current reference (`--patience 3 --min-gain 0.02`, not before `--min-steps`), or when the
budget ends. Check `win_vs_3m` at the stop: clearly above even play (the plateau band) means the model was still improving — resume with a
larger budget. The model to publish is `ppo_best.zip`.

**Interrupted?** Run the same command again with `--resume`: it continues from the latest checkpoint in `--out` and
replays the reference, best result and learning rate from the log. Use it also to extend a run that hit `--hours`.

## 3. Publish and accept
```bash
python -m bgai.models publish --game <slug> --id p2-<name> --players 2 --checkpoint runs/<slug>/anchored/p2/ppo_best.zip \
    --logs runs/<slug>/open/p2/train_log.csv runs/<slug>/anchored/p2/train_log.csv --recipe "<open cmd>" "<anchored cmd>" \
    --steps <steps> --games <games> --hours <h> --hardware "<cpu/gpu>"   # steps/games: all runs together, up to the checkpoint
python -m bgai.models accept --game <slug> --id p2-<name> \
    --vs greedy <open-run last ckpt> <open-run best ckpt> [<previous finished model id>] \
    --labels "greedy baseline" "open-run checkpoint it never trained against" "open-run best (trained against)" ... \
    --required ">=0.95" beats - beats --deals 750
```
Paired games: each model plays every seat of each deal once. Finished = every `required` row passes
(beats = more than 50 % + 2 standard errors, for every player count: with 3+ players this is stricter than even
play, by choice; Forest Shuffle and Through the Ages 4p keep it, as they keep `--rebase-at 0.8` and `>=0.95`). Keep the label wording: the dashboard reads "never trained against" or
"trained against" from it to describe the opponent correctly.

**Failed the greedy bar?** Look at `win_vs_3m` at the stop. Above the plateau band means the model still improves: start another
anchored stage from the run's last checkpoint (`--start-from` and `--reference` = that checkpoint, `--lr 2.5e-5`,
`--fixed` = open-run best, the previous reference and greedy, `--min-steps 4000000`, `--rebase-at 0.56`), publish
that stage's `ppo_best.zip` and accept again. Pick the model by the run's own rule, never by its score against greedy
on the acceptance deals (that would tune the model to the test). Wingspan: 91.9 % against greedy after 16M steps,
two more stages (about an hour each) gave 95.1 % at 28M steps, where `win_vs_3m` reached 0.5. Stop when `win_vs_3m`
stays at even play: the recipe is exhausted; publish as not finished and report it, or change the design (design-rl).
With 3+ players the acceptance test seats greedy at every other seat, while training puts a frozen opponent at one
seat only; `--frozen-seats <players − 1>` lets it take every other seat at frozen tables. Through the Ages 4p
(2026-11-04): two stages with `--frozen-seats 3` stayed at even play against their start (64.4 % against greedy
before), so it is no cure for a recipe that is exhausted.
Not finished within budget → do not call experiments "finished"; the lab tab shows the failed strength card (the rest of the page does not flag unfinished models).

## Pitfalls
- Watch `clipped` in the training printout: above ~0.3 for long means updates are too large (lower lr / epochs).
- Evaluation workers each load torch (~1.7 GB); keep `--eval-workers` small on machines with little memory.
- Training checkpoints go to `runs/` (git-ignored); only the published `model.zip` (~10–30 MB) is committed.
