"""Greedy baseline (design-rl): a sanity check and an early training opponent, not a strong player.

Big choices (every decision of the player whose turn it is, and reactions such as defending or answering a pact) are
judged by playing the turn out in a `clone()`: the answer, then its completion steps (which building, which card,
which target ... chosen by the best value, depth-limited), then the rest of the turn with simple rules (end the action
phase, pass, discard the least useful military card) through the end of the turn: production, famine, uprising and
the military draw are in the result. The value compared is own position value minus the best other player's.

Position value (culture points): culture + culture rating x rounds left, science rating and points, net food and
resource production, the famine expected in the next rounds (4 culture per missing food), population, stock of
food/resources (worthless in the last rounds), civil and military action totals, urban limit, strength (and a penalty
for trailing the strongest player, who invites aggressions and weakest-player events), cards in hand (a technology by
what developing it would add and how near its science cost is; others' hands by their public sizes only), what
developed technologies can still add, leader, wonders (an unfinished one by stages paid), colonies; discontent beyond
the unused workers (uprising) costs 8.

Information: the look-ahead runs on a copy whose hidden order is reshuffled first (civil and military decks, the
current events deck, the copy's random source), so the next current event and the end-of-turn military draw are
guesses, not knowledge. Other players' hands never enter the value. Defending is judged by a public bound: an aggression is played only when
the attacker's margin beats what the rival could add with its military hand size and military actions.
It never resigns (a resigned position is worth -1000). Ties at random (seeded).
"""
from __future__ import annotations

import random

from bgai.agents import Agent

from . import economy as E
from .cards import (BONUS, IS_STARTING, IS_TECH, KIND, LEVEL, S_CIVIL, S_COLON, S_CULT, S_FOODB, S_HAPPY,
                    S_MIL, S_RESB, S_SCI, S_STR, S_UNHAPPY, SCIENCE_COST, STAGE_COSTS, STAT_YIELDS, TOKEN_VALUE,
                    URBAN, URBAN_LIMIT, civil_deck_cards)

CARDS_PER_ROUND = 7.0                     # civil cards leaving the deck per round (measured in greedy games)
DEFENSE_PER_CARD = {"A": 1, "I": 2, "II": 3, "III": 4, "IV": 4}
FAIL = -1e6                               # an aggression the rival can probably repel
NESTED = ("CHOOSE_TECH", "UPGRADE_TO", "STAGES", "REVOLT", "SUB_ACTION", "POLITICS_CARD", "TARGET", "PACT_SIDE",
          "ABILITY", "CHOOSE_TACTIC", "MIX", "ANNEX", "INFILTRATE", "KIDNAP", "STEAL_TECH", "CANCEL_WHICH", "SEND",
          "DEFEND", "LOSE_WORKER", "LOSE_BLUE", "EVENT_CHOICE", "TERRORISM", "TAKE_LOOP")
MAX_BIDS = 3                              # bids judged: the lowest few (BID offers up to 128)
_AGE_SIZE: dict = {}


def _age_size(age: str, n: int) -> int:
    key = (age, n)
    if key not in _AGE_SIZE:
        _AGE_SIZE[key] = len(civil_deck_cards(age, n)) + (10 if n == 2 else 12)
    return _AGE_SIZE[key]


def rounds_left(g) -> float:
    """Production phases still to come for a player after the current one (estimate from the civil decks)."""
    s = g.s
    if s.last_round is not None:
        return max(0, s.last_round - s.round)
    later = {"A": ("I", "II", "III"), "I": ("II", "III"), "II": ("III",), "III": ()}.get(s.age, ())
    return (len(s.civil_deck) + sum(_age_size(a, g.num_players) for a in later)) / CARDS_PER_ROUND + 1


def _yield_value(c: int, r: float) -> float:
    """Value of one copy of a card's printed symbols for the rest of the game (one worker on it)."""
    h = min(r, 14)
    w = {S_CIVIL: 1.2 * h, S_MIL: 0.4 * h, S_CULT: r, S_SCI: 0.7 * h, S_HAPPY: 1.5, S_UNHAPPY: -1.5, S_STR: 0.3,
         S_COLON: 0.3, S_RESB: 0.8 * min(r, 8), S_FOODB: 0.6 * min(r, 8)}
    return sum(w[k] * x for k, x in STAT_YIELDS[c])


def _tech_gain(p, c: int, r: float) -> float:
    """What a technology could still add (beyond what its workers already produce): moving workers up from lower
    technologies of its kind, a first building of a new kind, a better government or special technology."""
    k = KIND[c]
    if k == "government":
        cur = p.government
        if cur == c:
            return 0.0
        return _yield_value(c, r) - _yield_value(cur, r) + 1.0 * ((URBAN_LIMIT[c] or 0) - (URBAN_LIMIT[cur] or 0))
    if k.startswith("special"):
        cur = p.specials.get(k)
        if cur == c:
            return 0.0
        return _yield_value(c, r) - (_yield_value(cur, r) if cur is not None else 0.0) + 2.0 + 1.5 * LEVEL[c]
    others = [t for t in p.techs if KIND[t] == k and t != c]
    if k in ("farm", "mine"):
        per = (0.6 if k == "farm" else 0.8) * min(r, 8)
        diff = lambda t: (TOKEN_VALUE[c] - TOKEN_VALUE[t]) * per
    elif k in URBAN:
        diff = lambda t: _yield_value(c, r) - _yield_value(t, r)
    else:                                                     # military units: strength
        diff = lambda t: (LEVEL[c] - LEVEL[t]) * 1.2
    gain, left = 0.0, 4
    for t in sorted(others, key=lambda t: LEVEL[t]):
        if LEVEL[t] < LEVEL[c] and left:
            w = min(p.workers.get(t, 0), left)
            gain += max(0.0, diff(t)) * w
            left -= w
    if not others:                                            # a new kind: its first building
        gain += _yield_value(c, r) if k in URBAN else (2.0 if k not in ("farm", "mine") else 0.0)
    return min(gain, 40.0)


HAND_SHARE, PLAY_SHARE = 0.45, 0.75          # share of a technology's possible gain counted in hand / in play


def _hand_tech_value(p, st, c: int, r: float) -> float:
    """A technology in hand: what developing it (and using it) would add, weighted by how near its cost is."""
    if c in p.techs or c == p.government or c in p.specials.values():
        return 0.1
    cost = SCIENCE_COST[c] or 1
    reach = min(1.0, (p.science + 2 * st.science) / cost)
    return 0.3 + HAND_SHARE * reach * max(0.0, _tech_gain(p, c, r))


def _military_card_value(c: int) -> float:
    k = KIND[c]
    if k == "tactic":
        return 3.0 + LEVEL[c]
    if k == "bonus":
        return 0.5 + 0.5 * BONUS[c]["defense"]
    if k == "event":
        return 1.0 + 0.5 * LEVEL[c]
    if k == "territory":
        return 1.0
    return 0.8


def value(g, seat: int, viewer: int, r: float) -> float:
    """Position value of `seat` as `viewer` may judge it (other players' hands only by their sizes)."""
    s = g.s
    p = s.players[seat]
    if p.resigned_order is not None:
        return -1000.0
    st = E.stats(g, seat)
    h = min(r, 14)
    late = min(1.0, r / 3)
    net_food = E.output(g, seat, "farm") - E.consumption(p.yellow_bank)
    net_res = E.output(g, seat, "mine") - E.corruption(p.blue_bank)
    v = p.culture + st.culture * r + 0.9 * st.science * min(r, 12) + 0.15 * p.science * late
    v += min(r, 8) * (0.6 * net_food + 0.8 * net_res)
    food, res = E.food(p), E.resources(p)
    if net_food < 0:                                          # famine: 4 culture per missing food (T12.7)
        stock = food
        for _ in range(int(min(r, 6))):
            stock += net_food
            if stock < 0:
                v += 4.0 * stock
                stock = 0
    v += late * (0.35 * min(food, 15) + 0.1 * max(0, food - 15) + 0.45 * min(res, 25) + 0.15 * max(0, res - 25))
    workers = p.pool + sum(p.workers.values())                # population: a worker on a card or unused
    v += late * (workers * (1.5 + 0.1 * min(r, 10)) + 0.2 * p.pool)
    v += h * (1.2 * st.civil + 0.4 * st.military) + late * 0.8 * st.urban_limit
    disc = E.discontent(g, seat)
    v -= 1.0 * disc + (8.0 if disc > p.pool else 0.0)
    strongest = max(E.stats(g, o).strength for o in range(g.num_players) if o != seat)
    v += 0.3 * min(st.strength, 80) - 0.8 * min(15, max(0, strongest - st.strength)) * late
    if seat == viewer:
        hand = 0.0
        for c in p.civil_hand:
            if IS_TECH[c]:
                hand += _hand_tech_value(p, st, c, r)
            else:
                hand += (3.0 + LEVEL[c]) if KIND[c] == "leader" else (1.5 + 0.5 * LEVEL[c])
        hand += sum(0.4 * _military_card_value(c) for c in p.military_hand)
        v += hand * late
    else:
        v += late * (1.5 * len(p.civil_hand) + 0.6 * len(p.military_hand))
    for c in p.techs:
        if not IS_STARTING[c]:
            v += PLAY_SHARE * _tech_gain(p, c, r) * late
    v += sum(2.0 + 1.5 * LEVEL[c] for c in p.specials.values()) * late
    if p.leader is not None:
        v += 3.0 * late
    if p.unfinished is not None:
        w, paid = p.unfinished[0], p.unfinished[1]
        total = max(1, len(STAGE_COSTS[w]))
        v += (_yield_value(w, r) + 3.0) * (0.2 + 0.6 * paid / total) * late + 1.0 * paid
    v += 3.0 * len(p.wonders) + 2.0 * len(p.colonies)
    return v


def relative(g, seat: int, r: float) -> float:
    own = value(g, seat, seat, r)
    return own - max(value(g, o, seat, r) for o in range(g.num_players) if o != seat)


def defense_bound(g, rival: int) -> int:
    """A rough public bound on what the rival could add in defense: cards it may play x a typical bonus value."""
    p = g.s.players[rival]
    k = min(len(p.military_hand), E.stats(g, rival).military)
    return k * DEFENSE_PER_CARD[g.s.age]


class GreedyAgent(Agent):
    name = "greedy"

    def __init__(self, seed=None, depth: int = 2):
        self.rng = random.Random(seed)
        self.depth = depth

    # ---- simple rules (rest of the turn in the copy, other players' answers there)
    @staticmethod
    def simple(g, viewer: int) -> int:
        from .engine import A_END, A_NO, A_CARD
        d = g.s.decisions.top
        legal = d.data["legal"]
        k = d.kind
        if k in ("ACTION", "POLITICS"):
            return A_END if A_END in legal else legal[0]
        if k == "DISCARD_MILITARY":
            return min(legal, key=lambda a: (_military_card_value(a - A_CARD), a))
        if k == "DEFEND":
            if d.data.get("attacker") == viewer and d.seat != viewer:
                return A_NO if d.data["need"] > defense_bound(g, d.seat) and A_NO in legal else FAIL
            cards = [a for a in legal if a != A_NO]
            return max(cards, key=lambda a: (BONUS[a - A_CARD]["defense"] if KIND[a - A_CARD] == "bonus" else 1, -a))
        if k in ("BID", "PACT_ANSWER") and A_NO in legal:
            return A_NO
        if k == "SEND":
            return legal[0] if len(legal) == 1 else (A_NO if A_NO in legal else min(legal))
        return legal[0]

    def _finish_turn(self, g, seat: int, t0: int, r: float, depth: int) -> float:
        """Value after the turn that was running at t0 is over (answers by the simple rules; own completion steps
        by the best value, `depth` levels deep)."""
        steps = 0
        while not g.game_over and g.s.turns == t0 and steps < 400:
            d = g.s.decisions.top
            if depth > 0 and d.seat == seat and d.kind in NESTED and len(d.data["legal"]) > 1:
                return max(self._eval(g, b, seat, t0, r, depth - 1) for b in self._candidates(g, d))
            a = self.simple(g, seat)
            if a == FAIL:
                return FAIL
            g.step_id(a)
            steps += 1
        return relative(g, seat, r)                 # the same horizon for every answer of one decision

    def _hidden_shuffled(self, game):
        """A copy with every hidden order reshuffled, so the look-ahead cannot read the decks."""
        g = game.clone()
        s = g.s
        self.rng.shuffle(s.civil_deck)
        self.rng.shuffle(s.military_deck)
        self.rng.shuffle(s.current_events)
        g.rng.seed(self.rng.getrandbits(64))
        return g

    def _eval(self, game, a: int, seat: int, t0: int, r: float, depth: int) -> float:
        g = game.clone()
        g.step_id(a)
        return self._finish_turn(g, seat, t0, r, depth)

    @staticmethod
    def _candidates(g, d) -> list:
        from .engine import A_NO
        legal = d.data["legal"]
        if d.kind == "BID":
            return ([A_NO] if A_NO in legal else []) + [a for a in legal if a != A_NO][:MAX_BIDS]
        return legal

    def act(self, game, seat: int) -> int:
        from .engine import A_CARD
        d = game.s.decisions.top
        legal = d.data["legal"]
        if len(legal) == 1:
            return legal[0]
        if d.kind == "DISCARD_MILITARY":
            return min(legal, key=lambda a: (_military_card_value(a - A_CARD), a))
        t0 = game.s.turns
        r = rounds_left(game)
        game = self._hidden_shuffled(game)          # one shuffled copy per decision: the same guess for every answer
        best, best_v = [], None
        for a in self._candidates(game, d):
            v = self._eval(game, a, seat, t0, r, self.depth)
            if best_v is None or v > best_v + 1e-9:
                best, best_v = [a], v
            elif abs(v - best_v) <= 1e-9:
                best.append(a)
        return self.rng.choice(best)
