"""Wingspan greedy baseline.

Main choices (which action, which bird to play) are judged by playing the rest of the turn in a copy of the game with
simple rules and comparing the value after the turn: own score minus the best other score, plus a small value for
food and cards in hand. Small choices use the simple rules directly (take food the hand needs, lay eggs where room
is, draw the best-value bird, use every power). It is a stronger opponent than random but plays no long plans.
"""
from __future__ import annotations

import random
from typing import Optional

from bgai.agents import Agent

from . import engine as E


def _value(g, seat: int) -> float:
    sc = g.scores()
    other = max(x for i, x in enumerate(sc) if i != seat)
    pl = g.p(seat)
    playable = len(g.playable_birds(seat))
    return sc[seat] - other + 0.45 * sum(pl.food) + 0.35 * min(len(pl.hand), 8) + 0.6 * playable


def _needed_food(g, seat: int) -> list:
    """How much each food would help pay for the birds in hand (cheap, high-value birds count more)."""
    need = [0.0] * 5
    for b in g.p(seat).hand:
        bd = g.bird(b)
        w = (bd.points + 1) / (bd.food_total + 1)
        for f in range(5):
            need[f] += bd.food[f] * w
        if bd.wild:
            for f in range(5):
                need[f] += 0.2 * w
    return need


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    # ---- simple rules for small choices
    def simple(self, g, seat: int) -> int:
        d = g.s.decisions.top
        legal = d.data["legal"]
        k = d.kind
        pl = g.p(seat)
        no = E.A_NO if E.A_NO in legal else None
        pick = lambda xs, key: max(xs, key=lambda a: (key(a), -a))
        if k == "SETUP_KEEP":
            b = g.bird(d.data["bird"])
            kept = g.s.tasks[-1].get("kept", 0)
            return E.A_YES if b.food_total <= 2 and b.points >= 2 and kept < 3 else E.A_NO
        if k in ("SETUP_FOOD", "TRADE_PAY_FOOD", "TRADE_GIVE"):
            need = _needed_food(g, seat)
            cands = [a for a in legal if a != no]
            return pick(cands, lambda a: -need[a - E.A_FOOD]) if cands else no
        if k in ("SETUP_BONUS", "KEEP_BONUS"):
            return legal[0]
        if k == "PLAY_BIRD":
            cands = [a for a in legal if a != no]
            if not cands:
                return no
            return pick(cands, lambda a: g.bird(a - E.A_BIRD).points - 0.5 * g.bird(a - E.A_BIRD).food_total)
        if k == "PLAY_HABITAT":
            return pick(legal, lambda a: -len(pl.rows[a - E.A_HAB]))
        if k in ("TAKE_DIE", "DUAL_FOOD", "CHOOSE_FOOD", "TRADE_GET"):
            need = _needed_food(g, seat)
            cands = [a for a in legal if a not in (E.A_NO, E.A_REROLL)]
            if not cands:
                return E.A_REROLL if E.A_REROLL in legal else legal[0]
            if E.A_YES in cands:
                return E.A_YES

            def food_of(a):
                if E.A_DIE <= a < E.A_DIE + 6:
                    face = a - E.A_DIE
                    return max(need[0], need[1]) if face == 5 else need[face]
                return need[a - E.A_FOOD] if E.A_FOOD <= a < E.A_FOOD + 5 else 0
            return pick(cands, food_of)
        if k == "LAY_EGG":
            cands = [a for a in legal if a != no]
            if not cands:
                return no
            return pick(cands, lambda a: g.bird(pl.rows[g.slot_of(a)[0]][g.slot_of(a)[1]].bird).egg_limit
                        - pl.rows[g.slot_of(a)[0]][g.slot_of(a)[1]].eggs)
        if k in ("PAY_EGG", "DISCARD_EGG", "TRADE_DISCARD_EGG"):
            cands = [a for a in legal if a != no]
            if not cands or (k == "DISCARD_EGG" and pl.eggs() < 3):
                return no if no is not None else legal[0]
            return pick(cands, lambda a: pl.rows[g.slot_of(a)[0]][g.slot_of(a)[1]].eggs)
        if k == "DRAW":
            cands = [a for a in legal if a != no]
            if not cands:
                return no

            def card_value(a):
                if a == E.A_DECK:
                    return 2.5
                b = g.bird(g.s.tray[a - E.A_TRAY])
                return b.points - 0.5 * b.food_total + 1
            return pick(cands, card_value)
        if k in ("TUCK", "END_DISCARD", "TRADE_DISCARD_CARD", "PICK_CARD"):
            cands = [a for a in legal if a != no]
            if not cands:
                return no
            best = k == "PICK_CARD"
            return pick(cands, lambda a: (1 if best else -1) * (g.bird(a - E.A_BIRD).points
                                                                 - 0.5 * g.bird(a - E.A_BIRD).food_total))
        if k == "TRADE":
            return E.A_NO
        if k == "CACHE":
            return E.A_YES
        if k == "USE_POWER":
            return E.A_YES
        if k == "PAY_FOOD":
            cands = [a for a in legal if a != E.A_YES]
            need = _needed_food(g, seat)
            return pick(cands, lambda a: -need[a - E.A_FOOD]) if cands else E.A_YES
        if k == "PAY_PAIR":
            need = _needed_food(g, seat)
            return pick(legal, lambda a: -need[a - E.A_FOOD])
        cands = [a for a in legal if a != no]
        return cands[0] if cands else legal[0]

    def _rollout_turn(self, g, seat: int) -> float:
        """Finish the current turn with the simple rules (all players' pink choices too), return seat's value."""
        turns = g.s.turns
        steps = 0
        while not g.game_over and g.s.turns == turns and steps < 200:
            who = g.current_seat
            g.step_id(self.simple(g, who))
            steps += 1
        return _value(g, seat)

    def act(self, game, seat: int) -> int:
        d = game.s.decisions.top
        legal = d.data["legal"]
        if d.kind in ("CHOOSE_ACTION", "PLAY_BIRD"):
            best, best_v = [], None
            for a in legal:
                g = game.clone()
                g.step_id(a)
                v = self._rollout_turn(g, seat)
                if best_v is None or v > best_v + 1e-9:
                    best, best_v = [a], v
                elif abs(v - best_v) <= 1e-9:
                    best.append(a)
            return self.rng.choice(best)
        return self.simple(game, seat)
