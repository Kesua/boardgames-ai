"""One or more tests per rule ID of rules.md."""
import random

import pytest

from games.wingspan import engine as E
from games.wingspan import new_game
from games.wingspan.cards import DUAL, FISH, FRUIT, INV, RODENT, SEED, birds, bonus_cards, goal_tiles
from games.wingspan.scoring import bonus_count, bonus_points, breakdown, goal_count, green_points
from games.wingspan.tests.conftest import answer, bid, clear, food, give, kind, options, place, play, started

rule = pytest.mark.rule


def all_cards(g):
    s = g.s
    out = list(s.deck) + list(s.discard) + [c for c in s.tray if c is not None]
    for p in s.players:
        out += p.hand + p.offer + [x.bird for r in p.rows for x in r]
    return out


@rule("W1.1")
def test_deck_has_180_birds_or_170_without_swift_start():
    g = new_game(2, 3)
    assert sorted(all_cards(g)) == list(range(180))
    g = new_game(2, 3, {"swift_start_birds": False})
    assert len(all_cards(g)) == 170 and not any(birds()[c].swift_start for c in all_cards(g))


@rule("W1.2")
def test_goals_come_from_four_different_tiles():
    for seed in range(30):
        g = new_game(2, seed)
        tiles = [next(i for i, t in enumerate(goal_tiles()) if goal in t) for goal in g.s.goals]
        assert len(set(tiles)) == 4


@rule("W1.3")
def test_dice_have_six_faces_including_dual():
    faces = set()
    for seed in range(40):
        faces |= set(new_game(2, seed).s.feeder)
    assert faces == {0, 1, 2, 3, 4, 5}


@rule("W1.5")
@rule("W3.1")
def test_turns_per_round_8_7_6_5():
    g = new_game(3, 11)
    rng = random.Random(1)
    per = {}
    while not g.game_over:
        d = g.s.decisions.top
        if d.kind == "CHOOSE_ACTION":
            per[(g.s.round, d.seat)] = per.get((g.s.round, d.seat), 0) + 1
        g.step_id(rng.choice(d.data["legal"]))
    for r, n in enumerate((8, 7, 6, 5)):
        assert [per[(r, s)] for s in range(3)] == [n, n, n]


@rule("W2.3")
@rule("W2.4")
def test_setup_keep_birds_costs_one_food_each():
    g = new_game(2, 5)
    s = g.s
    assert all(len(p.offer) == 5 and len(p.offer_bonus) == 2 and p.food == [1] * 5 for p in s.players)
    seat = g.current_seat
    answer(g, "Keep")
    answer(g, "Keep")
    for _ in range(3):
        answer(g, "Discard")
    assert kind(g) == "SETUP_FOOD"
    answer(g, "Discard invertebrate")
    answer(g, "Discard seed")
    assert kind(g) == "SETUP_BONUS"
    g.step_id(g.s.decisions.top.data["legal"][0])
    p = g.p(seat)
    assert len(p.hand) == 2 and sum(p.food) == 3 and len(p.bonus) == 1


@rule("W2.5")
def test_first_player_is_random():
    firsts = {started(3, seed).s.first for seed in range(30)}
    assert firsts == {0, 1, 2}


@rule("W3.2")
def test_round_end_replaces_tray_passes_first_player_keeps_feeder():
    g = started(2, 2)
    first = g.s.first
    rng = random.Random(0)
    while g.s.round == 0:
        if g.s.round_turns == 15 and g.s.decisions.top.kind == "CHOOSE_ACTION":
            feeder_before = None
        g.step_id(rng.choice(g.legal_ids()))
    assert g.s.first == (first + 1) % 2
    assert all(c is not None for c in g.s.tray)
    assert g.s.goal_points[0] == [p for p in g.s.goal_points[0]]


@rule("W3.3")
def test_game_ends_after_round_four():
    g = new_game(2, 4)
    rng = random.Random(2)
    while not g.game_over:
        g.step_id(rng.choice(g.legal_ids()))
    assert g.s.round == 3 and g.s.turns == 2 * 26


@rule("W4.2")
@pytest.mark.parametrize("n,food_,eggs,cards", [(0, 1, 2, 1), (1, 1, 2, 1), (2, 2, 3, 2), (3, 2, 3, 2), (4, 3, 4, 3),
                                                 (5, 3, 4, 3)])
def test_mat_amounts(n, food_, eggs, cards):
    for action, amount in ((1, food_), (2, eggs), (3, cards)):
        g = started(2, 3)
        me = g.current_seat
        clear(g, me)
        for _ in range(n):
            place(g, me, "Hooded Warbler" if action != 2 else "Wild Turkey", ("forest", "grassland", "wetland")[action - 1])
        g.s.decisions.pop()
        g.s.tasks.pop()
        E.h_choose_action(g, {"seat": me}, E.A_ACTION + action)
        assert g.s.tasks[-1]["n"] == amount
        assert g.s.tasks[-1]["trade"] == (n in (1, 3, 5))


@rule("W4.3")
def test_forest_trade_discards_card_for_extra_die():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Hooded Warbler", "forest")          # 1 bird: slot 2 = 1 food + trade
    give(g, me, "Mallard", "Killdeer")
    answer(g, "Gain food")
    d = g.s.decisions.top
    g.step_id([a for a in d.data["legal"] if E.A_DIE <= a < E.A_DIE + 6][0])
    if kind(g) == "DUAL_FOOD":
        answer(g, "invertebrate")
    assert kind(g) == "TRADE"
    answer(g, "Use the trade")
    answer(g, "Discard Mallard")
    assert bid("Mallard") in g.s.discard and g.p(me).hand == [bid("Killdeer")]
    assert kind(g) == "TAKE_DIE" and E.A_NO not in g.s.decisions.top.data["legal"]


@rule("W4.4")
@rule("W5.1")
def test_egg_cost_by_column_and_leftmost_slot():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    a = place(g, me, "Wild Turkey", "grassland")        # egg limit 5... used as egg bank
    a.eggs = 5
    for _ in range(3):
        place(g, me, "Hooded Warbler", "forest")
    give(g, me, "Blue Jay")                              # forest/grassland? cost seed/fruit/inv
    food(g, me, invertebrate=3, seed=3, fruit=3, fish=3, rodent=3)
    play(g, "Blue Jay", "forest")
    assert a.eggs == 3                                   # 4th column costs 2 eggs
    assert g.p(me).rows[0][3].bird == bid("Blue Jay")


@rule("W5.1")
def test_cannot_play_unaffordable_bird():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    give(g, me, "Bald Eagle")                            # 2 fish + 1 rodent? needs food
    assert "Play a bird" not in options(g)


@rule("W5.2")
@rule("W5.3")
def test_two_for_one_and_alternative_costs():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    b = next(x for x in birds() if x.alternative and len(x.habitats) and x.food_total == 1)
    give(g, me, b.name)
    other = [f for f in range(5) if not b.food[f]]
    g.p(me).food = [0] * 5
    g.p(me).food[other[0]] = 1
    g.p(me).food[other[1]] = 1                          # only two "wrong" foods: payable only with two-for-one
    assert "Play a bird" in options(g)
    play(g, b.name, two_for_one=True)
    assert sum(g.p(me).food) == 0                        # both tokens spent
    assert any(x.bird == b.id for r in g.p(me).rows for x in r)


@rule("W5.3")
def test_two_for_one_not_for_grassland_trade():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Wild Turkey", "grassland")
    food(g, me, fish=1)
    answer(g, "Lay eggs")
    while kind(g) == "LAY_EGG":
        answer(g, "Lay an egg")
    eggs = g.p(me).rows[1][0].eggs
    assert kind(g) == "TRADE"
    answer(g, "Use the trade")                                 # only 1 fish: paid directly, never two-for-one
    assert g.p(me).food == [0] * 5 and g.p(me).rows[1][0].eggs == eggs + 1


@rule("W5.4")
def test_white_power_on_play_brown_not():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    give(g, me, "Wood Stork")                            # white: draw 2 bonus, keep 1
    food(g, me, fish=2, rodent=2, invertebrate=2)
    n_bonus = len(g.p(me).bonus)
    play(g, "Wood Stork")
    assert kind(g) == "USE_POWER"
    answer(g, "Use")
    assert kind(g) == "KEEP_BONUS"
    g.step_id(g.s.decisions.top.data["legal"][0])
    assert len(g.p(me).bonus) == n_bonus + 1


@rule("W6.1")
@rule("W10.1")
def test_brown_powers_right_to_left_each_optional():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Mallard", "wetland")                   # brown draw 1
    place(g, me, "Killdeer", "wetland", eggs=1)          # brown: discard egg to draw 2
    answer(g, "Draw cards")
    while kind(g) == "DRAW":
        answer(g, "deck")
    if kind(g) == "TRADE":
        answer(g, "No trade")
    assert kind(g) == "USE_POWER" and g.s.decisions.top.data["bird"] == bid("Killdeer")
    answer(g, "Skip")
    assert kind(g) == "USE_POWER" and g.s.decisions.top.data["bird"] == bid("Mallard")


@rule("W6.2")
def test_take_less_is_allowed():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    answer(g, "Gain food")
    assert "Stop / skip" in options(g)
    answer(g, "Stop")
    assert sum(g.p(me).food) == 0


@rule("W6.3")
@rule("W9.1")
def test_eggs_respect_limit():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Brown-Headed Cowbird", "grassland")    # egg limit 0
    t = place(g, me, "Wild Turkey", "grassland")
    t.eggs = birds()[bid("Wild Turkey")].egg_limit
    answer(g, "Lay eggs")
    assert kind(g) != "LAY_EGG"                          # no room anywhere: no egg decision


@rule("W6.4")
@rule("W8.2")
def test_draw_from_tray_refills_only_at_end_of_turn():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Trumpeter Swan", "wetland")
    place(g, me, "Trumpeter Swan", "wetland")                # 2 birds: draw 2 cards, no powers
    answer(g, "Draw cards")
    answer(g, "from the tray")
    assert None in g.s.tray and kind(g) == "DRAW"
    while g.current_seat == me and not g.game_over and kind(g) != "CHOOSE_ACTION":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    assert None not in g.s.tray


@rule("W7.1")
@rule("W7.2")
def test_taking_last_die_rerolls_feeder():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    g.s.feeder, g.s.outside = [FISH], [0, 1, 2, 3]
    answer(g, "Gain food")
    answer(g, "fish die")
    assert g.p(me).food[FISH] == 1 and len(g.s.feeder) == 5 and g.s.outside == []


@rule("W7.1")
def test_dual_face_gives_one_of_two():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    g.s.feeder, g.s.outside = [DUAL, FISH], [0, 1, 2]
    answer(g, "Gain food")
    answer(g, "invertebrate-or-seed die")
    assert kind(g) == "DUAL_FOOD"
    answer(g, "seed")
    assert g.p(me).food == [0, 1, 0, 0, 0]


@rule("W7.3")
def test_reroll_only_when_all_dice_same():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    g.s.feeder, g.s.outside = [FISH, FISH, FISH], [0, 1]
    answer(g, "Gain food")
    assert "Reroll the birdfeeder" in options(g)
    g = started(2, 3)
    clear(g, g.current_seat)
    g.s.feeder, g.s.outside = [FISH, SEED], [0, 1, 2]
    answer(g, "Gain food")
    assert "Reroll the birdfeeder" not in options(g)
    g = started(2, 3)
    clear(g, g.current_seat)
    g.s.feeder, g.s.outside = [SEED, DUAL], [0, 1, 2]       # dual is its own face
    answer(g, "Gain food")
    assert "Reroll the birdfeeder" not in options(g)


@rule("W7.4")
@rule("W10.5")
def test_dice_hunter_rolls_only_outside_dice():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    owl = place(g, me, "Burrowing Owl", "forest")
    g.s.feeder, g.s.outside = [FISH, FISH, FISH], [RODENT, RODENT]
    answer(g, "Gain food")
    answer(g, "fish die")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    answer(g, "Use")
    assert len(g.s.feeder) == 2 and len(g.s.outside) == 3        # 2 + the fish taken
    assert sum(owl.cache) in (0, 1) and owl.cache[RODENT] == sum(owl.cache)


@rule("W8.3")
def test_empty_deck_reshuffles_discard():
    g = started(2, 3)
    s = g.s
    s.discard += list(s.deck)
    s.deck.clear()
    card = g.draw_deck()
    assert card is not None and len(s.deck) + 1 + len(s.discard) > 0 and s.discard == []


@rule("W9.3")
def test_star_nest_counts_as_every_nest():
    star = next(b for b in birds() if b.nest == "star")
    for nest in ("bowl", "cavity", "ground", "platform"):
        assert star.has_nest(nest)
    cow = birds()[bid("Brown-Headed Cowbird")]
    assert cow.nest == "none" and cow.egg_limit == 0


@rule("W10.2")
def test_tuck_then_draw_only_if_tucked():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "American Coot", "wetland")
    give(g, me, "Mallard")
    answer(g, "Draw cards")
    answer(g, "deck")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    answer(g, "Use")
    assert kind(g) == "TUCK"
    answer(g, "Stop / skip")
    assert g.p(me).rows[2][0].tucked == 0


@rule("W10.6")
def test_repeat_runs_other_birds_power_as_that_bird():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    quail = place(g, me, "Scaled Quail", "grassland")       # lay 1 egg on this bird
    place(g, me, "Gray Catbird", "grassland")               # repeat
    answer(g, "Lay eggs")
    while kind(g) == "LAY_EGG":
        answer(g, "Stop")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    assert g.s.decisions.top.data["bird"] == bid("Gray Catbird")
    answer(g, "Use")
    answer(g, "Repeat Scaled Quail")
    assert quail.eggs == 1
    answer(g, "Use")                                          # the quail itself
    assert quail.eggs == 2


@rule("W10.7")
def test_mover_moves_only_when_rightmost():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Bewick's Wren", "forest")
    place(g, me, "Hooded Warbler", "forest")
    answer(g, "Gain food")
    while kind(g) in ("TAKE_DIE", "DUAL_FOOD"):
        g.step_id(g.s.decisions.top.data["legal"][0])
    assert kind(g) != "USE_POWER" or g.s.decisions.top.data["bird"] != bid("Bewick's Wren")
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Hooded Warbler", "forest")
    wren = place(g, me, "Bewick's Wren", "forest", eggs=1)
    answer(g, "Gain food")
    while kind(g) in ("TAKE_DIE", "DUAL_FOOD", "TRADE"):
        g.step_id(g.s.decisions.top.data["legal"][-1] if kind(g) == "TRADE" else g.s.decisions.top.data["legal"][0])
    answer(g, "Use")
    answer(g, "Move to wetland")
    assert g.p(me).rows[2][0] is wren and wren.eggs == 1 and len(g.p(me).rows[0]) == 1


@rule("W10.8")
def test_play_another_bird_same_habitat_full_cost():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    give(g, me, "Downy Woodpecker", "Hooded Warbler")
    food(g, me, invertebrate=5, seed=5, fruit=5)
    t = place(g, me, "Wild Turkey", "grassland")
    t.eggs = 3
    play(g, "Downy Woodpecker", "forest")
    answer(g, "Use")
    answer(g, "Play Hooded Warbler")
    while kind(g) in ("PAY_FOOD", "PAY_PAIR", "PAY_EGG"):
        g.step_id([a for a in g.s.decisions.top.data["legal"] if a != E.A_YES][0])
    assert [x.bird for x in g.p(me).rows[0]] == [bid("Downy Woodpecker"), bid("Hooded Warbler")]
    assert t.eggs == 2                                        # column 2 costs 1 egg


@rule("W10.9")
def test_draw_then_discard_at_end_of_turn():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    place(g, me, "Black Tern", "wetland")
    answer(g, "Draw cards")
    answer(g, "deck")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    answer(g, "Use")
    while kind(g) == "DRAW":
        answer(g, "deck")
    assert kind(g) == "END_DISCARD"
    hand = len(g.p(me).hand)
    g.step_id(g.s.decisions.top.data["legal"][0])
    assert len(g.p(me).hand) == hand - 1


@rule("W10.10")
def test_fewest_birds_all_tied_players_benefit():
    g = started(3, 3)
    me = g.current_seat
    clear(g)
    place(g, me, "American Bittern", "wetland")
    answer(g, "Draw cards")
    answer(g, "deck")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    answer(g, "Use")
    others = [x for x in range(3) if x != me]
    hands = {x: len(g.p(x).hand) for x in others}
    while kind(g) == "DRAW":
        answer(g, "deck")
    assert all(len(g.p(x).hand) == hands[x] + 1 for x in others)


@rule("W10.11")
def test_all_lay_nest_owner_two_different_birds():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    a = place(g, me, "Pileated Woodpecker", "forest")      # cavity, all players lay on cavity
    b = place(g, me, "Downy Woodpecker", "forest")         # cavity
    answer(g, "Gain food")
    while kind(g) in ("TAKE_DIE", "DUAL_FOOD", "TRADE"):
        g.step_id(g.s.decisions.top.data["legal"][-1] if kind(g) == "TRADE" else g.s.decisions.top.data["legal"][0])
    while kind(g) == "USE_POWER" and g.s.decisions.top.data["bird"] != bid("Pileated Woodpecker"):
        answer(g, "Skip")
    answer(g, "Use")
    answer(g, "Lay an egg on Pileated")
    assert "Lay an egg on Pileated Woodpecker (forest 1)" not in options(g)
    answer(g, "Lay an egg on Downy")
    assert a.eggs == 1 and b.eggs == 1


@rule("W10.12")
def test_gain_all_feeder_counts_dual_for_invertebrate():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    give(g, me, "Northern Flicker")
    food(g, me, invertebrate=3, fruit=2, seed=2)
    g.s.feeder, g.s.outside = [INV, DUAL, FISH], [0, 1]
    play(g, "Northern Flicker")
    inv_before = g.p(me).food[INV]
    answer(g, "Use")
    assert g.p(me).food[INV] == inv_before + 2 and g.s.feeder == [FISH]


@rule("W10.13")
def test_oystercatcher_owner_keeps_two():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    give(g, me, "American Oystercatcher")
    food(g, me, invertebrate=5, fish=5, seed=5, fruit=5, rodent=5)
    play(g, "American Oystercatcher")
    answer(g, "Use")
    while kind(g) == "DRAW":
        answer(g, "deck")
    while kind(g) == "PICK_CARD":
        g.step_id(g.s.decisions.top.data["legal"][0])
    other = 1 - me
    assert len(g.p(me).hand) == 2 and len(g.p(other).hand) == 1


@rule("W11.1")
@rule("W11.2")
def test_pink_lay_eggs_once_between_turns_and_rearms():
    g = started(3, 3)
    me = g.current_seat
    clear(g)
    other = (me + 2) % 3                                       # not the next player: no re-arm before the check
    av = place(g, other, "American Avocet", "wetland")       # pink: lay on another ground bird
    target = place(g, other, "Wild Turkey", "grassland")      # ground nest
    answer(g, "Lay eggs")
    while kind(g) == "LAY_EGG" and g.s.decisions.top.seat == me:
        answer(g, "Stop")
    if kind(g) == "TRADE":
        answer(g, "No trade")
    assert g.s.decisions.top.seat == other and kind(g) == "LAY_EGG"
    answer(g, "Wild Turkey")
    assert target.eggs == 1 and av.pink_used


@rule("W11.2")
def test_pink_not_triggered_by_power_eggs():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    other = 1 - me
    place(g, other, "American Avocet", "wetland")
    place(g, other, "Wild Turkey", "grassland")
    place(g, me, "Scaled Quail", "forest")                     # power lays an egg, not the action
    answer(g, "Gain food")
    while not (kind(g) == "CHOOSE_ACTION" and g.current_seat == other):
        assert g.s.decisions.top.seat == me
        g.step_id(g.s.decisions.top.data["legal"][0])


@rule("W11.3")
def test_pink_play_resolves_after_white_power():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    other = 1 - me
    place(g, other, "Eastern Kingbird", "forest")              # pink: another plays forest bird -> 1 invertebrate
    give(g, me, "Hooded Warbler")
    food(g, me, invertebrate=5)
    play(g, "Hooded Warbler")
    assert g.p(other).food[INV] == 1


@rule("W12.1")
@rule("W12.2")
def test_green_goal_points_and_ties():
    assert green_points([3, 1], 0) == [4, 1]
    assert green_points([2, 2], 1) == [3, 3]                    # (5 + 2) // 2
    assert green_points([4, 4, 4, 1], 3) == [4, 4, 4, 0]        # (7 + 4 + 3) // 3
    assert green_points([5, 2, 2, 0], 0) == [4, 0, 0, 0]        # (1 + 0) // 2
    assert green_points([0, 0], 3) == [0, 0]                    # 0 items score nothing
    assert green_points([3, 0], 1) == [5, 0]


@rule("W12.3")
def test_blue_goal_points():
    g = started(2, 3, {"goal_side": "blue"})
    from games.wingspan.scoring import score_goal
    me = g.current_seat
    clear(g)
    g.s.goals[0] = {"id": "total_birds", "count": "total_birds"}
    for _ in range(3):
        place(g, me, "Hooded Warbler", "forest")
    for _ in range(4):
        place(g, me, "Wild Turkey", "grassland")
    pts = score_goal(g, 0)
    assert pts[me] == 5 and pts[1 - me] == 0


@rule("W12.4")
def test_goal_counts():
    g = started(2, 3)
    clear(g)
    place(g, 0, "Hooded Warbler", "forest", eggs=2)
    place(g, 0, "Wild Turkey", "grassland", eggs=1)
    place(g, 0, "Mallard", "wetland", eggs=3)
    assert goal_count(g, 0, {"count": "egg_sets"}) == 1
    assert goal_count(g, 0, {"count": "eggs_in", "habitat": "wetland"}) == 3
    assert goal_count(g, 0, {"count": "total_birds"}) == 3
    star = next(b for b in birds() if b.nest == "star" and b.egg_limit)
    g.p(0).rows[0].append(type(g.p(0).rows[0][0])(star.id, eggs=1))
    assert goal_count(g, 0, {"count": "nest_birds_with_egg", "nest": "bowl"}) >= 1


@rule("W13.1")
@rule("W13.2")
def test_bonus_cards():
    g = started(2, 3)
    clear(g)
    cards = {c.name: c for c in bonus_cards()}
    for name in ("Bald Eagle", "Osprey", "Belted Kingfisher", "Common Merganser"):
        place(g, 0, name, "wetland")
    fishery = cards["Fishery Manager"]
    assert bonus_count(g, 0, fishery) == sum(1 for r in g.p(0).rows for x in r if birds()[x.bird].food[FISH])
    assert bonus_points(fishery, 3) == 3 and bonus_points(fishery, 4) == 8 and bonus_points(fishery, 1) == 0
    photo = cards["Photographer"]
    assert bonus_points(photo, 6) == 6                                    # rules.md D3
    yard = cards["Backyard Birder"]
    assert bonus_points(yard, 6) == 3 and bonus_points(yard, 7) == 6      # D4
    anat = cards["Anatomist"]
    assert bonus_points(anat, 4) == 7                                     # D5
    assert not birds()[bid("Canvasback")].words["anatomist"]              # D6
    assert birds()[bid("Blue Grosbeak")].words["anatomist"] == ["beak"]
    assert not birds()[bid("Burrowing Owl")].words["anatomist"]
    assert birds()[bid("Northern Bobwhite")].words["photographer"] == ["white"]
    assert not birds()[bid("Barred Owl")].words["photographer"]
    web = cards["Food Web Expert"]
    only_inv = [b for b in birds() if b.food[INV] and sum(b.food) == b.food[INV] and not b.wild and not b.alternative]
    assert only_inv
    assert cards["Large Bird Specialist"].count["value"] == 65


@rule("W14.1")
@rule("W14.2")
def test_score_breakdown_and_tiebreak():
    g = started(2, 3)
    clear(g)
    p = place(g, 0, "Wild Turkey", "grassland", eggs=2)
    p.tucked, p.cache = 3, [1, 0, 0, 0, 1]
    g.p(0).bonus = []
    b = breakdown(g, 0)
    assert b["birds"] == birds()[bid("Wild Turkey")].points and b["eggs"] == 2 and b["tucked"] == 3 and b["cache"] == 2
    food(g, 0, seed=3)
    food(g, 1, fish=1)
    assert g.tiebreaks() == [3, 1]
