"""Observation vector for Wingspan (version 1), from the deciding player's view. Values are clipped to [0, 1].

Layout (sizes for P players):
  global    round one-hot 4, own turns left / 8, game progress, goals of rounds 1-4 (one-hot 16 each), feeder face
            counts / 5 (6), dice outside / 5, tray birds (count per bird id, 180), deck / 180, discard / 180,
            bonus deck / 26                                                               = 260
  decision  kind one-hot (31), context bird one-hot (180), amount left / 5, foods allowed (5), food needed (5),
            pink flag, purpose flag                                                         = 224
  self      hand (count per bird id, 180), hand size / 20, bonus cards held (26), food / 10 (5), discards owed,
            15 mat slots x 58 features, held bonus cards' progress (count / 10, points / 10 per card: 52),
            goal counts of rounds 1-4 / 10, score breakdown / 50 (6)                         = 1145
  others    per other player (clockwise): food / 10 (5), hand size / 20, birds per row / 5 (3), eggs per row / 15
            (3), cache / 10, tucked / 10, goal counts / 10 (4), score breakdown / 50 (6), pink powers by kind (4),
            score / 100                                                                     = 29 each
  lead      0.5 + (own score - best other) / 100
Hidden information stays hidden: other players' hands and bonus cards are not encoded (only their sizes), their
bonus-card points are left out of their scores, and while players still choose their starting hands nobody sees
another player's hand size, food or the discard pile (W2.4: the choices are secret).
"""
from __future__ import annotations

import numpy as np

from bgai.kit import add_counts, one_hot

from .cards import COLORS, FOODS, NESTS, bonus_cards, birds, goal_ids, power_kinds

N_BIRDS = 180
SLOT = 58
PINKS = ("pink_play", "pink_lay_eggs", "pink_gain_food_rodent", "pink_predator")


def _slot_static():
    """Per bird: the 51 static slot features (everything but occupied/eggs/cache/tucked)."""
    kinds = power_kinds()
    out = np.zeros((N_BIRDS, SLOT - 4), dtype=np.float32)
    for b in birds():
        v = out[b.id]
        v[0] = b.points / 9
        v[1] = b.egg_limit / 6
        v[2 + NESTS.index(b.nest)] = 1
        v[8 + COLORS.index(b.color)] = 1
        v[12 + kinds.index(b.power["type"] if b.power else "none")] = 1
        v[42] = b.predator
        v[43] = b.flocking
        v[44] = min(b.wingspan, 250) / 250
        for i in range(5):
            v[45 + i] = b.food[i] / 3
        v[50] = b.wild / 2
        for h in b.habitats:
            v[51 + h] = 1
    return out


class StateEncoder:
    version = 1

    def __init__(self, num_players: int):
        from .engine import DECISION_KINDS
        self.n = num_players
        self.kinds = {k: i for i, k in enumerate(DECISION_KINDS)}
        self.goal_index = {g: i for i, g in enumerate(goal_ids())}
        self.static = _slot_static()
        self.size = 260 + 224 + 1145 + 29 * (num_players - 1) + 1

    def encode(self, g, seat: int) -> np.ndarray:
        from .scoring import bonus_count, bonus_points, goal_count
        s = g.s
        v = np.zeros(self.size, dtype=np.float32)
        me = g.p(seat)
        # ---- global
        one_hot(v, 0, s.round)
        from .engine import TURNS
        taken = s.round_turns // self.n + (1 if (seat - s.first) % self.n < s.round_turns % self.n else 0)
        v[4] = (TURNS[s.round] - taken) / 8
        v[5] = s.turns / (26 * self.n)
        for r, goal in enumerate(s.goals):
            one_hot(v, 6 + 16 * r, self.goal_index[goal["id"]])
        add_counts(v, 70, s.feeder, 0.2)
        v[76] = len(s.outside) / 5
        add_counts(v, 77, (c for c in s.tray if c is not None), 1.0)
        v[257] = len(s.deck) / 180
        v[258] = len(s.discard) / 180 if s.setup_done else 0.0
        v[259] = len(s.bonus_deck) / 26
        i = 260
        # ---- decision
        d = s.decisions.top
        if d is not None:
            one_hot(v, i, self.kinds[d.kind])
            b = d.data.get("bird")
            if b is not None:
                one_hot(v, i + 31, b)
            v[i + 211] = d.data.get("left", 0) / 5
            for f in d.data.get("foods") or []:
                v[i + 212 + f] = 1
            for f in d.data.get("need") or []:
                v[i + 217 + f] = 1
            v[i + 222] = 1.0 if d.data.get("pink") else 0.0
            v[i + 223] = 1.0 if d.data.get("purpose") == "action" else 0.0
        i += 224
        # ---- self
        add_counts(v, i, me.hand, 0.5)
        i += N_BIRDS
        v[i] = len(me.hand) / 20
        i += 1
        for c in me.bonus:
            v[i + c] = 1
        i += 26
        for f in range(5):
            v[i + f] = me.food[f] / 10
        i += 5
        v[i] = me.end_discards / 2
        i += 1
        for h in range(3):
            for c in range(5):
                j = i + (h * 5 + c) * SLOT
                if c < len(me.rows[h]):
                    p = me.rows[h][c]
                    v[j] = 1
                    v[j + 1] = p.eggs / 6
                    v[j + 2] = sum(p.cache) / 6
                    v[j + 3] = p.tucked / 10
                    v[j + 4:j + SLOT] = self.static[p.bird]
        i += 15 * SLOT
        cards = bonus_cards()
        for c in me.bonus:
            n = bonus_count(g, seat, cards[c])
            v[i + 2 * c] = n / 10
            v[i + 2 * c + 1] = bonus_points(cards[c], n) / 10
        i += 52
        for r, goal in enumerate(s.goals):
            v[i + r] = goal_count(g, seat, goal) / 10
        i += 4
        bds = g.breakdowns()
        for x in range(self.n):
            if x != seat:
                bds[x] = dict(bds[x], bonus=0)              # other players' bonus cards are secret
        for k, x in enumerate(bds[seat].values()):
            v[i + k] = x / 50
        i += 6
        # ---- others
        for k in range(1, self.n):
            o = (seat + k) % self.n
            op = g.p(o)
            if s.setup_done:
                for f in range(5):
                    v[i + f] = op.food[f] / 10
                v[i + 5] = len(op.hand) / 20
            for h in range(3):
                v[i + 6 + h] = len(op.rows[h]) / 5
                v[i + 9 + h] = sum(p.eggs for p in op.rows[h]) / 15
            v[i + 12] = sum(sum(p.cache) for _, _, p in op.placed()) / 10
            v[i + 13] = sum(p.tucked for _, _, p in op.placed()) / 10
            for r, goal in enumerate(s.goals):
                v[i + 14 + r] = goal_count(g, o, goal) / 10
            for kk, x in enumerate(bds[o].values()):
                v[i + 18 + kk] = x / 50
            for _, _, p in op.placed():
                pw = g.bird(p.bird).power
                if pw and pw["type"] in PINKS:
                    v[i + 24 + PINKS.index(pw["type"])] += 0.5
            v[i + 28] = sum(bds[o].values()) / 100
            i += 29
        scores = [sum(b.values()) - (b["bonus"] if j == seat else 0) for j, b in enumerate(bds)]   # like with like
        v[i] = 0.5 + (scores[seat] - max(sc for j, sc in enumerate(scores) if j != seat)) / 100
        return np.clip(v, 0.0, 1.0, out=v)
