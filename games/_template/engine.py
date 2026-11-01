"""Toy engine built from the shared kit. Rule IDs refer to rules.md in this folder."""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from typing import Optional

from bgai.kit import CodecBuilder, Decision, DecisionStack, Deck, Rng, TextLog

COLOURS = ("red", "green", "blue")
CARDS = [(n, c) for c in range(3) for n in range(1, 16)]          # T1.1: 45 cards, 1..15 in 3 colours
CODEC = CodecBuilder([("MARKET", 3), ("DECK", 1)])                 # frozen action numbering


@dataclass
class State:
    deck: Deck
    market: list
    hands: list
    current: int = 0
    turns: int = 0
    decisions: DecisionStack = field(default_factory=DecisionStack)
    over: bool = False
    log: TextLog = field(default_factory=TextLog)


class Game:
    def __init__(self, num_players: int = 2, seed: Optional[int] = None):
        self.num_players = num_players
        self.rng = Rng(seed)
        self.s: Optional[State] = None

    def reset(self) -> "Game":
        deck = Deck(range(len(CARDS)))
        deck.shuffle(self.rng)                                      # T2.1
        market = deck.draw_many(3)
        self.s = State(deck=deck, market=market, hands=[[] for _ in range(self.num_players)])
        self._ask()
        return self

    def clone(self) -> "Game":
        g = Game.__new__(Game)
        g.num_players = self.num_players
        g.s = pickle.loads(pickle.dumps(self.s))
        g.rng = Rng()
        g.rng.setstate(self.rng.getstate())
        return g

    # ---- flow
    def _ask(self) -> None:
        s = self.s
        legal = [CODEC.encode("MARKET", i) for i in range(len(s.market))] + ([CODEC.encode("DECK")] if s.deck else [])
        s.decisions.push(Decision("TAKE", {"legal": legal}, s.current))

    @property
    def current_seat(self) -> int:
        return self.s.current

    @property
    def game_over(self) -> bool:
        return self.s.over

    @property
    def turns(self) -> int:
        return self.s.turns

    def legal_ids(self) -> list:
        d = self.s.decisions.top
        return list(d.data["legal"]) if d else []

    def step_id(self, a: int) -> None:
        s = self.s
        if a not in self.legal_ids():
            raise ValueError(f"illegal action {a}")
        s.log.add(s.current, self.describe(a))
        s.decisions.pop()
        seg, i = CODEC.decode(a)
        card = s.market.pop(i) if seg == "MARKET" else s.deck.draw()   # T3.1
        s.hands[s.current].append(card)
        if seg == "MARKET" and s.deck:
            s.market.append(s.deck.draw())                             # T3.2: refill the market at once
        s.turns += 1
        if not s.deck and not s.market:                                # T4.1
            s.over = True
            return
        s.current = (s.current + 1) % self.num_players
        self._ask()

    # ---- results (T5)
    def breakdowns(self) -> list:
        out = []
        for h in self.s.hands:
            numbers = sum(CARDS[c][0] for c in h)
            sets = sum(5 for col in range(3) if sum(1 for c in h if CARDS[c][1] == col) >= 3)
            out.append({"numbers": numbers, "sets": sets})
        return out

    def scores(self) -> list:
        return [sum(b.values()) for b in self.breakdowns()]

    def tiebreaks(self):
        return None

    # ---- records and review
    def describe(self, a: int) -> str:
        seg, i = CODEC.decode(a)
        if seg == "DECK":
            return "Take the deck's top card"
        n, c = CARDS[self.s.market[i]]
        return f"Take {COLOURS[c]} {n} from the market"

    def record_info(self, a: int) -> dict:
        seg, i = CODEC.decode(a)
        card = self.s.market[i] if seg == "MARKET" else None
        key = f"{COLOURS[CARDS[card][1]]}_{CARDS[card][0]}" if card is not None else None
        return {"decision": "TAKE", "action": seg, "card": key, "item": key,
                "tags": {"colour": COLOURS[CARDS[card][1]] if card is not None else None}, "extra": {}}

    def tableau(self, seat: int) -> list:
        return [{"item": f"{COLOURS[CARDS[c][1]]}_{CARDS[c][0]}", "kind": "card", "group": COLOURS[CARDS[c][1]],
                 "slot": k, "host": None, "points": CARDS[c][0], "tags": {"colour": COLOURS[CARDS[c][1]]}}
                for k, c in enumerate(self.s.hands[seat])]

    def seat_extra(self, seat: int) -> dict:
        return {"cards": len(self.s.hands[seat]), "hand_left": []}

    def text_state(self) -> str:
        s = self.s
        fmt = lambda c: f"{COLOURS[CARDS[c][1]]} {CARDS[c][0]}"
        lines = [f"turn {s.turns}, P{s.current} to act, deck {len(s.deck)}", "market: " + ", ".join(map(fmt, s.market))]
        lines += [f"P{i}: " + ", ".join(map(fmt, h)) + f"  score {self.scores()[i]}" for i, h in enumerate(s.hands)]
        return "\n".join(lines)


def invariants(g) -> list:
    s = g.s
    total = len(s.deck) + len(s.market) + sum(len(h) for h in s.hands)
    return [] if total == len(CARDS) else [f"cards {total} != {len(CARDS)}"]
