"""Observation: market cards (one-hot per card), own cards, card counts per colour for every player (self first)."""
from __future__ import annotations

import numpy as np

from bgai.kit import add_counts

from .engine import CARDS


class StateEncoder:
    version = 1

    def __init__(self, num_players: int):
        self.n = num_players
        self.size = 2 * len(CARDS) + 3 * num_players + 1

    def encode(self, g, seat: int) -> np.ndarray:
        s = g.s
        v = np.zeros(self.size, dtype=np.float32)
        add_counts(v, 0, s.market, 1.0)
        add_counts(v, len(CARDS), s.hands[seat], 1.0)
        i = 2 * len(CARDS)
        for k in range(self.n):
            hand = s.hands[(seat + k) % self.n]
            for col in range(3):
                v[i + col] = min(sum(1 for c in hand if CARDS[c][1] == col), 6) / 6
            i += 3
        v[i] = len(s.deck) / len(CARDS)
        return v
