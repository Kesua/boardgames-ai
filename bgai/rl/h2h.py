"""Paired matches on the same deals: agent A takes every seat of each deal once, all other seats are agent B.

An agent is "random", "greedy" or a checkpoint path (any observation version of the game). Models play
deterministically, so the same seeds give comparable numbers over a training run. Ties count as wins (bgai.kit.scores).

python -m bgai.rl.h2h --game <slug> --players 2 --a <ckpt> --b <ckpt|greedy|random> --seeds 750 [--first-seed 20000]
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import statistics


def _agent(spec, players, who: str, seed: int):
    from ..agents import PolicyAgent, RandomAgent
    if who == "random":
        return RandomAgent(seed)
    if who == "greedy":
        return spec.greedy(seed)
    return PolicyAgent(who, spec, players)


def _play(job) -> list:
    slug, a, b, players, seeds, options = job
    import torch
    torch.set_num_threads(1)
    from ..agents import play_game
    from ..game import load_spec
    from ..kit.scores import winners
    spec = load_spec(slug)
    first = seeds[0] if seeds else 0
    agent_a, agent_b = _agent(spec, players, a, first), _agent(spec, players, b, first + 1)
    out = []
    for seed in seeds:
        for seat in range(players):
            g = spec.new_game(players, seed, options)
            sc = play_game(g, [agent_a if s == seat else agent_b for s in range(players)], max_steps=spec.max_steps)
            won = seat in winners(sc, g.tiebreaks())
            out.append((seed, seat, sc[seat], max(x for s, x in enumerate(sc) if s != seat), won))
    return out


def match(slug: str, a: str, b: str, players: int, seeds, workers: int = 8, options=None, pool=None) -> list:
    """Rows (seed, seat of A, A's score, best other score, A won), players games per seed."""
    from ..game import load_spec
    options = options if options is not None else dict(load_spec(slug).default_options)
    seeds = list(seeds)
    jobs = [(slug, a, b, players, seeds[i::workers], options) for i in range(workers) if seeds[i::workers]]
    if pool is not None:
        return [r for part in pool.map(_play, jobs) for r in part]
    with mp.get_context("spawn").Pool(len(jobs)) as own:
        return [r for part in own.map(_play, jobs) for r in part]


def summary(rows: list) -> dict:
    win = [1.0 if r[4] else 0.0 for r in rows]
    margin = [r[2] - r[3] for r in rows]
    n = len(rows)
    se = lambda xs: statistics.stdev(xs) / n ** 0.5 if n > 1 else float("nan")
    return {"games": n, "win": statistics.mean(win), "win_se": se(win), "margin": statistics.mean(margin),
            "margin_se": se(margin), "score": statistics.mean(r[2] for r in rows),
            "other": statistics.mean(r[3] for r in rows)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--seeds", type=int, default=750)
    ap.add_argument("--first-seed", type=int, default=20000)
    ap.add_argument("--workers", type=int, default=8)
    x = ap.parse_args()
    s = summary(match(x.game, x.a, x.b, x.players, range(x.first_seed, x.first_seed + x.seeds), x.workers))
    print(f"A wins {s['win']:.3f} +- {s['win_se']:.3f} of {s['games']} games, margin {s['margin']:+.1f} +- "
          f"{s['margin_se']:.1f}, scores {s['score']:.1f} vs {s['other']:.1f}")
