"""Greedy baseline: one-step lookahead on a hand-made value of the position (culture now and per remaining round,
science, production, actions, strength; design-rl improves it). Ties at random.

Military rules of thumb (it never resigns: a resigned position is worth -1000):
- an aggression is valued as if it succeeds only when the attacker's margin beats a rough bound of what the rival
  could still defend with (public: military hand size, military action total); otherwise as failed;
- defending: play the strongest legal card (a tie is still reachable whenever a card is legal);
- colonization: bid the minimum only while it is small, send what costs least (lookahead).
"""
from __future__ import annotations

import random

from bgai.agents import Agent

from . import economy as E
from .cards import BONUS, IS_STARTING, IS_TECH, KIND, LEVEL, TOKEN_VALUE

ROUNDS_LEFT = {"A": 18, "I": 15, "II": 10, "III": 5, "IV": 1}
HAND_VALUE = {"leader": 2.0, "action": 1.5, "wonder": 0.0}
COMPLETIONS = ("CHOOSE_TECH", "UPGRADE_TO", "STAGES", "REVOLT", "SUB_ACTION", "POLITICS_CARD", "TARGET", "PACT_SIDE",
               "ABILITY", "CHOOSE_TACTIC", "MIX", "ANNEX", "INFILTRATE", "KIDNAP", "STEAL_TECH", "CANCEL_WHICH")
DEFENSE_PER_CARD = {"A": 1, "I": 2, "II": 3, "III": 4, "IV": 4}


def rounds_left(g) -> int:
    s = g.s
    if s.last_round is not None:
        return max(0, s.last_round - s.round + 1)
    return ROUNDS_LEFT[s.age]


def value(g, seat: int) -> float:
    s = g.s
    p = s.players[seat]
    if p.resigned_order is not None:
        return -1000.0
    st = E.stats(g, seat)
    r = rounds_left(g)
    food_prod = sum(p.workers.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] == "farm") + st.food_bonus
    res_prod = sum(p.workers.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] == "mine") + st.resource_bonus
    net_food = food_prod - E.consumption(p.yellow_bank)
    net_res = res_prod - E.corruption(p.blue_bank)
    horizon = min(r, 8)
    val = p.culture + st.culture * r + 0.4 * p.science + 0.6 * st.science * r
    val += 0.3 * E.food(p) + 0.4 * E.resources(p)
    val += horizon * (0.4 * net_food + 0.6 * net_res)
    if net_food < 0:
        val += 2.0 * net_food * min(r, 5)
    val += r * (1.2 * st.civil + 0.3 * st.military)
    val += 0.6 * p.pool
    if E.discontent(g, seat) > p.pool:
        val -= 10
    val += 0.5 * min(st.strength, 60)
    for c in p.civil_hand:
        val += 1.0 if IS_TECH[c] else HAND_VALUE.get(KIND[c], 0.5)
    for c in p.military_hand:
        val += 0.4 + (0.2 * BONUS[c]["defense"] if KIND[c] == "bonus" else 0.0)
    for c in p.techs:                                               # developed technologies: future options
        if not IS_STARTING[c]:
            val += 2.0 + 1.5 * LEVEL[c]
    for c in p.specials.values():
        val += 3.0 + 2.0 * LEVEL[c]
    if p.leader is not None:
        val += 3.0
    if p.unfinished is not None:
        val += 1.5 * p.unfinished[1]
    val += 3.0 * len(p.wonders) + 2.0 * len(p.colonies)
    if s.turn_seat == seat and not s.game_over:                     # production and actions still to come this turn
        val += st.culture + 0.4 * st.science + 0.3 * net_food + 0.4 * net_res
        val += 0.8 * E.civil_available(g, seat) + 0.2 * E.military_available(g, seat)
    return val


def defense_bound(g, rival: int) -> int:
    """A rough public bound on what the rival could add in defense: cards it may play x a typical bonus value."""
    p = g.s.players[rival]
    k = min(len(p.military_hand), E.stats(g, rival).military)
    return k * DEFENSE_PER_CARD[g.s.age]


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def _look(self, game, a: int, seat: int, depth: int) -> float:
        """Value after answer a; a verb that opens a completion step (which building, how many stages, which card,
        which target ...) is valued by its best completion."""
        from .engine import A_NO
        g = game.clone()
        g.step_id(a)
        d = g.s.decisions.top
        if d is not None and not g.game_over and d.seat != seat and d.kind == "DEFEND" and depth:
            if d.data["need"] > defense_bound(g, d.seat):                    # likely success: value it
                g.step_id(A_NO)
                d = g.s.decisions.top
            else:
                return value(g, seat) - 1.0
        if depth and d is not None and d.seat == seat and d.kind in COMPLETIONS and not g.game_over:
            return max(self._look(g, b, seat, depth - 1) for b in g.legal_ids())
        return value(g, seat)

    def act(self, game, seat: int) -> int:
        from .engine import A_AMOUNT, A_CARD, A_NO
        legal = game.legal_ids()
        if len(legal) == 1:
            return legal[0]
        d = game.s.decisions.top
        if d.kind == "DEFEND":
            cards = [a for a in legal if a != A_NO]
            c = max(cards, key=lambda a: (BONUS[a - A_CARD]["defense"] if KIND[a - A_CARD] == "bonus" else 1, -a))
            return c
        if d.kind == "BID":
            bids = sorted(a for a in legal if a != A_NO)
            return bids[0] if bids and bids[0] - A_AMOUNT + 1 <= 4 else A_NO
        best, best_v = [], None
        for a in legal:
            v = self._look(game, a, seat, 3)
            if best_v is None or v > best_v + 1e-9:
                best, best_v = [a], v
            elif abs(v - best_v) <= 1e-9:
                best.append(a)
        return self.rng.choice(best)
