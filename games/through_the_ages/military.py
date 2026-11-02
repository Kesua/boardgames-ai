"""Military cards and strength (PLAN.md section 2). Stage 1 holds only what a peaceful game needs: drawing military
cards (T3.7), discarding them by age (T6.5, D7) and strength without armies (T11.3). Armies and tactics (T11.4),
colonization (T8), aggressions and wars (T9) and the T8.3 ranking helper come in stage 2."""
from __future__ import annotations

from .cards import AGE


def discard(g, card: int) -> None:
    """T6.5 / D7: a military card goes to the discard pile only if it belongs to the current age; an older card
    leaves the game (its pile left with its age)."""
    s = g.s
    if AGE[card] == s.age:
        s.military_discard.append(card)
    else:
        s.removed_military.append(card)


def draw(g, seat: int, n: int) -> int:
    """T3.7: draw up to n cards from the current military deck; an empty deck is refilled from the current age's
    shuffled discard pile. None in Age IV. Returns the number drawn."""
    s = g.s
    if s.age == "IV" or n <= 0:
        return 0
    p = s.players[seat]
    got = 0
    for _ in range(n):
        if not s.military_deck and s.military_discard:
            s.military_deck.extend(s.military_discard)
            s.military_discard = []
            s.military_deck.shuffle(g.rng)
            s.log.add(None, "Military discard pile shuffled into a new military deck")
        c = s.military_deck.draw()
        if c is None:
            break
        p.military_hand.append(c)
        got += 1
    return got


def strength(g, seat: int) -> int:
    """T11.3 without armies (stage 2 adds tactics, armies and air forces, T11.4)."""
    from .economy import stats
    return stats(g, seat).strength
