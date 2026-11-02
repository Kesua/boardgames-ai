"""Greedy baseline: one-step lookahead on a hand-made value of the position (culture now and per remaining round,
science, production, actions; design-rl improves it). Ties at random."""
from __future__ import annotations

import random

from bgai.agents import Agent

from . import economy as E
from .cards import IS_STARTING, IS_TECH, KIND, LEVEL, TOKEN_VALUE

ROUNDS_LEFT = {"A": 18, "I": 15, "II": 10, "III": 5, "IV": 1}
HAND_VALUE = {"leader": 2.0, "action": 1.5, "wonder": 0.0}
COMPLETIONS = ("CHOOSE_TECH", "UPGRADE_TO", "STAGES", "REVOLT", "SUB_ACTION")


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
    food_prod = sum(p.workers.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] == "farm")
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
    for c in p.civil_hand:
        val += 1.0 if IS_TECH[c] else HAND_VALUE.get(KIND[c], 0.5)
    for c in p.techs:                                               # developed technologies: future options
        if not IS_STARTING[c]:
            val += 2.0 + 1.5 * LEVEL[c]
    for c in p.specials.values():
        val += 3.0 + 2.0 * LEVEL[c]
    if p.leader is not None:
        val += 3.0
    if p.unfinished is not None:
        val += 1.5 * p.unfinished[1]
    val += 3.0 * len(p.wonders)
    if s.turn_seat == seat and not s.game_over:                     # production and actions still to come this turn
        val += st.culture + 0.4 * st.science + 0.3 * net_food + 0.4 * net_res
        val += 0.8 * E.civil_available(g, seat) + 0.2 * E.military_available(g, seat)
    return val


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def _look(self, game, a: int, seat: int, depth: int) -> float:
        """Value after answer a; a verb that opens a completion step (which building, how many stages ...) is valued
        by its best completion."""
        g = game.clone()
        g.step_id(a)
        d = g.s.decisions.top
        if depth and d is not None and d.seat == seat and d.kind in COMPLETIONS and not g.game_over:
            return max(self._look(g, b, seat, depth - 1) for b in g.legal_ids())
        return value(g, seat)

    def act(self, game, seat: int) -> int:
        legal = game.legal_ids()
        if len(legal) == 1:
            return legal[0]
        best, best_v = [], None
        for a in legal:
            v = self._look(game, a, seat, 2)
            if best_v is None or v > best_v + 1e-9:
                best, best_v = [a], v
            elif abs(v - best_v) <= 1e-9:
                best.append(a)
        return self.rng.choice(best)
