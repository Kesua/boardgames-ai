"""Rule tests for build stage 2: tactics, armies and strength (T6.4, T11.3, T11.4), politics (T3.3, T3.4, T7),
events and colonization (T8), aggressions and wars (T9), pacts (T10), payments (T12.3, T12.9), the final Age III
evaluation (T14.2), expansion rules (T15) and hidden information (T16)."""
import itertools
import random
from collections import Counter

import numpy as np
import pytest

from games.through_the_ages import SPEC, new_game
from games.through_the_ages import economy as E
from games.through_the_ages import military as M
from games.through_the_ages import politics as P
from games.through_the_ages.cards import (AGE, BRONZE, EFFECT_TYPE, KIND, LEVEL, MILITARY_KINDS, N_CARDS, SET, TACTIC,
                                          civil_deck_cards, military_deck_cards)
from games.through_the_ages.tests.conftest import (answer, cid, fresh, give, has, kind, mil, next_turn, options, place,
                                                   play_to_round, politics, reveal_now, strength, tokens, touch)

rule = pytest.mark.rule


def two(seed=0, n=2, **opts):
    g = fresh(n, seed) if not opts else None
    if g is None:
        g = new_game(n, seed, opts)
        play_to_round(g, 2)
    s = g.current_seat
    return g, s, [(s + k) % n for k in range(1, n)]


def skip(g):
    """Pass the political action if it is still a decision (a lone PASS is applied automatically)."""
    if kind(g) == "POLITICS":
        answer(g, "Pass the political action")


def maybe(g, text):
    """Answer `text` unless it was the only answer and already applied automatically."""
    if has(g, text):
        answer(g, text)


def set_tactic(g, s, name, age=None):
    c = cid(name, age)
    g.p(s).tactic = c
    g.s.common_tactics.append(c)
    touch(g, s)
    return c


def set_pact(g, owner, name, partner, side=None, age=None):
    c = cid(name, age)
    g.p(owner).pact = [c, partner, side]
    touch(g)
    return c


# ===================================================================================================== T3 turn
@rule("T3.3")
def test_start_of_turn_refill_then_war_then_tactic_to_common_area():
    g, s, (o,) = two()
    p = g.p(s)
    war = cid("War over Culture")
    p.wars = [[war, o]]
    legion = cid("Legion")
    p.exclusive_tactic = p.tactic = legion
    touch(g, s)
    next_turn(g)
    assert g.current_seat == o and p.wars and p.exclusive_tactic == legion        # nothing moves before s's turn
    row_before = list(g.s.row)
    next_turn(g)
    log = list(g.s.log)
    i_war = max(i for i, x in enumerate(log) if "War over Culture" in x and "tie" in x)
    i_tac = max(i for i, x in enumerate(log) if "becomes a common tactic" in x)
    assert i_war < i_tac                                                           # (2) war before (3) tactic
    assert g.s.row != row_before                                                   # (1) refilled
    assert p.wars == [] and p.exclusive_tactic is None and legion in g.s.common_tactics and p.tactic == legion


@rule("T3.4")
def test_one_optional_political_action():
    g, s, (o,) = two()
    give(g, s, ("Crusades", "I"), ("Barbarians", "I"))
    politics(g)
    assert kind(g) == "POLITICS" and has(g, "Pass the political action") and has(g, "Prepare an event")
    answer(g, "Prepare an event")
    answer(g, "Prepare Crusades")
    assert kind(g) == "ACTION" and g.current_seat == s                             # only one political action
    politics(g)
    answer(g, "Pass the political action")
    assert kind(g) == "ACTION" and len(g.p(s).military_hand) == 1


# ===================================================================================================== T6 tactics
@rule("T6.4")
def test_play_tactic_one_military_action_copy_two_one_per_turn():
    g, s, (o,) = two()
    p, q = g.p(s), g.p(o)
    legion, phalanx = give(g, s, "Legion", "Phalanx")
    assert has(g, "Play tactic Legion") and not has(g, "Copy a common tactic")
    answer(g, "Play tactic Legion")
    assert (p.tactic, p.exclusive_tactic, p.military_spent) == (legion, legion, 1)
    assert not has(g, "Play tactic Phalanx")                                       # at most one play or copy
    next_turn(g)
    assert not has(g, "Copy a common tactic")                                      # still exclusive
    next_turn(g)                                                                    # s's turn: Legion becomes common
    assert legion in g.s.common_tactics and p.tactic == legion
    next_turn(g)
    assert g.current_seat == o and has(g, "Copy a common tactic")
    answer(g, "Copy a common tactic")
    assert q.tactic == legion and q.military_spent == 2 and legion in g.s.common_tactics
    assert not has(g, "Copy a common tactic")
    q.military_spent = 1
    touch(g, o)
    assert not has(g, "Copy a common tactic")                                      # needs 2 military actions


# ===================================================================================================== T7 politics
@rule("T7.1")
def test_political_actions_and_their_costs():
    g, s, (o,) = two()
    politics(g)
    assert kind(g) == "ACTION" and g.drain_forced()[-1]["action"] == "PASS"         # nothing to do: passed
    give(g, s, ("Crusades", "I"), ("Aggression: Raid", "II"), ("War over Territory", "II"))
    mil(g, s, "Swordsmen", k=1)
    politics(g)
    assert has(g, "Prepare an event") and has(g, "Play an aggression") and has(g, "Declare a war")
    assert not has(g, "Offer a pact") and not has(g, "Resign")
    answer(g, "Pass")
    g.p(s).military_spent = 1                                                      # Raid II and the war cost 2
    touch(g, s)
    politics(g)
    assert not has(g, "Play an aggression") and not has(g, "Declare a war") and has(g, "Prepare an event")
    answer(g, "Pass")
    g.p(s).military_spent = 0
    g.s.last_round = g.s.round                                                     # no war in the last round
    touch(g, s)
    politics(g)
    assert has(g, "Play an aggression") and not has(g, "Declare a war")
    answer(g, "Pass")
    # pacts with 3-4 players; resigning only with the option and not in Age IV
    g3, s3, _ = two(1, 3, allow_resign=True)
    give(g3, s3, ("Open Borders Agreement", "I"))
    politics(g3)
    assert has(g3, "Offer a pact") and has(g3, "Resign")
    answer(g3, "Pass")
    g3.s.age = "IV"
    politics(g3)
    assert not has(g3, "Resign")


@rule("T7.2")
def test_resign_leaves_the_game_wars_score_seven_pacts_removed():
    g, s, (o1, o2) = two(2, 3, allow_resign=True)
    r = s
    p = g.p(r)
    give(g, r, ("Crusades", "I"), "Iron")
    war = cid("War over Territory")
    g.p(o1).wars = [[war, r]]
    pact = set_pact(g, o2, "Open Borders Agreement", r)
    culture = g.p(o1).culture
    politics(g, r)
    answer(g, "Resign")
    assert p.resigned_order == 0 and p.civil_hand == [] and p.military_hand == []
    assert sorted(p.hand_at_resign) == sorted([cid("Crusades"), cid("Iron")])
    assert g.p(o1).wars == [] and g.p(o1).culture == culture + 7
    assert g.p(o2).pact is None and pact in g.s.military_discard
    assert g.current_seat == o1 and g.s.turn_seat == o1                            # play goes on
    assert g.active_seats() == [x for x in range(3) if x != r]
    # later ages are set up for the players still in the game (2 players: 2-player civil deck, 3-player proxies)
    deck = g.build_civil_deck("II")
    assert len(deck) == len(civil_deck_cards("II", 2)) + 7 + 5
    # rounds start with the first player still in the game; the starting player resigned
    play_to_round(g, 3)
    assert g.s.round_first == o1 and g.s.turn_seat == o1
    # one player left: the game ends at once and that player wins
    g2, s2, (o,) = two(3, 2, allow_resign=True)
    politics(g2, s2)
    answer(g2, "Resign")
    assert g2.game_over and g2.scores()[s2] == -1 and g2.scores()[o] >= 0


@rule("T7.3")
def test_resigned_players_rank_below_everyone_later_resignation_higher():
    g, s, (o1, o2, o3) = two(4, 4, allow_resign=True)
    politics(g, s)
    answer(g, "Resign")
    assert g.current_seat == o1
    politics(g, o1)
    answer(g, "Resign")
    sc = g.scores()
    assert sc[s] == -2 and sc[o1] == -1 and sc[o2] >= 0 and sc[o3] >= 0
    assert [sum(b.values()) for b in g.breakdowns()] == sc


# ===================================================================================================== T8 events, colonization
@rule("T8.1")
def test_prepare_scores_age_reveals_current_and_flips_future_by_age():
    g, s, (o,) = two()
    p = g.p(s)
    crusades = give(g, s, ("Crusades", "I"))[0]
    sci = [g.p(x).science for x in range(2)]
    g.s.current_events = [[cid("Development of Science"), None], [cid("Development of Crafts"), None]]
    politics(g)
    answer(g, "Prepare an event")
    assert g.s.future_events[0][:2] == [crusades, s] and p.culture == 1               # age I: 1 culture
    assert [g.p(x).science for x in range(2)] == [x + 2 for x in sci]              # Development of Science
    assert g.s.past_events[-1] == cid("Development of Science") and len(g.s.current_events) == 1
    # the last current event: afterwards the future deck becomes current, older ages on top
    g.s.future_events = [[cid("Cold War"), o], [cid("Pestilence"), o], [cid("Rats"), o]] + g.s.future_events
    give(g, s, ("Development of Agriculture", "A"))
    politics(g)
    answer(g, "Prepare an event")
    assert p.culture == 1                                                          # age A: 0 culture
    assert g.s.future_events == [] and len(g.s.current_events) == 5
    assert [LEVEL[e[0]] for e in g.s.current_events] == sorted(LEVEL[e[0]] for e in g.s.current_events)
    assert g.s.current_events[0][0] == cid("Development of Agriculture")


@rule("T8.2")
def test_event_choices_go_clockwise_from_the_revealer():
    g, s, (o1, o2) = two(0, 3)
    reveal_now(g, "Development of Markets")
    order = []
    while kind(g) == "EVENT_CHOICE":
        order.append(g.current_seat)
        answer(g, "Gain 2 food")
    assert order == [s, o1, o2]
    assert kind(g) == "ACTION" and g.current_seat == s


@rule("T8.3")
def test_ranking_ties_current_player_counts_higher_then_clockwise():
    g, s, (o1, o2) = two(0, 3)
    assert M.rank_players(g, "strength", "high") == [s, o1, o2]
    assert M.rank_players(g, "strength", "low") == [o2, o1, s]
    assert M.top_two(g, "strength", "low") == [o2, o1]
    g.s.game_end_eval = True                                                       # at game end: starting player
    start = g.s.start_seat
    assert M.rank_players(g, "strength", "high")[0] == start
    g.s.game_end_eval = False
    mil(g, o2, "Swordsmen")
    assert M.top(g, "strength") == o2 and M.top(g, "strength", "low") == o1
    assert M.all_with_most(g, "happiness") == [s, o1, o2]                          # "all with the most" keeps ties
    g2, s2, (x,) = two()
    assert M.top_two(g2, "strength") == [s2] and M.top_two(g2, "strength", "low") == [x]


def territory_game(n=3, seed=0):
    g, s, others = two(seed, n)
    for x in range(n):
        mil(g, x, "Swordsmen", k=1)                                                # force 1 + 2 = 3 each
    mil(g, others[-1], "Swordsmen", k=1)                                           # the last one: force 5
    return g, s, others


@rule("T8.4")
def test_colonization_auction_clockwise_higher_bids_last_bidder_colonizes():
    g, s, (o1, o2) = territory_game()
    terr = reveal_now(g, "Developed Territory", "I")
    assert kind(g) == "BID" and g.current_seat == s
    assert options(g) == ["Pass (no bid)", "Bid 1 for Developed Territory (I)", "Bid 2 for Developed Territory (I)",
                          "Bid 3 for Developed Territory (I)"]                     # at most the largest force
    answer(g, "Bid 2")
    assert g.current_seat == o1 and not has(g, "Bid 2 ")
    answer(g, "Bid 3")
    assert g.current_seat == o2 and has(g, "Bid 5") and not has(g, "Bid 6")
    answer(g, "Pass")
    assert kind(g) == "SEND" and g.current_seat == o1                              # s could not bid 4: passed
    assert g.drain_forced()[-1]["action"] == "BID_PASS"
    # nobody bids: the territory goes to the past events
    g, s, _ = territory_game(seed=1)
    terr = reveal_now(g, "Vast Territory", "I")
    while kind(g) == "BID":
        answer(g, "Pass")
    assert terr in g.s.past_events and all(terr not in g.p(x).colonies for x in range(3))


@rule("T8.5")
def test_colonization_force_units_armies_modifier_bonus_cards_overpay_allowed():
    g, s, _ = territory_game()
    p = g.p(s)
    sw = cid("Swordsmen")
    mil(g, s, "Swordsmen", k=1)                                                    # Warriors 1 + 2 Swordsmen 4
    set_tactic(g, s, "Legion")                                                     # 3 infantry: +2
    place(g, s, "Cartography")                                                     # colonization +2
    place(g, s, "Warfare")                                                         # strength +1: not counted
    bonus = give(g, s, ("Military Bonus", "I"))[0]                                 # colonization +1
    assert M.max_colonization_force(g, s) == 1 + 4 + 2 + 2 + 1
    assert M.colonization_force(g, s, {sw: 1}, []) == 2 + 0 + 2                     # no army with one unit
    reveal_now(g, "Wealthy Territory", "I")
    answer(g, "Bid 9")
    while kind(g) == "BID":
        answer(g, "Pass")
    assert kind(g) == "SEND" and g.current_seat == s and not has(g, "Stop sending")
    answer(g, "Send a unit from Swordsmen")
    answer(g, "Send a unit from Swordsmen")
    assert not has(g, "Stop sending")                                              # 4 + 2 < 9
    answer(g, "Play Military Bonus")                                               # 4+2+1 = 7
    forced = [r["action"] for r in g.drain_forced()]
    assert forced[-2:] == ["SEND_UNIT", "COLONIZE"]                                # Warriors: army of 3 -> 10
    assert bonus not in p.military_hand and bonus in g.s.military_discard
    assert cid("Wealthy Territory", "I") in p.colonies and p.workers[sw] == 0


@rule("T8.6")
def test_after_colonizing_units_to_yellow_bank_colony_permanent_then_one_time():
    g, s, _ = territory_game()
    p = g.p(s)
    terr = reveal_now(g, "Developed Territory", "I")
    yellow, blue, sci = p.yellow_bank, p.blue_bank, p.science
    answer(g, "Bid 1")
    while kind(g) == "BID":
        answer(g, "Pass")
    answer(g, "Send a unit from Swordsmen")
    answer(g, "Stop sending")
    assert terr in p.colonies and terr in p.play_order and terr not in g.s.past_events
    assert p.workers[cid("Swordsmen")] == 0 and p.yellow_bank == yellow + 1 + 1    # sent worker + yellow symbol
    assert p.blue_bank == blue + 1 and p.science == sci + 3                        # blue symbol, then 3 science
    assert strength(g, s) == 1


@rule("T8.7")
def test_colony_one_time_effect_only_once_annexed_moves_lost_is_removed():
    g, s, (o,) = two()
    terr = cid("Strategic Territory", "I")
    q = g.p(o)
    q.colonies.append(terr)
    g.enter_play(o, terr)
    assert strength(g, o) == 1 + 2
    mil(g, s, "Swordsmen", k=2)
    give(g, s, ("Aggression: Annex", "II"))
    hand = len(g.p(s).military_hand)
    politics(g)
    answer(g, "Play an aggression")
    assert terr in g.p(s).colonies and terr not in q.colonies
    assert strength(g, o) == 1 and strength(g, s) == 5 + 2                         # permanent effect moved
    assert len(g.p(s).military_hand) == hand - 1                                   # no 3 military cards again
    reveal_now(g, "Independence Declaration", seat=s)                              # the weakest (o) has none
    assert terr in g.p(s).colonies
    g.p(s).colonies.remove(terr)
    q.colonies.append(terr)
    g.p(s).play_order.remove(terr)
    q.play_order.append(terr)
    touch(g)
    reveal_now(g, "Independence Declaration", seat=s)
    assert terr not in q.colonies and terr not in q.play_order and strength(g, o) == 1


# ===================================================================================================== T9 aggressions, wars
@rule("T9.1")
def test_aggression_only_against_weaker_pacts_forbid_attack_bonus_ending_pacts():
    g, s, (o,) = two()
    give(g, s, ("Aggression: Plunder", "I"))
    politics(g)
    assert not has(g, "Play an aggression")                                        # equal strength
    skip(g)
    set_pact(g, s, "Open Borders Agreement", o)                                    # +2 when attacking the partner
    politics(g)
    assert has(g, "Play an aggression")
    skip(g)
    g.p(s).pact = None
    mil(g, s, "Swordsmen")
    set_pact(g, o, "Peace Treaty", s)                                              # no attack allowed
    politics(g)
    assert not has(g, "Play an aggression")
    skip(g)
    g.p(o).pact = None
    mil(g, o, "Swordsmen")
    set_pact(g, o, "Promise of Military Protection", s, side="B")                  # s holds A; o has +4 (ends)
    assert strength(g, o) == 3 + 4
    mil(g, s, "Swordsmen")
    assert strength(g, s) == 5
    politics(g)
    assert has(g, "Play an aggression")                                            # 5 > 3: the +4 is not counted
    answer(g, "Play an aggression")
    assert g.p(o).pact is None                                                     # removed by the attack


@rule("T9.2")
def test_defense_cards_reach_tie_or_nothing_card_cap_and_discards():
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=2)                                                    # 5 vs 1: need 4
    agg = give(g, s, ("Aggression: Plunder", "I"))[0]
    b1, b2, leg = give(g, o, ("Military Bonus", "I"), ("Military Bonus", "I"), "Legion")
    politics(g)
    answer(g, "Play an aggression")
    assert kind(g) == "DEFEND" and g.current_seat == o
    assert options(g) == ["Do not defend", "Defend with Military Bonus (I) (+2)"]  # Legion (+1) cannot reach 4
    answer(g, "Defend with Military Bonus")
    assert g.drain_forced()[-1]["action"] == "DEFEND"                               # the 2nd bonus: the only way on
    assert kind(g) == "ACTION" and g.current_seat == s                             # repelled: nothing taken
    assert g.p(o).military_hand == [leg] and g.s.military_discard.count(b1) == 2 and agg in g.s.military_discard
    # cap: military action total 2 cards; with 3 cards that only reach together, nothing can be played
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=2)
    give(g, s, ("Aggression: Plunder", "I"))
    give(g, o, "Legion", "Phalanx", "Fighting Band", "Heavy Cavalry")
    politics(g)
    answer(g, "Play an aggression")
    assert g.drain_forced()[-1]["action"] == "NO_DEFENSE"                          # forced: plunder follows
    assert kind(g) == "MIX" and g.current_seat == s


@rule("T9.3")
def test_several_attacks_on_one_player_and_war_plus_aggression_same_turn():
    g, s, (o1, o2) = two(0, 3)
    for x in (s, o1):
        mil(g, x, "Swordsmen", k=2)
        give(g, x, ("Aggression: Spy", "II"))
    g.p(o2).science = 20
    politics(g, s)
    answer(g, "Play an aggression")
    maybe(g, "on P" + str(o2))                                                     # o1 is as strong: o2 only
    next_turn(g)
    assert g.current_seat == o1
    politics(g, o1)
    answer(g, "Play an aggression")
    maybe(g, "on P" + str(o2))                                                     # s is as strong: o2 only
    assert g.p(o2).science == 10
    # a war resolved at the start of the turn and an aggression against the same player in that turn
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=2)
    g.p(s).wars = [[cid("War over Culture"), o]]
    g.p(o).culture = 20
    give(g, s, ("Aggression: Armed Intervention", "III"))
    next_turn(g)
    next_turn(g)
    assert g.p(o).culture == 20 - 5 - 4 and g.p(s).wars == []
    politics(g, s)
    assert has(g, "Play an aggression")


@rule("T9.4")
def test_declare_war_pays_no_strength_check_removes_ending_pact():
    g, s, (o,) = two()
    mil(g, o, "Swordsmen", k=3)                                                    # the target is much stronger
    war = give(g, s, ("War over Territory", "II"))[0]
    set_pact(g, o, "Military Pact", s)
    politics(g)
    answer(g, "Declare a war")
    assert g.p(s).wars == [[war, o]] and g.p(s).military_spent == 2 and g.p(o).pact is None
    assert war not in g.p(s).military_hand


@rule("T9.5")
def test_war_resolves_at_declarers_next_turn_current_strength_tie_nothing():
    g, s, (o,) = two()
    war = give(g, s, ("Hybrid War", "III"))[0]
    g.p(o).culture = 30
    politics(g)
    answer(g, "Declare a war")
    mil(g, s, "Swordsmen", k=2)                                                    # strength changes before
    next_turn(g)
    assert g.p(o).culture == 30
    next_turn(g)                                                                    # s's next turn starts
    assert g.p(o).culture == 30 - 4 and g.p(s).culture == 4                        # advantage 5 - 1
    assert g.p(s).wars == [] and war in g.s.removed_military + g.s.military_discard
    rec = [r for r in g.drain_forced() if r["decision"] == "WAR_RESOLUTION"]
    assert rec and rec[-1]["card"] == "hybrid_war_iii"
    # a tie has no effect
    g, s, (o,) = two()
    give(g, s, ("Hybrid War", "III"))
    g.p(o).culture = 30
    politics(g)
    answer(g, "Declare a war")
    next_turn(g)
    next_turn(g)
    assert g.p(o).culture == 30 and g.p(s).culture == 0


@rule("T9.6")
def test_war_over_technology_steals_specials_by_cost_identity_and_level_rules():
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=5)                                                    # 11 vs 1: advantage 10
    q = g.p(o)
    place(g, o, "Warfare")                                                         # cost 5, strength +1 -> adv 9
    place(g, o, "Cartography")                                                     # cost 4
    place(g, o, "Code of Laws")                                                    # cost 6
    place(g, s, "Navigation")                                                      # s has a higher colonization
    g.p(s).civil_hand.append(cid("Code of Laws"))                                  # identical card in hand
    q.science = 10
    g.p(s).wars = [[cid("War over Technology"), o]]
    next_turn(g)
    next_turn(g)
    assert kind(g) == "STEAL_TECH" and g.current_seat == s
    assert sorted(options(g)) == sorted(["Take Warfare (I) from P%d" % o, "Take Cartography (I) from P%d" % o,
                                         "Take the rest as science"])              # no Code of Laws (in hand)
    answer(g, "Take Warfare")                                                      # 9 - 5 = 4 left
    assert g.p(s).specials["special_military"] == cid("Warfare") and "special_military" not in q.specials
    answer(g, "Take Cartography")                                                  # lower than Navigation: gone
    assert g.p(s).specials["special_colonization"] == cid("Navigation") and "special_colonization" not in q.specials
    assert q.science == 10 and kind(g) != "STEAL_TECH"                             # 0 left: no science


# ===================================================================================================== T10 pacts
@rule("T10.1")
def test_offer_pact_sides_accept_or_refuse():
    g, s, (o1, o2) = two(0, 3)
    pact = give(g, s, ("Acceptance of Supremacy", "II"))[0]
    politics(g)
    answer(g, "Offer a pact")
    answer(g, f"on P{o1}")
    assert kind(g) == "PACT_SIDE"
    answer(g, "Take side A")
    assert kind(g) == "PACT_ANSWER" and g.current_seat == o1
    answer(g, "Refuse")
    assert pact in g.p(s).military_hand and kind(g) == "ACTION" and g.current_seat == s   # action used
    politics(g)
    answer(g, "Offer a pact")
    answer(g, f"on P{o2}")
    answer(g, "Take side B")
    answer(g, "Accept")
    assert g.p(s).pact == [pact, o2, "B"] and pact not in g.p(s).military_hand
    assert E.stats(g, s).resource_bonus == -1 and E.stats(g, o2).resource_bonus == 1


@rule("T10.2")
def test_accepted_pact_replaces_own_pact_applies_at_once_party_in_other_areas():
    g, s, (o1, o2) = two(0, 3)
    old = set_pact(g, s, "Peace Treaty", o1)
    other = set_pact(g, o2, "Military Pact", s)                                     # s is party in o2's area
    assert strength(g, s) == 1 + 3
    new = give(g, s, ("Open Borders Agreement", "I"))[0]
    mil_before = E.military_available(g, o1)
    politics(g)
    answer(g, "Offer a pact")
    answer(g, f"on P{o1}")
    answer(g, "Accept")
    assert g.p(s).pact == [new, o1, None] and old in g.s.removed_military + g.s.military_discard
    assert g.p(o2).pact[0] == other and strength(g, s) == 4                        # the other pact stays
    assert E.military_available(g, o1) == mil_before + 1                           # applies at once


@rule("T10.3")
def test_cancel_pact_ends_on_attack_and_when_antiquated():
    g, s, (o1, o2) = two(0, 3)
    pact = set_pact(g, o1, "International Trade Agreement", s, side="A")
    politics(g)
    answer(g, "Cancel a pact")
    assert g.p(o1).pact is None and pact in g.s.removed_military                  # an Age II card in Age I
    set_pact(g, s, "Military Pact", o1)
    mil(g, s, "Swordsmen", k=2)
    give(g, s, ("Aggression: Spy", "II"))
    politics(g)
    answer(g, "Play an aggression")
    answer(g, f"on P{o1}")
    assert g.p(s).pact is None                                                     # ended by the attack
    old = set_pact(g, s, "Open Borders Agreement", o2)
    g.begin_age("II")
    assert g.p(s).pact is not None
    g.begin_age("III")                                                             # Age I antiquated
    assert g.p(s).pact is None and old in g.s.removed_military


# ===================================================================================================== T11 strength
@rule("T11.3")
def test_strength_units_armies_and_modifiers():
    g, s, _ = two()
    assert strength(g, s) == 1                                                     # Warriors
    mil(g, s, "Swordsmen", k=2)
    assert strength(g, s) == 5
    set_tactic(g, s, "Legion")                                                     # one army of 3 infantry: +2
    assert strength(g, s) == 7 and E.stats(g, s).army == 2
    place(g, s, "Warfare")                                                         # +1
    assert strength(g, s) == 8


def brute_armies(tactic, units, air):
    """Best total over every grouping of the units into armies (each unit in at most one army)."""
    eff = EFFECT_TYPE[tactic]
    if eff == "hussars":
        req = Counter({"cavalry": 2})
    else:
        req = Counter({k: v for k, v in TACTIC[tactic]["units"].items() if v})
    size = sum(req.values())
    kmax = len(units) // size
    lvl = LEVEL[tactic]
    best = 0
    for assign in itertools.product(range(kmax + 1), repeat=len(units)):
        groups = {}
        for u, a in zip(units, assign):
            if a < kmax:
                groups.setdefault(a, []).append(u)
        vals = []
        for us in groups.values():
            if Counter(t for t, _ in us) != req:
                break
            if eff == "hussars":
                vals.append(2 + min(lv for _, lv in us))
            elif TACTIC[tactic]["outdated_strength"] and lvl >= 2 and any(lv <= lvl - 2 for _, lv in us):
                vals.append(TACTIC[tactic]["outdated_strength"])
            else:
                vals.append(TACTIC[tactic]["strength"])
        else:
            vals.sort(reverse=True)
            best = max(best, sum(vals) + sum(vals[:air]))
    return best


@rule("T11.4")
def test_army_forming_matches_brute_force_on_small_cases():
    tactics = [c for c in range(N_CARDS) if KIND[c] == "tactic"]
    rng = random.Random(7)
    levels = {"infantry": [0, 1, 2, 3], "cavalry": [1, 2, 3], "artillery": [2, 3]}
    for _ in range(400):
        t = rng.choice(tactics)
        units = [(k, rng.choice(levels[k])) for k in (rng.choice(list(levels)) for _ in range(rng.randint(0, 7)))]
        air = rng.randint(0, 2)
        lv = {k: tuple(sorted((x for kk, x in units if kk == k), reverse=True)) for k in levels}
        got = M.army_strength(t, lv["infantry"], lv["cavalry"], lv["artillery"], air)
        assert got == brute_armies(t, units, air), (t, units, air)


@rule("T11.4")
def test_outdated_armies_and_air_forces_in_play():
    g, s, _ = two()
    g.begin_age("II")
    g.begin_age("III")
    set_tactic(g, s, "Modern Army")                                                # 2 inf, 1 cav, 1 art: 13 / 7
    mil(g, s, "Swordsmen", k=1)                                                    # Warriors (0) + Swordsmen (1)
    mil(g, s, "Tanks", k=1)
    mil(g, s, "Rockets", k=1)
    assert E.stats(g, s).army == 7                                                 # level 0/1 units: outdated
    g.p(s).workers[cid("Warriors")] = 0
    g.p(s).workers[cid("Swordsmen")] = 0
    mil(g, s, "Modern Infantry", k=2)
    assert E.stats(g, s).army == 13
    mil(g, s, "Air Forces", k=1)
    assert E.stats(g, s).army == 26                                                # air force doubles the army


# ===================================================================================================== T12 payments
@rule("T12.3")
def test_change_by_moving_tokens_needs_no_bank_overpay_only_if_bank_ends_empty():
    g, s, _ = two()
    p = g.p(s)
    coal, iron = place(g, s, "Coal"), place(g, s, "Iron")
    tokens(g, s, "Bronze", 0)
    tokens(g, s, "Coal", 1)
    p.blue_bank = 0
    p.tokens = {coal: 1}
    assert E.pay(p, "mine", 1) == 1 and p.tokens == {iron: 1} and p.blue_bank == 0  # Coal token moves to Iron
    # without Iron: exact change needs a bank token (3 -> 1 + 1)
    p.techs.remove(iron)
    p.tokens = {coal: 1}
    p.blue_bank = 4
    assert E.pay(p, "mine", 1) == 1 and p.tokens == {BRONZE: 2} and p.blue_bank == 3
    # empty bank: exact impossible; paying more must leave the bank empty (move to Bronze: 2), not return (3)
    p.tokens = {coal: 1}
    p.blue_bank = 0
    assert E.pay(p, "mine", 1) == 2 and p.tokens == {BRONZE: 1} and p.blue_bank == 0
    assert E.plan_payment((3, 1), (1, 0), 0, 1) == (0, 1)
    assert E.plan_payment((3, 2, 1), (1, 0, 0), 0, 1) == (0, 1, 0)


@rule("T12.9")
def test_temporary_resources_for_units_spent_first_and_vanish():
    g, s, _ = two()
    p = g.p(s)
    give(g, s, ("Patriotism", "A"))
    tokens(g, s, "Bronze", 1)
    answer(g, "Play action card Patriotism")
    assert p.temp == {"unit": 1} and E.military_available(g, s) == 3
    assert not has(g, "Build a farm") and has(g, "Build a military unit")         # only for military units
    answer(g, "Build a military unit")
    assert p.temp == {"unit": 0} and E.resources(p) == 0 and p.workers[cid("Warriors")] == 2
    g, s, _ = two()
    p = g.p(s)
    give(g, s, ("Patriotism", "A"))
    answer(g, "Play action card Patriotism")
    next_turn(g)
    assert p.temp == {} and p.temp_military == 0


# ===================================================================================================== T14 game end
@rule("T14.2")
def test_final_evaluation_age_iii_events_current_then_future_deck():
    g, s, (o,) = two()
    q = g.p(o)
    q.colonies.append(cid("Historic Territory", "I"))
    imp_col, imp_strength = cid("Impact of Colonies"), cid("Impact of Strength")
    g.s.current_events = [[imp_col, None], [cid("Development of Science"), None], [cid("Modern Army"), None],
                          [cid("Cold War"), None]]
    g.s.future_events = [[imp_strength, s]]
    mil(g, s, "Swordsmen")
    cult = [g.p(x).culture for x in range(2)]
    sci = [g.p(x).science for x in range(2)]
    g.end_game()
    log = [x for x in g.s.log if x.startswith("Final evaluation")]
    assert log == ["Final evaluation: Impact of Colonies (III)", "Final evaluation: Impact of Strength (III)"]
    assert g.p(o).culture == cult[o] + 3 and g.p(s).culture == cult[s] + 10        # 2 players: 10 / 0
    assert [g.p(x).science for x in range(2)] == sci                               # other ages ignored (D19)
    assert g.game_over


# ===================================================================================================== T15 expansion
@rule("T15.1")
def test_expansion_parts_together_new_military_decks():
    names = lambda age, n: {(AGE[c], KIND[c]) for c in military_deck_cards(age, n)}   # noqa: E731
    assert cid("Development of Planning") in military_deck_cards("A", 2)
    assert cid("Hussars") in military_deck_cards("II", 2) and cid("Arms Industry") in military_deck_cards("II", 4)
    assert SET[cid("Wealthy Territory", "I")] == "rebalanced"
    assert all(KIND[c] in MILITARY_KINDS for age in ("A", "I", "II", "III") for c in military_deck_cards(age, 4))
    assert ("I", "pact") not in names("I", 2) and ("I", "pact") in names("I", 3)    # T2.2


@rule("T15.5")
def test_new_military_cards_follow_their_card_data_and_clarifications():
    hussars = cid("Hussars")
    assert M.army_strength(hussars, (), (3, 1), (), 0) == 2 + 1                    # knight + tank: 3
    assert M.army_strength(hussars, (), (3, 3, 1, 0), (), 0) == 5 + 2              # pairs maximise the total
    new = [c for c in range(N_CARDS) if KIND[c] in MILITARY_KINDS and SET[c] == "new"]
    assert all(EFFECT_TYPE[c] is not None or KIND[c] in ("tactic", "bonus") for c in new)


@rule("T15.7")
def test_kidnapped_action_card_playable_this_turn():
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=2)
    give(g, s, ("Aggression: Kidnap", "I"))
    g.p(o).civil_hand.append(cid("Cultural Heritage", "A"))
    politics(g)
    answer(g, "Play an aggression")
    assert kind(g) == "KIDNAP"
    answer(g, "Take Cultural Heritage")
    culture = g.p(s).culture
    assert has(g, "Play action card Cultural Heritage")
    answer(g, "Play action card Cultural Heritage")
    assert g.p(s).culture == culture + 4 + 3                                       # its 4 + Kidnap's 3


@rule("T15.10")
def test_revealed_non_event_gives_everyone_one_science():
    g, s, (o,) = two()
    sci = [g.p(x).science for x in range(2)]
    reveal_now(g, "Legion")
    assert [g.p(x).science for x in range(2)] == [x + 1 for x in sci] and cid("Legion") in g.s.past_events


# ===================================================================================================== T16 information
def hidden_variants(g, viewer):
    """Changes of things `viewer` must not see (PLAN 8)."""
    other = [x for x in range(g.num_players) if x != viewer]

    def swap(c):
        """Another card of the same age and deck (only counts per age are public)."""
        return next(x for x in range(N_CARDS) if x != c and AGE[x] == AGE[c] and
                    (KIND[x] in MILITARY_KINDS) == (KIND[c] in MILITARY_KINDS) and KIND[x] not in ("wonder",))

    def hands(h):
        for x in other:
            if h.p(x).leader is None or EFFECT_TYPE[h.p(x).leader] != "ashoka":   # Ashoka: open civil hand
                h.p(x).civil_hand = [swap(c) for c in h.p(x).civil_hand]
            h.p(x).military_hand = [swap(c) for c in h.p(x).military_hand]

    def decks(h):
        h.s.military_deck.reverse()
        h.s.civil_deck.reverse()
        h.s.age_a_unused.reverse()

    def known(e):
        return e[1] == viewer or viewer in P.known_by(e)

    def events(h):
        h.s.current_events = [e if known(e) else [swap(e[0])] + e[1:] for e in h.s.current_events]
        h.s.future_events = [e if known(e) else [swap(e[0])] + e[1:] for e in h.s.future_events]

    return [hands, decks, events]


@rule("T16.1")
@rule("T16.2")
def test_changing_anything_hidden_from_a_seat_leaves_its_observation_unchanged():
    for n in (2, 3, 4):
        g = fresh(n, 5)
        rng = random.Random(n)
        for _ in range(150):                                                       # some real game state
            g.step_id(rng.choice(g.legal_ids()))
        viewer = g.current_seat
        enc = SPEC.encoder(n)
        g.s.future_events = [[cid("Barbarians"), other] for other in range(n) if other != viewer][:1]
        base = enc.encode(g, viewer)
        for change in hidden_variants(g, viewer):
            h = g.clone()
            change(h)
            assert np.array_equal(base, enc.encode(h, viewer)), change.__name__
    # Kidnap's candidates: only the aggressor's observation shows them
    g, s, (o,) = two()
    mil(g, s, "Swordsmen", k=2)
    give(g, s, ("Aggression: Kidnap", "I"))
    g.p(o).civil_hand = [cid("Iron")]
    politics(g)
    answer(g, "Play an aggression")
    enc = SPEC.encoder(2)
    v_me, v_other = enc.encode(g, s), enc.encode(g, o)
    h = g.clone()
    h.s.decisions.top.data["candidates"] = [cid("Alchemy")]                        # what the aggressor sees
    assert not np.array_equal(v_me, enc.encode(h, s)) and np.array_equal(v_other, enc.encode(h, o))


@rule("T16.2")
def test_cards_that_reveal_information_reach_exactly_the_players_who_may_see_it():
    """Joan of Arc's top event and Nostradamus' seen events reach their owner's observation only (Nostradamus: not
    their order once the future deck became the shuffled current deck, review F12); Ian Fleming's look
    only his owner's; Ashoka's open civil hand every player's."""
    g, s, (o1, o2) = two(n=3)
    enc = SPEC.encoder(3)

    def seen_by(change):
        h = g.clone()
        change(h)
        return [x for x in (s, o1, o2) if not np.array_equal(enc.encode(g, x), enc.encode(h, x))]

    def swap_event(entry_list):
        def change(h):
            e = getattr(h.s, entry_list)[0]
            e[0] = cid("Development of Science") if e[0] != cid("Development of Science") else cid("Rats")
        return change

    g.s.current_events.insert(0, [cid("Development of Crafts"), None, [], [s]])    # Joan of Arc's look
    assert seen_by(swap_event("current_events")) == [s]
    g.s.future_events.insert(0, [cid("Development of Crafts"), o1, [s]])            # o1's, seen by Nostradamus
    assert seen_by(swap_event("future_events")) == [s, o1]
    g.s.current_events = [[cid("Good Harvest"), o1, [s]], [cid("Rats"), o1, [s]]]   # Nostradamus' cards after the
    assert seen_by(lambda h: h.s.current_events.reverse()) == []                    # shuffle: the order is hidden
    g.s.current_events[0].append([s])                                               # unless Joan of Arc looked at
    assert seen_by(lambda h: h.s.current_events.reverse()) == [s]                   # the top card
    g.p(s).peek = [o1, [cid("Legion")]]                                             # Ian Fleming's look
    assert seen_by(lambda h: setattr(h.p(s), "peek", [o1, [cid("Phalanx")]])) == [s]
    g.p(o2).civil_hand = [cid("Iron")]
    assert seen_by(lambda h: setattr(h.p(o2), "civil_hand", [cid("Alchemy")])) == [o2]   # same age: hidden
    place(g, o2, "Ashoka")
    assert seen_by(lambda h: setattr(h.p(o2), "civil_hand", [cid("Alchemy")])) == [s, o1, o2]


# ===================================================================================================== whole games
@pytest.mark.parametrize("n", [2, 3, 4])
def test_random_games_with_resigning_end_and_keep_invariants(n):
    for seed in range(3):
        g = new_game(n, 200 + seed, {"allow_resign": True})
        rng = random.Random(seed)
        steps = 0
        while not g.game_over:
            if steps % 5 == 0:
                assert SPEC.invariants(g) == []
            g.step_id(rng.choice(g.legal_ids()))
            steps += 1
        assert steps < SPEC.max_steps // 10 and SPEC.invariants(g) == []
        assert [sum(b.values()) for b in g.breakdowns()] == g.scores()
        assert sum(1 for x in g.scores() if x < 0) == g.s.resigned


def test_greedy_never_resigns_and_still_scores():
    from games.through_the_ages.agents import GreedyAgent
    g = new_game(2, 11, {"allow_resign": True})
    agents = [GreedyAgent(1), GreedyAgent(2)]
    steps = 0
    while not g.game_over and steps < 4000:
        g.step_id(agents[g.current_seat].act(g, g.current_seat))
        steps += 1
    assert g.s.resigned == 0
