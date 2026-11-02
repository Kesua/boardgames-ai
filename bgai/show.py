"""Print one game as readable text: every decision with who made it, then the final state and scores.

python -m bgai.show --game <slug> [--players 2] [--seed 1] [--agents greedy random] [--max-lines 400]

Agents: greedy, random or a model id (games/<slug>/models/<id>). Use it to read a game against the real rules
(review-game-pr skill: "does it look like the real game?").
"""
from __future__ import annotations

import argparse

from .agents import PolicyAgent, RandomAgent
from .game import load_spec


def make_agent(spec, kind: str, players: int, seed: int):
    if kind == "random":
        return RandomAgent(seed)
    if kind == "greedy":
        return spec.greedy(seed=seed)
    from .experiment import game_dir
    return PolicyAgent(str(game_dir(spec.slug) / "models" / kind / "model.zip"), spec, players)


def show(slug: str, players: int, seed: int, agents: list, max_lines: int) -> list:
    spec = load_spec(slug)
    kinds = (agents * players)[:players]
    seats = [make_agent(spec, k, players, seed * 10 + j) for j, k in enumerate(kinds)]
    g = spec.new_game(players, seed, dict(spec.default_options))
    lines = [f"{spec.name}, {players} players, seed {seed}, seats: {', '.join(kinds)}"]
    while not g.game_over:
        seat = g.current_seat
        a = seats[seat].act(g, seat)
        if len(lines) < max_lines:
            lines.append(f"[turn {g.turns}] P{seat}: {g.describe(a)}")
        g.step_id(a)
    if len(lines) >= max_lines:
        lines.append(f"... (cut at {max_lines} lines; --max-lines to see more)")
    lines += ["", "Final state:", g.text_state(), "",
              "Scores: " + ", ".join(f"P{i} {s} {g.breakdowns()[i]}" for i, s in enumerate(g.scores()))]
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--agents", nargs="+", default=["greedy"], help="one per seat, repeated to fill the table")
    ap.add_argument("--max-lines", type=int, default=400)
    a = ap.parse_args(argv)
    print("\n".join(show(a.game, a.players, a.seed, a.agents, a.max_lines)))


if __name__ == "__main__":
    main()
