"""Readings settled by the independent engine review (checks/review.md, findings F1-F18; rules.md T17 D20-D33).
One test per finding; each failed on the reviewed engine and passes after the fix."""
import numpy as np
import pytest

from games.through_the_ages import economy as E
from games.through_the_ages import effects
from games.through_the_ages import engine as En
from games.through_the_ages import military as M
from games.through_the_ages import politics as P
from games.through_the_ages.cards import EFFECT, KEY, SCIENCE_COST, STAGE_COSTS
from games.through_the_ages.encoder import M_INDEX, StateEncoder
from games.through_the_ages.tests.conftest import (answer, cid, give, has, kind, options, place, reveal_now, run_now,
                                                   touch)
from games.through_the_ages.tests.test_cards_civil import complete, game, hand, lead, own_action, play, res, st
from games.through_the_ages.tests.test_cards_military import make_pact

card = pytest.mark.card
rule = pytest.mark.rule


# ------------------------------------------------------------------------------------------------- F1
@rule("T5.7")
@card("engineering_genius_a")
def test_f1_engineering_genius_builds_exactly_one_stage_even_with_a_construction_technology():
    g, s, _ = game()
    place(g, s, "Masonry")                                                        # 2 stages per wonder action
    p = g.p(s)
    w = cid("Pyramids")
    p.unfinished = [w, 0, 0]
    res(g, s, 10)
    r0 = E.resources(p)
    hand(g, s, cid("Engineering Genius", "A"))
    answer(g, "Play action card Engineering Genius")
    assert p.unfinished[1] == 1 and r0 - E.resources(p) == max(0, STAGE_COSTS[w][0] - 2)
    assert has(g, "Build a wonder stage")                                         # the normal action: still 2
    answer(g, "Build a wonder stage")
    assert kind(g) == "STAGES" and len(options(g)) == 2


# ------------------------------------------------------------------------------------------------- F2
@rule("T4.2")
@card("charles_darwin_ii")
def test_f2_darwin_take_discount_is_offered_with_one_civil_action_left_and_in_international_agreement():
    g, s, _ = game()
    lead(g, s, "charles_darwin_ii")
    p = g.p(s)
    p.civil_spent = E.stats(g, s).civil - 1                                       # exactly 1 civil action left
    touch(g, s)
    g.s.row[6] = cid("Alchemy")                                                   # slot 7: 2 -> 1 with Darwin
    assert g.take_cost(s, 6) == 1 and 6 in g.take_slots(s)
    assert has(g, "Take Alchemy")
    assert 6 in g.take_slots(s, budget=1)                                         # International Agreement budget


# ------------------------------------------------------------------------------------------------- F3
@card("st_peter_s_basilica_i")
@card("charles_darwin_ii")
def test_f3_darwin_and_st_peters_cancel_on_temples():
    g, s, _ = game()
    p = g.p(s)
    p.workers[cid("Religion")] = 1
    p.yellow_bank -= 1
    touch(g, s)
    h0 = st(g, s).happiness                                                       # Religion: 1 face
    place(g, s, "St. Peter's Basilica")
    lead(g, s, "charles_darwin_ii")
    assert st(g, s).happiness == h0 + 1                                           # printed 1 + St. Peter's own face


# ------------------------------------------------------------------------------------------------- F4
@card("hollywood_iii")
def test_f4_hollywood_counts_leader_culture_bonuses_of_theaters_and_libraries():
    g, s, _ = game()
    place(g, s, "Drama", workers=2)                                               # 2 culture each
    lead(g, s, "charlie_chaplin_iii")                                             # best theater doubled: +2
    c0 = g.p(s).culture
    complete(g, s, "hollywood_iii")
    assert g.p(s).culture - c0 == 2 * (2 + 2 + 2)


@card("internet_iii")
def test_f4_internet_counts_leader_science_bonuses_of_urban_buildings():
    g, s, _ = game()
    place(g, s, "Printing Press", workers=1)                                      # 1 culture, 1 science
    lead(g, s, "isaac_newton_ii")                                                 # best lab/library: +1 science
    c0 = g.p(s).culture
    complete(g, s, "internet_iii")
    assert g.p(s).culture - c0 == 1 + (1 + 1) + 1                                 # Philosophy, Printing Press, Newton


# ------------------------------------------------------------------------------------------------- F5
@rule("T5.9")
@card("development_of_civilization_a")
def test_f5_development_of_civilization_allows_a_revolution_one_science_cheaper():
    g, s, _ = game()
    p = g.p(s)
    mon = hand(g, s, cid("Monarchy"))
    p.science = 1                                                                 # revolution 2 - 1; peaceful 8 - 1: no
    touch(g, s)
    assert p.civil_spent == 0
    reveal_now(g, "Development of Civilization")
    answer(g, "Develop a technology (1 science less)")
    if kind(g) == "SUB_ACTION" and has(g, "Develop Monarchy"):
        answer(g, "Develop Monarchy")
    assert p.government == mon and p.science == 0 and p.civil_spent == st(g, s).civil


# ------------------------------------------------------------------------------------------------- F6, F18
@rule("T11.6")
@card("maximilien_robespierre_ii")
def test_f6_robespierre_revolution_keeps_patriotisms_military_action():
    g, s, _ = game()
    lead(g, s, "maximilien_robespierre_ii")
    p = g.p(s)
    play(g, s, "patriotism_a")
    p.military_spent = 0
    hand(g, s, cid("Monarchy"))
    p.science = 10
    touch(g, s)
    answer(g, "Change government to Monarchy")
    if kind(g) == "REVOLT":
        answer(g, "Revolution")
    assert p.temp_military == 1 and E.military_available(g, s) == 1


@rule("T5.10")
@card("maximilien_robespierre_ii")
@card("breakthrough_i")
def test_f6_robespierre_revolution_through_breakthrough_costs_no_civil_action():
    g, s, _ = game()
    lead(g, s, "maximilien_robespierre_ii")
    p = g.p(s)
    p.civil_spent = p.military_spent = 0
    hand(g, s, cid("Breakthrough", "I"))
    mon = hand(g, s, cid("Monarchy"))
    p.science = 10
    touch(g, s)
    answer(g, "Play action card Breakthrough")
    if kind(g) == "SUB_ACTION":
        answer(g, "Develop Monarchy")
    if kind(g) == "REVOLT":
        answer(g, "Revolution")
    assert p.government == mon and p.civil_spent == 0 and E.military_available(g, s) == 0


@rule("T11.6")
@card("hammurabi_a")
def test_f18_hammurabis_temporary_civil_action_survives_a_revolution():
    g, s, _ = game()
    lead(g, s, "hammurabi_a")
    p = g.p(s)
    p.civil_spent = p.military_spent = 0
    touch(g, s)
    answer(g, "Hammurabi")
    hand(g, s, cid("Monarchy"))
    p.science = 10
    touch(g, s)
    answer(g, "Change government to Monarchy")
    if kind(g) == "REVOLT":
        answer(g, "Revolution")
    assert p.temp_civil == 1 and E.civil_available(g, s) == 1


# ------------------------------------------------------------------------------------------------- F7
@rule("T7.1")
@card("pierre_de_coubertin_iii")
def test_f7_olympics_can_be_declared_after_the_political_action_was_given_up():
    g, s, _ = game()
    lead(g, s, "pierre_de_coubertin_iii")
    p = g.p(s)
    p.forfeit_politics = 1
    own_action(g, s, ("POLITICS", "ACTION"))
    assert kind(g) == "POLITICS" and g.current_seat == s
    assert sorted(options(g)) == sorted(["Pass the political action", En.VERB_TEXT["OLYMPICS"]])
    c0 = p.culture
    answer(g, "Pierre de Coubertin")
    assert p.culture == c0 + 8 and g.s.olympics is not None and kind(g) == "ACTION"


# ------------------------------------------------------------------------------------------------- F8
@card("silk_road_i")
@card("endowment_for_the_arts_iii")
def test_f8_silk_road_adds_one_to_a_per_civilization_total_of_zero():
    g, s, _ = game()
    place(g, s, "Silk Road")
    g.p(s).culture = 50                                                           # nobody has more
    c0 = g.p(s).culture
    play(g, s, "endowment_for_the_arts_iii")
    assert g.p(s).culture == c0 + 1


@card("silk_road_i")
@card("wave_of_nationalism_ii")
def test_f8_silk_road_adds_one_to_military_resources_per_stronger_civilization_of_zero():
    g, s, _ = game()
    place(g, s, "Silk Road")
    play(g, s, "wave_of_nationalism_ii")                                          # nobody is stronger
    assert g.p(s).temp.get("unit") == 1


# ------------------------------------------------------------------------------------------------- F9, F10
@card("homer_a")
def test_f9_homers_face_stays_on_a_ruined_wonder():
    g, s, _ = game()
    p = g.p(s)
    w = place(g, s, "Pyramids")
    p.homer_wonder = w
    touch(g, s)
    h = st(g, s).happiness
    g.ruin_wonder(s, w)
    assert st(g, s).happiness == h


@card("international_tourism_iii")
def test_f10_international_tourism_counts_a_ruined_wonder():
    g, s, (o, _) = game(3)
    w = place(g, o, "Pyramids")
    make_pact(g, s, o, "International Tourism", "III")
    c = st(g, s).culture
    g.ruin_wonder(o, w)
    assert st(g, s).culture == c


@card("united_nations_iii")
def test_f10_united_nations_counts_a_ruined_wonder():
    g, s, _ = game()
    w = place(g, s, "Pyramids")
    g.ruin_wonder(s, w)
    c0 = g.p(s).culture
    complete(g, s, "united_nations_iii")
    assert g.p(s).culture - c0 == 4 * 2                                           # ruined Pyramids + itself


# ------------------------------------------------------------------------------------------------- F11
@card("james_watt_ii")
@card("machu_picchu_i")
def test_f11_james_watt_best_mine_counts_machu_picchus_extra_token():
    g, s, _ = game()
    place(g, s, "Machu Picchu")
    p = g.p(s)
    lead(g, s, "james_watt_ii")
    c0 = p.culture
    lead(g, s, "aristotle_a")                                                     # Watt leaves play
    assert p.culture - c0 == 2 * 1 + 1                                            # Bronze 2 workers + 1 extra token


# ------------------------------------------------------------------------------------------------- F12
@rule("T16.1")
@card("nostradamus_i")
def test_f12_nostradamus_does_not_learn_the_order_after_the_future_deck_is_shuffled():
    g, s, (q, _) = game(3)
    nos = cid("Nostradamus")
    g.p(q).leader = nos
    g.p(q).play_order.append(nos)
    touch(g)
    e1, e2 = cid("Good Harvest"), cid("Rats")
    g.s.current_events = [[cid("Development of Crafts"), None]]
    g.s.future_events = [[e1, s, [q]], [e2, s, [q]]]
    run_now(g, P.reveal, g, s)                                                    # the future deck becomes current
    assert {e[0] for e in g.s.current_events} == {e1, e2}
    enc = StateEncoder(3)
    v = enc.encode(g, q)
    known = enc.known_offset
    assert v[known + M_INDEX[e1]] == v[known + M_INDEX[e2]] == 0.5
    h = g.clone()
    h.s.current_events.reverse()
    assert np.array_equal(v, enc.encode(h, q))


# ------------------------------------------------------------------------------------------------- F13
@card("christopher_columbus_i")
def test_f13_columbus_colonization_records_the_territory():
    g, s, _ = game()
    lead(g, s, "christopher_columbus_i")
    a, b = give(g, s, ("Wealthy Territory", "I"), ("Vast Territory", "I"))
    own_action(g, s, ("POLITICS",))
    answer(g, "Columbus")
    assert sorted(g.record_info(x)["card"] for x in g.legal_ids()) == sorted([KEY[a], KEY[b]])
    g, s, _ = game()
    lead(g, s, "christopher_columbus_i")
    a = give(g, s, ("Wealthy Territory", "I"))[0]
    own_action(g, s, ("POLITICS",))
    g.drain_forced()
    answer(g, "Columbus")                                                         # one territory: forced
    assert [f["card"] for f in g.drain_forced() if f["action"].startswith("ABILITY_COLONIZE")] == [KEY[a]]


# ------------------------------------------------------------------------------------------------- F14
@card("johannes_gutenberg_i")
def test_f14_gutenberg_is_optional_and_can_wait_for_a_later_lab_action():
    g, s, _ = game()
    lead(g, s, "johannes_gutenberg_i")
    p = g.p(s)
    alchemy = cid("Alchemy")
    g.s.row[0] = alchemy
    g._dirty = True
    spent, cult = p.civil_spent, p.culture
    answer(g, "Take Alchemy")                                                     # a normal civil action
    assert p.civil_spent == spent + 1 and not p.flags.get("gutenberg_used") and p.culture == cult
    p.science = SCIENCE_COST[alchemy] - 1
    touch(g, s)
    assert not has(g, "Develop Alchemy")                                          # without him: 4 science
    answer(g, "Johannes Gutenberg")
    assert sorted(options(g)) == sorted(["End the action phase", "Develop Alchemy (I)",
                                         "Build a farm, mine or urban building"])
    spent = p.civil_spent
    answer(g, "Develop Alchemy")
    assert alchemy in p.techs and p.science == 0 and p.civil_spent == spent and p.culture == cult + 2
    assert not has(g, "Johannes Gutenberg")                                       # once per turn


@card("johannes_gutenberg_i")
@card("breakthrough_i")
def test_f14_gutenberg_pays_for_an_action_card_used_on_a_lab_or_library_with_both_benefits():
    g, s, _ = game()
    lead(g, s, "johannes_gutenberg_i")
    p = g.p(s)
    pp, iron = give(g, s, "Printing Press", "Iron")
    hand(g, s, cid("Breakthrough", "I"))
    p.science = SCIENCE_COST[pp] - 1
    touch(g, s)
    spent, cult = p.civil_spent, p.culture
    answer(g, "Johannes Gutenberg")
    answer(g, "Play action card Breakthrough")
    assert kind(g) != "SUB_ACTION" or options(g) == ["Develop Printing Press (I) (action card)"]
    if kind(g) == "SUB_ACTION":
        answer(g, "Develop Printing Press")
    assert pp in p.techs and iron in p.civil_hand and p.civil_spent == spent and p.culture == cult + 2
    assert p.science == 0 + EFFECT[cid("Breakthrough", "I")]["then_gain"]["science"]


@card("johannes_gutenberg_i")
def test_f14_gutenberg_alone_builds_a_lab_when_no_civil_action_is_left():
    g, s, _ = game()
    lead(g, s, "johannes_gutenberg_i")
    p = g.p(s)
    p.civil_spent = st(g, s).civil
    res(g, s, 3)
    touch(g, s)
    assert not has(g, "Build a farm")
    answer(g, "Johannes Gutenberg")
    answer(g, "Build a farm, mine or urban building")
    if kind(g) == "CHOOSE_TECH":
        answer(g, "on Philosophy")
    assert p.workers[cid("Philosophy")] == 2


# ------------------------------------------------------------------------------------------------- F15
@rule("T15.6")
@card("bill_gates_iii")
def test_f15_bill_gates_labs_produce_blue_tokens_like_mines():
    g, s, _ = game()
    lead(g, s, "bill_gates_iii")
    p = g.p(s)
    alchemy = place(g, s, "Alchemy", workers=2)
    assert st(g, s).resource_bonus == 0
    r0 = E.resources(p)
    E.produce_step(g, s, "mine")
    assert p.tokens.get(alchemy) == 2 and E.resources(p) == r0 + 2 + 2           # Bronze 2 workers + Alchemy 2
    assert effects.mine_production(g, s) == 2 and E.output(g, s, "mine") == 4     # Impact of Industry: mines only
    c0 = p.culture
    lead(g, s, "aristotle_a")                                                     # he leaves play
    assert p.culture == c0 + 2 and p.tokens.get(alchemy) == 2                     # resources stay usable
    E.produce_step(g, s, "mine")
    assert p.tokens.get(alchemy) == 2                                             # labs no longer produce
    E.pay(p, "mine", E.resources(p))
    assert not p.tokens.get(alchemy)


# ------------------------------------------------------------------------------------------------- F16
@rule("T6.4")
@card("sun_tzu_a")
def test_f16_sun_tzus_tactic_gives_its_bonus_to_whoever_copies_it_and_is_never_merged():
    g, s, (o,) = game()
    lead(g, s, "sun_tzu_a")
    band = give(g, s, "Fighting Band")[0]
    answer(g, "Play tactic Fighting Band")
    lead(g, s, "aristotle_a")                                                     # Sun Tzu goes under the band
    own_action(g, s)                                                              # it becomes common
    own_action(g, o)
    assert band in g.s.common_tactics and g.p(s).tactic_boost == band
    q = g.p(o)
    q.workers[cid("Warriors")] += 1                                               # 2 infantry: a Fighting Band army
    q.yellow_bank -= 1
    q.military_spent = 0
    touch(g, o)
    plain = M.army_forming(band, *M.unit_levels(q))[0]
    answer(g, "Copy a common tactic")
    if kind(g) == "CHOOSE_TACTIC":
        answer(g, "Fighting Band")
    assert q.tactic == band and st(g, o).army == plain + 1                        # +1 for the copier
    g2, s2, (o2,) = game()
    lead(g2, s2, "sun_tzu_a")
    band = give(g2, s2, "Fighting Band")[0]
    answer(g2, "Play tactic Fighting Band")
    lead(g2, s2, "aristotle_a")
    own_action(g2, o2)
    give(g2, o2, "Fighting Band")
    q = g2.p(o2)
    q.workers[cid("Warriors")] += 1
    q.yellow_bank -= 1
    q.military_spent = 0
    touch(g2, o2)
    answer(g2, "Play tactic Fighting Band")                                       # its own copy: not merged
    assert st(g2, o2).army == M.army_forming(band, *M.unit_levels(q))[0]


# ------------------------------------------------------------------------------------------------- F17
@card("trade_routes_agreement_i")
def test_f17_trade_routes_only_during_the_users_own_turn_and_without_a_per_turn_limit():
    g, s, (o, _) = game(3)
    make_pact(g, s, o, "Trade Routes Agreement", "I", "A")                        # s: food as resources
    assert "uses_per_turn" not in EFFECT[cid("Trade Routes Agreement")]
    p = g.p(s)
    f, r = E.food(p), E.resources(p)
    assert g.afford(s, "mine", r + f) and not g.afford(s, "mine", r + f + 1)
    g.pay(s, "mine", r + 1)
    g.pay(s, "mine", 1)                                                           # a second conversion this turn
    assert E.resources(p) == 0 and E.food(p) == f - 2
    q = g.p(o)
    assert not g.afford(o, "farm", E.food(q) + 1)                                 # not during s's turn
    g.s.turn_seat = o
    assert g.afford(o, "farm", E.food(q) + 1)
