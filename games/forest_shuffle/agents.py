"""Forest Shuffle greedy baseline: one-step lookahead on score margin; discards cheap cards when paying.

Same decisions as the original forest_shuffle GreedyAgent (same random tie-breaking), returning action numbers.
"""
from __future__ import annotations

import random
from typing import Optional

from bgai.agents import Agent

from .core.actions import ActionKind
from .engine.scoring import score_player


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _card_value(self, game, def_id: int) -> int:
        d = game.db.defs[def_id]
        if d.layout == "WOODY_PLANT":
            return game.db.species[d.species].cost + 1
        return max(game.db.species[h.species].cost for h in d.halves)

    def _cheapest(self, game, acts):
        low = min(self._card_value(game, a.card) for a in acts)
        return self.rng.choice([a for a in acts if self._card_value(game, a.card) == low])

    def _margin(self, game, seat: int) -> float:
        scores = [score_player(game.db, game.state.players, i) for i in range(game.num_players)]
        return scores[seat] - max(sc for i, sc in enumerate(scores) if i != seat)

    def _resolve(self, g):
        """Finish payment and target choices in a lookahead clone (cheapest card, first target)."""
        while g.state.decisions and g.state.decisions[-1].kind in ("PAY", "CHOOSE_TARGET"):
            acts = g.legal_actions()
            g.step(self._cheapest(g, acts) if acts[0].kind == ActionKind.PAY else acts[0])

    def choose(self, game, seat: int):
        acts = game.legal_actions()
        if len(acts) == 1:
            return acts[0]
        if all(a.kind in (ActionKind.PAY, ActionKind.CHOOSE_CARD) for a in acts):
            return self._cheapest(game, acts)
        sap = [a for a in acts if a.kind == ActionKind.PLAY_SAPLING]     # evaluate only the cheapest sapling
        cand = [a for a in acts if a.kind != ActionKind.PLAY_SAPLING]
        if sap:
            cand.append(self._cheapest(game, sap))
        best, best_val = [], None
        for a in cand:
            g = game.clone()
            g.step(a)
            self._resolve(g)
            val = self._margin(g, seat) + 0.05 * len(g.state.players[seat].hand)
            if a.kind == ActionKind.PLAY_SAPLING:
                val -= 0.5
            if best_val is None or val > best_val + 1e-9:
                best, best_val = [a], val
            elif abs(val - best_val) <= 1e-9:
                best.append(a)
        return self.rng.choice(best)

    def act(self, game, seat: int) -> int:
        return game.codec.encode(self.choose(game, seat))
