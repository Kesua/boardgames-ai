"""Pending choices as a stack: the top decision is the one to answer now.

A turn is a chain of small choices (choose an action, then pay, then choose a target ...). Each choice the agent has
to make is one Decision on the stack; resolving it may push more decisions. `seat` names who decides; None means
the player whose turn it is. Games use this so that big choices become several small numbered steps (the action
list stays a fixed size) and so that players can decide outside their own turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Decision:
    kind: str
    data: dict = field(default_factory=dict)
    seat: Optional[int] = None


class DecisionStack(list):
    """A list of Decision with the top at the end. Behaviour is frozen (tests/test_kit.py)."""

    def push(self, d: Decision) -> None:
        self.append(d)

    @property
    def top(self) -> Optional[Decision]:
        return self[-1] if self else None

    def decider(self, turn_seat: int) -> int:
        """Seat that answers the top decision: its own seat, else the player whose turn it is."""
        d = self.top
        return turn_seat if d is None or d.seat is None else d.seat
