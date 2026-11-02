"""First simple observation (build-engine; design-rl improves it). For the deciding seat, values in [0, 1]:

global   age, round, last-round info, seat offset to the starting player, decision kind, card row (per cost group a
         card-count vector), occupied slots, deck sizes, event-deck counts per age, leaders/wonders still to come and
         the public Age A deck (T15.8, T15.9)
own      civil and military hand (counts per card id), the cards the pending decision is about
players  (decider first, then clockwise) cards in play, workers, tokens, banks, points, ratings, actions, hand
         sizes per age (T16.1: other players' hands are hidden; only counts per age are public)
"""
from __future__ import annotations

import numpy as np

from . import economy as E
from .cards import AGE, AGES, HOLDS_WORKERS, KIND, N_CARDS
from .state import LEADER_PROXY, WONDER_PROXY

WORKER_CARDS = [c for c in range(N_CARDS) if HOLDS_WORKERS[c]]
W_INDEX = {c: i for i, c in enumerate(WORKER_CARDS)}
TOKEN_CARDS = [c for c in range(N_CARDS) if KIND[c] in ("farm", "mine")]
T_INDEX = {c: i for i, c in enumerate(TOKEN_CARDS)}
N_SCALARS = 31


def _clip(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


class StateEncoder:
    version = 1

    def __init__(self, num_players: int):
        from .engine import DECISION_KINDS
        self.n = num_players
        self.kinds = {k: i for i, k in enumerate(DECISION_KINDS)}
        self.global_size = 5 + 1 + 2 + 4 + len(DECISION_KINDS) + 3 * N_CARDS + 13 + 3 + 4 + 4 + N_CARDS
        self.own_size = 3 * N_CARDS
        self.player_size = N_CARDS + len(WORKER_CARDS) + len(TOKEN_CARDS) + N_SCALARS
        self.size = self.global_size + self.own_size + num_players * self.player_size

    def encode(self, g, seat: int) -> np.ndarray:
        from .engine import ROW_COST
        s = g.s
        v = np.zeros(self.size, dtype=np.float32)
        i = 0
        v[i + AGES.index(s.age)] = 1
        i += 5
        v[i] = _clip(s.round / 40)
        v[i + 1] = 1.0 if s.last_round is not None else 0.0
        v[i + 2] = _clip((s.last_round - s.round) / 2) if s.last_round is not None else 0.0
        i += 3
        v[i + (s.start_seat - seat) % self.n] = 1
        i += 4
        d = s.decisions.top
        if d is not None:
            v[i + self.kinds[d.kind]] = 1
        i += len(self.kinds)
        for slot, c in enumerate(s.row):                                     # card row by cost group
            if c is not None:
                v[i + (ROW_COST[slot] - 1) * N_CARDS + c] += 0.5
                v[i + 3 * N_CARDS + slot] = 1
        i += 3 * N_CARDS + 13
        v[i] = _clip(len(s.civil_deck) / 60)
        v[i + 1] = _clip(len(s.military_deck) / 60)
        v[i + 2] = _clip(len(s.military_discard) / 30)
        i += 3
        for c, _ in s.current_events:                                       # counts per age only (T16.1)
            v[i + AGES.index(AGE[c])] += 1 / 6
        i += 4
        for c, _ in s.future_events:
            v[i + AGES.index(AGE[c])] += 1 / 6
        i += 4
        for c in s.civil_deck:                                               # still to come (public mix)
            if c >= WONDER_PROXY:
                c = s.selection[s.age]["wonders"][c - WONDER_PROXY]
            elif c >= LEADER_PROXY:
                c = s.selection[s.age]["leaders"][c - LEADER_PROXY]
            elif s.age != "A":
                continue
            v[i + c] = 1.0
        later = AGES[AGES.index(s.age) + 1:4]
        for age in later:
            for c in s.selection[age]["leaders"] + s.selection[age]["wonders"]:
                v[i + c] = 1.0
        i += N_CARDS
        me = s.players[seat]
        for c in me.civil_hand:
            v[i + c] += 1 / 3
        i += N_CARDS
        for c in me.military_hand:
            v[i + c] += 1 / 3
        i += N_CARDS
        if d is not None:
            for key in ("card", "frm", "source"):
                c = d.data.get(key)
                if c is not None:
                    v[i + c] = 1.0
        i += N_CARDS
        for k in range(self.n):
            self._player(g, (seat + k) % self.n, v, i)
            i += self.player_size
        np.clip(v, 0.0, 1.0, out=v)
        return v

    def _player(self, g, seat: int, v, i: int) -> None:
        p = g.s.players[seat]
        st = E.stats(g, seat)
        for c in p.play_order:
            v[i + c] = 1.0
        if p.unfinished is not None:
            v[i + p.unfinished[0]] = 0.5
        i += N_CARDS
        for c, k in p.workers.items():
            v[i + W_INDEX[c]] = _clip(k / 6)
        i += len(WORKER_CARDS)
        for c, k in p.tokens.items():
            v[i + T_INDEX[c]] = _clip(k / 10)
        i += len(TOKEN_CARDS)
        hand_ages = [0] * 8
        for c in p.civil_hand:
            hand_ages[AGES.index(AGE[c])] += 1
        for c in p.military_hand:
            hand_ages[4 + AGES.index(AGE[c])] += 1
        unf = p.unfinished
        scalars = [p.blue_bank / 18, p.yellow_bank / 24, p.pool / 10, E.food(p) / 30, E.resources(p) / 30,
                   p.science / 60, p.culture / 250, st.culture / 30, st.science / 30, st.happiness / 8,
                   E.discontent(g, seat) / 8, st.strength / 60, st.civil / 10, E.civil_available(g, seat) / 10,
                   st.military / 10, E.military_available(g, seat) / 10, len(p.civil_hand) / 10,
                   len(p.military_hand) / 10, (unf[1] / 5) if unf else 0.0, len(p.wonders) / 6,
                   1.0 if p.resigned_order is not None else 0.0, st.resource_bonus / 5 + 0.5]
        scalars += [x / 6 for x in hand_ages]
        scalars.append(len(p.leaders_taken) / 4)
        for j, x in enumerate(scalars):
            v[i + j] = _clip(x)
