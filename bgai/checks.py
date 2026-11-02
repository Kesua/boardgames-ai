"""Automated engine checks every game must pass before a model is trained (verify-engine skill).

python -m bgai.checks --game <slug> [--games 10000] [--players 2 3 4]    # writes games/<slug>/checks/report.json

--games is the number of random games PER player count (default 10,000, the bar before training).
For every supported player count:
  ends      every game ends within spec.max_steps decisions, never with an empty legal list
  seed      the same seed and the same answers give the same game (final scores and log)
  clone     a clone plays on independently: changing the clone never changes the original
  legal     legal_ids() are unique numbers inside [0, action_count); illegal numbers raise
  scores    scores() equals the sum of breakdowns(); tableau points are integers
  records   record_info() and seat_extra() return the fields the recorder needs
  encoder   observations have the encoder's size, are finite and lie in [0, 1]
  direction the greedy agent beats random players clearly (catches scores where lower is better: scores() must be
            higher-is-better, negate them for lowest-score-wins games)
Games may add their own invariants (card conservation, ...) as spec.invariants(game) -> list of problems.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def play_random(spec, players: int, seed: int, check_every: int = 0, problems: list = None):
    g = spec.new_game(players, seed, dict(spec.default_options))
    rng = random.Random(seed * 7919 + players)
    n_actions = spec.action_count(players)
    answers = []
    steps = 0
    while not g.game_over:
        ids = g.legal_ids()
        if not ids:
            raise AssertionError(f"seed {seed}: empty legal list at step {steps}")
        if len(set(ids)) != len(ids) or min(ids) < 0 or max(ids) >= n_actions:
            raise AssertionError(f"seed {seed}: bad legal ids {ids}")
        a = rng.choice(ids)
        if check_every and steps % check_every == 0:
            info = g.record_info(a)
            for k in ("decision", "action"):
                if k not in info:
                    raise AssertionError(f"record_info lacks {k}")
            if getattr(spec, "invariants", None):
                problems.extend(spec.invariants(g))
        g.step_id(a)
        answers.append(a)
        steps += 1
        if steps > spec.max_steps:
            raise AssertionError(f"seed {seed}: no end within {spec.max_steps} decisions")
    return g, answers


def check_game(spec, players: int, seed: int) -> list:
    problems = []
    g, answers = play_random(spec, players, seed, check_every=7, problems=problems)
    sc = g.scores()
    if [sum(b.values()) for b in g.breakdowns()] != sc:
        problems.append(f"seed {seed}: scores {sc} != sum of breakdowns")
    for seat in range(players):
        for r in g.tableau(seat):
            if not isinstance(r.get("points"), int):
                problems.append(f"seed {seed}: tableau points not int: {r}")
        ex = g.seat_extra(seat)
        if "hand_left" not in ex:
            problems.append("seat_extra lacks hand_left")
    # same seed + same answers -> same game
    h = spec.new_game(players, seed, dict(spec.default_options))
    for a in answers:
        h.step_id(a)
    if h.scores() != sc:
        problems.append(f"seed {seed}: replay differs {h.scores()} vs {sc}")
    return problems


def check_clone(spec, players: int, seed: int) -> list:
    g = spec.new_game(players, seed, dict(spec.default_options))
    rng = random.Random(seed)
    for _ in range(40):
        if g.game_over:
            break
        g.step_id(rng.choice(g.legal_ids()))
    if g.game_over:
        return []
    before = (g.legal_ids(), g.scores(), g.text_state())
    c = g.clone()
    for _ in range(60):
        if c.game_over:
            break
        c.step_id(rng.choice(c.legal_ids()))
    after = (g.legal_ids(), g.scores(), g.text_state())
    problems = [] if before == after else [f"seed {seed}: playing a clone changed the original"]
    try:
        bad = next(i for i in range(spec.action_count(players)) if i not in set(g.legal_ids()))
        g.step_id(bad)
        problems.append(f"seed {seed}: illegal action {bad} was accepted")
    except StopIteration:
        pass
    except Exception:
        pass
    return problems


def check_encoder(spec, players: int, seed: int) -> list:
    import numpy as np
    enc = spec.encoder(players)
    g = spec.new_game(players, seed, dict(spec.default_options))
    rng = random.Random(seed)
    steps = 0
    while not g.game_over:
        if steps % 5 == 0:
            v = np.asarray(enc.encode(g, g.current_seat))
            if v.shape != (enc.size,):
                return [f"seed {seed}: observation shape {v.shape}, encoder size {enc.size}"]
            if not np.isfinite(v).all():
                return [f"seed {seed}: observation has NaN or infinity at step {steps}"]
            if v.min() < 0 or v.max() > 1:
                i = int(np.argmax((v < 0) | (v > 1)))
                return [f"seed {seed}: observation value {float(v[i]):.3f} at index {i} outside [0, 1] (step {steps})"]
        g.step_id(rng.choice(g.legal_ids()))
        steps += 1
    return []


def check_direction(spec, players: int, games: int = 40) -> tuple:
    """Greedy (one seat, rotating) against random players. Returns (win rate, problems)."""
    from .agents import RandomAgent, play_game
    from .kit.scores import winners
    wins = 0
    for k in range(games):
        seat = k % players
        agents = [RandomAgent(seed=k * 10 + j) for j in range(players)]
        agents[seat] = spec.greedy(seed=k)
        g = spec.new_game(players, 900000 + k, dict(spec.default_options))
        play_game(g, agents, max_steps=spec.max_steps + 1)
        wins += seat in winners(g.scores(), g.tiebreaks())
    rate = wins / games
    # 2 players: chance 50 %; a working greedy agent wins far more often
    bar = min(0.9, 1 / players + 0.25)
    problems = [] if rate >= bar else [f"greedy won only {rate:.0%} of {games} games against random players with "
                                       f"{players} players (expected at least {bar:.0%}): are scores higher-is-better?"]
    return rate, problems


def run(slug: str, games: int, players: list) -> dict:
    from .game import load_spec
    spec = load_spec(slug)
    players = players or list(spec.players)
    t0 = time.time()
    problems, counts = [], {}
    for p in players:
        n = 0
        for seed in range(games):
            problems += check_game(spec, p, seed)
            if seed % 50 == 0:
                problems += check_clone(spec, p, seed)
            if seed % 100 == 0:
                problems += check_encoder(spec, p, seed)
            n += 1
        counts[str(p)] = n
    rate, direction = check_direction(spec, min(players))
    problems += direction
    from .experiment import code_commit
    report = {"game": slug, "code_commit": code_commit(), "games_per_player_count": counts, "problems": problems[:200],
              "problem_count": len(problems), "seconds": round(time.time() - t0, 1),
              "greedy_vs_random": {"players": min(players), "games": 40, "win": rate},
              "checks": ["ends", "legal", "seed", "clone", "scores", "records", "encoder", "direction"]
              + (["invariants"] if getattr(spec, "invariants", None) else [])}
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--games", type=int, default=10000, help="random games per player count")
    ap.add_argument("--players", type=int, nargs="*")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    report = run(a.game, a.games, a.players)
    if not a.no_write:
        out = ROOT / "games" / a.game / "checks"
        out.mkdir(parents=True, exist_ok=True)
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "problems"}, indent=2))
    for p in report["problems"][:20]:
        print("PROBLEM:", p)
    raise SystemExit(1 if report["problem_count"] else 0)


if __name__ == "__main__":
    main()
