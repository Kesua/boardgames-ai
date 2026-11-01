"""Bird power effects (rules.md W10, W11). Each effect is a task handler like those in engine.py."""
from __future__ import annotations

from .cards import DUAL, FOODS, HABITATS, INV, RODENT, SEED

NESTS_ORDER = ("bowl", "cavity", "ground", "platform")


def _e():
    from . import engine as E
    return E


def power_of(g, seat, h, c) -> dict:
    return g.bird(g.at(seat, h, c).bird).power


def repeat_targets(g, seat, h, c, predator_only: bool, chain: list) -> list:
    E = _e()
    out = []
    for i, p in enumerate(g.p(seat).rows[h]):
        b = g.bird(p.bird)
        if i == c or (h, i) in chain or b.color != "brown" or not b.power:
            continue
        if predator_only and not b.predator:
            continue
        out.append(E.A_SLOT + h * 5 + i)
    return out


def can_use(g, seat, h, c) -> bool:
    """False when the power could not change anything now (then it is not offered)."""
    s = g.s
    pl = g.p(seat)
    p = g.at(seat, h, c)
    pw = g.bird(p.bird).power
    t = pw["type"]
    feeder_has = lambda foods: bool(g.die_options(foods)) or g.reroll_allowed()
    if t == "gain_feeder":
        return feeder_has([FOODS.index(f) for f in pw["foods"]])
    if t == "lay_egg":
        return p.eggs < g.bird(p.bird).egg_limit if pw["target"] == "this" else bool(g.lay_slots(seat))
    if t == "lay_each_nest":
        return bool(g.lay_slots(seat, pw["nest"]))
    if t == "all_lay_nest":
        return any(g.lay_slots(x, pw["nest"]) for x in range(g.num_players))
    if t in ("draw", "egg_for_cards") and not g.can_draw():
        return False
    if t == "tuck_hand":
        return bool(pl.hand)
    if t == "food_for_tucks":
        return pl.food[FOODS.index(pw["food"])] > 0 and (bool(s.deck) or bool(s.discard))
    if t == "egg_for_wild":
        return bool(g.egg_slots(seat, exclude=(h, c)))
    if t == "egg_for_cards":
        return bool(g.egg_slots(seat))
    if t == "hunt_card":
        return bool(s.deck) or bool(s.discard)
    if t == "hunt_dice":
        return bool(s.outside)
    if t == "move":
        return c == len(pl.rows[h]) - 1 and any(len(pl.rows[x]) < 5 for x in range(3) if x != h)
    if t == "repeat":
        return bool(repeat_targets(g, seat, h, c, pw["predator_only"], []))
    if t == "trade_food":
        return sum(pl.food) > 0
    if t == "draw_bonus":
        return bool(s.bonus_deck) or bool(s.bonus_discard)
    if t == "gain_all_feeder":
        f = FOODS.index(pw["food"])
        return bool(g.die_options([f])) or g.reroll_allowed()
    if t == "play_another":
        hab = h if pw["habitat"] == "this" else HABITATS.index(pw["habitat"])
        return bool(g.playable_birds(seat, hab))
    if t == "take_tray":
        return any(x is not None for x in s.tray)
    if t == "each_gain_die" or t == "fewest_die":
        return True
    if t == "all_draw_deck":
        return bool(s.deck) or bool(s.discard)                      # deck only, never the tray
    if t in ("oystercatcher", "fewest_draw"):
        return g.can_draw()
    return True


def start_effect(g, seat, h, c, chain):
    """Run the power of the bird at (seat, h, c) after the owner chose to use it."""
    E = _e()
    s = g.s
    pl = g.p(seat)
    p = g.at(seat, h, c)
    b = g.bird(p.bird)
    pw = b.power
    t = pw["type"]
    push = s.tasks.append
    if t == "gain_feeder":
        push(E._take_die_task(seat, foods=[FOODS.index(f) for f in pw["foods"]], optional=True,
                              cache_pos=(h, c), may_cache=pw["may_cache"]))
    elif t == "gain_supply":
        push({"op": "eff_supply", "seat": seat, "h": h, "c": c, "foods": [FOODS.index(f) for f in pw["foods"]],
              "count": pw["count"], "cache": pw["cache"]})
    elif t == "all_gain_supply":
        f = FOODS.index(pw["food"])
        for x in g.order_from(seat):
            g.gain(x, f)                                    # W10.3: every player gains (taking food never hurts)
    elif t == "lay_egg":
        if pw["target"] == "this":
            if p.eggs < b.egg_limit:
                p.eggs += 1
        else:
            push({"op": "eff_lay", "seat": seat, "slots_nest": None, "exclude": None, "optional": True})
    elif t == "lay_each_nest":
        for hh, cc, q in pl.placed():
            if g.bird(q.bird).has_nest(pw["nest"]) and q.eggs < g.bird(q.bird).egg_limit:
                q.eggs += 1
    elif t == "all_lay_nest":
        order = g.order_from(seat)
        for x in reversed(order[1:]):
            push({"op": "eff_lay", "seat": x, "slots_nest": pw["nest"], "exclude": None, "optional": True})
        push({"op": "eff_lay2", "seat": seat, "nest": pw["nest"], "first": None})
    elif t == "draw":
        push({"op": "draw_n", "seat": seat, "n": pw["count"], "done": 0, "discard_end": pw["discard_end"],
              "to": "hand"})
    elif t == "all_draw_deck":
        for x in g.order_from(seat):
            card = g.draw_deck()
            if card is not None:
                g.p(x).hand.append(card)
    elif t in ("fewest_draw", "fewest_die"):
        hab = HABITATS.index(pw["habitat"])
        low = min(len(g.p(x).rows[hab]) for x in range(g.num_players))
        tied = [x for x in g.order_from(seat) if len(g.p(x).rows[hab]) == low]       # W10.10
        if t == "fewest_die" and len(tied) > 1:
            push({"op": "eff_each_die", "seat": seat, "start": None, "only": tied})   # Hermit Thrush: owner picks first
            return
        for x in reversed(tied):
            if t == "fewest_draw":
                push({"op": "draw_n", "seat": x, "n": 1, "done": 0, "discard_end": 0, "to": "hand"})
            else:
                push(E._take_die_task(x, optional=True))
    elif t == "each_gain_die":
        push({"op": "eff_each_die", "seat": seat, "start": None})
    elif t == "tuck_hand":
        push({"op": "eff_tuck", "seat": seat, "h": h, "c": c, "then": pw["then"], "pink": None})
    elif t == "food_for_tucks":
        pl.food[FOODS.index(pw["food"])] -= 1
        for _ in range(pw["count"]):
            card = g.draw_deck()
            if card is not None:
                p.tucked += 1
    elif t == "egg_for_wild":
        push({"op": "eff_egg_wild", "seat": seat, "h": h, "c": c, "count": pw["count"], "stage": "egg"})
    elif t == "egg_for_cards":
        push({"op": "eff_egg_cards", "seat": seat, "stage": "egg"})
    elif t == "hunt_card":
        card = g.draw_deck()
        if card is not None:
            if g.bird(card).wingspan < pw["below"]:                                       # W10.5: strictly less
                p.tucked += 1
                s.log.add(seat, f"{b.name} hunts {g.bird(card).name}: tucked")
                push({"op": "trigger", "kind": "predator", "active": seat})
            else:
                s.discard.append(card)
                s.log.add(seat, f"{b.name} misses ({g.bird(card).name})")
    elif t == "hunt_dice":
        f = FOODS.index(pw["food"])
        s.outside = [g.rng.randrange(6) for _ in s.outside]                              # W7.4
        if f in s.outside:
            p.cache[f] += 1
            s.log.add(seat, f"{b.name} rolls {[FACES_TXT[x] for x in s.outside]}: caches 1 {FOODS[f]}")
            push({"op": "trigger", "kind": "predator", "active": seat})
        else:
            s.log.add(seat, f"{b.name} rolls {[FACES_TXT[x] for x in s.outside]}: miss")
    elif t == "move":
        push({"op": "eff_move", "seat": seat, "h": h, "c": c})
    elif t == "repeat":
        push({"op": "eff_repeat", "seat": seat, "h": h, "c": c, "chain": list(chain) + [(h, c)],
              "predator_only": pw["predator_only"]})
    elif t == "trade_food":
        push({"op": "eff_trade", "seat": seat, "give": None})
    elif t == "draw_bonus":
        push({"op": "eff_bonus", "seat": seat, "drawn": None})
    elif t == "gain_all_feeder":
        push({"op": "eff_gain_all", "seat": seat, "food": FOODS.index(pw["food"])})
    elif t == "play_another":
        hab = h if pw["habitat"] == "this" else HABITATS.index(pw["habitat"])
        push({"op": "play_bird", "seat": seat, "habitat": hab, "optional": True, "stage": "bird"})
    elif t == "oystercatcher":
        push({"op": "eff_oyster", "seat": seat, "stage": "draw", "picker": 0})
        push({"op": "draw_n", "seat": seat, "n": g.num_players + 1, "done": 0, "discard_end": 0, "to": "reveal",
              "must": True})
    elif t == "take_tray":
        for i in range(3):
            if s.tray[i] is not None:
                pl.hand.append(s.tray[i])
                s.tray[i] = None
    else:
        raise ValueError(f"no effect for {t}")


FACES_TXT = ("invertebrate", "seed", "fish", "fruit", "rodent", "invertebrate/seed")


# ---------------------------------------------------------------------- effect handlers
def h_supply(g, t, a):
    E = _e()
    if a is not None:
        t["food"] = a - E.A_FOOD
        return
    if "food" not in t:
        if len(t["foods"]) > 1:
            g._ask("CHOOSE_FOOD", t["seat"], [E.A_FOOD + f for f in t["foods"]])
            return
        t["food"] = t["foods"][0]
    g.s.tasks.pop()
    if t["cache"]:
        g.at(t["seat"], t["h"], t["c"]).cache[t["food"]] += t["count"]
    else:
        g.gain(t["seat"], t["food"], t["count"])


def h_lay(g, t, a):
    """Lay 1 egg on one of the player's birds (optionally only a nest type, optionally not one bird)."""
    E = _e()
    if a is not None:
        g.s.tasks.pop()
        if a != E.A_NO:
            h, c = g.slot_of(a)
            g.at(t["seat"], h, c).eggs += 1
            t["laid"] = (h, c)
            if t.get("mark"):
                m = t["mark"]
                g.at(m[0], m[1], m[2]).pink_used = True
        return
    slots = g.lay_slots(t["seat"], t["slots_nest"], t["exclude"])
    if not slots:
        g.s.tasks.pop()
        return
    g._ask("LAY_EGG", t["seat"], slots + ([E.A_NO] if t["optional"] else []), left=1, pink=bool(t.get("mark")))


def h_lay2(g, t, a):
    """W10.11: the owner lays 1 egg on a [nest] bird, then may lay 1 on a different [nest] bird."""
    E = _e()
    seat = t["seat"]
    if a is not None:
        if a == E.A_NO:
            g.s.tasks.pop()
            return
        h, c = g.slot_of(a)
        g.at(seat, h, c).eggs += 1
        if t["first"] is None:
            t["first"] = (h, c)
        else:
            g.s.tasks.pop()
        return
    slots = g.lay_slots(seat, t["nest"], t["first"])
    if not slots:
        g.s.tasks.pop()
        return
    g._ask("LAY_EGG", seat, slots + [E.A_NO], left=1 if t["first"] else 2)


def h_draw_n(g, t, a):
    """Draw up to n cards one at a time from tray or deck (to the hand, or to the reveal for the Oystercatcher)."""
    E = _e()
    s = g.s
    seat = t["seat"]
    if a is not None:
        if a == E.A_NO:
            t["done"] = t["n"]
            return
        if t["to"] == "reveal":
            card = g.draw_deck() if a == E.A_DECK else s.tray[a - E.A_TRAY]
            if a != E.A_DECK:
                s.tray[a - E.A_TRAY] = None
            if card is not None:
                s.reveal.append(card)
        else:
            g.take_card(seat, a)
        t["done"] += 1
        t["drawn"] = t.get("drawn", 0) + 1
        return
    opts = g.draw_options()
    if t["done"] < t["n"] and opts:
        g._ask("DRAW", seat, opts + ([] if t.get("must") else [E.A_NO]), left=t["n"] - t["done"])
        return
    s.tasks.pop()
    if t["discard_end"] and t.get("drawn"):
        g.p(seat).end_discards += t["discard_end"]                   # W10.9


def h_each_die(g, t, a):
    """W10.3: each player takes 1 die, starting with the player the owner chooses."""
    E = _e()
    if a is not None:
        t["start"] = (t["seat"] + a - E.A_PLAYER) % g.num_players
        return
    only = t.get("only")
    if t["start"] is None:
        seats = only if only else list(range(g.num_players))
        g._ask("START_PLAYER", t["seat"], [E.A_PLAYER + (x - t["seat"]) % g.num_players for x in seats])
        return
    g.s.tasks.pop()
    for x in reversed([x for x in g.order_from(t["start"]) if not only or x in only]):
        g.s.tasks.append(E._take_die_task(x, optional=True))


def h_tuck(g, t, a):
    """Tuck 1 card from hand behind this bird; if you do, the follow-up (W10.2). Also the pink Horned Lark."""
    E = _e()
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    if a is not None:
        s.tasks.pop()
        if a == E.A_NO:
            return
        card = a - E.A_BIRD
        pl.hand.remove(card)
        p = g.at(seat, t["h"], t["c"])
        p.tucked += 1
        if t.get("pink"):
            p.pink_used = True
        then = t["then"]
        if not then:
            return
        tt = then["type"]
        if tt == "draw":
            s.tasks.append({"op": "draw_n", "seat": seat, "n": 1, "done": 0, "discard_end": 0, "to": "hand"})
        elif tt == "lay_egg" and then["target"] == "this":
            if p.eggs < g.bird(p.bird).egg_limit:
                p.eggs += 1
        elif tt == "lay_egg":
            s.tasks.append({"op": "eff_lay", "seat": seat, "slots_nest": None, "exclude": None, "optional": True})
        elif tt == "gain_supply":
            s.tasks.append({"op": "eff_supply", "seat": seat, "h": t["h"], "c": t["c"],
                            "foods": [FOODS.index(f) for f in then["foods"]], "count": 1, "cache": False})
        return
    if not pl.hand:
        s.tasks.pop()
        return
    g._ask("TUCK", seat, [E.A_BIRD + b for b in sorted(set(pl.hand))] + [E.A_NO], bird=g.at(seat, t["h"], t["c"]).bird)


def h_egg_wild(g, t, a):
    E = _e()
    seat = t["seat"]
    if a is not None:
        if t["stage"] == "egg":
            if a == E.A_NO:
                g.s.tasks.pop()
                return
            h, c = g.slot_of(a)
            g.at(seat, h, c).eggs -= 1
            t["stage"] = "food"
            t["left"] = t["count"]
        else:
            g.gain(seat, a - E.A_FOOD)
            t["left"] -= 1
        return
    if t["stage"] == "egg":
        g._ask("DISCARD_EGG", seat, g.egg_slots(seat, exclude=(t["h"], t["c"])) + [E.A_NO])
        return
    if t["left"] > 0:
        g._ask("CHOOSE_FOOD", seat, [E.A_FOOD + f for f in range(5)])
        return
    g.s.tasks.pop()


def h_egg_cards(g, t, a):
    E = _e()
    seat = t["seat"]
    if a is not None:
        g.s.tasks.pop()
        if a != E.A_NO:
            h, c = g.slot_of(a)
            g.at(seat, h, c).eggs -= 1
            g.s.tasks.append({"op": "draw_n", "seat": seat, "n": 2, "done": 0, "discard_end": 0, "to": "hand"})
        return
    g._ask("DISCARD_EGG", seat, g.egg_slots(seat) + [E.A_NO])


def h_move(g, t, a):
    """W10.7: move the rightmost bird to the leftmost empty slot of another row."""
    E = _e()
    seat, h, c = t["seat"], t["h"], t["c"]
    pl = g.p(seat)
    if a is not None:
        g.s.tasks.pop()
        if a != E.A_NO:
            p = pl.rows[h].pop(c)
            pl.rows[a - E.A_HAB].append(p)
        return
    if c != len(pl.rows[h]) - 1:
        g.s.tasks.pop()
        return
    opts = [E.A_HAB + x for x in range(3) if x != h and len(pl.rows[x]) < 5]
    if not opts:
        g.s.tasks.pop()
        return
    g._ask("MOVE", seat, opts + [E.A_NO], bird=pl.rows[h][c].bird)


def h_repeat(g, t, a):
    """W10.6: run another brown bird's power in this row again, as that bird."""
    E = _e()
    seat, h, c = t["seat"], t["h"], t["c"]
    if a is not None:
        g.s.tasks.pop()
        if a != E.A_NO:
            th, tc = g.slot_of(a)
            if can_use(g, seat, th, tc):
                start_effect(g, seat, th, tc, t["chain"])
        return
    opts = repeat_targets(g, seat, h, c, t["predator_only"], t["chain"])
    if not opts:
        g.s.tasks.pop()
        return
    g._ask("REPEAT", seat, opts + [E.A_NO])


def h_trade(g, t, a):
    E = _e()
    seat = t["seat"]
    pl = g.p(seat)
    if a is not None:
        if t["give"] is None:
            if a == E.A_NO:
                g.s.tasks.pop()
                return
            t["give"] = a - E.A_FOOD
            pl.food[t["give"]] -= 1
        else:
            g.gain(seat, a - E.A_FOOD)
            g.s.tasks.pop()
        return
    if t["give"] is None:
        g._ask("TRADE_GIVE", seat, [E.A_FOOD + f for f in range(5) if pl.food[f]] + [E.A_NO])
        return
    g._ask("TRADE_GET", seat, [E.A_FOOD + f for f in range(5) if f != t["give"]])


def h_bonus(g, t, a):
    """W10.14: draw 2 bonus cards, keep 1, discard the other."""
    E = _e()
    s = g.s
    seat = t["seat"]
    if a is not None:
        keep = a - E.A_BONUS
        g.p(seat).bonus.append(keep)
        s.bonus_discard += [x for x in t["drawn"] if x != keep]
        s.tasks.pop()
        return
    if t["drawn"] is None:
        drawn = []
        for _ in range(2):
            if not s.bonus_deck and s.bonus_discard:
                from bgai.kit import Deck
                s.bonus_deck = Deck(s.bonus_discard)
                s.bonus_discard = []
                s.bonus_deck.shuffle(g.rng)
            card = s.bonus_deck.draw()
            if card is not None:
                drawn.append(card)
        t["drawn"] = drawn
    if not t["drawn"]:
        s.tasks.pop()
        return
    g._ask("KEEP_BONUS", seat, [E.A_BONUS + x for x in t["drawn"]])


def h_gain_all(g, t, a):
    """W10.12: optional reroll first, then take every die showing the food (dual counts for invertebrate/seed)."""
    E = _e()
    s = g.s
    seat, f = t["seat"], t["food"]
    if a is not None:
        if a == E.A_REROLL:
            g.reroll()
            return
        t["take"] = True
        return
    if not t.get("take") and g.reroll_allowed():
        g._ask("TAKE_DIE", seat, [E.A_YES, E.A_REROLL], foods=[f], purpose="all")
        return
    s.tasks.pop()
    faces = [x for x in s.feeder if x == f or (x == DUAL and f in (INV, SEED))]
    for x in faces:                     # the feeder refills only after the last die is gone: refill dice are not ours
        g.take_die(x)
        g.gain(seat, f)


def h_oyster(g, t, a):
    """W10.13: starting with the owner, each player keeps 1 of the revealed cards; the owner keeps the last one."""
    E = _e()
    s = g.s
    owner = t["seat"]
    order = g.order_from(owner)
    if a is not None:
        card = a - E.A_BIRD
        s.reveal.remove(card)
        g.p(order[t["picker"]]).hand.append(card)
        t["picker"] += 1
        return
    if t["picker"] < len(order) and len(s.reveal) > 1:
        g._ask("PICK_CARD", order[t["picker"]], [E.A_BIRD + c for c in sorted(set(s.reveal))])
        return
    s.tasks.pop()
    g.p(owner).hand.extend(s.reveal)
    s.reveal = []


# ---------------------------------------------------------------------- pink powers (W11)
def pink_effect(g, t, a):
    E = _e()
    s = g.s
    seat, h, c = t["seat"], t["h"], t["c"]
    p = g.at(seat, h, c)
    if p is None or p.pink_used:
        s.tasks.pop()
        return
    pw = g.bird(p.bird).power
    tp = pw["type"]
    s.tasks.pop()
    if tp == "pink_play":
        then = pw["then"]
        if then["type"] == "gain_supply":
            g.gain(seat, FOODS.index(then["foods"][0]))
            p.pink_used = True
        else:
            s.tasks.append({"op": "eff_tuck", "seat": seat, "h": h, "c": c, "then": None, "pink": True})
    elif tp == "pink_lay_eggs":
        s.tasks.append({"op": "eff_lay", "seat": seat, "slots_nest": pw["nest"],
                        "exclude": (h, c) if pw["other"] else None, "optional": True, "mark": (seat, h, c)})
    elif tp == "pink_gain_food_rodent":
        p.cache[RODENT] += 1
        p.pink_used = True
    elif tp == "pink_predator":
        s.tasks.append(E._take_die_task(seat, optional=True, mark=(seat, h, c)))


HANDLERS = {"eff_supply": h_supply, "eff_lay": h_lay, "eff_lay2": h_lay2, "draw_n": h_draw_n, "eff_each_die": h_each_die,
            "eff_tuck": h_tuck, "eff_egg_wild": h_egg_wild, "eff_egg_cards": h_egg_cards, "eff_move": h_move,
            "eff_repeat": h_repeat, "eff_trade": h_trade, "eff_bonus": h_bonus, "eff_gain_all": h_gain_all,
            "eff_oyster": h_oyster}
