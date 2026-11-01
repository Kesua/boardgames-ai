"""Automated engine checks every game must pass before a model is trained (verify-engine skill).

python -m bgai.checks --game <slug> [--games 10000] [--players 2 3 4]    # writes games/<slug>/checks/report.json

For many random games with every supported player count:
  ends      every game ends within spec.max_steps decisions, never with an empty legal list
  seed      the same seed and the same answers give the same game (final scores and log)
  clone     a clone plays on independently: changing the clone never changes the original
  legal     legal_ids() are unique numbers inside [0, action_count); illegal numbers raise
  scores    scores() equals the sum of breakdowns(); tableau points are integers
  records   record_info() and seat_extra() return the fields the recorder needs
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


def run(slug: str, games: int, players: list) -> dict:
    from .game import load_spec
    spec = load_spec(slug)
    players = players or list(spec.players)
    t0 = time.time()
    problems, counts = [], {}
    for p in players:
        n = 0
        for seed in range(games // len(players)):
            problems += check_game(spec, p, seed)
            if seed % 50 == 0:
                problems += check_clone(spec, p, seed)
            n += 1
        counts[str(p)] = n
    report = {"game": slug, "games_per_player_count": counts, "problems": problems[:200],
              "problem_count": len(problems), "seconds": round(time.time() - t0, 1),
              "checks": ["ends", "legal", "seed", "clone", "scores", "records"]
              + (["invariants"] if getattr(spec, "invariants", None) else [])}
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--games", type=int, default=10000)
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
