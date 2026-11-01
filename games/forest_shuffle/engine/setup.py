"""Deck construction and initial deal."""
from __future__ import annotations

from bgai.kit import Deck

from ..core.cards import CardInstance

REMOVAL = {0: {2: 30, 3: 20, 4: 10, 5: 0}, 1: {2: 45, 3: 30, 4: 15, 5: 0}, 2: {2: 80, 3: 50, 4: 35, 5: 20}}


def removal_count(num_players: int, expansions) -> int:
    n_exp = len([e for e in expansions if e != "base"])
    return 10 + REMOVAL[n_exp][num_players]


def build_deck(db, rng, num_players: int, expansions):
    uid, cards, winters = 0, [], []
    for d in db.defs:
        if d.expansion not in expansions:
            continue
        for _ in range(d.count):
            inst = CardInstance(uid, d.def_id)
            uid += 1
            (winters if d.layout == "WINTER" else cards).append(inst)
    rng.shuffle(cards)
    k = removal_count(num_players, expansions)
    removed, cards = cards[:k], cards[k:]
    third = len(cards) // 3
    top, middle, bottom = cards[:third], cards[third:2 * third], cards[2 * third:]
    bottom = bottom + winters[:2]
    rng.shuffle(bottom)
    bottom = [winters[2]] + bottom
    return Deck(top + middle + bottom), removed


def deal_hands(state, num_players: int) -> None:
    for p in state.players:
        for _ in range(6):
            p.hand.append(state.deck.draw())


def can_mulligan(db, hand) -> bool:
    for c in hand:
        d = db.defs[c.def_id]
        if d.layout == "WOODY_PLANT" and db.species[d.species].kind == "TREE":
            return False
    return True
