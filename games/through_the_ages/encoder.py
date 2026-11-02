"""First simple observation (build-engine; design-rl improves it). For the deciding seat, values in [0, 1]:

global   age, round, last-round info, seat offset to the starting player, decision kind, card row (per cost group a
         card-count vector), occupied slots, deck sizes, event-deck counts per age, leaders/wonders still to come and
         the public Age A deck (T15.8, T15.9), common tactics, past events
decision the cards the pending decision is about, its numbers (bid, force, strength needed, budget, advantage left),
         the other player it concerns (seat offset) and, only for the decider, a candidate vector (Kidnap's
         candidates from the rival's hand, Development of Planning's 3 shown cards)
own      civil and military hand (counts per card id), the events I prepared that wait in either event deck, the
         events I know otherwise (Nostradamus: others' prepared events; Joan of Arc: the top current event) and the
         military hand I looked at this turn (Ian Fleming)
players  (decider first, then clockwise) cards in play (incl. tactic, colonies, pact, wars), workers, tokens, banks,
         points, ratings, actions, armies, pact side and partner, war targets, hand sizes per age, the civil hand of a
         player with Ashoka in play (T16.2: open hand), civil card states (Hippocrates' reminders, Louvre tokens,
         Saladin's mode, Sun Tzu's tactics, Homer's tuck, once-per-game abilities used)

Hidden (T16.1, PLAN 8): other players' civil and military hands (only counts per age), deck orders, the current
events deck and other players' prepared events (only counts per age), the Age A cards set aside.
"""
from __future__ import annotations

import numpy as np

from . import economy as E
from . import military as M
from .cards import AGE, AGES, EFFECT_TYPE, HOLDS_WORKERS, KIND, MILITARY_KINDS, N_CARDS
from .politics import known_by, peeked_by
from .state import LEADER_PROXY, WONDER_PROXY

WORKER_CARDS = [c for c in range(N_CARDS) if HOLDS_WORKERS[c]]
W_INDEX = {c: i for i, c in enumerate(WORKER_CARDS)}
TOKEN_CARDS = [c for c in range(N_CARDS) if E.VALUE[c]]                    # farms, mines, Bill Gates' labs
T_INDEX = {c: i for i, c in enumerate(TOKEN_CARDS)}
MIL_CARDS = [c for c in range(N_CARDS) if KIND[c] in MILITARY_KINDS]
M_INDEX = {c: i for i, c in enumerate(MIL_CARDS)}
N_MIL = len(MIL_CARDS)
N_SCALARS = 51
N_CONTEXT = 8


def _clip(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


class StateEncoder:
    version = 2

    def __init__(self, num_players: int):
        from .engine import DECISION_KINDS
        self.n = num_players
        self.kinds = {k: i for i, k in enumerate(DECISION_KINDS)}
        self.global_size = 5 + 1 + 2 + 4 + len(DECISION_KINDS) + 3 * N_CARDS + 13 + 3 + 4 + 4 + N_CARDS + 2 * N_MIL + 5
        self.context_size = N_CONTEXT + 4 + N_CARDS
        self.own_size = 4 * N_CARDS + 2 * N_MIL
        self.player_size = 2 * N_CARDS + len(WORKER_CARDS) + len(TOKEN_CARDS) + N_SCALARS
        self.size = self.global_size + self.context_size + self.own_size + num_players * self.player_size

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
        for e in s.current_events:                                          # counts per age only (T16.1)
            v[i + AGES.index(AGE[e[0]])] += 1 / 6
        i += 4
        for e in s.future_events:
            v[i + AGES.index(AGE[e[0]])] += 1 / 6
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
        for c in s.common_tactics:
            v[i + M_INDEX[c]] = 1.0
        i += N_MIL
        for c in s.past_events:
            v[i + M_INDEX[c]] += 0.5
        i += N_MIL
        v[i] = 1.0 if s.nobel_prize is not None else 0.0                     # Alfred Nobel's prize running
        if s.olympics is not None:                                           # Olympic Games: owner offset
            v[i + 1 + (s.olympics[0] - seat) % self.n] = 1.0
        i += 5
        # ---- decision context
        if d is not None:
            data = d.data
            nums = [data.get("bid", 0) / 40, data.get("force", 0) / 40, data.get("need", 0) / 30,
                    data.get("left", 0) / 20, data.get("budget", 0) / 5, len(data.get("legal", ())) / 30,
                    1.0 if d.seat == seat else 0.0, 1.0 if data.get("side") == "A" else 0.0]
            for j, x in enumerate(nums):
                v[i + j] = _clip(x)
            other = next((data[k] for k in ("victim", "attacker", "offerer") if isinstance(data.get(k), int)), None)
            if other is None and d.kind == "PACT_SIDE":
                other = data["target"]
            if other is not None and 0 <= other < self.n:
                v[i + N_CONTEXT + (other - seat) % self.n] = 1
            if d.seat == seat:                                               # only the decider sees candidates
                for c in data.get("candidates", ()) or data.get("shown", ()):
                    v[i + N_CONTEXT + 4 + c] = 1.0
        i += self.context_size
        # ---- own private
        me = s.players[seat]
        for c in me.civil_hand:
            v[i + c] += 1 / 3
        i += N_CARDS
        for c in me.military_hand:
            v[i + c] += 1 / 3
        i += N_CARDS
        if d is not None:
            for key in ("card", "frm", "source") + (("target",) if d.kind == "EVENT_CHOICE" else ()):
                c = d.data.get(key)
                if isinstance(c, int):
                    v[i + c] = 1.0
        i += N_CARDS
        known = i + N_MIL
        for e in s.current_events + s.future_events:                        # my prepared events (I know them)
            if e[1] == seat:
                v[i + M_INDEX[e[0]]] += 0.5
            elif seat in known_by(e):                                        # Nostradamus, Joan of Arc
                v[known + M_INDEX[e[0]]] += 0.5
        if s.current_events and seat in peeked_by(s.current_events[0]):      # only Joan's look tells the position:
            v[known + M_INDEX[s.current_events[0][0]]] = 1.0                # the top card (Nostradamus' cards do not)
        i += 2 * N_MIL
        if me.peek is not None:                                              # Ian Fleming's look this turn
            for c in me.peek[1]:
                v[i + c] += 1 / 3
        i += N_CARDS
        for k in range(self.n):
            self._player(g, (seat + k) % self.n, seat, v, i)
            i += self.player_size
        np.clip(v, 0.0, 1.0, out=v)
        return v

    def _player(self, g, seat: int, viewer: int, v, i: int) -> None:
        p = g.s.players[seat]
        st = E.stats(g, seat)
        for c in p.play_order:
            v[i + c] = 1.0
        if p.unfinished is not None:
            v[i + p.unfinished[0]] = 0.5
        if p.tactic is not None:
            v[i + p.tactic] = 1.0
        if p.pact is not None:
            v[i + p.pact[0]] = 1.0
        for c, _ in p.wars:
            v[i + c] = 1.0
        i += N_CARDS
        if seat == viewer or (p.leader is not None and EFFECT_TYPE[p.leader] == "ashoka"):
            for c in p.civil_hand:                                           # T16.2: Ashoka's hand is open
                v[i + c] += 1 / 3
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
        n = self.n
        pact_partner = [0.0] * 3
        pact_side = 0.0
        for owner, card, partner, side in M.pacts_in_play(g):
            sd = M.side_of(owner, partner, side, seat)
            if sd is not False:
                other = partner if seat == owner else owner
                pact_partner[(other - seat - 1) % n] = 1.0
                pact_side = 1.0 if sd == "A" else 0.5 if sd == "B" else 0.25
        war_on = [0.0] * 3
        for _, t in p.wars:
            war_on[(t - seat - 1) % n] = 1.0
        scalars = [p.blue_bank / 18, p.yellow_bank / 24, p.pool / 10, E.food(p) / 30, E.resources(p) / 30,
                   p.science / 60, p.culture / 250, st.culture / 30, st.science / 30, st.happiness / 8,
                   E.discontent(g, seat) / 8, st.strength / 60, st.civil / 10, E.civil_available(g, seat) / 10,
                   st.military / 10, E.military_available(g, seat) / 10, len(p.civil_hand) / 10,
                   len(p.military_hand) / 10, (unf[1] / 5) if unf else 0.0, len(p.wonders) / 6,
                   1.0 if p.resigned_order is not None else 0.0, st.resource_bonus / 5 + 0.5]
        scalars += [x / 6 for x in hand_ages]
        scalars.append(len(p.leaders_taken) / 4)
        scalars += [st.army / 40, st.colonization / 10 + 0.3, len(p.colonies) / 6,
                    1.0 if p.exclusive_tactic is not None else 0.0, pact_side, len(M.wars_on(g, seat)) / 3,
                    1.0 if p.forfeit_politics else 0.0]
        scalars += war_on + pact_partner
        scalars += [p.reminders / 3, p.louvre_tokens / 3, 1.0 if p.saladin == 0 else 0.0,
                    1.0 if p.saladin == 1 else 0.0, 1.0 if p.tactic_boost is not None else 0.0,
                    len(p.kept_tactics) / 3, len(p.used) / 2 + (0.5 if p.homer_wonder is not None else 0.0)]
        for j, x in enumerate(scalars):
            v[i + j] = _clip(x)
