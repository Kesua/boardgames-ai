"""Rule tests (one or more per rule ID of rules.md implemented in stage 1: a complete peaceful game; stage 2 rules are
in test_rules_military.py)."""
import random

import numpy as np
import pytest

from games.through_the_ages import SPEC, new_game
from games.through_the_ages import economy as E
from games.through_the_ages import engine as En
from games.through_the_ages.cards import (AGE, AGRICULTURE, BRONZE, DESPOTISM, KIND, LEVEL, NAME, PHILOSOPHY,
                                          RELIGION, WARRIORS, civil_deck_cards, copies, military_deck_cards)
from games.through_the_ages.state import LEADER_PROXY, WONDER_PROXY
from games.through_the_ages.tests.conftest import (answer, cid, end_turn, fresh, give, has, kind, options, place,
                                                   play_to_round, refresh, started, tokens, touch)

rule = pytest.mark.rule


def avail(g, s):
    return E.civil_available(g, s), E.military_available(g, s)


# ===================================================================================================== T1 components
@rule("T1.1")
def test_boards_card_row_of_13_and_event_areas():
    g = started(2, 1)
    s = g.s
    assert len(s.row) == 13 and None not in s.row
    assert len(s.current_events) == 4 and s.future_events == [] and s.past_events == [] and s.common_tactics == []
    assert len(s.players) == 2


@rule("T1.2")
def test_card_row_costs_1_2_3():
    assert En.ROW_COST == (1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)
    for seed in range(5):
        g = started(4, seed)
        for slot, c in enumerate(g.s.row):
            if KIND[c] != "wonder":
                assert g.take_cost(0, slot) == En.ROW_COST[slot]


@rule("T1.3")
def test_a_civil_and_a_military_deck_per_age_none_in_age_iv():
    g = fresh(2, 3)
    assert g.s.age == "I"
    assert all(AGE[c] == "I" for c in g.s.civil_deck if c < LEADER_PROXY)
    assert g.s.military_deck and all(AGE[c] == "I" for c in g.s.military_deck)
    for age in ("II", "III"):
        g.begin_age(age)
        assert all(AGE[c] == age for c in g.s.civil_deck if c < LEADER_PROXY)
        assert g.s.military_deck and all(AGE[c] == age for c in g.s.military_deck)
    g.begin_age("IV")
    assert not g.s.civil_deck and not g.s.military_deck


@rule("T1.5")
@rule("T2.3")
def test_player_board_and_starting_tokens():
    g = started(3, 2)
    for p in g.s.players:
        assert p.blue_bank == 16 and p.yellow_bank == 18 and p.pool == 1
        assert p.workers == {WARRIORS: 1, AGRICULTURE: 2, BRONZE: 2, PHILOSOPHY: 1, RELIGION: 0}
        assert p.government == DESPOTISM
        assert sorted(NAME[c] for c in p.techs) == ["Agriculture", "Bronze", "Philosophy", "Religion", "Warriors"]
        assert not p.tokens and p.science == 0 and p.culture == 0 and not p.civil_hand and not p.military_hand


@rule("T1.6")
@rule("T2.4")
def test_despotism_and_starting_statistics():
    g = started(2, 0)
    st = g.stats(0)
    assert (st.civil, st.military, st.urban_limit) == (4, 2, 2)
    assert (st.science, st.culture, st.strength, st.happiness) == (1, 0, 1, 0)


CORRUPTION = [6, 4, 4, 4, 4, 4, 2, 2, 2, 2, 2] + [0] * 10                       # N = 0..20
POP_COST = [None, 7, 7, 7, 7, 5, 5, 5, 5, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2]
CONSUMPTION = [6, 4, 4, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0]
HAPPY = [8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 1, 1, 0, 0, 0, 0]


@rule("T1.7")
@rule("T1.9")
@pytest.mark.parametrize("n", range(21))
def test_corruption_table(n):
    assert E.corruption(n) == CORRUPTION[n]


@rule("T1.8")
@rule("T1.9")
@pytest.mark.parametrize("n", range(21))
def test_yellow_bank_tables(n):
    assert (E.pop_cost(n), E.consumption(n), E.happy_required(n)) == (POP_COST[n], CONSUMPTION[n], HAPPY[n])


@rule("T1.9")
def test_token_supply_unlimited_banks_grow_beyond_printed_spaces():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    g.change_tokens(s, 30, 5)
    assert p.blue_bank > 16 and p.yellow_bank == 23 and E.corruption(p.blue_bank) == 0
    assert E.consumption(p.yellow_bank) == 0 and E.pop_cost(p.yellow_bank) == 2


# ===================================================================================================== T2 setup
def civil_count(age, n):
    return len(civil_deck_cards(age, n))


@rule("T2.1")
def test_civil_decks_lose_marked_cards_for_fewer_players():
    for age in ("I", "II", "III"):
        assert civil_count(age, 4) - civil_count(age, 3) == {"I": 3, "II": 2, "III": 1}[age]
        assert civil_count(age, 4) - civil_count(age, 2) == {"I": 9, "II": 9, "III": 11}[age]
    for n, (nl, nw) in ((2, (6, 4)), (3, (7, 5)), (4, (7, 5))):
        g = fresh(n, 1)
        g.s.civil_deck = g.build_civil_deck("II")
        real = [c for c in g.s.civil_deck if c < LEADER_PROXY]
        assert sorted(real) == sorted(civil_deck_cards("II", n))
        assert len(g.s.civil_deck) - len(real) == nl + nw


@rule("T2.2")
def test_two_players_play_without_pacts():
    assert not [c for c in military_deck_cards("I", 2) if KIND[c] == "pact"]
    assert [c for c in military_deck_cards("I", 3) if KIND[c] == "pact"]
    g = fresh(2, 4)
    assert not [c for c in g.s.military_deck if KIND[c] == "pact"]


@rule("T2.5")
def test_current_events_deal_players_plus_two_age_a_cards():
    for n in (2, 3, 4):
        g = started(n, 7)
        s = g.s
        assert len(s.current_events) == n + 2 and all(AGE[e[0]] == "A" for e in s.current_events)
        assert sorted([e[0] for e in s.current_events] + s.age_a_unused) == sorted(military_deck_cards("A", n))
        assert s.future_events == [] and s.past_events == []


@rule("T2.6")
@rule("T15.8")
def test_age_a_row_and_deck_hold_the_selected_leaders_and_wonders():
    for n, size in ((2, 20), (3, 22), (4, 22)):
        g = started(n, 5)
        s = g.s
        cards = list(s.row) + list(s.civil_deck)
        assert len(s.row) == 13 and len(cards) == size and all(AGE[c] == "A" for c in cards)
        lw = sorted(c for c in cards if KIND[c] in ("leader", "wonder"))
        assert lw == sorted(s.selection["A"]["leaders"] + s.selection["A"]["wonders"])


@rule("T2.7")
def test_random_starting_player_never_changes():
    starts = {new_game(3, seed).s.start_seat for seed in range(30)}
    assert starts == {0, 1, 2}
    g = new_game(2, 11)
    first = g.s.start_seat
    rng = random.Random(0)
    while not g.game_over:
        g.step_id(rng.choice(g.legal_ids()))
        assert g.s.start_seat == first


@rule("T2.8")
def test_round_one_civil_actions_one_two_three_four_no_military():
    g = started(4, 3)
    start = g.s.start_seat
    for k in range(4):
        assert avail(g, (start + k) % 4) == (k + 1, 0)


# ===================================================================================================== T3 turn
@rule("T3.1")
@rule("T3.3")
def test_turn_parts_in_order_refill_first():
    g = started(2, 2)
    play_to_round(g, 2)
    log = g.s.log
    i_age = max(i for i, l in enumerate(log) if l == "Age I begins")
    start = g.s.start_seat
    assert log[i_age + 1] == f"P{start}: Pass the political action (only option)"
    assert None not in g.s.row
    end_turn(g)
    tail = [l for l in log[i_age:] if l.startswith(f"P{start}")]
    assert tail[0].endswith("(only option)") and "End the action phase" in tail[1] and "Production" in tail[-1]


@rule("T3.2")
def test_round_one_only_takes_no_refill_no_military_draw():
    g = started(2, 4)
    assert g.s.round == 1 and kind(g) == "ACTION"
    segs = {En.CODEC.decode(a)[0] for a in g.legal_ids()}
    assert segs <= {"END", "ROW"}
    answer(g, "from row slot 1 ")
    assert g.s.row[0] is None
    play_to_round(g, 2)
    assert all(not p.military_hand for p in g.s.players)


@rule("T3.4")
def test_politics_phase_offered_from_round_two_nothing_to_do_passes():
    g = started(2, 6)
    forced_round1 = [r for r in g.drain_forced() if r["decision"] == "POLITICS"]
    assert not forced_round1
    play_to_round(g, 2)
    pol = [r for r in g.drain_forced() if r["decision"] == "POLITICS"]
    assert pol and pol[-1]["action"] == "PASS"


@rule("T3.5")
def test_actions_any_order_stop_any_time_only_payable_actions():
    g = fresh(2, 0)
    s = g.current_seat
    assert has(g, "End the action phase") and avail(g, s)[0] == 4
    tokens(g, s, "Bronze", 0)
    assert not has(g, "Build a farm") and not has(g, "Build a military unit")
    tokens(g, s, "Bronze", 3)
    assert has(g, "Build a farm") and has(g, "Build a military unit")


@rule("T3.6")
def test_end_of_turn_discard_then_production_then_draw_then_reset():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    give(g, s, ("Military Bonus", "I"), ("Military Bonus", "I"), ("Military Bonus", "I"), ("Legion", "I"))
    answer(g, "Increase population")
    sci, deck = p.science, len(g.s.military_deck)
    answer(g, "End the action phase")
    assert kind(g) == "DISCARD_MILITARY" and g.current_seat == s and p.science == sci   # (1) before production
    g.step_id(g.legal_ids()[0])                                    # Legion; the second discard is forced
    assert g.current_seat != s and len(g.drain_forced()) >= 1
    assert p.science == sci + 1                                                          # (3) production
    assert len(p.military_hand) == 4 and len(g.s.military_deck) == deck - 2              # (4) 2 drawn
    assert (p.civil_spent, p.military_spent) == (0, 0)                                   # (5) reset


@rule("T3.7")
def test_draw_one_military_card_per_available_military_action_max_three():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Julius Caesar")
    place(g, s, "Warfare")
    assert avail(g, s)[1] == 4
    end_turn(g)
    assert len(p.military_hand) == 3
    g = fresh(2, 0)
    s = g.current_seat
    g.p(s).military_spent = 1
    end_turn(g)
    assert len(g.p(s).military_hand) == 1
    # empty deck: the current age's discard pile is shuffled into a new deck
    g = fresh(2, 0)
    s = g.current_seat
    g.s.military_discard = list(g.s.military_deck)
    g.s.military_deck.clear()
    end_turn(g)
    assert len(g.p(s).military_hand) == 2 and len(g.s.military_discard) == 0
    # none in Age IV
    g = fresh(2, 0)
    s = g.current_seat
    g.begin_age("II"), g.begin_age("III"), g.begin_age("IV")
    end_turn(g)
    assert g.p(s).military_hand == []


# ===================================================================================================== T4 card row
@rule("T4.1")
@pytest.mark.parametrize("n,k", [(2, 3), (3, 2), (4, 1)])
def test_refill_discards_slides_and_deals(n, k):
    g = fresh(n, 2)
    s = g.s
    row = list(s.row)
    row[k + 1] = None                                                                    # a taken card
    s.row = list(row)
    sel = s.selection["I"]
    top = [sel["leaders"][c - LEADER_PROXY] if LEADER_PROXY <= c < WONDER_PROXY else
           sel["wonders"][c - WONDER_PROXY] if c >= WONDER_PROXY else c for c in s.civil_deck[:k + 1]]
    removed = len(s.removed_civil)
    g.refill()
    kept = [c for c in row[k:] if c is not None]
    assert s.row == kept + top                                                           # slide left, deal in order
    assert len(s.removed_civil) == removed + k and s.removed_civil[-k:] == row[:k]


@rule("T4.2")
def test_take_pays_slot_cost_into_hand():
    g = fresh(2, 0)
    s = g.current_seat
    slot = next(i for i in range(5, 9) if KIND[g.s.row[i]] not in ("wonder",))
    c = g.s.row[slot]
    refresh(g)
    g.step_id(En.A_ROW + slot)
    assert c in g.p(s).civil_hand and g.s.row[slot] is None and avail(g, s)[0] == 2


@rule("T4.3")
def test_civil_hand_limit_is_civil_action_total():
    g = fresh(2, 0)
    s = g.current_seat
    give(g, s, ("Rich Land", "A"), ("Urban Growth", "A"), ("Stockpile", "A"), ("Frugality", "A"))
    g.s.row[0] = cid("Reserves", "I")
    g.s.row[1] = cid("Pyramids")
    touch(g)
    assert not has(g, "Take Reserves") and has(g, "Take Pyramids")
    g.p(s).civil_hand.pop()
    touch(g)
    assert has(g, "Take Reserves")


@rule("T4.4")
def test_no_second_technology_of_the_same_name():
    g = fresh(2, 0)
    s = g.current_seat
    g.s.row[0] = cid("Iron")
    g.s.row[1] = cid("Alchemy")
    give(g, s, "Iron")
    place(g, s, "Alchemy")
    assert not has(g, "Take Iron") and not has(g, "Take Alchemy")
    g.p(s).civil_hand = []
    touch(g)
    assert has(g, "Take Iron")


@rule("T4.5")
def test_one_leader_per_age_for_the_whole_game():
    g = fresh(2, 0)
    s = g.current_seat
    g.s.row[0] = cid("Moses")
    g.s.row[1] = cid("Homer")
    touch(g)
    answer(g, "Take Moses")
    assert not has(g, "Take Homer")
    answer(g, "Play leader Moses")
    g.p(s).leader = None
    g.p(s).play_order.remove(cid("Moses"))
    touch(g)
    assert not has(g, "Take Homer")


@rule("T4.6")
def test_wonder_cost_surcharge_and_one_unfinished():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    g.s.row[0] = cid("Pyramids")
    g.s.row[1] = cid("Colossus")
    place(g, s, "Hanging Gardens")
    give(g, s, ("Rich Land", "A"), ("Urban Growth", "A"), ("Stockpile", "A"), ("Frugality", "A"))  # no hand limit
    assert g.take_cost(s, 0) == 2
    answer(g, "Take Pyramids")
    assert p.unfinished == [cid("Pyramids"), 0, 0] and cid("Pyramids") not in p.civil_hand
    assert not has(g, "Take Colossus")


# ===================================================================================================== T5 civil actions
@rule("T5.1")
@rule("T11.7")
def test_increase_population():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    tokens(g, s, "Agriculture", 3)
    answer(g, "Increase population")
    assert p.yellow_bank == 17 and p.pool == 2 and E.food(p) == 1 and avail(g, s)[0] == 3
    p.yellow_bank = 0
    touch(g)
    assert not has(g, "Increase population")
    p.yellow_bank = 12
    tokens(g, s, "Agriculture", 3)
    touch(g)
    assert not has(g, "Increase population")                                             # costs 4
    g.apply_gain(s, {"population": 2}, "events")                                         # gain population: free
    assert p.yellow_bank == 10 and p.pool == 4


@rule("T5.2")
def test_build_farm_mine_urban():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    tokens(g, s, "Bronze", 3)
    answer(g, "Build a farm")
    assert set(options(g)) == {"Build on Agriculture (A)", "Build on Bronze (A)", "Build on Philosophy (A)",
                               "Build on Religion (A)"}
    answer(g, "Build on Philosophy")
    assert p.workers[PHILOSOPHY] == 2 and p.pool == 0 and E.resources(p) == 0 and avail(g, s)[0] == 3


@rule("T5.3")
def test_urban_limit_counts_all_levels_of_a_type():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Theology")
    p.workers[RELIGION] = 1
    p.workers[cid("Theology")] = 1
    p.yellow_bank -= 2
    p.pool = 2
    tokens(g, s, "Bronze", 10)
    touch(g)
    answer(g, "Build a farm")
    opts = options(g)
    assert "Build on Religion (A)" not in opts and "Build on Theology (I)" not in opts
    assert "Build on Philosophy (A)" in opts and "Build on Agriculture (A)" in opts


@rule("T5.4")
def test_upgrade_pays_the_cost_difference():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Iron")
    tokens(g, s, "Bronze", 3)
    answer(g, "Upgrade a farm")                              # Bronze -> Iron is the only upgrade: both steps forced
    assert [r["action"] for r in g.drain_forced()][-2:] == ["UPGRADE_FROM", "UPGRADE"]
    assert p.workers[BRONZE] == 1 and p.workers[cid("Iron")] == 1 and E.resources(p) == 0
    assert avail(g, s)[0] == 3


@rule("T5.5")
def test_destroy_returns_worker_to_pool():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    answer(g, "Destroy a farm")
    answer(g, "Destroy a building on Bronze")
    assert p.workers[BRONZE] == 1 and p.pool == 2 and avail(g, s)[0] == 3


@rule("T5.6")
def test_play_leader_replacing_returns_one_civil_action():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    give(g, s, "Homer", "Julius Caesar")
    answer(g, "Play leader Homer")
    assert p.leader == cid("Homer") and avail(g, s)[0] == 3 and g.stats(s).happiness == 1
    answer(g, "Play leader Julius Caesar")
    assert p.leader == cid("Julius Caesar") and cid("Homer") in p.left_play
    assert avail(g, s)[0] == 3 and g.stats(s).happiness == 0                             # 1 spent, 1 back


@rule("T5.7")
def test_wonder_stages_tokens_and_completion():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.unfinished = [cid("Pyramids"), 0, 0]                                               # stages 3, 2, 1
    tokens(g, s, "Bronze", 6)
    bank = p.blue_bank
    touch(g)
    answer(g, "Build a wonder stage")
    assert p.unfinished == [cid("Pyramids"), 1, 1] and E.resources(p) == 3
    assert p.blue_bank == bank + 3 - 1                                                   # paid 3, one token on stage
    place(g, s, "Masonry")                                                               # 2 stages per action
    answer(g, "Build a wonder stage")
    assert kind(g) == "STAGES"
    answer(g, "Build 2 stages")
    assert p.unfinished is None and cid("Pyramids") in p.wonders and E.resources(p) == 0
    assert g.stats(s).civil == 5 and avail(g, s)[0] == 3                                 # Pyramids: +1 civil action


@rule("T5.8")
def test_develop_technology_special_replacement_and_government():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.science = 30
    give(g, s, "Iron", "Code of Laws", "Monarchy")
    answer(g, "Develop Iron")
    assert cid("Iron") in p.techs and p.science == 25 and avail(g, s)[0] == 3
    answer(g, "Develop Code of Laws")
    assert p.specials["special_civil"] == cid("Code of Laws") and avail(g, s)[0] == 3   # +1 civil action
    place(g, s, "Justice System")
    assert p.specials["special_civil"] == cid("Justice System")
    give(g, s, ("Code of Laws", "I"))
    p.flags = {}
    answer(g, "Develop Code of Laws")                                                    # lower level: discarded
    assert p.specials["special_civil"] == cid("Justice System")
    sci = p.science
    answer(g, "Change government to Monarchy")
    if kind(g) == "REVOLT":
        answer(g, "Peaceful change")
    assert p.government == cid("Monarchy") and p.science == sci - 8


@rule("T5.9")
def test_revolution_costs_all_civil_actions_new_civil_actions_arrive_spent():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.science = 10
    give(g, s, "Monarchy")
    answer(g, "Change government to Monarchy")
    assert kind(g) == "REVOLT"
    answer(g, "Revolution to Monarchy")
    assert p.government == cid("Monarchy") and p.science == 8
    assert avail(g, s) == (0, 3)                                                         # 5 spent; military +1
    g = fresh(2, 0)
    s = g.current_seat
    g.p(s).science = 10
    give(g, s, "Monarchy", "Iron")
    answer(g, "Develop Iron")                                                            # one action spent
    g.p(s).science = 9
    touch(g)
    answer(g, "Change government to Monarchy")
    assert g.p(s).science == 1 and g.p(s).government == cid("Monarchy")                 # only peaceful (8)


@rule("T5.10")
def test_action_card_effect_then_discard_not_the_same_phase():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    g.s.row[0] = cid("Cultural Heritage", "A")
    touch(g)
    answer(g, "Take Cultural Heritage")
    assert not has(g, "Play action card Cultural Heritage")
    end_turn(g)
    play_to_round(g, 3)
    while g.current_seat != s:
        end_turn(g)
    sci, cul = p.science, p.culture
    answer(g, "Play action card Cultural Heritage")
    assert p.science == sci + 1 and p.culture == cul + 4 and cid("Cultural Heritage", "A") in g.s.removed_civil
    assert p.culture_book[("actions", cid("Cultural Heritage", "A"))] == 4 and avail(g, s)[0] == 3
    give(g, s, ("Rich Land", "A"))
    tokens(g, s, "Bronze", 1)
    answer(g, "Play action card Rich Land")                  # nothing to upgrade: "build" is forced
    answer(g, "Build on Bronze")                                                         # 2 - 1 discount: 1 paid
    assert p.workers[BRONZE] == 3 and E.resources(p) == 0 and avail(g, s)[0] == 2


# ===================================================================================================== T6 military (units, hand)
@rule("T6.1")
@rule("T6.2")
@rule("T6.3")
def test_build_upgrade_disband_units_with_military_actions():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Swordsmen")
    tokens(g, s, "Bronze", 6)
    answer(g, "Build a military unit")
    answer(g, "Build a unit on Warriors")
    assert p.workers[WARRIORS] == 2 and E.resources(p) == 4 and avail(g, s) == (4, 1)
    answer(g, "Upgrade a military unit")                     # Warriors -> Swordsmen (3 - 2 = 1), forced steps
    assert p.workers[cid("Swordsmen")] == 1 and E.resources(p) == 3 and avail(g, s) == (4, 0)
    assert g.stats(s).strength == 1 + 2


@rule("T6.5")
def test_military_hand_limit_at_end_of_turn_and_discard_by_age():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    old = cid("Development of Agriculture", "A")
    give(g, s, ("Military Bonus", "I"), ("Legion", "I"))
    p.military_hand.append(old)
    end_turn_kinds = []
    answer(g, "End the action phase")
    end_turn_kinds.append(kind(g))
    answer(g, "Discard military card Development of Agriculture")
    assert old in g.s.removed_military and old not in g.s.military_discard
    assert end_turn_kinds == ["DISCARD_MILITARY"]
    from games.through_the_ages import military
    military.discard(g, cid("Legion", "I"))
    assert cid("Legion", "I") in g.s.military_discard


# ===================================================================================================== T11 statistics
@rule("T11.1")
def test_symbols_per_worker_and_unfinished_wonders_give_nothing():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.workers[RELIGION] = 2
    touch(g)
    st = g.stats(s)
    assert st.culture == 2 and st.happiness == 2 and st.civil == 4                      # Despotism once
    p.unfinished = [cid("Pyramids"), 2, 2]
    touch(g)
    assert g.stats(s).civil == 4


@rule("T11.2")
@rule("T11.5")
def test_ratings_and_happiness_are_clipped():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Fundamentalism")                                                        # science -2
    p.workers[PHILOSOPHY] = 1
    touch(g)
    assert g.stats(s).science == 0
    p.workers[RELIGION] = 12
    touch(g)
    assert g.stats(s).happiness == 8


@rule("T11.6")
def test_action_totals_rise_available_fall_spent_first():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.civil_spent = 2
    place(g, s, "Code of Laws")
    assert avail(g, s)[0] == 3 and p.civil_spent == 2                                    # new action available
    p.military_spent = 1
    place(g, s, "Julius Caesar")                                                         # +1 military
    assert avail(g, s)[1] == 2
    before = E.totals(g, s)
    g.leave_play(s, p.leader)
    p.leader = None
    E.settle_totals(g, s, before)
    assert p.military_spent == 0 and avail(g, s)[1] == 2                                 # spent removed first
    p.temp_civil = 1
    E.spend_civil(p, 1)
    assert p.temp_civil == 0 and p.civil_spent == 2                                      # temporary first


@rule("T11.8")
def test_uprising_skips_production():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.yellow_bank = 10                                                                   # 3 happy faces required
    p.yellow_owned -= 8
    touch(g)
    assert E.discontent(g, s) == 3 and p.pool == 1
    sci = p.science
    end_turn(g)
    assert p.science == sci and "Uprising" in g.s.log.render(last=30)
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.yellow_bank, p.pool = 16, 3
    p.yellow_owned = 16 + 3 + 6
    touch(g)
    assert E.discontent(g, s) == 1
    sci = p.science
    end_turn(g)
    assert p.science == sci + 1


@rule("T11.9")
def test_token_symbols_enter_and_leave_play():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    bank = p.blue_bank
    place(g, s, "Justice System")                                                        # +3 blue tokens
    assert p.blue_bank == bank + 3 and p.blue_owned == 19
    tokens(g, s, "Agriculture", 3)
    tokens(g, s, "Bronze", 2)
    p.blue_bank = 1
    p.blue_owned = 1 + 5
    before = E.totals(g, s)
    del p.specials["special_civil"]
    g.leave_play(s, cid("Justice System"))
    E.settle_totals(g, s, before)
    g._run()
    assert kind(g) == "LOSE_BLUE" and p.blue_bank == 0
    answer(g, "Take a blue token from Bronze")
    answer(g, "Take a blue token from Agriculture")
    assert p.tokens == {AGRICULTURE: 2, BRONZE: 1} and p.blue_owned == 3
    p.yellow_bank = 1
    g.change_tokens(s, 0, -3)                                                            # D6: only what the bank holds
    assert p.yellow_bank == 0


@rule("T11.10")
def test_card_levels():
    assert [LEVEL[cid(n)] for n in ("Agriculture", "Irrigation", "Selective Breeding", "Mechanized Agriculture")] \
        == [0, 1, 2, 3]


# ===================================================================================================== T12 food and resources
@rule("T12.1")
def test_token_values_by_card():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Irrigation")
    tokens(g, s, "Agriculture", 2)
    tokens(g, s, "Irrigation", 3)
    assert E.food(p) == 2 + 6


@rule("T12.2")
def test_gain_uses_fewest_tokens_and_bank_limit():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Irrigation")
    tokens(g, s, "Agriculture", 0)
    p.blue_bank = 10
    E.gain(p, "farm", 5)
    assert p.tokens == {cid("Irrigation"): 2, AGRICULTURE: 1, **{k: v for k, v in p.tokens.items()
                                                                if k not in (cid("Irrigation"), AGRICULTURE)}}
    assert p.blue_bank == 7
    p.blue_bank = 1
    assert E.gain(p, "farm", 5) == 2 and p.blue_bank == 0


@rule("T12.3")
def test_pay_exact_with_change_or_overpay_only_without_change():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Iron")
    tokens(g, s, "Agriculture", 0)
    tokens(g, s, "Bronze", 3)
    tokens(g, s, "Iron", 1)
    E.pay(p, "mine", 2)                                       # exact: return 2 Bronze tokens (most tokens back)
    assert p.tokens == {BRONZE: 1, cid("Iron"): 1}
    tokens(g, s, "Bronze", 0)
    E.pay(p, "mine", 1)                                       # change: the Iron token becomes a Bronze token
    assert p.tokens == {BRONZE: 1}
    tokens(g, s, "Bronze", 0)
    tokens(g, s, "Iron", 1)
    bank = p.blue_bank
    p.blue_bank = 0
    paid = E.pay(p, "mine", 1)                                # no bank token for change -> overpay
    assert paid == 1 and p.tokens == {BRONZE: 1} and p.blue_bank == 0
    p.blue_bank = bank
    with pytest.raises(ValueError):
        E.pay(p, "mine", 5)
    assert E.lose(p, "mine", 5) == 4 and E.resources(p) == 0  # losing more than you have: lose all


@rule("T12.4")
def test_points_never_below_zero_actual_loss_booked():
    g = fresh(2, 0)
    p = g.p(g.current_seat)
    p.culture = 3
    assert E.add_culture(p, -10, "famine") == -3 and p.culture == 0
    assert p.culture_book[("famine", None)] == -3
    p.science = 2
    assert E.add_science(p, -5) == -2 and p.science == 0


@rule("T12.5")
def test_corruption_before_production_rest_as_food():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    tokens(g, s, "Bronze", 1)
    tokens(g, s, "Agriculture", 5)
    p.blue_bank = 5                                                                      # corruption 4
    p.blue_owned = 5 + 6
    g.production(s)
    # corruption: 1 resource + 3 food; then +2 food (2 farmers), consumption 0, +2 resources
    assert E.food(p) == 5 - 3 + 2 and E.resources(p) == 2


@rule("T12.6")
@rule("T12.8")
def test_production_highest_level_first_when_bank_runs_short():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Irrigation")
    p.workers[cid("Irrigation")] = 2
    p.workers[AGRICULTURE] = 0
    tokens(g, s, "Agriculture", 0)
    tokens(g, s, "Bronze", 0)
    p.blue_bank = 1
    p.blue_owned = 1
    touch(g)
    assert E.produce(p, "farm") == 2 and p.tokens == {cid("Irrigation"): 1} and p.blue_bank == 0
    assert E.produce(p, "mine") == 0


@rule("T12.7")
def test_consumption_and_famine():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    p.yellow_bank = 8                                                                    # consumption 3
    p.pool += 10
    p.workers[RELIGION] = 0
    p.workers[AGRICULTURE] = 0
    tokens(g, s, "Agriculture", 1)
    p.culture = 5
    touch(g)
    g.production(s)                                           # 1 food paid, 2 missing: -8 culture, only 5 to lose
    assert E.food(p) == 0 and p.culture == 0
    assert p.culture_book[("famine", None)] == -5


@rule("T15.6")
def test_resource_production_bonus_after_mines():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    place(g, s, "Communism")                                                             # +1 resource production
    tokens(g, s, "Bronze", 0)
    p.blue_bank = 16
    p.blue_owned = 16 + sum(p.tokens.values())
    p.workers[RELIGION] = 2
    p.pool = 5
    touch(g)
    g.production(s)
    assert E.resources(p) == 2 + 1


# ===================================================================================================== T13 ages
@rule("T13.1")
def test_age_a_ends_at_first_refill():
    g = started(2, 9)
    deck_a = list(g.s.civil_deck)
    play_to_round(g, 2)
    s = g.s
    assert s.age == "I" and None not in s.row
    assert all(c in s.removed_civil or c in s.row for c in deck_a)
    assert all(AGE[c] == "I" for c in s.civil_deck if c < LEADER_PROXY)
    assert all(p.yellow_bank == 18 for p in s.players)                                   # nothing lost


@rule("T13.2")
def test_age_ends_when_last_card_is_dealt_refill_goes_on():
    g = fresh(2, 0)
    s = g.s
    s.civil_deck[:] = s.civil_deck[:1]
    s.row[3] = None
    s.row[4] = None
    g.refill()
    assert s.age == "II" and None not in s.row
    assert sum(AGE[c] == "II" for c in s.row) >= 4


@rule("T13.3")
@rule("T13.4")
def test_age_ii_antiquates_age_a_and_costs_two_yellow_tokens():
    g = fresh(2, 0)
    s = g.current_seat
    p = g.p(s)
    give(g, s, ("Stockpile", "A"), "Iron")
    place(g, s, "Homer")
    p.unfinished = [cid("Pyramids"), 1, 1]
    p.blue_bank -= 1
    yb = p.yellow_bank
    bank = p.blue_bank
    g.begin_age("II")
    assert p.civil_hand == [cid("Iron")] and p.leader is None and cid("Homer") in p.left_play
    assert p.unfinished is None and p.blue_bank == bank + 1
    assert AGRICULTURE in p.techs and p.yellow_bank == yb - 2


@rule("T13.5")
def test_new_age_replaces_military_deck_and_discard():
    g = fresh(2, 0)
    s = g.s
    s.military_discard = [s.military_deck.pop()]
    g.begin_age("II")
    assert s.military_discard == [] and all(AGE[c] == "II" for c in s.military_deck)
    assert sum(AGE[c] == "I" for c in s.removed_military) == len(military_deck_cards("I", 2))


# ===================================================================================================== T14 end
@rule("T14.1")
def test_last_round_depends_on_who_starts_age_iv():
    g = fresh(2, 0)
    g.begin_age("II"), g.begin_age("III")
    g.s.turn_seat = g.s.round_first
    g.begin_age("IV")
    assert g.s.last_round == g.s.round
    g = fresh(2, 0)
    g.begin_age("II"), g.begin_age("III")
    g.s.turn_seat = 1 - g.s.round_first
    g.begin_age("IV")
    assert g.s.last_round == g.s.round + 1


@rule("T14.1")
@rule("T14.3")
def test_game_ends_after_last_round_equal_turns_score_is_culture():
    for n in (2, 3, 4):
        g = new_game(n, 21)
        rng = random.Random(n)
        while not g.game_over:
            g.step_id(rng.choice(g.legal_ids()))
        assert g.s.age == "IV" and g.s.round == g.s.last_round
        assert g.s.turns == g.s.round * n
        assert all(sum(l.startswith(f"P{i}: Production") or l == f"P{i}: Uprising: no production"
                       for l in g.s.log) == g.s.round for i in range(n))
        assert g.scores() == [p.culture for p in g.s.players]
        assert [sum(b.values()) for b in g.breakdowns()] == g.scores()


# ===================================================================================================== T15 public mix
@rule("T15.4")
def test_public_mix_selection_sizes():
    for n, (nl, nw) in ((2, (6, 4)), (3, (7, 5)), (4, (7, 5))):
        g = started(n, 13)
        for age in ("A", "I", "II", "III"):
            sel = g.s.selection[age]
            assert len(set(sel["leaders"])) == nl and len(set(sel["wonders"])) == nw
            assert all(KIND[c] == "leader" and AGE[c] == age for c in sel["leaders"])
            assert all(KIND[c] == "wonder" and AGE[c] == age for c in sel["wonders"])


@rule("T15.9")
def test_proxies_are_replaced_by_the_board_cards():
    g = fresh(4, 2)
    s = g.s
    sel = s.selection["I"]
    s.civil_deck[:0] = [LEADER_PROXY + 2, WONDER_PROXY + 1]
    s.proxies_created += 2
    s.civil_created -= 2
    s.row[0] = None
    s.row[1] = None
    s.row[2] = None
    g.refill()
    assert sel["leaders"][2] in s.row and sel["wonders"][1] in s.row
    assert all(c < LEADER_PROXY for c in s.row)


# ===================================================================================================== T16 information
@rule("T16.1")
def test_encoder_hides_other_players_hands():
    g = fresh(3, 1)
    s = g.current_seat
    other = (s + 1) % 3
    enc = SPEC.encoder(3)
    g.p(other).civil_hand = [cid("Iron")]
    g.p(other).military_hand = [cid("Legion", "I")]
    v1 = enc.encode(g, s)
    g.p(other).civil_hand = [cid("Alchemy")]
    g.p(other).military_hand = [cid("Military Bonus", "I")]
    assert np.array_equal(v1, enc.encode(g, s))
    g.p(s).civil_hand = [cid("Alchemy")]
    assert not np.array_equal(v1, enc.encode(g, s))
    assert enc.size == len(v1) and v1.min() >= 0 and v1.max() <= 1


# ===================================================================================================== whole games
@pytest.mark.parametrize("n", [2, 3, 4])
def test_random_games_end_well_below_max_steps_and_keep_invariants(n):
    for seed in range(3):
        g = new_game(n, 100 + seed)
        rng = random.Random(seed)
        steps = 0
        while not g.game_over:
            if steps % 5 == 0:
                assert SPEC.invariants(g) == []
            legal = g.legal_ids()
            assert legal
            g.step_id(rng.choice(legal))
            steps += 1
        assert steps < SPEC.max_steps // 10
        assert SPEC.invariants(g) == []
        assert [sum(b.values()) for b in g.breakdowns()] == g.scores()


def test_clone_is_independent():
    g = fresh(2, 0)
    c = g.clone()
    rng = random.Random(1)
    before = g.text_state()
    for _ in range(50):
        if c.game_over:
            break
        c.step_id(rng.choice(c.legal_ids()))
    assert g.text_state() == before
