"""Military computations (PLAN.md sections 2, 6): drawing and discarding military cards (T3.7, T6.5), armies and
strength (T11.3, T11.4), colonization force (T8.5), attack and defense strength (T9.1, T9.5), pacts and wars in play
(T9, T10) and the T8.3 ranking helper `rank_players`.

Pure functions of the state; the politics flow (decisions) lives in politics.py.
"""
from __future__ import annotations

from functools import lru_cache

from .cards import AGE, BONUS, EFFECT, EFFECT_TYPE, KIND, LEVEL, STAT_YIELDS, S_STR, TACTIC

TACTIC_UNITS = ("infantry", "cavalry", "artillery")


# ================================================================================================= cards (T3.7, T6.5)
def discard(g, card: int) -> None:
    """T6.5 / D7: a military card goes to the discard pile only if it belongs to the current age; an older card
    leaves the game (its pile left with its age)."""
    s = g.s
    if AGE[card] == s.age:
        s.military_discard.append(card)
    else:
        s.removed_military.append(card)


def draw(g, seat: int, n: int) -> int:
    """T3.7: draw up to n cards from the current military deck; an empty deck is refilled from the current age's
    shuffled discard pile. None in Age IV. Returns the number drawn."""
    s = g.s
    if s.age == "IV" or n <= 0:
        return 0
    p = s.players[seat]
    got = 0
    for _ in range(n):
        if not s.military_deck and s.military_discard:
            s.military_deck.extend(s.military_discard)
            s.military_discard = []
            s.military_deck.shuffle(g.rng)
            s.log.add(None, "Military discard pile shuffled into a new military deck")
        c = s.military_deck.draw()
        if c is None:
            break
        p.military_hand.append(c)
        got += 1
    return got


# ================================================================================================= armies (T11.4)
def unit_levels(p, sent: dict = None) -> tuple:
    """(infantry levels, cavalry levels, artillery levels, air forces): sorted level tuples of the units (workers on
    unit technologies), or of the `sent` units {card: count} only."""
    lv = {"infantry": [], "cavalry": [], "artillery": []}
    air = 0
    src = p.workers if sent is None else sent
    for c, k in src.items():
        if not k:
            continue
        kind = KIND[c]
        if kind == "air_force":
            air += k
        elif kind in lv:
            lv[kind] += [LEVEL[c]] * k
    return tuple(tuple(sorted(lv[t], reverse=True)) for t in TACTIC_UNITS) + (air,)


@lru_cache(maxsize=200000)
def army_strength(tactic: int, inf: tuple, cav: tuple, art: tuple, air: int) -> int:
    """T11.4: total tactical strength of the armies formed in the best way. Units are given as level tuples.

    Every army adds the same value except outdated ones (Age II/III tactics, a unit two or more levels below the
    tactic) and Hussars (2 + level of the lower cavalry), so the best forming is: as many armies as possible, as many
    of them full-strength as the modern units allow, air forces on the best armies (each doubles one army)."""
    if tactic is None:
        return 0
    if EFFECT_TYPE[tactic] == "hussars":                      # expansion tactic: armies of 2 cavalry
        base = EFFECT[tactic]["base"]
        values = [base + cav[2 * i + 1] for i in range(len(cav) // 2)]   # sorted pairs maximise the sum of minima
    else:
        t = TACTIC[tactic]
        req = [t["units"][k] for k in TACTIC_UNITS]
        have = (inf, cav, art)
        need = [i for i in range(3) if req[i]]
        if not need:
            return 0
        k = min(len(have[i]) // req[i] for i in need)
        lvl = LEVEL[tactic]
        if t["outdated_strength"] is None or lvl < 2:
            full = k
        else:
            full = min(k, min(sum(1 for x in have[i] if x >= lvl - 1) // req[i] for i in need))
        values = [t["strength"]] * full + [t["outdated_strength"] or 0] * (k - full)
    values.sort(reverse=True)
    return sum(values) + sum(values[:air])


def armies(p) -> int:
    if p.tactic is None:
        return 0
    return army_strength(p.tactic, *unit_levels(p))


def unit_strength(sent: dict) -> int:
    """Printed strength of the given units {card: count} (T8.5: other strength modifiers do not count)."""
    out = 0
    for c, k in sent.items():
        for st, x in STAT_YIELDS[c]:
            if st == S_STR:
                out += x * k
    return out


# ================================================================================================= strength (T11.3)
def strength(g, seat: int) -> int:
    from .economy import stats
    return stats(g, seat).strength


def colonization_force(g, seat: int, sent: dict, bonus_cards: list, extra: int = 0) -> int:
    """T8.5: strength of the sent units + tactical strength of the armies they form + colonization modifier + the
    colonization values of the bonus cards played (+ extra: James Cook, Isabella in stage 3)."""
    from .economy import stats
    p = g.s.players[seat]
    force = unit_strength(sent) + (army_strength(p.tactic, *unit_levels(p, sent)) if p.tactic is not None else 0)
    force += stats(g, seat).colonization + sum(BONUS[c]["colonization"] for c in bonus_cards) + extra
    return force


def max_colonization_force(g, seat: int) -> int:
    """The largest force the player could send now (T8.4 bid limit): every unit and every bonus card; 0 without
    units (at least one unit must be sent)."""
    p = g.s.players[seat]
    units = {c: k for c, k in p.workers.items() if k and KIND[c] in ("infantry", "cavalry", "artillery", "air_force")}
    if not units:
        return 0
    bonus = [c for c in p.military_hand if KIND[c] == "bonus"]
    return max(0, colonization_force(g, seat, units, bonus))


# ================================================================================================= pacts and wars (T9, T10)
def pacts_in_play(g) -> list:
    """(owner, card, partner, owner side) of every pact in play, owners clockwise from seat 0."""
    out = []
    for q in g.s.players:
        if q.pact is not None:
            out.append((q.seat, q.pact[0], q.pact[1], q.pact[2]))
    return out


def side_of(owner: int, partner: int, owner_side, seat: int):
    """The side ('A'/'B'/None for symmetric pacts) `seat` holds in a pact, or False if not a party."""
    if seat == owner:
        return owner_side
    if seat == partner:
        return None if owner_side is None else ("B" if owner_side == "A" else "A")
    return False


def pacts_between(g, a: int, b: int) -> list:
    return [x for x in pacts_in_play(g) if {x[0], x[2]} == {a, b}]


def pact_flag(card: int, flag: str) -> bool:
    return bool((EFFECT[card] or {}).get(flag))


def forbids_attack(g, a: int, b: int) -> bool:
    """A pact between a and b that forbids attacking (Acceptance of Supremacy, Peace Treaty, Loss of Sovereignty)."""
    return any(pact_flag(x[1], "no_attack") for x in pacts_between(g, a, b))


def forbids_war_on(g, target: int) -> bool:
    """Loss of Sovereignty: no one may declare war on its side B."""
    for owner, card, partner, side in pacts_in_play(g):
        if pact_flag(card, "no_war_on_b") and side_of(owner, partner, side, target) == "B":
            return True
    return False


def pact_side_yields(card: int, side) -> dict:
    eff = EFFECT[card] or {}
    if EFFECT_TYPE[card] == "pact_symmetric":
        return eff.get("both", {})
    if EFFECT_TYPE[card] == "pact_ab" and side in ("A", "B"):
        return eff.get(side.lower(), {})
    return {}


def ending_pact_strength(g, seat: int, other: int) -> int:
    """Strength `seat` gets from pacts with `other` that end when one attacks the other (T9.1: not counted)."""
    out = 0
    for owner, card, partner, side in pacts_between(g, seat, other):
        if pact_flag(card, "ends_on_attack"):
            out += pact_side_yields(card, side_of(owner, partner, side, seat)).get("strength", 0)
    return out


def attack_bonus(g, attacker: int, target: int) -> int:
    """Bonuses that apply when attacking this player (Open Borders Agreement: +2 against the partner)."""
    out = 0
    for owner, card, partner, side in pacts_between(g, attacker, target):
        out += (EFFECT[card] or {}).get("attack_bonus", 0)
    return out


def attack_strengths(g, attacker: int, target: int) -> tuple:
    """(attacker, target) strengths for an attack (T9.1, T9.5): attack bonuses against this rival counted, strength
    from pacts between them that end on attack not counted (they are removed by the attack)."""
    from .economy import stats
    a = stats(g, attacker).strength_raw - ending_pact_strength(g, attacker, target) + attack_bonus(g, attacker, target)
    d = stats(g, target).strength_raw - ending_pact_strength(g, target, attacker)
    return max(0, a), max(0, d)


def wars_on(g, seat: int) -> list:
    """(declarer, war card) of every war aimed at `seat`."""
    return [(q.seat, w[0]) for q in g.s.players for w in q.wars if w[1] == seat]


# ================================================================================================= ranking (T8.3)
def stat_value(g, seat: int, stat) -> int:
    from . import economy as E
    if callable(stat):
        return stat(g, seat)
    p = g.s.players[seat]
    st = E.stats(g, seat)
    if stat == "strength":
        return st.strength
    if stat == "culture_points":
        return p.culture
    if stat == "happiness":
        return st.happiness
    if stat == "culture_rating":
        return st.culture
    if stat == "science_rating":
        return st.science
    if stat == "discontent":
        return E.discontent(g, seat)
    raise KeyError(stat)


def rank_players(g, stat, mode: str = "high", game_end: bool = False) -> list:
    """T8.3: the players still in the game ordered from the strongest/most (mode 'high') or from the weakest/least
    (mode 'low'). Ties: the current player counts as higher, then the players clockwise from it; at game end the
    starting player counts as current. Card overrides (Genghis Khan wins ties, Nostradamus +3 in weakest checks) are
    hook points (effects 'rank_bonus', 'tie_priority'), filled in stage 3."""
    from . import effects
    s = g.s
    first = s.start_seat if (game_end or s.game_end_eval) else s.turn_seat
    order = g.active_seats(first)
    keyed = []
    for i, seat in enumerate(order):
        v = stat_value(g, seat, stat) + effects.query(g, "rank_bonus", seat, stat=stat, mode=mode)
        prio = effects.query(g, "tie_priority", seat, stat=stat, mode=mode)       # > 0: wins ties (Genghis Khan)
        tie = (-prio, i)                                                           # smaller = counts higher
        keyed.append((v, tie, seat))
    if mode == "high":
        keyed.sort(key=lambda x: (-x[0], x[1]))
    else:
        keyed.sort(key=lambda x: (x[0], (-x[1][0], -x[1][1])))
    return [x[2] for x in keyed]


def top(g, stat, mode: str = "high") -> int:
    """'The strongest / weakest / most / least' (one player)."""
    return rank_players(g, stat, mode)[0]


def top_two(g, stat, mode: str = "high") -> list:
    """'The two strongest (weakest)'; with 2 players only the stronger (weaker) (T8.3)."""
    r = rank_players(g, stat, mode)
    return r[:2] if len(r) >= 3 else r[:1]


def all_with_most(g, stat) -> list:
    """'All civilizations with the most …' keeps ties (clockwise from the current player)."""
    vals = {seat: stat_value(g, seat, stat) for seat in g.active_seats(g.s.turn_seat)}
    best = max(vals.values())
    return [seat for seat in g.active_seats(g.s.turn_seat) if vals[seat] == best]
