"""Seeded randomness and a card pile with the top card at index 0."""
from __future__ import annotations

import random
from typing import Optional

# The one random source of a game. Python's Mersenne Twister: the same seed gives the same shuffle, choice and
# randrange sequence on every platform for a fixed Python version (pinned in requirements.lock).
Rng = random.Random


class Deck(list):
    """A pile of cards. Index 0 is the top. Behaviour is frozen (tests/test_kit.py)."""

    def shuffle(self, rng: random.Random) -> None:
        rng.shuffle(self)

    def draw(self) -> Optional[object]:
        """Remove and return the top card, or None when the pile is empty."""
        return self.pop(0) if self else None

    def draw_many(self, n: int) -> list:
        """Up to n cards from the top, in drawing order."""
        out = []
        for _ in range(n):
            if not self:
                break
            out.append(self.pop(0))
        return out

    def put_bottom(self, cards) -> None:
        self.extend(cards)
