"""Greedy baseline: take the option that raises the own score most right now (ties at random)."""
from __future__ import annotations

import random

from bgai.agents import Agent


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def act(self, game, seat: int) -> int:
        best, best_v = [], None
        for a in game.legal_ids():
            g = game.clone()
            g.step_id(a)
            v = g.scores()[seat]
            if best_v is None or v > best_v:
                best, best_v = [a], v
            elif v == best_v:
                best.append(a)
        return self.rng.choice(best)
