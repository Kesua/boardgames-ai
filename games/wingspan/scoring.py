"""Scoring: end-of-round goals (W12), bonus cards (W13), final score (W14)."""
from __future__ import annotations

from .cards import FOODS, HABITATS, INV, bonus_data

GREEN = None


def goal_count(g, seat: int, goal: dict) -> int:
    """W12.4: what a player has for one goal right now."""
    pl = g.p(seat)
    k = goal["count"]
    if k == "birds_in":
        return len(pl.rows[HABITATS.index(goal["habitat"])])
    if k == "eggs_in":
        return sum(p.eggs for p in pl.rows[HABITATS.index(goal["habitat"])])
    if k == "nest_birds_with_egg":
        return sum(1 for _, _, p in pl.placed() if p.eggs > 0 and g.bird(p.bird).has_nest(goal["nest"]))
    if k == "eggs_in_nest":
        return sum(p.eggs for _, _, p in pl.placed() if g.bird(p.bird).has_nest(goal["nest"]))
    if k == "total_birds":
        return sum(len(r) for r in pl.rows)
    if k == "egg_sets":
        return min(sum(p.eggs for p in row) for row in pl.rows)
    raise ValueError(k)


def green_points(counts: list, round_index: int) -> list:
    """W12.1/W12.2: places 1-3 score the round's values; ties share the covered places (sum, divide, round down);
    a player with 0 items scores 0."""
    values = list(bonus_data()["goals"]["green"][round_index]) + [0] * len(counts)
    order = sorted(set(counts), reverse=True)
    out = [0] * len(counts)
    place = 0
    for v in order:
        tied = [i for i, c in enumerate(counts) if c == v]
        pts = sum(values[place:place + len(tied)]) // len(tied)
        for i in tied:
            out[i] = pts if v > 0 else 0
        place += len(tied)
    return out


def score_goal(g, round_index: int) -> list:
    goal = g.s.goals[round_index]
    counts = [goal_count(g, seat, goal) for seat in range(g.num_players)]
    if g.s.goal_side == "blue":
        return [min(c, bonus_data()["goals"]["blue_max"]) for c in counts]          # W12.3
    return green_points(counts, round_index)


def eats(b, food: int) -> bool:
    return b.food[food] > 0                                                         # W13.2: wild never counts


def bonus_count(g, seat: int, card) -> int:
    """W13.2: how many birds (or cards) a bonus card counts for a player."""
    pl = g.p(seat)
    k = card.count
    t = k["type"]
    if t == "hand":
        return len(pl.hand)
    if t == "fewest_habitat":
        return min(len(r) for r in pl.rows)
    n = 0
    for _, _, p in pl.placed():
        b = g.bird(p.bird)
        if t == "word":
            ok = bool(b.words[k["list"]])
        elif t == "points_below":
            ok = b.points < k["value"]
        elif t == "flocking":
            ok = b.flocking
        elif t == "predator":
            ok = b.predator
        elif t == "eats":
            ok = eats(b, FOODS.index(k["food"]))
        elif t == "eats_only":
            f = FOODS.index(k["food"])
            ok = b.food[f] > 0 and not b.wild and not b.alternative and sum(b.food) == b.food[f]
        elif t == "eggs_at_least":
            ok = p.eggs >= k["value"]
        elif t == "nest":
            ok = b.has_nest(k["nest"])
        elif t == "only_habitat":
            ok = b.habitats == (HABITATS.index(k["habitat"]),)
        elif t == "wingspan_above":
            ok = b.wingspan > k["value"]
        elif t == "wingspan_at_most":
            ok = b.wingspan <= k["value"]
        elif t == "wild_cost":
            ok = b.wild > 0
        else:
            raise ValueError(t)
        n += ok
    return n


def bonus_points(card, count: int) -> int:
    if card.per:
        return card.per * count
    pts = 0
    for lo, p in card.tiers:                                                       # W13.1: highest tier reached
        if count >= lo:
            pts = p
    return pts


def breakdown(g, seat: int) -> dict:
    """W14.1 score categories."""
    pl = g.p(seat)
    birds = eggs = cache = tucked = 0
    for _, _, p in pl.placed():
        birds += g.bird(p.bird).points
        eggs += p.eggs
        cache += sum(p.cache)
        tucked += p.tucked
    bonus = sum(bonus_points(g.bonus[c], bonus_count(g, seat, g.bonus[c])) for c in pl.bonus)
    goals = sum(g.s.goal_points[r][seat] for r in range(4))
    return {"birds": birds, "bonus": bonus, "goals": goals, "eggs": eggs, "cache": cache, "tucked": tucked}
