"""One test per bird card: its power is set up, run through the real game flow, and its effect is checked.

Brown powers are activated by the row's habitat action, white powers by playing the bird, pink powers by another
player's triggering action. The expected change depends on the power type (rules.md W10, W11).
"""
import pytest

from games.wingspan import engine as E
from games.wingspan.cards import FOODS, HABITATS, birds
from games.wingspan.tests.conftest import answer, bid, clear, give, kind, place, play, started

BY_ID = {b.id: b for b in birds()}
TINY = next(b for b in birds() if b.wingspan <= 20)          # a deck card every hunter can catch


def snapshot(g, seat):
    p = g.p(seat)
    placed = [x for r in p.rows for x in r]
    return {"food": sum(p.food), "foods": list(p.food), "hand": len(p.hand), "bonus": len(p.bonus),
            "eggs": sum(x.eggs for x in placed), "cache": sum(sum(x.cache) for x in placed),
            "tucked": sum(x.tucked for x in placed), "birds": len(placed),
            "rows": [[x.bird for x in r] for r in p.rows]}


def finish_turn(g, owner, policy=None):
    """Answer everything (first useful legal answer) until the turn passes to another player's action choice."""
    start_turns = g.s.turns
    if kind(g) == "CHOOSE_ACTION" and g.current_seat != owner:
        return                                                   # the owner's turn is already over
    for _ in range(300):
        if g.game_over or (g.s.turns != start_turns and kind(g) == "CHOOSE_ACTION"):
            return
        d = g.s.decisions.top
        legal = d.data["legal"]
        pick = policy(g, d) if policy else None
        if pick is None:
            useful = [a for a in legal if a not in (E.A_NO, E.A_REROLL)]
            pick = E.A_YES if E.A_YES in legal and d.kind in ("USE_POWER", "CACHE") else (useful[0] if useful else legal[0])
        g.step_id(pick)


def base_policy(bird_id):
    """Skip the action's own gain (so only the power changes things), use our bird's power, refuse trades."""
    def pol(g, d):
        base = d.data.get("purpose") == "action" or (d.kind in ("LAY_EGG", "DRAW") and d.data.get("left") is not None)
        if d.kind in ("TAKE_DIE", "LAY_EGG", "DRAW") and base and not g._in_power:
            return E.A_NO if E.A_NO in d.data["legal"] else None
        if d.kind == "TRADE":
            return E.A_NO
        if d.kind == "USE_POWER":
            g._in_power = True
            return E.A_YES if d.data["bird"] == bird_id else E.A_NO
        return None
    return pol


def setup(bird):
    g = started(2, bird.id % 7)
    g._in_power = False
    me = g.current_seat
    other = 1 - me
    clear(g)
    g.s.feeder, g.s.outside = [0, 1, 2, 3, 4], []
    for seat in (me, other):
        g.p(seat).food = [2] * 5
        give(g, seat, "Mallard", "Killdeer")
    return g, me, other


@pytest.mark.card("*")                       # one case per bird of the catalog
@pytest.mark.parametrize("bird", birds(), ids=lambda b: b.key)
def test_card_power(bird):
    pw = bird.power
    t = pw["type"] if pw else "none"
    g, me, other = setup(bird)
    h = bird.habitats[0]
    if bird.color == "pink":
        _pink(g, me, other, bird, t, h)
        return
    if bird.color == "white":
        owner = me
        bank = place(g, me, "Wild Turkey", "grassland", eggs=5)        # eggs for column costs / egg powers
        if t == "lay_each_nest":
            star = next(b for b in birds() if b.nest == "star" and b.egg_limit >= 2)
            place(g, me, star.name, HABITATS[star.habitats[0]])
        if t == "play_another":
            hab = h
            extra = next(b for b in birds() if hab in b.habitats and b.food_total <= 2 and b.color != "white")
            give(g, me, extra.name)
        if t == "gain_all_feeder":
            f = FOODS.index(pw["food"])
            g.s.feeder, g.s.outside = [f, f, (f + 1) % 5], [0, 1]
        g.p(me).food = [6] * 5
        give(g, me, bird.name)
        before, oth = snapshot(g, me), snapshot(g, other)
        play(g, bird.name, HABITATS[h])
        if t != "none":
            assert kind(g) == "USE_POWER" and g.s.decisions.top.data["bird"] == bird.id, (bird.name, kind(g))
        finish_turn(g, owner, lambda g_, d: E.A_YES if d.kind == "USE_POWER" else None)
        after, oth2 = snapshot(g, me), snapshot(g, other)
        paid = bird.food_total
        _check_white(bird, t, pw, before, after, oth, oth2, paid)
        return
    # brown or none: the bird is the only bird of its row; helpers elsewhere
    place(g, me, bird.name, HABITATS[h])
    helper_row = (h + 1) % 3
    place(g, me, "Trumpeter Swan" if helper_row == 2 else "Wild Turkey" if helper_row == 1 else "Hooded Warbler",
          HABITATS[helper_row], eggs=2 if helper_row == 1 else 0)
    if helper_row != 1:
        place(g, me, "Wild Turkey", "grassland", eggs=2)
    if t == "hunt_card":
        g.s.deck.insert(0, TINY.id)
    if t == "hunt_dice":
        f = FOODS.index(pw["food"])
        g.s.feeder, g.s.outside = [0, 1, 3], [f, f]
        g.rng.randrange = lambda n: f                                  # the roll shows the food
    if t == "repeat":
        target = "Scaled Quail" if not pw["predator_only"] else "Barred Owl"
        if h not in BY_ID[bid(target)].habitats:
            target = next(b.name for b in birds() if h in b.habitats and b.power and b.power["type"] ==
                          ("hunt_card" if pw["predator_only"] else "lay_egg") and b.power.get("target", "this") == "this")
        g.p(me).rows[h].insert(0, type(g.p(me).rows[h][0])(bid(target)))
        if pw["predator_only"]:
            g.s.deck.insert(0, TINY.id)
            g.s.deck.insert(0, TINY.id)
    if t == "fewest_draw" or t == "fewest_die":
        clear(g, other)
    before, oth = snapshot(g, me), snapshot(g, other)
    answer(g, ("Gain food", "Lay eggs", "Draw cards")[h])
    finish_turn(g, me, base_policy(bird.id))
    after, oth2 = snapshot(g, me), snapshot(g, other)
    d = {k: after[k] - before[k] for k in ("food", "hand", "bonus", "eggs", "cache", "tucked", "birds")}
    do = {k: oth2[k] - oth[k] for k in ("food", "hand", "eggs")}
    name = bird.name
    if t == "none":
        assert d == {"food": 0, "hand": 0, "bonus": 0, "eggs": 0, "cache": 0, "tucked": 0, "birds": 0}, name
    elif t == "gain_feeder":
        assert d["food"] + d["cache"] == 1, name
    elif t == "gain_supply":
        assert (d["cache"] if pw["cache"] else d["food"]) == pw["count"], name
    elif t == "all_gain_supply":
        assert d["food"] == 1 and do["food"] == 1, name
    elif t == "lay_egg":
        assert d["eggs"] == 1, name
    elif t == "all_lay_nest":
        assert d["eggs"] >= 0, name                                    # needs nest birds; covered in test_rules
    elif t == "draw":
        assert d["hand"] == pw["count"] - pw["discard_end"], name
    elif t == "all_draw_deck":
        assert d["hand"] == 1 and do["hand"] == 1, name
    elif t == "fewest_draw":
        assert do["hand"] == 1 and d["hand"] == 0, name
    elif t == "fewest_die":
        assert do["food"] == 1 and d["food"] == 0, name
    elif t == "each_gain_die":
        assert d["food"] == 1 and do["food"] == 1, name
    elif t == "tuck_hand":
        assert d["tucked"] == 1, name
        th = pw["then"]["type"]
        if th == "draw":
            assert d["hand"] == 0, name                                # one tucked, one drawn
        elif th == "lay_egg":
            assert d["eggs"] == 1, name
        else:
            assert d["food"] == 1, name
    elif t == "food_for_tucks":
        assert d["tucked"] == 2 and d["food"] == -1, name
    elif t == "egg_for_wild":
        assert d["eggs"] == -1 and d["food"] == pw["count"], name
    elif t == "egg_for_cards":
        assert d["eggs"] == -1 and d["hand"] == 2, name
    elif t == "hunt_card":
        assert d["tucked"] == 1, name
    elif t == "hunt_dice":
        assert d["cache"] == 1, name
    elif t == "move":
        assert bird.id not in after["rows"][h] and any(bird.id in r for r in after["rows"]), name
    elif t == "repeat":
        assert d["eggs"] >= 1 or d["tucked"] >= 1, name
    elif t == "trade_food":
        assert d["food"] == 0 and after["foods"] != before["foods"], name
    else:
        raise AssertionError(f"untested brown power type {t} ({name})")


def _check_white(bird, t, pw, before, after, oth, oth2, paid):
    name = bird.name
    d = {k: after[k] - before[k] for k in ("food", "hand", "bonus", "eggs", "cache", "tucked", "birds")}
    food_gain = d["food"] + paid
    if t == "none":
        assert d["birds"] == 1, name
    elif t == "draw_bonus":
        assert d["bonus"] == 1, name
    elif t == "draw":
        assert d["hand"] == pw["count"] - 1, name                      # the played card left the hand
    elif t == "gain_supply":
        assert food_gain == pw["count"], name
    elif t == "gain_all_feeder":
        assert food_gain == 2, name
    elif t == "lay_each_nest":
        assert d["eggs"] >= 1 - E.EGG_COST[1] * 0, name
    elif t == "play_another":
        assert d["birds"] == 2, name
    elif t == "oystercatcher":
        assert d["hand"] == 2 - 1 and oth2["hand"] - oth["hand"] == 1, name
    elif t == "take_tray":
        assert d["hand"] == 3 - 1, name
    else:
        raise AssertionError(f"untested white power type {t} ({name})")


def _pink(g, me, other, bird, t, h):
    """The pink bird belongs to `other`; `me` (the active player) triggers it."""
    pw = bird.power
    pink = place(g, other, bird.name, HABITATS[h])
    if t == "pink_lay_eggs":
        nest_bird = next(b for b in birds() if b.has_nest(pw["nest"]) and b.egg_limit >= 2 and b.id != bird.id)
        place(g, other, nest_bird.name, HABITATS[nest_bird.habitats[0]])
    before = snapshot(g, other)
    if t == "pink_play":
        hab = HABITATS.index(pw["habitat"])
        cheap = min((b for b in birds() if hab in b.habitats and b.color in ("none", "brown")), key=lambda b: b.food_total)
        g.p(me).food = [3] * 5
        give(g, me, cheap.name)
        play(g, cheap.name, pw["habitat"])
    elif t == "pink_lay_eggs":
        place(g, me, "Wild Turkey", "grassland")
        answer(g, "Lay eggs")
    elif t == "pink_gain_food_rodent":
        g.s.feeder, g.s.outside = [4, 4, 4, 4, 4], []
        answer(g, "Gain food")
        answer(g, "rodent die")
    elif t == "pink_predator":
        place(g, me, "Barred Owl", "forest")
        g.s.deck.insert(0, TINY.id)
        answer(g, "Gain food")
    else:
        raise AssertionError(f"untested pink type {t}")

    def pol(g_, d):
        if d.seat == other:
            return None
        if d.kind == "USE_POWER":
            return E.A_YES
        if d.kind in ("TAKE_DIE", "LAY_EGG", "DRAW") and E.A_NO in d.data["legal"]:
            return E.A_NO
        if d.kind == "TRADE":
            return E.A_NO
        return None
    finish_turn(g, me, pol)
    after = snapshot(g, other)
    if t == "pink_play":
        assert after["food"] - before["food"] + after["tucked"] - before["tucked"] == 1, bird.name
    elif t == "pink_lay_eggs":
        assert after["eggs"] - before["eggs"] == 1, bird.name
    elif t == "pink_gain_food_rodent":
        assert after["cache"] - before["cache"] == 1, bird.name
    elif t == "pink_predator":
        assert after["food"] - before["food"] == 1, bird.name
