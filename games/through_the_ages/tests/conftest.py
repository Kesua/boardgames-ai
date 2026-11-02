"""Helpers to build exact Through the Ages situations for rule tests (pattern: games/wingspan/tests/conftest.py)."""
from __future__ import annotations

from games.through_the_ages import economy as E
from games.through_the_ages import engine as En
from games.through_the_ages import new_game
from games.through_the_ages.cards import KIND, SPECIALS, card_id


def cid(name: str, age: str = None) -> int:
    return card_id(name, age)


def started(players: int = 2, seed: int = 0):
    """A new game at the starting player's first decision (round 1)."""
    return new_game(players, seed)


def fresh(players: int = 2, seed: int = 0):
    """A game at round 2: everybody passed round 1 without taking a card; the starting player is at ACTION."""
    g = new_game(players, seed)
    while g.s.round < 2 or g.s.decisions.top.kind != "ACTION":
        legal = g.legal_ids()
        g.step_id(En.A_END if En.A_END in legal else legal[0])
    return g


def seat(g) -> int:
    return g.current_seat


def touch(g, s: int = None) -> None:
    for p in g.s.players if s is None else [g.p(s)]:
        E.touch(p)
    g._dirty = True


def place(g, s: int, name: str, age: str = None, workers: int = 0) -> int:
    """Put a card into play for seat s (technology, special, government, leader or completed wonder), without
    paying, token symbols included (T11.9)."""
    c = cid(name, age)
    p = g.p(s)
    k = KIND[c]
    before = E.totals(g, s)
    if k == "government":
        g.leave_play(s, p.government)
        p.government = c
    elif k in SPECIALS:
        if k in p.specials:
            g.leave_play(s, p.specials[k])
        p.specials[k] = c
    elif k == "leader":
        if p.leader is not None:
            g.leave_play(s, p.leader)
        p.leader = c
    elif k == "wonder":
        p.wonders.append(c)
    else:
        p.techs.append(c)
    g.enter_play(s, c)
    if workers:
        p.workers[c] = p.workers.get(c, 0) + workers
        p.yellow_bank -= workers
    E.settle_totals(g, s, before)
    touch(g, s)
    return c


def give(g, s: int, *names) -> list:
    """Cards into seat s's hand (civil or military by the card's deck)."""
    out = []
    for n in names:
        c = cid(*n) if isinstance(n, tuple) else cid(n)
        (g.p(s).military_hand if KIND[c] in ("event", "territory", "aggression", "war", "pact", "tactic", "bonus")
         else g.p(s).civil_hand).append(c)
        out.append(c)
    g._dirty = True
    return out


def tokens(g, s: int, name: str, n: int, age: str = None) -> None:
    """Set the blue tokens on a farm or mine in play (taken from / returned to the blue bank)."""
    c = cid(name, age)
    p = g.p(s)
    old = p.tokens.get(c, 0)
    p.blue_bank -= n - old
    if n:
        p.tokens[c] = n
    else:
        p.tokens.pop(c, None)
    g._dirty = True


def refresh(g) -> None:
    """Recompute the pending decision after a test changed the state directly."""
    if getattr(g, "_dirty", False):
        g._dirty = False
        g.s.decisions.pop()
        task = g.s.tasks[-1]
        En.HANDLERS[task["op"]](g, task, None)
        g._run()


def options(g) -> list:
    refresh(g)
    return [g.describe(a) for a in g.legal_ids()]


def kind(g) -> str:
    refresh(g)
    return g.s.decisions.top.kind


def answer(g, text: str) -> None:
    """Answer the pending decision with the legal answer whose description contains `text` (case-insensitive)."""
    refresh(g)
    opts = {g.describe(a): a for a in g.legal_ids()}
    hits = [a for t, a in opts.items() if text.lower() in t.lower()]
    assert hits, f"no legal answer like {text!r} in {g.s.decisions.top.kind}: {list(opts)}"
    g.step_id(hits[0])


def has(g, text: str) -> bool:
    return any(text.lower() in t.lower() for t in options(g))


def end_turn(g) -> None:
    """End the current player's action phase and discard military cards (first ones) until another decision."""
    s0 = g.s.turn_seat
    answer(g, "End the action phase")
    while not g.game_over and g.s.turn_seat == s0 and g.s.decisions.top.kind == "DISCARD_MILITARY":
        g.step_id(g.legal_ids()[0])


def play_to_round(g, r: int) -> None:
    """Every player ends the action phase at once until round r starts (ACTION of its first player)."""
    while not g.game_over and (g.s.round < r or g.s.decisions.top.kind != "ACTION"):
        legal = g.legal_ids()
        g.step_id(En.A_END if En.A_END in legal else legal[0])


# ----------------------------------------------------------------------------------------------- stage 2 helpers
def politics(g, s: int = None) -> None:
    """Open a politics phase for seat s now (test harness): the pending decision is put aside and asked again when
    the political action is over."""
    refresh(g)
    s = g.current_seat if s is None else s
    g.s.decisions.pop()
    g.s.tasks.append({"op": "politics", "seat": s})
    g._run()


def run_now(g, fn, *args, **kw) -> None:
    """Call fn (which may push tasks) with the pending decision put aside, then run the task loop."""
    refresh(g)
    g.s.decisions.pop()
    fn(*args, **kw)
    g._run()


def reveal_now(g, name, age: str = None, seat: int = None) -> int:
    """Put an event on top of the current events deck and reveal it now as if seat prepared (T8.1)."""
    from games.through_the_ages import politics as P
    c = cid(name, age) if not isinstance(name, int) else name
    seat = g.current_seat if seat is None else seat
    g.s.current_events.insert(0, [c, None])
    run_now(g, P.reveal, g, seat)
    return c


def mil(g, s: int, name: str, age: str = None, k: int = 1) -> int:
    """k units of the military unit technology `name` for seat s (put into play if needed)."""
    c = cid(name, age)
    p = g.p(s)
    if c not in p.techs:
        place(g, s, name, age)
    p.workers[c] = p.workers.get(c, 0) + k
    p.yellow_bank -= k
    touch(g, s)
    return c


def strength(g, s: int) -> int:
    return E.stats(g, s).strength


def answer_all(g, text: str) -> None:
    """Answer with `text` while such an answer is legal."""
    while not g.game_over and has(g, text):
        answer(g, text)


def to_action(g) -> None:
    """Pass political actions until the current player is at ACTION."""
    while not g.game_over and kind(g) == "POLITICS":
        answer(g, "Pass the political action")


def next_turn(g) -> None:
    """End the current turn and bring the next player to its action phase (political action passed)."""
    end_turn(g)
    to_action(g)
