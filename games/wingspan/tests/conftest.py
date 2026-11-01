"""Helpers to build exact game situations for rule tests."""
from __future__ import annotations

import pytest

from games.wingspan import new_game
from games.wingspan import engine as E
from games.wingspan.cards import FOODS, HABITATS, birds
from games.wingspan.engine import Placed

BY_NAME = {b.name: b for b in birds()}


def bid(name: str) -> int:
    return BY_NAME[name].id


def started(players: int = 2, seed: int = 0, options=None):
    """A game after setup (every player kept no birds and the first bonus card), at the first player's turn."""
    g = new_game(players, seed, options)
    while g.s.tasks and g.s.decisions.top.kind.startswith("SETUP"):
        d = g.s.decisions.top
        legal = d.data["legal"]
        g.step_id(E.A_NO if E.A_NO in legal else legal[0])
    assert g.s.decisions.top.kind == "CHOOSE_ACTION"
    return g


def clear(g, seat=None):
    g._dirty = True
    for p in g.s.players if seat is None else [g.p(seat)]:
        p.hand, p.food, p.rows = [], [0] * 5, [[], [], []]


def place(g, seat: int, name: str, habitat: str, eggs: int = 0) -> Placed:
    g._dirty = True
    p = Placed(bid(name), eggs=eggs)
    g.p(seat).rows[HABITATS.index(habitat)].append(p)
    return p


def give(g, seat: int, *names):
    g._dirty = True
    g.p(seat).hand += [bid(n) for n in names]


def food(g, seat: int, **kw):
    g._dirty = True
    g.p(seat).food = [kw.get(f, 0) for f in FOODS]


def refresh(g):
    """Recompute the pending decision after a test changed the state directly."""
    if getattr(g, "_dirty", False):
        g.s.decisions.pop()
        g._run()
        g._dirty = False


def answer(g, text: str):
    """Answer the pending decision with the legal action whose description contains `text`."""
    refresh(g)
    d = g.s.decisions.top
    opts = {g.describe(a): a for a in d.data["legal"]}
    hits = [a for t, a in opts.items() if text.lower() in t.lower()]
    assert hits, f"no legal answer like {text!r} in {d.kind}: {list(opts)}"
    g.step_id(hits[0])


def options(g) -> list:
    refresh(g)
    d = g.s.decisions.top
    return [g.describe(a) for a in d.data["legal"]]


def kind(g) -> str:
    refresh(g)
    return g.s.decisions.top.kind


def play(g, name: str, habitat: str = None, two_for_one: bool = False):
    """Take the play-a-bird action with `name`, choosing `habitat` if asked; pay eggs and food with the first legal
    answers (direct food before two-for-one unless two_for_one)."""
    answer(g, "Play a bird")
    if kind(g) == "PLAY_BIRD":
        answer(g, "Play " + name)
    if kind(g) == "PLAY_HABITAT":
        legal = g.s.decisions.top.data["legal"]
        g.step_id(E.A_HAB + HABITATS.index(habitat) if habitat else legal[0])
    while kind(g) in ("PAY_EGG", "PAY_FOOD", "PAY_PAIR"):
        legal = g.s.decisions.top.data["legal"]
        direct = [a for a in legal if a != E.A_YES]
        g.step_id(E.A_YES if (two_for_one and E.A_YES in legal) or not direct else direct[0])


@pytest.fixture
def g2():
    return started(2, 1)
