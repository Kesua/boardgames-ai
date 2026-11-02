"""All-seat self-play PPO training of any game, one model per player count.

python -m bgai.rl.train --game <slug> --players 2 --out runs/<slug>/open --timesteps 20000000 [--resume]

The standard recipe (open run, then anchored run, then acceptance) is in .agents/skills/train-model/SKILL.md.

Every seat at the table plays the current policy and learns (bgai/rl/selfplay.py); in `--frozen-share`
of the games one seat is a frozen opponent from the pool: `--fixed` opponents ("greedy" or any checkpoint, also of
observation version 1), the anchor, every checkpoint at a multiple of `--keep-every` steps, the last `--pool-size`
checkpoints, and a random agent until the model beats it in 95 % of evaluation games. "steps" counts learned decisions of all seats; the log
also counts games. The PPO update runs on the GPU when torch sees one.

Checkpoints go to <out>/p<players>/ppo_<steps>.zip and ppo_latest.zip (runs/ is git-ignored; a finished model is
published into games/<slug>/models/ with python -m bgai.models). After each chunk a row is appended to
<out>/p<players>/train_log.csv:

  games            games finished so far
  win_vs_random    win rate against RandomAgent (only while it is in the pool)
  win_vs_greedy    win rate against GreedyAgent
  win_vs_anchor    win rate against a fixed older snapshot (checkpoint nearest `--anchor-steps`)
  margin_vs_anchor mean (own score - best other score) in those games
  mean_score       mean own score in the anchor games (or the random games before an anchor exists)
  win_vs_1m, margin_vs_1m, win_vs_3m, margin_vs_3m
                   every 1M steps: paired games (same deals, every seat once) against the checkpoints 1M and 3M
                   steps older; 2p 200 deals, 4p 100 deals
  win_vs_ref, margin_vs_ref
                   every 1M steps with `--reference`: paired games against that fixed model on `--reference-deals`
                   deals (seeds 20000.., as bgai.rl.h2h); a checkpoint that beats the best so far against the same
                   reference (column `reference`) by at least `--min-gain` is copied to ppo_best.zip

Progress rules (lessons of the Forest Shuffle 2p runs: pure self-play drifts, only an outside reference shows it):
  --patience N     stop once N paired evaluations in a row brought no gain of `--min-gain` (not before `--min-steps`)
  --rebase-at W    when the win rate against the reference reaches W, the best checkpoint becomes the new reference
                   (the yardstick gets stronger) and the learning rate is multiplied by `--lr-decay`
On --resume the reference, best result, evaluations without gain and learning rate are replayed from the log.
  random_in_pool   1 while the random agent is still a frozen opponent

Evaluation games run on `--envs` worker processes; models play deterministically, ties count as wins.
"""
from __future__ import annotations

import argparse
import csv
import glob
import multiprocessing as mp
import os
import re
import shutil
import time

from .h2h import match, summary

LOG_COLUMNS = ["time", "steps", "games", "win_vs_random", "win_vs_greedy", "win_vs_anchor", "margin_vs_anchor",
               "mean_score", "win_vs_1m", "margin_vs_1m", "win_vs_3m", "margin_vs_3m", "win_vs_ref", "margin_vs_ref",
               "reference", "anchor", "pool_size", "random_in_pool", "learn_minutes", "eval_minutes"]
PAIRED_EVERY = 1_000_000
RETIRE_RANDOM = 0.95


def checkpoints(out_dir: str) -> list:
    """Sorted (steps, path) for all numbered checkpoints."""
    out = []
    for c in glob.glob(os.path.join(out_dir, "ppo_*.zip")):
        m = re.search(r"ppo_(\d+)\.zip$", c)
        if m:
            out.append((int(m.group(1)), c))
    return sorted(out)


def pick_anchor(out_dir: str, anchor_steps: int):
    cands = [(abs(s - anchor_steps), p) for s, p in checkpoints(out_dir) if s >= anchor_steps * 0.8]
    return min(cands)[1] if cands else None


def log_rows(log_path: str) -> list:
    """Rows of the training log; a log with older columns is rewritten with LOG_COLUMNS (new cells empty)."""
    if not os.path.exists(log_path):
        return []
    with open(log_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if reader.fieldnames != LOG_COLUMNS:
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, LOG_COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    return rows


def fmt(x, digits=3) -> str:
    return "" if x is None else f"{x:.{digits}f}"


def ref_step(st: dict, steps: int, win: float, out_dir: str, min_gain: float, rebase_at: float, lr_decay: float) -> dict:
    """One paired evaluation against the reference. st: reference, best (win rate), best_steps, stale (evaluations
    without a gain of min_gain), lr. Returns the new state plus `gain` and `rebased` flags for this evaluation."""
    st = dict(st, gain=False, rebased=False)
    if win - st["best"] >= min_gain:
        st.update(best=win, best_steps=steps, stale=0, gain=True)
    else:
        st["stale"] += 1
    if rebase_at is not None and win >= rebase_at and st["best_steps"] is not None:
        st.update(reference=os.path.join(out_dir, f"ppo_{st['best_steps']}.zip"), best=-1.0, best_steps=None, stale=0,
                  lr=st["lr"] * lr_decay, rebased=True)
    return st


def replay_ref(rows: list, st: dict, **rules) -> dict:
    """The reference state after the logged evaluations (rows measured against another reference are skipped)."""
    for r in rows:
        if r.get("win_vs_ref") and os.path.normpath(r.get("reference") or "") == os.path.normpath(st["reference"] or ""):
            st = ref_step(st, int(r["steps"]), float(r["win_vs_ref"]), **rules)
    return st


def make_model(spec, players: int, seed: int, net):
    """A fresh MaskablePPO model with the game's observation size and action count."""
    import gymnasium as gym
    import numpy as np
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    size, n = spec.encoder(players).size, spec.action_count(players)

    class _Spaces(gym.Env):
        observation_space = gym.spaces.Box(0.0, 1.0, (size,), dtype=np.float32)
        action_space = gym.spaces.Discrete(n)

        def reset(self, *, seed=None, options=None):
            return np.zeros(size, dtype=np.float32), {}

        def step(self, action):
            return np.zeros(size, dtype=np.float32), 0.0, True, False, {}

        def action_masks(self):
            return np.ones(n, dtype=bool)

    return MaskablePPO("MlpPolicy", DummyVecEnv([_Spaces]), policy_kwargs=dict(net_arch=list(net)), learning_rate=2.5e-4,
                       ent_coef=0.01, gamma=0.995, verbose=0, seed=seed, device="cpu")


def train(slug: str, players: int, total_timesteps: int, out_dir: str, workers: int = 16, tables: int = 4, chunk: int = 200_000,
          snapshot_every: int = 2, pool_size: int = 4, reward: str = "mixed", seed: int = 0,
          frozen_share: float = 0.2, rollout: int = 16384, eval_games: int = 40, greedy_games: int = 8,
          anchor: str = None, anchor_steps: int = 1_000_000, resume: bool = False, hours: float = None,
          lr: float = 2.5e-4, epochs: int = 10, fixed: tuple = (), keep_every: int = 2_000_000, reference: str = None,
          reference_deals: int = 750, min_gain: float = 0.0, patience: int = None, min_steps: int = 0,
          rebase_at: float = None, lr_decay: float = 0.5, start_from: str = None, net: tuple = (512, 512, 256),
          options: dict = None, eval_workers: int = 4):
    import torch
    from sb3_contrib import MaskablePPO

    from ..game import load_spec
    from .selfplay import AllSeatTrainer

    spec = load_spec(slug)
    options = options if options is not None else dict(spec.default_options)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - workers))
    out_dir = os.path.join(out_dir, f"p{players}")
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, "train_log.csv")

    done, ckpt = 0, None
    if resume and checkpoints(out_dir):
        done, ckpt = checkpoints(out_dir)[-1]
    if ckpt:
        model = MaskablePPO.load(ckpt, device="cpu")
        print(f"resumed from {ckpt} at {done} steps", flush=True)
    elif checkpoints(out_dir):
        raise SystemExit(f"{out_dir} already has checkpoints; pass --resume or choose another --out")
    elif start_from:
        model = MaskablePPO.load(start_from, device="cpu")      # anchored run: continue the open run's best weights
        print(f"starting from the weights of {start_from}", flush=True)
    else:
        model = make_model(spec, players, seed, net)
    if model.observation_space.shape[0] != spec.encoder(players).size:
        raise SystemExit(f"{ckpt} uses another observation version; train into a new --out directory")

    rows = log_rows(log_path) if done else []
    last = rows[-1] if rows else {}
    rules = dict(out_dir=out_dir, min_gain=min_gain, rebase_at=rebase_at, lr_decay=lr_decay)
    ref = replay_ref(rows, {"reference": reference, "best": -1.0, "best_steps": None, "stale": 0, "lr": lr}, **rules)
    lr = ref["lr"]
    games0 = int(float(last.get("games") or 0)) if done else 0
    random_in_pool = last.get("random_in_pool", "1") != "0" if done else True
    anchor_path = anchor or pick_anchor(out_dir, anchor_steps)

    def pool_paths():
        ckpts = checkpoints(out_dir)
        kept = [p for s, p in ckpts if keep_every and s % keep_every == 0]
        recent = [p for _, p in ckpts][-pool_size:]
        return list(dict.fromkeys(list(fixed) + ([anchor_path] if anchor_path else []) + kept + recent))

    trainer = AllSeatTrainer(model, slug, players, workers=workers, tables=tables, reward=reward, seed=seed + done,
                             frozen_share=frozen_share, rollout=rollout, device=device, lr=lr, epochs=epochs,
                             options=options, max_steps=spec.max_steps)
    pool = pool_paths() if done else list(fixed)
    trainer.set_pool(pool, random_in_pool)
    print(f"p{players}: update on {device}, {workers} workers x {tables} tables, frozen share {frozen_share}, "
          f"lr {lr}, epochs {epochs}, pool {[os.path.basename(p) for p in pool]}, reference {ref['reference']} "
          f"(best {ref['best']:.3f}, {ref['stale']} without gain)", flush=True)

    eval_pool = mp.get_context("spawn").Pool(eval_workers)     # each evaluation worker loads torch: keep it small
    new_log = not os.path.exists(log_path)
    k, base, carry, start = 0, 30000, 0, time.time()
    try:
        with open(log_path, "a", newline="") as f:
            log = csv.writer(f)
            if new_log:
                log.writerow(LOG_COLUMNS)
            while done < total_timesteps and (hours is None or time.time() - start < hours * 3600):
                t0 = time.time()
                target, learned = min(chunk, total_timesteps - done) - carry, 0
                while learned < target:
                    s = trainer.update(trainer.collect())
                    learned += s["samples"]
                carry = learned - target                     # updates overshoot the chunk; count it in the next one
                done += chunk
                k += 1
                latest = os.path.join(out_dir, f"ppo_{done}.zip")
                model.save(latest)
                model.save(os.path.join(out_dir, "ppo_latest.zip"))
                t1 = time.time()

                per = lambda games: max(1, games // players)
                ev = lambda b, n, s0: summary(match(slug, latest, b, players, range(s0, s0 + per(n)), eval_workers, options,
                                                   pool=eval_pool))
                r_rand = ev("random", eval_games, base) if random_in_pool else None
                r_greedy = ev("greedy", greedy_games, base + 1000) if greedy_games else None
                if anchor_path is None:
                    anchor_path = pick_anchor(out_dir, anchor_steps)
                r_anchor = ev(anchor_path, eval_games, base + 2000) if anchor_path else None
                paired = {}
                if done % PAIRED_EVERY == 0:
                    deals = 200 if players == 2 else 100
                    for key, back in (("1m", PAIRED_EVERY), ("3m", 3 * PAIRED_EVERY)):
                        old = os.path.join(out_dir, f"ppo_{done - back}.zip")
                        if os.path.exists(old):
                            paired[key] = summary(match(slug, latest, old, players,
                                                        range(base + 5000, base + 5000 + deals), eval_workers, options,
                                                        pool=eval_pool))
                    if ref["reference"]:
                        measured = ref["reference"]
                        paired["ref"] = summary(match(slug, latest, measured, players,
                                                      range(20000, 20000 + reference_deals), eval_workers, options,
                                                      pool=eval_pool))
                        ref = ref_step(ref, done, paired["ref"]["win"], **rules)
                        if ref["gain"]:
                            shutil.copyfile(latest, os.path.join(out_dir, "ppo_best.zip"))
                        if ref["rebased"]:
                            for g in trainer.optimizer.param_groups:
                                g["lr"] = ref["lr"]
                            print(f"REBASE: {paired['ref']['win']:.3f} >= {rebase_at} against {measured}; new reference "
                                  f"{ref['reference']}, lr {ref['lr']:g}", flush=True)
                if r_rand and r_rand["win"] >= RETIRE_RANDOM:
                    random_in_pool = False
                if k % snapshot_every == 0 or not random_in_pool:
                    pool = pool_paths()
                    trainer.set_pool(pool, random_in_pool)
                t2 = time.time()

                mean_score = (r_anchor or r_rand or {}).get("score")
                row = [time.strftime("%Y-%m-%d %H:%M:%S"), done, games0 + trainer.games,
                       fmt(r_rand and r_rand["win"]), fmt(r_greedy and r_greedy["win"]),
                       fmt(r_anchor and r_anchor["win"]), fmt(r_anchor and r_anchor["margin"], 1), fmt(mean_score, 1),
                       fmt(paired.get("1m", {}).get("win")), fmt(paired.get("1m", {}).get("margin"), 1),
                       fmt(paired.get("3m", {}).get("win")), fmt(paired.get("3m", {}).get("margin"), 1),
                       fmt(paired.get("ref", {}).get("win")), fmt(paired.get("ref", {}).get("margin"), 1),
                       measured if "ref" in paired else "",
                       os.path.basename(anchor_path) if anchor_path else "", len(pool), int(random_in_pool),
                       f"{(t1 - t0) / 60:.1f}", f"{(t2 - t1) / 60:.1f}"]
                log.writerow(row)
                f.flush()
                print(f"[{row[0]}] p{players} steps={done} games={row[2]} random={row[3]} greedy={row[4]} "
                      f"anchor={row[5]} margin={row[6]} vs1m={row[8]} vs3m={row[10]} ref={row[12]} ({row[13]}) "
                      f"pool={len(pool)} random_in_pool={row[17]} learn={row[-2]}m eval={row[-1]}m "
                      f"(pg {s['pg']:+.3f} vf {s['vf']:.3f} ent {s['ent']:.2f} clipped {s['clipped']:.2f}) "
                      f"best_vs_ref={ref['best']:.3f}@{ref['best_steps']} without_gain={ref['stale']}", flush=True)
                if patience and done >= min_steps and ref["stale"] >= patience:
                    print(f"STOP: {ref['stale']} paired evaluations without a gain of {min_gain} against "
                          f"{ref['reference']}; best {ref['best']:.3f} at {ref['best_steps']} steps", flush=True)
                    break
    finally:
        trainer.close()
        eval_pool.terminate()
    return os.path.join(out_dir, "ppo_latest.zip")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="game slug (games/<slug>)")
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--timesteps", type=int, default=5_000_000)
    ap.add_argument("--envs", type=int, default=16, help="game worker processes")
    ap.add_argument("--eval-workers", type=int, default=4, help="processes for evaluation games (each loads torch)")
    ap.add_argument("--tables", type=int, default=4, help="games per worker")
    ap.add_argument("--chunk", type=int, default=200_000)
    ap.add_argument("--snapshot-every", type=int, default=2)
    ap.add_argument("--pool-size", type=int, default=4)
    ap.add_argument("--reward", choices=["win", "margin", "mixed"], default="mixed")
    ap.add_argument("--frozen-share", type=float, default=0.2)
    ap.add_argument("--rollout", type=int, default=16384, help="learned decisions per PPO update")
    ap.add_argument("--out", required=True, help="run folder, e.g. runs/<slug>/open (checkpoints go to <out>/p<players>)")
    ap.add_argument("--start-from", default=None, help="checkpoint whose weights a new run starts from (anchored run)")
    ap.add_argument("--net", type=int, nargs="+", default=[512, 512, 256], help="hidden layer sizes of a new model")
    ap.add_argument("--options", default=None, help="JSON game options (default: the game's default options)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-games", type=int, default=40)
    ap.add_argument("--greedy-games", type=int, default=40)
    ap.add_argument("--anchor", default=None, help="checkpoint used as fixed evaluation opponent")
    ap.add_argument("--anchor-steps", type=int, default=1_000_000)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--hours", type=float, default=None, help="stop after the first chunk that ends past this time")
    ap.add_argument("--lr", type=float, default=2.5e-4)
    ap.add_argument("--epochs", type=int, default=10, help="passes over each batch in the PPO update")
    ap.add_argument("--fixed", nargs="*", default=[], help='opponents always in the pool: "greedy" or checkpoints')
    ap.add_argument("--keep-every", type=int, default=2_000_000, help="checkpoints at multiples of this stay in the pool")
    ap.add_argument("--reference", default=None, help="fixed model for paired games every 1M steps (win_vs_ref)")
    ap.add_argument("--reference-deals", type=int, default=750)
    ap.add_argument("--min-gain", type=float, default=0.0, help="win-rate gain against the reference that counts as progress")
    ap.add_argument("--patience", type=int, default=None, help="stop after this many evaluations without progress")
    ap.add_argument("--min-steps", type=int, default=0, help="never stop for lack of progress before this many steps")
    ap.add_argument("--rebase-at", type=float, default=None, help="win rate against the reference that makes the best "
                    "checkpoint the new reference")
    ap.add_argument("--lr-decay", type=float, default=0.5, help="learning-rate factor at each rebase")
    a = ap.parse_args()
    import json
    train(a.game, a.players, a.timesteps, a.out, a.envs, a.tables, a.chunk, a.snapshot_every, a.pool_size, a.reward, a.seed,
          a.frozen_share, a.rollout, a.eval_games, a.greedy_games, a.anchor, a.anchor_steps, a.resume, a.hours,
          a.lr, a.epochs, tuple(a.fixed), a.keep_every, a.reference, a.reference_deals, a.min_gain, a.patience,
          a.min_steps, a.rebase_at, a.lr_decay, a.start_from, tuple(a.net), json.loads(a.options) if a.options else None, a.eval_workers)
