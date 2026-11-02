"""Observation for the deciding seat (design-rl, version 1): a float32 vector, every value clipped to [0, 1].

Index spaces: CIVIL = the 167 civil cards, MIL = the 125 military cards, PLAY = cards that can lie in a player's area
(civil cards, tactics, territories, pacts, wars: 212), CARD = all 292. STATIC = 55 printed features per card (kind,
age, costs, stages, urban limit, symbols, token value, tactic/bonus values), computed once.

global   age one-hot 5, round / 30, last round flag, last round distance, rounds left estimate / 25, seat offset to
         the starting player 4, decision kind one-hot 28; card row: per slot (13) occupied, take cost for the decider
         / 4, discarded at the next refill, the card's civil STATIC (45) = 624, row cards as CIVIL counts; deck sizes 3,
         current / future events counts per age 4 + 4, leaders/wonders still to come and the public Age A deck (CIVIL),
         common tactics (MIL), past events (MIL), Nobel's prize + Olympic Games owner 5, the open civil hand of
         another player with Ashoka (CIVIL) and its owner's offset 4, lead: own culture, culture rating, science rating
         and strength minus the best other player's (centred at 0.5) 4
decision 8 numbers (bid, force, strength needed, amount left, budget, legal count, decider is me, side A), the other
         player it concerns (offset 4), the card concerned (CARD one-hot) and its STATIC, and only for the decider a
         candidate vector (CARD: Kidnap's candidates, Development of Planning's shown cards)
own      civil hand (CIVIL counts), military hand (MIL counts), the events I prepared in either event deck (MIL), the
         events I know otherwise (MIL: Nostradamus' seen events, Joan of Arc's top event; position only for Joan),
         the military hand I looked at this turn (MIL, Ian Fleming)
players  decider first, then clockwise: cards in play (PLAY; unfinished wonder 0.5), workers per worker-holding card,
         blue tokens per token card, 63 numbers (banks, pool, food, resources, points, ratings, actions, hand sizes per
         age, army, colonies, pacts, wars, card states, production and consumption, corruption, population cost,
         happy faces required, workers, urban limit, whose turn)

Hidden (T16.1, PLAN 8): other players' civil and military hands (only counts per age) unless Ashoka opens a civil
hand (T16.2), deck orders, the current events deck and other players' prepared events (only counts per age) unless
known (Nostradamus, Joan of Arc), the Age A cards set aside, Ian Fleming's look for anyone but his owner.
"""
from __future__ import annotations

import numpy as np

from . import economy as E
from . import military as M
from .cards import (AGE, AGES, BONUS, CARDS, DECK_OF, EFFECT_TYPE, HOLDS_WORKERS, KIND, MILITARY_KINDS, N_CARDS,
                    TACTIC)
from .politics import known_by, peeked_by
from .state import LEADER_PROXY, WONDER_PROXY

CIVIL_CARDS = [c for c in range(N_CARDS) if DECK_OF[c] == "civil"]
C_INDEX = {c: i for i, c in enumerate(CIVIL_CARDS)}
N_CIVIL = len(CIVIL_CARDS)
MIL_CARDS = [c for c in range(N_CARDS) if KIND[c] in MILITARY_KINDS]
M_INDEX = {c: i for i, c in enumerate(MIL_CARDS)}
N_MIL = len(MIL_CARDS)
PLAY_CARDS = CIVIL_CARDS + [c for c in MIL_CARDS if KIND[c] in ("tactic", "territory", "pact", "war")]
P_INDEX = {c: i for i, c in enumerate(PLAY_CARDS)}
N_PLAY = len(PLAY_CARDS)
WORKER_CARDS = [c for c in range(N_CARDS) if HOLDS_WORKERS[c]]
W_INDEX = {c: i for i, c in enumerate(WORKER_CARDS)}
TOKEN_CARDS = [c for c in range(N_CARDS) if E.VALUE[c]]                    # farms, mines, Bill Gates' labs
T_INDEX = {c: i for i, c in enumerate(TOKEN_CARDS)}

CIVIL_KINDS = ("farm", "mine", "lab", "temple", "library", "theater", "arena", "infantry", "cavalry", "artillery",
               "air_force", "special_civil", "special_military", "special_colonization", "special_construction",
               "government", "leader", "wonder", "action")
YIELDS = (("food", 5), ("resources", 5), ("science", 5), ("culture", 4), ("happy", 4), ("unhappy", 1),
          ("strength", 13), ("civil_actions", 7), ("military_actions", 5), ("colonization", 4))


def _static() -> np.ndarray:
    """STATIC features per card id: the first N_STATIC_CIVIL describe civil cards fully (row slots use them)."""
    out = np.zeros((N_CARDS, N_STATIC), dtype=np.float32)
    for c in CARDS:
        v, i = out[c["id"]], 0
        if c["kind"] in CIVIL_KINDS:
            v[CIVIL_KINDS.index(c["kind"])] = 1
        i += len(CIVIL_KINDS)
        v[i + AGES.index(c["age"])] = 1
        i += 5
        for key, top in (("science_cost", 18), ("revolution_cost", 9), ("resource_cost", 11), ("urban_limit", 4)):
            v[i] = (c[key] or 0) / top
            i += 1
        stages = c["stage_costs"] or []
        v[i], v[i + 1] = len(stages) / 5, sum(stages) / 17
        i += 2
        y = c["yields"] or {}
        for key, top in YIELDS:
            v[i] = abs(y.get(key, 0)) / top
            i += 1
        v[i] = (y.get("blue_tokens", 0) + 4) / 8
        v[i + 1] = (y.get("yellow_tokens", 0) + 4) / 8
        v[i + 2] = 1.0 if c["effect"] else 0.0
        v[i + 3] = 1.0 if c["starting"] else 0.0
        i += 4
        assert i == N_STATIC_CIVIL
        if c["kind"] in MILITARY_KINDS:
            v[i + MILITARY_KINDS.index(c["kind"])] = 1
        i += len(MILITARY_KINDS)
        v[i] = (c["military_action_cost"] or 0) / 3
        v[i + 1] = ((TACTIC[c["id"]] or {}).get("strength") or 0) / 10
        b = BONUS[c["id"]] or {}
        v[i + 2] = (b.get("defense") or 0) / 6
        v[i + 3] = (b.get("colonization") or 0) / 3
    return out


N_STATIC_CIVIL = len(CIVIL_KINDS) + 5 + 4 + 2 + len(YIELDS) + 4
N_STATIC = N_STATIC_CIVIL + len(MILITARY_KINDS) + 4
STATIC = _static()
SLOT = 3 + N_STATIC_CIVIL
N_SCALARS = 63
N_CONTEXT = 8


def _clip(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


class StateEncoder:
    version = 1

    def __init__(self, num_players: int):
        from .engine import DECISION_KINDS
        self.n = num_players
        self.kinds = {k: i for i, k in enumerate(DECISION_KINDS)}
        self.global_size = (5 + 4 + 4 + len(DECISION_KINDS) + 13 * SLOT + N_CIVIL + 3 + 8 + N_CIVIL + 2 * N_MIL + 5
                            + N_CIVIL + 4 + 4)
        self.context_size = N_CONTEXT + 4 + N_CARDS + N_STATIC + N_CARDS
        self.own_size = N_CIVIL + 4 * N_MIL
        self.known_offset = self.global_size + self.context_size + N_CIVIL + 2 * N_MIL   # own: events I know
        self.player_size = N_PLAY + len(WORKER_CARDS) + len(TOKEN_CARDS) + N_SCALARS
        self.size = self.global_size + self.context_size + self.own_size + num_players * self.player_size

    def encode(self, g, seat: int) -> np.ndarray:
        from .agents import rounds_left
        from .engine import ROW_COST, ROW_DISCARD
        s = g.s
        n = self.n
        v = np.zeros(self.size, dtype=np.float32)
        d = s.decisions.top
        # ---- global
        i = 0
        v[i + AGES.index(s.age)] = 1
        i += 5
        v[i] = _clip(s.round / 30)
        v[i + 1] = 1.0 if s.last_round is not None else 0.0
        v[i + 2] = _clip((s.last_round - s.round) / 2) if s.last_round is not None else 0.0
        v[i + 3] = _clip(rounds_left(g) / 25)
        i += 4
        v[i + (s.start_seat - seat) % n] = 1
        i += 4
        if d is not None:
            v[i + self.kinds[d.kind]] = 1
        i += len(self.kinds)
        k_discard = ROW_DISCARD[max(2, len(g.active_seats()))]
        row_ids = i + 13 * SLOT
        for slot, c in enumerate(s.row):                                     # card row, slot by slot
            if c is not None:
                o = i + slot * SLOT
                v[o] = 1
                v[o + 1] = _clip(g.take_cost(seat, slot) / 4)
                v[o + 2] = 1.0 if slot < k_discard else 0.0
                v[o + 3:o + SLOT] = STATIC[c, :N_STATIC_CIVIL]
                v[row_ids + C_INDEX[c]] += 0.5
        i = row_ids + N_CIVIL
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
            v[i + C_INDEX[c]] = 1.0
        for age in AGES[AGES.index(s.age) + 1:4]:
            for c in s.selection[age]["leaders"] + s.selection[age]["wonders"]:
                v[i + C_INDEX[c]] = 1.0
        i += N_CIVIL
        for c in s.common_tactics:
            v[i + M_INDEX[c]] = 1.0
        i += N_MIL
        for c in s.past_events:
            v[i + M_INDEX[c]] += 0.5
        i += N_MIL
        v[i] = 1.0 if s.nobel_prize is not None else 0.0                     # Alfred Nobel's prize running
        if s.olympics is not None:                                           # Olympic Games: owner offset
            v[i + 1 + (s.olympics[0] - seat) % n] = 1.0
        i += 5
        for q in s.players:                                                  # T16.2: Ashoka opens the civil hand
            if q.seat != seat and q.leader is not None and EFFECT_TYPE[q.leader] == "ashoka":
                for c in q.civil_hand:
                    v[i + C_INDEX[c]] += 1 / 3
                v[i + N_CIVIL + (q.seat - seat) % n] = 1.0
        i += N_CIVIL + 4
        me, st = s.players[seat], E.stats(g, seat)
        others = [o for o in range(n) if o != seat]
        ost = [E.stats(g, o) for o in others]
        v[i] = _clip(0.5 + (me.culture - max(s.players[o].culture for o in others)) / 100)
        v[i + 1] = _clip(0.5 + (st.culture - max(x.culture for x in ost)) / 20)
        v[i + 2] = _clip(0.5 + (st.science - max(x.science for x in ost)) / 20)
        v[i + 3] = _clip(0.5 + (st.strength - max(x.strength for x in ost)) / 30)
        i += 4
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
            if other is not None and 0 <= other < n:
                v[i + N_CONTEXT + (other - seat) % n] = 1
            o = i + N_CONTEXT + 4
            for key in ("card", "frm", "source") + (("target",) if d.kind == "EVENT_CHOICE" else ()):
                c = data.get(key)
                if isinstance(c, int) and 0 <= c < N_CARDS:
                    v[o + c] = 1.0
                    v[o + N_CARDS:o + N_CARDS + N_STATIC] = np.maximum(v[o + N_CARDS:o + N_CARDS + N_STATIC], STATIC[c])
            if d.seat == seat:                                               # only the decider sees candidates
                o += N_CARDS + N_STATIC
                for c in data.get("candidates", ()) or data.get("shown", ()):
                    v[o + c] = 1.0
        i += self.context_size
        # ---- own private
        for c in me.civil_hand:
            v[i + C_INDEX[c]] += 1 / 3
        i += N_CIVIL
        for c in me.military_hand:
            v[i + M_INDEX[c]] += 1 / 3
        i += N_MIL
        known = i + N_MIL
        assert known == self.known_offset
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
                v[i + M_INDEX[c]] += 1 / 3
        i += N_MIL
        for k in range(n):
            self._player(g, (seat + k) % n, v, i)
            i += self.player_size
        np.clip(v, 0.0, 1.0, out=v)
        return v

    def _player(self, g, seat: int, v, i: int) -> None:
        s = g.s
        p = s.players[seat]
        st = E.stats(g, seat)
        for c in p.play_order:
            if c in P_INDEX:
                v[i + P_INDEX[c]] = 1.0
        if p.unfinished is not None:
            v[i + P_INDEX[p.unfinished[0]]] = 0.5
        for c in [p.tactic, p.pact[0] if p.pact is not None else None] + [c for c, _ in p.wars] + p.colonies:
            if c is not None:
                v[i + P_INDEX[c]] = 1.0
        i += N_PLAY
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
        pop_cost = E.pop_cost_for(g, seat)
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
        scalars += [E.output(g, seat, "farm") / 15, E.output(g, seat, "mine") / 15,
                    E.consumption(p.yellow_bank) / 6, E.corruption(p.blue_bank) / 6,
                    1.0 if pop_cost is None else pop_cost / 7, E.happy_required(p.yellow_bank) / 8,
                    (p.pool + sum(p.workers.values())) / 25, st.urban_limit / 6,
                    1.0 if s.turn_seat == seat else 0.0, 1.0 if p.flags.get("tactic_done") else 0.0,
                    len(p.ruined) / 3, st.food_bonus / 5 + 0.5]
        assert len(scalars) == N_SCALARS, len(scalars)
        for j, x in enumerate(scalars):
            v[i + j] = _clip(x)
