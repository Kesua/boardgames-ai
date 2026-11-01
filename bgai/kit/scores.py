"""Winners and ranks from final scores.

Platform convention (used by every summary): a player wins when no other player is strictly better, comparing
(score, tiebreak) — so players still tied after the tiebreak all win ("ties count as wins"). Ranks order players by
(score, tiebreak) from best; players that are still tied are ordered by seat (stable sort), so ranks are always
1..n. Games without an official tiebreak pass none.
"""
from __future__ import annotations

from typing import Optional


def _keys(scores: list, tiebreaks: Optional[list]) -> list:
    return [(s, tiebreaks[i] if tiebreaks is not None else 0) for i, s in enumerate(scores)]


def winners(scores: list, tiebreaks: Optional[list] = None) -> list:
    keys = _keys(scores, tiebreaks)
    best = max(keys)
    return [i for i, k in enumerate(keys) if k == best]


def ranks(scores: list, tiebreaks: Optional[list] = None) -> list:
    """Rank (1 = best) per seat."""
    keys = _keys(scores, tiebreaks)
    order = sorted(range(len(keys)), key=lambda i: (-keys[i][0], -keys[i][1]))
    out = [0] * len(keys)
    for r, seat in enumerate(order):
        out[seat] = r + 1
    return out
