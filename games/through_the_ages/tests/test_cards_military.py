"""One test per military-deck card (base, rebalanced and expansion military decks, 125 cards): the card is used
through the real flow (revealed as an event, colonized, played as an aggression, war, pact or tactic, used in
defense or colonization) and its effect is checked. Grouped by effect family; every case names its card."""
import pytest

from games.through_the_ages import economy as E
from games.through_the_ages import military as M
from games.through_the_ages import politics as P
from games.through_the_ages.cards import (AGE, BONUS, BY_KEY, CARDS, EFFECT, KIND, LEVEL, NAME, RESOURCE_COST,
                                          S_UNHAPPY, TACTIC)
from games.through_the_ages.tests.conftest import (answer, cid, fresh, give, has, kind, mil, next_turn, place,
                                                   politics, reveal_now, run_now, strength, tokens, touch)

card = pytest.mark.card


def mcard(key, *extra):
    """One parametrized case per card, marked card("<key>") (tools/check_repo.py reads the marks)."""
    return pytest.param(key, *extra, marks=card(key), id=key)


def game(n=2, seed=0):
    g = fresh(n, seed)
    s = g.current_seat
    return g, s, [(s + k) % n for k in range(1, n)]


def snap(g, x):
    p = g.p(x)
    return {"food": E.food(p), "resources": E.resources(p), "science": p.science, "culture": p.culture,
            "population": p.pool, "military_cards": len(p.military_hand), "yellow": p.yellow_bank,
            "blue": p.blue_owned, "workers": g.workers_total(x), "civil": E.civil_available(g, x)}


def diff(a, b):
    return {k: b[k] - a[k] for k in a if b[k] != a[k]}


def maybe(g, text):
    if has(g, text):
        answer(g, text)


def stronger(g, s, k=2):
    mil(g, s, "Swordsmen", k=k)                       # strength 1 + 2k


# ===================================================================================================== Age A events
@pytest.mark.parametrize("key", [mcard("development_of_agriculture_a"), mcard("development_of_crafts_a"),
                                 mcard("development_of_politics_a"), mcard("development_of_science_a"),
                                 mcard("development_of_settlement_a"), mcard("development_of_trade_routes_a"),
                                 mcard("pestilence_i")])
def test_each_civilization_gains(key):
    g, s, (o,) = game()
    c = BY_KEY[key]
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, c)
    for x in (s, o):
        d = diff(before[x], snap(g, x))
        exp = dict(EFFECT[c]["gain"])
        if "population" in exp:                      # gain/lose population: pool and yellow bank move together
            exp["yellow"] = -exp["population"]
        for k, v in exp.items():
            assert d.get(k, 0) == v, (key, k, d)
    assert c in g.s.past_events


@pytest.mark.parametrize("key", [mcard("development_of_markets_a")])
def test_each_chooses_food_or_resources(key):
    g, s, (o,) = game()
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, BY_KEY[key])
    answer(g, "Gain 2 food")
    answer(g, "Gain 2 resources")
    assert diff(before[s], snap(g, s)) == {"food": 2}
    assert diff(before[o], snap(g, o)) == {"resources": 2}


@pytest.mark.parametrize("key", [mcard("development_of_religion_a"), mcard("development_of_warfare_a")])
def test_each_may_build_a_free_age_a_building(key):
    target = {"development_of_religion_a": "Religion", "development_of_warfare_a": "Warriors"}[key]
    g, s, (o,) = game()
    c = cid(target)
    w = [g.p(x).workers.get(c, 0) for x in (s, o)]
    res = [E.resources(g.p(x)) for x in (s, o)]
    reveal_now(g, BY_KEY[key])
    answer(g, "for free")
    answer(g, "Do not build")
    assert g.p(s).workers[c] == w[0] + 1 and g.p(o).workers.get(c, 0) == w[1]
    assert [E.resources(g.p(x)) for x in (s, o)] == res and g.p(s).pool == 0




@pytest.mark.parametrize("key", [mcard("development_of_civilization_a")])
def test_development_of_civilization_one_cheaper_action(key):
    g, s, (o,) = game()
    before = snap(g, s)
    cost = E.pop_cost(g.p(s).yellow_bank)
    reveal_now(g, BY_KEY[key])
    assert kind(g) == "SUB_ACTION" and g.current_seat == s
    answer(g, "Increase population (1 food less)")
    assert g.current_seat == o
    answer(g, "Do nothing")
    d = diff(before, snap(g, s))
    assert d["population"] == 1 and d["food"] == -(cost - 1) and d.get("civil", 0) == 0


@pytest.mark.parametrize("key", [mcard("development_of_planning_a")])
def test_development_of_planning_each_picks_one_for_itself(key):
    g, s, (o,) = game()
    shown = [cid("Development of Science"), cid("Development of Crafts"), cid("Development of Agriculture")]
    g.s.age_a_unused = list(shown)
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, BY_KEY[key])
    assert kind(g) == "EVENT_CHOICE" and g.current_seat == s
    answer(g, "Apply Development of Science")
    assert g.current_seat == o
    answer(g, "Apply Development of Crafts")
    assert diff(before[s], snap(g, s)) == {"science": 2}
    assert diff(before[o], snap(g, o)) == {"resources": 2}
    assert sorted(g.s.age_a_unused) == sorted(shown) and not g.s.resolving


# ===================================================================================================== Age I events
@pytest.mark.parametrize("key", [mcard("barbarians_i")])
def test_barbarians_most_culture_among_two_weakest_loses_population(key):
    g, s, (o,) = game()
    stronger(g, s)
    g.p(o).culture = 10
    reveal_now(g, BY_KEY[key])
    assert g.p(o).pool == 0 and g.p(s).pool == 1
    g, s, (o,) = game()
    stronger(g, s)
    g.p(s).culture = 10                                                            # the strongest: nothing
    reveal_now(g, BY_KEY[key])
    assert g.p(s).pool == 1 and g.p(o).pool == 1


@pytest.mark.parametrize("key", [mcard("border_conflict_i")])
def test_border_conflict_weakest_destroys_strongest_gains(key):
    g, s, (o,) = game()
    stronger(g, s)
    res = E.resources(g.p(s))
    agri = g.p(o).workers[cid("Agriculture")]
    reveal_now(g, BY_KEY[key])
    assert kind(g) == "LOSE_WORKER" and g.current_seat == o
    answer(g, "on Agriculture")
    assert g.p(o).workers[cid("Agriculture")] == agri - 1 and g.p(o).pool == 2
    assert E.resources(g.p(s)) == res + 3


@pytest.mark.parametrize("key", [mcard("call_to_arms_i")])
def test_call_to_arms_weakest_lose_actions_draw_cards(key):
    g, s, (o1, o2) = game(3)
    before = {x: snap(g, x) for x in (s, o1, o2)}
    reveal_now(g, BY_KEY[key])                                                     # all equal: o2 then o1 weakest
    assert diff(before[o2], snap(g, o2)) == {"civil": -2, "military_cards": 2}
    assert diff(before[o1], snap(g, o1)) == {"civil": -1, "military_cards": 1}
    assert diff(before[s], snap(g, s)) == {}


@pytest.mark.parametrize("key", [mcard("crusades_i"), mcard("reign_of_terror_i"), mcard("refugees_ii"),
                                 mcard("independence_declaration_ii")])
def test_strongest_and_weakest(key):
    g, s, (o,) = game()
    c = BY_KEY[key]
    stronger(g, s)
    g.p(s).culture = g.p(o).culture = 10
    terr = cid("Historic Territory", "I")
    g.p(o).colonies.append(terr)
    g.enter_play(o, terr)
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, c)
    ds, do = diff(before[s], snap(g, s)), diff(before[o], snap(g, o))
    eff = EFFECT[c]
    for gain, d in ((eff.get("strongest", {}), ds), (eff.get("weakest", {}), do)):
        for k, v in gain.items():
            assert d.get(k, 0) == v, (key, k, d)
    if eff.get("weakest_loses_colony"):
        assert g.p(o).colonies == [] and terr not in g.p(o).play_order


@pytest.mark.parametrize("key", [mcard("cultural_influence_i"), mcard("scientific_breakthrough_i")])
def test_score_own_rating(key):
    g, s, (o,) = game()
    p = g.p(s)
    p.workers[cid("Religion")] = 1
    p.pool -= 1
    touch(g, s)
    st = E.stats(g, s)
    before = snap(g, s)
    reveal_now(g, BY_KEY[key])
    d = diff(before, snap(g, s))
    if EFFECT[BY_KEY[key]]["rating"] == "culture":
        assert d == {"culture": st.culture} and st.culture == 1
    else:
        assert d == {"science": st.science} and st.science >= 1


@pytest.mark.parametrize("key", [mcard("dark_ages_i")])
def test_dark_ages_lose_half_of_science_above_four(key):
    g, s, (o,) = game()
    g.p(s).science, g.p(o).science = 9, 4
    reveal_now(g, BY_KEY[key])
    assert (g.p(s).science, g.p(o).science) == (6, 4)


@pytest.mark.parametrize("key", [mcard("foray_i"), mcard("raiders_i")])
def test_two_strongest_gain_or_two_weakest_lose_a_mix(key):
    g, s, (o,) = game()
    stronger(g, s)
    tokens(g, o, "Bronze", 2)
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, BY_KEY[key])
    if key == "foray_i":                                                           # 2 players: the stronger
        assert g.current_seat == s and kind(g) == "MIX" and not has(g, "Stop")
        answer(g, "Gain 1 food")
        answer(g, "Gain 1 resource")
        answer(g, "Gain 1 resource")
        assert diff(before[s], snap(g, s)) == {"food": 1, "resources": 2} and diff(before[o], snap(g, o)) == {}
    else:
        assert g.current_seat == o
        answer(g, "Lose 1 food")
        answer(g, "Lose 1 resource")
        assert diff(before[o], snap(g, o)) == {"food": -1, "resources": -1} and diff(before[s], snap(g, s)) == {}


@pytest.mark.parametrize("key", [mcard("good_harvest_i"), mcard("new_deposits_i"), mcard("economic_progress_ii")])
def test_produce_now(key):
    g, s, (o,) = game()
    p = g.p(s)
    p.yellow_bank -= 6                                                             # consumption 2
    p.pool += 6
    touch(g, s)
    before = snap(g, s)
    reveal_now(g, BY_KEY[key])
    d = diff(before, snap(g, s))
    farms = p.workers[cid("Agriculture")]
    mines = p.workers[cid("Bronze")]
    exp = {"good_harvest_i": {"food": farms}, "new_deposits_i": {"resources": mines},
           "economic_progress_ii": {"food": farms - 2, "resources": mines}}[key]  # corruption 0, consumption 2
    assert d == {k: v for k, v in exp.items() if v}


@pytest.mark.parametrize("key", [mcard("immigration_i")])
def test_immigration_all_with_most_happy_faces(key):
    g, s, (o1, o2) = game(3)
    for x in (s, o2):
        g.p(x).workers[cid("Religion")] = 1
        g.p(x).yellow_bank -= 1
        touch(g, x)
    reveal_now(g, BY_KEY[key])
    assert [g.p(x).pool for x in (s, o1, o2)] == [2, 1, 2]


@pytest.mark.parametrize("key", [mcard("knowledge_of_the_ancestors_i")])
def test_knowledge_of_the_ancestors(key):
    g, s, (o,) = game()
    place(g, s, "Pyramids")                                                        # Age A: counts double
    g.p(s).unfinished = [cid("Great Wall"), 0, 0]
    before = snap(g, s)
    reveal_now(g, BY_KEY[key])
    assert diff(before, snap(g, s)) == {"science": 2, "resources": 1}


@pytest.mark.parametrize("key", [mcard("rats_i")])
def test_rats_everyone_loses_all_food(key):
    g, s, (o,) = game()
    assert E.food(g.p(s)) > 0
    reveal_now(g, BY_KEY[key])
    assert E.food(g.p(s)) == 0 and E.food(g.p(o)) == 0


@pytest.mark.parametrize("key", [mcard("rebellion_i")])
def test_rebellion_spends_two_civil_actions_per_discontent(key):
    g, s, (o1, o2) = game(3)
    for x, k in ((s, 10), (o1, 4)):                                                # discontent 4 (yellow 8), 1 (14)
        g.p(x).yellow_bank -= k
        g.p(x).pool += k
        touch(g, x)
    before = {x: snap(g, x) for x in (s, o1, o2)}
    reveal_now(g, BY_KEY[key])
    assert diff(before[s], snap(g, s)) == {"civil": -4}                            # all 4 it has (8 asked)
    assert diff(before[o1], snap(g, o1)).get("civil") == -2
    assert diff(before[o2], snap(g, o2)) == {}


@pytest.mark.parametrize("key", [mcard("uncertain_borders_i")])
def test_uncertain_borders_strongest_takes_a_yellow_token(key):
    g, s, (o,) = game()
    stronger(g, s)
    ys, yo = g.p(s).yellow_bank, g.p(o).yellow_bank
    reveal_now(g, BY_KEY[key])
    assert (g.p(s).yellow_bank, g.p(o).yellow_bank) == (ys + 1, yo - 1)


# ===================================================================================================== Age II events
@pytest.mark.parametrize("key", [mcard("arms_industry_ii")])
def test_arms_industry_resources_per_highest_unit_type(key):
    g, s, (o,) = game()
    place(g, s, "Knights")                                                         # only s has cavalry
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, BY_KEY[key])
    assert diff(before[s], snap(g, s)) == {"resources": 4}                         # infantry (tie) + cavalry
    assert diff(before[o], snap(g, o)) == {"resources": 2}


@pytest.mark.parametrize("key", [mcard("civil_unrest_ii")])
def test_civil_unrest(key):
    g, s, (o,) = game()
    p = g.p(s)
    p.yellow_bank -= 6                                                             # 12 left: 2 discontent
    p.pool += 6
    p.culture = 20
    touch(g, s)
    bank = p.blue_bank
    reveal_now(g, BY_KEY[key])
    assert p.culture == 20 - 8 and p.blue_bank == bank - 1 and p.blue_owned == 15
    assert g.p(o).blue_owned == 16


@pytest.mark.parametrize("key", [mcard("cold_war_ii"), mcard("crime_wave_ii")])
def test_two_strongest_or_weakest_gain(key):
    g, s, (o,) = game()
    stronger(g, s)
    g.p(s).culture = g.p(o).culture = 10
    before = {x: snap(g, x) for x in (s, o)}
    reveal_now(g, BY_KEY[key])
    if key == "cold_war_ii":
        assert diff(before[s], snap(g, s)) == {"science": 6} and diff(before[o], snap(g, o)) == {}
    else:
        assert diff(before[o], snap(g, o)) == {"culture": -3, "blue": -1} and diff(before[s], snap(g, s)) == {}


@pytest.mark.parametrize("key", [mcard("emigration_ii")])
def test_emigration_loses_half_the_discontent_workers(key):
    g, s, (o,) = game()
    p = g.p(s)
    p.yellow_bank -= 8                                                             # 10 left: 3 discontent
    p.pool += 8
    touch(g, s)
    reveal_now(g, BY_KEY[key])
    assert p.pool == 9 - 2 and p.yellow_bank == 12


@pytest.mark.parametrize("key", [mcard("freedom_of_movement_ii")])
def test_freedom_of_movement(key):
    g, s, (o,) = game()
    agri, bronze = cid("Agriculture"), cid("Bronze")
    w = dict(g.p(s).workers)
    reveal_now(g, BY_KEY[key])
    answer(g, "Move a worker from Agriculture")
    answer(g, "to Bronze")
    assert g.current_seat == o
    answer(g, "Move no worker")
    assert g.p(s).workers[agri] == w[agri] - 1 and g.p(s).workers[bronze] == w[bronze] + 1


@pytest.mark.parametrize("key", [mcard("iconoclasm_ii")])
def test_iconoclasm_removes_leaders_of_other_ages(key):
    g, s, (o,) = game()
    homer = place(g, s, "Homer")
    joan = place(g, o, "Joan of Arc")
    reveal_now(g, BY_KEY[key])                                                     # Age I now
    assert g.p(s).leader is None and homer in g.p(s).left_play and g.p(o).leader == joan


@pytest.mark.parametrize("key", [mcard("international_agreement_ii")])
def test_international_agreement_takes_for_five_actions_and_forfeits_politics(key):
    g, s, (o,) = game()
    stronger(g, s)
    row = list(g.s.row)
    reveal_now(g, BY_KEY[key])
    assert kind(g) == "TAKE_LOOP" and g.current_seat == s
    answer(g, "from row slot 1 ")
    answer(g, "from row slot 2 ")
    answer(g, "Stop taking cards")
    p = g.p(s)
    assert sorted(p.civil_hand) == sorted(row[:2]) and p.forfeit_politics == 1
    assert g.s.row[:11] == row[2:] and None not in g.s.row                         # slid left, refilled
    next_turn(g)
    next_turn(g)
    assert any("gives up this political action" in x for x in g.s.log) and p.forfeit_politics == 0


@pytest.mark.parametrize("key", [mcard("international_negotiations_ii")])
def test_international_negotiations(key):
    g, s, (o,) = game()
    stronger(g, s)
    g.p(o).science = 5
    tokens(g, o, "Agriculture", 4)                                                 # science or food possible
    sci = g.p(s).science
    reveal_now(g, BY_KEY[key])
    assert kind(g) == "EVENT_CHOICE" and g.current_seat == s                       # the revealer chooses
    answer(g, "pays 3 science")
    assert g.p(o).science == 2 and g.p(s).science == sci + 3


@pytest.mark.parametrize("key", [mcard("national_pride_ii")])
def test_national_pride_most_culture_points_score(key):
    g, s, (o,) = game()
    g.p(o).culture = 7
    reveal_now(g, BY_KEY[key])
    assert g.p(o).culture == 12 and g.p(s).culture == 0


@pytest.mark.parametrize("key", [mcard("politics_of_strength_ii")])
def test_politics_of_strength(key):
    g, s, (o,) = game()
    stronger(g, s)
    give(g, o, "Legion", "Phalanx", ("Military Bonus", "I"), "Fighting Band")
    hand = len(g.p(s).military_hand)
    reveal_now(g, BY_KEY[key])
    assert len(g.p(s).military_hand) == hand + 5
    for _ in range(2):
        g.step_id(g.legal_ids()[0])
    g.step_id(g.legal_ids()[0])
    assert len(g.p(o).military_hand) == 1
    g, s, (o,) = game()                                                            # Age IV: culture instead
    stronger(g, s)
    g.s.age = "IV"
    g.p(o).culture = 10
    reveal_now(g, BY_KEY[key])
    assert g.p(s).culture == 5 and g.p(o).culture == 7


@pytest.mark.parametrize("key", [mcard("popularization_of_science_ii")])
def test_popularization_of_science(key):
    g, s, (o,) = game()
    sci = E.stats(g, s).science
    reveal_now(g, BY_KEY[key])
    assert g.p(s).culture == sci and sci >= 1


@pytest.mark.parametrize("key", [mcard("prosperity_ii")])
def test_prosperity_food_per_happy_face(key):
    g, s, (o,) = game()
    place(g, s, "Theology", workers=1)                                             # 2 happy faces
    food = E.food(g.p(s))
    reveal_now(g, BY_KEY[key])
    assert E.food(g.p(s)) == food + 2


@pytest.mark.parametrize("key", [mcard("ravages_of_time_ii")])
def test_ravages_of_time_ruins_an_old_wonder(key):
    g, s, (o,) = game()
    pyr = place(g, s, "Pyramids")
    civil, cult = E.stats(g, s).civil, E.stats(g, s).culture
    reveal_now(g, BY_KEY[key])
    st = E.stats(g, s)
    assert g.p(s).ruined == [pyr] and pyr not in g.p(s).wonders
    assert st.civil == civil - 1 and st.culture == cult + 2


@pytest.mark.parametrize("key", [mcard("terrorism_ii")])
def test_terrorism_fewest_culture_destroys_urban_buildings(key):
    g, s, (o1, o2) = game(3)
    g.p(s).culture, g.p(o2).culture = 5, 3
    phil = cid("Philosophy")
    reveal_now(g, BY_KEY[key])                                                     # o1 has the fewest
    assert g.p(s).workers[phil] == 0 and g.p(o2).workers[phil] == 0 and g.p(o1).workers[phil] == 1
    assert g.p(s).pool == 2


# ===================================================================================================== Age III events
def impact(key, setup, expected):
    g, s, (o,) = game()
    setup(g, s, o)
    before = [g.p(x).culture for x in (s, o)]
    reveal_now(g, BY_KEY[key])
    assert [g.p(x).culture - b for x, b in zip((s, o), before)] == expected(g, s, o), key


def _workers(g, s, name, k, age=None):
    place(g, s, name, age, workers=k)


IMPACTS = {
    "impact_of_agriculture_iii": (lambda g, s, o: None, lambda g, s, o: [2 + 4, 2 + 4]),     # 2 farmers, no consumption
    "impact_of_architecture_iii": (lambda g, s, o: _workers(g, s, "Alchemy", 2), lambda g, s, o: [2, 0]),
    "impact_of_balance_iii": (lambda g, s, o: _workers(g, s, "Theology", 1), lambda g, s, o: [2 * 1, 0]),
    "impact_of_colonies_iii": (lambda g, s, o: g.p(s).colonies.extend([cid("Vast Territory", "I")] * 2),
                               lambda g, s, o: [6, 0]),
    "impact_of_competition_iii": (lambda g, s, o: (mil(g, s, "Swordsmen", k=2), _workers(g, o, "Bread and Circuses",
                                                                                           1)),
                                  lambda g, s, o: [2, 1]),
    "impact_of_culture_iii": (lambda g, s, o: _workers(g, o, "Theology", 1), lambda g, s, o: [0, 10]),
    "impact_of_government_iii": (lambda g, s, o: place(g, s, "Warfare"), lambda g, s, o: [2 * 4 + 3, 2 * 4 + 2]),
    "impact_of_happiness_iii": (lambda g, s, o: (_workers(g, s, "Theology", 1), setattr(g.p(o), "yellow_bank", 12)),
                                lambda g, s, o: [4, -0]),
    "impact_of_harmony_iii": (lambda g, s, o: None, lambda g, s, o: [4 * 1, 4 * 1]),         # 1 unit, 1 urban
    "impact_of_industry_iii": (lambda g, s, o: _workers(g, s, "Iron", 1), lambda g, s, o: [2 + 2, 2]),
    "impact_of_population_iii": (lambda g, s, o: (setattr(g.p(s), "pool", 7), setattr(g.p(s), "yellow_bank", 12)),
                                 lambda g, s, o: [2 * (13 - 2 - 10), 0]),
    "impact_of_progress_iii": (lambda g, s, o: place(g, s, "Warfare"), lambda g, s, o: [2, 0]),
    "impact_of_science_iii": (lambda g, s, o: _workers(g, o, "Alchemy", 1), lambda g, s, o: [0, 10]),
    "impact_of_strength_iii": (lambda g, s, o: mil(g, o, "Swordsmen"), lambda g, s, o: [0, 10]),
    "impact_of_technology_iii": (lambda g, s, o: (place(g, s, "Computers"), place(g, s, "Tanks")),
                                 lambda g, s, o: [8, 0]),
    "impact_of_variety_iii": (lambda g, s, o: (place(g, s, "Warfare"), _workers(g, s, "Theology", 1)),
                              lambda g, s, o: [2 * (1 + 2 + 1), 2 * 2]),     # infantry, lab+temple, special
    "impact_of_wonders_iii": (lambda g, s, o: (place(g, s, "Pyramids"), place(g, o, "Great Wall")),
                              lambda g, s, o: [5, 4]),
}


@pytest.mark.parametrize("key", [mcard("impact_of_agriculture_iii"), mcard("impact_of_architecture_iii"),
                                 mcard("impact_of_balance_iii"),
                                 mcard("impact_of_colonies_iii"),
                                 mcard("impact_of_competition_iii"),
                                 mcard("impact_of_culture_iii"),
                                 mcard("impact_of_government_iii"),
                                 mcard("impact_of_happiness_iii"),
                                 mcard("impact_of_harmony_iii"),
                                 mcard("impact_of_industry_iii"),
                                 mcard("impact_of_population_iii"),
                                 mcard("impact_of_progress_iii"),
                                 mcard("impact_of_science_iii"),
                                 mcard("impact_of_strength_iii"),
                                 mcard("impact_of_technology_iii"),
                                 mcard("impact_of_variety_iii"),
                                 mcard("impact_of_wonders_iii")])
def test_age_iii_impact_events(key):
    impact(key, *IMPACTS[key])


# ===================================================================================================== territories
TERRITORIES = ["developed_territory_i", "historic_territory_i", "inhabited_territory_i", "strategic_territory_i",
               "vast_territory_i", "wealthy_territory_i", "developed_territory_ii", "historic_territory_ii",
               "inhabited_territory_ii", "strategic_territory_ii", "vast_territory_ii", "wealthy_territory_ii",
               "autonomous_territory_ii"]


def colonize_alone(g, s, o, c):
    """o has no units (cannot bid); s bids 1 and sends its Warriors."""
    q = g.p(o)
    q.workers[cid("Warriors")] = 0
    q.pool += 1
    touch(g, o)
    reveal_now(g, c, seat=s)
    answer(g, "Bid 1 for")


@pytest.mark.parametrize("key", [mcard("developed_territory_i"), mcard("historic_territory_i"),
                                 mcard("inhabited_territory_i"),
                                 mcard("strategic_territory_i"),
                                 mcard("vast_territory_i"),
                                 mcard("wealthy_territory_i"),
                                 mcard("developed_territory_ii"),
                                 mcard("historic_territory_ii"),
                                 mcard("inhabited_territory_ii"),
                                 mcard("strategic_territory_ii"),
                                 mcard("vast_territory_ii"),
                                 mcard("wealthy_territory_ii"),
                                 mcard("autonomous_territory_ii")])
def test_territory_colonized_permanent_and_one_time_effects(key):
    g, s, (o,) = game()
    c = BY_KEY[key]
    p = g.p(s)
    before = snap(g, s)
    st0 = E.stats(g, s)
    colonize_alone(g, s, o, c)
    if KIND[c] == "territory" and EFFECT[c]["type"] == "territory_choice":
        answer(g, "Gain 7 culture")
        once = {"culture": 7}
    else:
        once = dict(EFFECT[c]["once"])
    assert c in p.colonies and p.workers[cid("Warriors")] == 0
    d = diff(before, snap(g, s))
    y = CARDS[c]["yields"]
    exp = dict(once)
    exp["yellow"] = 1 + y.get("yellow_tokens", 0) - once.get("population", 0)    # sent worker, symbol, pop
    exp["blue"] = y.get("blue_tokens", 0)
    exp["workers"] = -1 + once.get("population", 0)
    exp["civil"] = y.get("civil_actions", 0)
    for k, v in exp.items():
        if k == "resources" and y.get("blue_tokens", 0) < 0:
            continue
        assert d.get(k, 0) == v, (key, k, d)
    st = E.stats(g, s)
    assert st.strength == st0.strength - 1 + y.get("strength", 0)
    assert st.happiness == min(8, st0.happiness + y.get("happy", 0))


# ===================================================================================================== aggressions
def attack(g, s, o, name, age, k=2, target=None):
    stronger(g, s, k)
    give(g, s, (name, age))
    politics(g, s)
    answer(g, "Play an aggression")
    maybe(g, f"on P{o}")


@pytest.mark.parametrize("key", [mcard("aggression_enslave_i")])
def test_enslave(key):
    g, s, (o,) = game()
    before = {x: snap(g, x) for x in (s, o)}
    attack(g, s, o, "Aggression: Enslave", "I")
    assert diff(before[o], snap(g, o)) == {"population": -1, "yellow": 1, "workers": -1}
    d = diff(before[s], snap(g, s))
    assert d["food"] == 2 and d["resources"] == 2


@pytest.mark.parametrize("key", [mcard("aggression_kidnap_i")])
def test_kidnap(key):
    g, s, (o,) = game()
    g.p(o).civil_hand = [cid("Iron"), cid("Homer")]
    attack(g, s, o, "Aggression: Kidnap", "I")
    assert kind(g) == "KIDNAP" and has(g, "Take no card")
    answer(g, "Take Homer")
    assert cid("Homer") in g.p(s).civil_hand and g.p(o).civil_hand == [cid("Iron")] and "A" in g.p(s).leaders_taken


@pytest.mark.parametrize("key", [mcard("aggression_plunder_i"), mcard("aggression_plunder_ii"),
                                 mcard("aggression_plunder_iii")])
def test_plunder(key):
    age = AGE[BY_KEY[key]]
    g, s, (o,) = game()
    tokens(g, o, "Bronze", 8)
    n = EFFECT[BY_KEY[key]]["amount"]
    before = {x: snap(g, x) for x in (s, o)}
    attack(g, s, o, "Aggression: Plunder", age)
    assert kind(g) == "MIX" and has(g, "Stop taking")
    for _ in range(n):
        answer(g, "Take 1 resource")
    assert diff(before[o], snap(g, o)) == {"resources": -n}
    assert diff(before[s], snap(g, s))["resources"] == n




@pytest.mark.parametrize("key", [mcard("aggression_raid_i"), mcard("aggression_raid_ii"), mcard("aggression_raid_iii")])
def test_raid(key):
    age = AGE[BY_KEY[key]]
    labs = {"I": ["Alchemy"], "II": ["Alchemy", "Scientific Method"], "III": ["Computers", "Scientific Method"]}[age]
    g, s, (o,) = game()
    place(g, s, "Warfare")                                                         # 3 military actions
    q = g.p(o)
    q.workers[cid("Philosophy")] = 0                                               # only the given labs
    q.pool += 1
    labs = [place(g, o, name, workers=1) for name in labs]
    res = E.resources(g.p(s))
    attack(g, s, o, "Aggression: Raid", age, k=3)
    while kind(g) == "LOSE_WORKER":
        answer(g, "Destroy a building on " + NAME[max((c for c in labs if g.p(o).workers.get(c, 0)), key=LEVEL.__getitem__)])
    assert all(g.p(o).workers[c] == 0 for c in labs)
    assert E.resources(g.p(s)) == res + (sum(RESOURCE_COST[c] for c in labs) + 1) // 2




@pytest.mark.parametrize("key", [mcard("aggression_annex_ii")])
def test_annex(key):
    g, s, (o,) = game()
    terr = cid("Strategic Territory", "II")
    g.p(o).colonies.append(terr)
    g.enter_play(o, terr)
    attack(g, s, o, "Aggression: Annex", "II", k=4)
    assert terr in g.p(s).colonies and strength(g, s) == 9 + 4 and strength(g, o) == 1


@pytest.mark.parametrize("key", [mcard("aggression_infiltrate_ii")])
def test_infiltrate(key):
    g, s, (o,) = game()
    joan = place(g, o, "Joan of Arc")
    attack(g, s, o, "Aggression: Infiltrate", "II")
    assert g.p(o).leader is None and joan in g.p(o).left_play and g.p(s).culture == 3


@pytest.mark.parametrize("key", [mcard("aggression_spy_ii"), mcard("aggression_armed_intervention_iii")])
def test_steal_points(key):
    c = BY_KEY[key]
    what, name, age = EFFECT[c]["what"], NAME[c], AGE[c]
    g, s, (o,) = game()
    setattr(g.p(o), what, 10)
    before = getattr(g.p(s), what)
    attack(g, s, o, name, age)
    n = EFFECT[BY_KEY[key]]["amount"]
    assert getattr(g.p(o), what) == 10 - n and getattr(g.p(s), what) == before + n




@pytest.mark.parametrize("key", [mcard("aggression_occupy_iii")])
def test_occupy_takes_a_bundle(key):
    g, s, (o,) = game()
    place(g, s, "Warfare")
    q = g.p(o)
    q.science, q.culture = 2, 10
    tokens(g, o, "Bronze", 5)
    before = {x: snap(g, x) for x in (s, o)}
    attack(g, s, o, "Aggression: Occupy", "III")
    d = diff(before[o], snap(g, o))
    assert d["resources"] == -3 and d["science"] == -2 and d["culture"] == -3 and d["food"] == -min(3, before[o]["food"])


# ===================================================================================================== wars
def war(g, s, o, name):
    g.p(s).wars = [[cid(name), o]]
    touch(g)
    run_now(g, P.resolve_wars, g, s)


@pytest.mark.parametrize("key", [mcard("war_over_technology_ii")])
def test_war_over_technology(key):
    g, s, (o,) = game()
    stronger(g, s, 4)                                                              # 9 vs 2 (Cartography +1): 7
    place(g, o, "Cartography")
    g.p(o).science = 10
    war(g, s, o, "War over Technology")
    answer(g, "Take Cartography")                                                  # cost 4: 3 left as science
    assert g.p(s).specials["special_colonization"] == cid("Cartography") and g.p(o).science == 7


@pytest.mark.parametrize("key", [mcard("war_over_territory_ii")])
def test_war_over_territory(key):
    g, s, (o,) = game()
    stronger(g, s, 5)                                                              # 11 vs 1: 1 + 10 // 5 = 3
    ys, yo = g.p(s).yellow_bank, g.p(o).yellow_bank
    war(g, s, o, "War over Territory")
    assert (g.p(s).yellow_bank, g.p(o).yellow_bank) == (ys + 3, yo - 3)


@pytest.mark.parametrize("key", [mcard("war_over_culture_iii")])
def test_war_over_culture(key):
    g, s, (o,) = game()
    mil(g, o, "Swordsmen", k=1)                                                    # the defender wins by 2
    g.p(s).culture = 20
    war(g, s, o, "War over Culture")
    assert g.p(s).culture == 20 - 7 and g.p(o).culture == 7


@pytest.mark.parametrize("key", [mcard("hybrid_war_iii")])
def test_hybrid_war_unhappy_while_pending_then_culture(key):
    g, s, (o1, o2) = game(3)
    stronger(g, s, 2)
    g.p(o1).culture = 10
    g.p(s).wars = [[cid("Hybrid War"), o1]]
    touch(g)
    assert [E.stats(g, x).v[S_UNHAPPY] for x in (s, o1, o2)] == [2, 2, 0]
    run_now(g, P.resolve_wars, g, s)
    assert g.p(o1).culture == 6 and g.p(s).culture == 4
    assert [E.stats(g, x).v[S_UNHAPPY] for x in (s, o1, o2)] == [0, 0, 0]


# ===================================================================================================== pacts
def make_pact(g, s, o, name, age, side=None):
    give(g, s, (name, age))
    politics(g, s)
    answer(g, "Offer a pact")
    answer(g, f"on P{o}")
    if side:
        answer(g, f"Take side {side}")
    answer(g, "Accept")


@pytest.mark.parametrize("key", [mcard("naval_trade_agreement_i")])
def test_naval_trade_agreement(key):
    g, s, (o, _) = game(3)
    bs, bo = g.p(s).blue_owned, g.p(o).blue_owned
    make_pact(g, s, o, "Naval Trade Agreement", "I", "A")
    assert g.p(s).blue_owned == bs - 1 and g.p(o).blue_owned == bo + 2 and E.stats(g, s).colonization == 1
    run_now(g, P.remove_pact, g, s, "test")
    assert g.p(s).blue_owned == bs and g.p(o).blue_owned == bo and E.stats(g, s).colonization == 0


@pytest.mark.parametrize("key", [mcard("open_borders_agreement_i")])
def test_open_borders(key):
    g, s, (o, x) = game(3)
    ma = [E.stats(g, y).military for y in (s, o, x)]
    make_pact(g, s, o, "Open Borders Agreement", "I")
    assert [E.stats(g, y).military for y in (s, o, x)] == [ma[0] + 1, ma[1] + 1, ma[2]]
    assert M.attack_strengths(g, s, o) == (1 + 2, 1) and M.attack_strengths(g, s, x) == (1, 1)


@pytest.mark.parametrize("key", [mcard("trade_routes_agreement_i")])
def test_trade_routes(key):
    g, s, (o, _) = game(3)
    make_pact(g, s, o, "Trade Routes Agreement", "I", "A")
    tokens(g, s, "Bronze", 1)
    food = E.food(g.p(s))
    assert g.afford(s, "mine", 1 + food) and not g.afford(s, "mine", 2 + food) and not g.afford(o, "farm", 99)
    answer(g, "Build a military unit")                                             # Warriors cost 2: 1 + 1 food
    assert E.resources(g.p(s)) == 0 and E.food(g.p(s)) == food - 1
    assert g.afford(s, "mine", 1)                                                  # no per-turn limit (D33)


@pytest.mark.parametrize("key", [mcard("acceptance_of_supremacy_ii"), mcard("international_trade_agreement_ii"),
                                 mcard("promise_of_military_protection_ii"), mcard("loss_of_sovereignty_iii")])
def test_pacts_with_sides(key):
    a, b = {"acceptance_of_supremacy_ii": ({"res": 1}, {"res": -1}),
            "international_trade_agreement_ii": ({"res": 1}, {"food": 1}),
            "promise_of_military_protection_ii": ({"cult": 1}, {"str": 4, "cult": -1}),
            "loss_of_sovereignty_iii": ({"cult": 2}, {"cult": -2})}[key]
    g, s, (o, x) = game(3)
    for y in (s, o):
        place(g, y, "Theology", workers=2)                                         # culture rating 2 to lose from
    before = {y: E.stats(g, y) for y in (s, o)}
    name = {"acceptance_of_supremacy_ii": "Acceptance of Supremacy", "international_trade_agreement_ii":
            "International Trade Agreement", "promise_of_military_protection_ii": "Promise of Military Protection",
            "loss_of_sovereignty_iii": "Loss of Sovereignty"}[key]
    make_pact(g, s, o, name, AGE[BY_KEY[key]], "A")
    for y, exp in ((s, a), (o, b)):
        st, b0 = E.stats(g, y), before[y]
        got = {"res": st.resource_bonus - b0.resource_bonus, "food": st.food_bonus - b0.food_bonus,
               "cult": st.culture - b0.culture, "str": st.strength - b0.strength}
        assert {k: v for k, v in got.items() if v} == exp, (key, y, got)
    eff = EFFECT[BY_KEY[key]]
    assert M.forbids_attack(g, s, o) == bool(eff.get("no_attack"))
    assert M.forbids_war_on(g, o) == bool(eff.get("no_war_on_b")) and not M.forbids_war_on(g, s)
    if eff.get("ends_on_attack"):
        assert M.attack_strengths(g, o, s)[0] == 1                                 # the +4 does not count




@pytest.mark.parametrize("key", [mcard("scientific_cooperation_ii")])
def test_scientific_cooperation(key):
    g, s, (o, _) = game(3)
    make_pact(g, s, o, "Scientific Cooperation", "II")
    g.p(s).science, g.p(o).science = 3, 1
    give(g, s, "Iron")                                                             # science cost 5 -> 3
    answer(g, "Develop Iron")
    assert g.p(s).science == 0 and g.p(o).science == 0
    give(g, s, "Alchemy")
    g.p(s).science = 10
    touch(g, s)
    assert not has(g, "Develop Alchemy")                                           # the partner cannot pay


@pytest.mark.parametrize("key", [mcard("international_tourism_iii")])
def test_international_tourism(key):
    g, s, (o, _) = game(3)
    place(g, o, "Pyramids")
    place(g, o, "Colossus")
    place(g, s, "Library of Alexandria")
    cs, co = E.stats(g, s).culture, E.stats(g, o).culture
    make_pact(g, s, o, "International Tourism", "III")
    assert E.stats(g, s).culture == cs + 2 and E.stats(g, o).culture == co + 1


@pytest.mark.parametrize("key", [mcard("military_pact_iii"), mcard("peace_treaty_iii")])
def test_symmetric_pacts(key):
    str_, cult, no_attack = {"military_pact_iii": (3, 0, False), "peace_treaty_iii": (0, 1, True)}[key]
    g, s, (o, x) = game(3)
    name = {"military_pact_iii": "Military Pact", "peace_treaty_iii": "Peace Treaty"}[key]
    make_pact(g, s, o, name, "III")
    for y in (s, o):
        assert strength(g, y) == 1 + str_ and E.stats(g, y).culture == cult
    assert M.forbids_attack(g, s, o) == no_attack and strength(g, x) == 1
    if str_:
        assert M.attack_strengths(g, s, o) == (1, 1)                               # ends on attack: not counted




# ===================================================================================================== tactics
TACTICS = ["fighting_band_i", "heavy_cavalry_i", "legion_i", "medieval_army_i", "phalanx_i", "classic_army_ii",
           "conquistadors_ii", "defensive_army_ii", "fortifications_ii", "mobile_artillery_ii", "napoleonic_army_ii",
           "entrenchments_iii", "mechanized_army_iii", "modern_army_iii", "positional_army_iii", "shock_troops_iii"]
MODERN = {"infantry": "Modern Infantry", "cavalry": "Tanks", "artillery": "Rockets"}
OLD = {"infantry": "Warriors", "cavalry": "Knights", "artillery": "Cannon"}


@pytest.mark.parametrize("key", [mcard("fighting_band_i"), mcard("heavy_cavalry_i"), mcard("legion_i"),
                                 mcard("medieval_army_i"), mcard("phalanx_i"),
                                 mcard("classic_army_ii"), mcard("conquistadors_ii"),
                                 mcard("defensive_army_ii"),
                                 mcard("fortifications_ii"),
                                 mcard("mobile_artillery_ii"),
                                 mcard("napoleonic_army_ii"),
                                 mcard("entrenchments_iii"),
                                 mcard("mechanized_army_iii"),
                                 mcard("modern_army_iii"),
                                 mcard("positional_army_iii"),
                                 mcard("shock_troops_iii")])
def test_tactic_forms_armies(key):
    c = BY_KEY[key]
    t = TACTIC[c]
    for units, expected in ((MODERN, t["strength"]), (OLD, None)):
        g, s, _ = game()
        g.p(s).workers[cid("Warriors")] = 0
        for kind_, k in t["units"].items():
            if k:
                mil(g, s, units[kind_], k=k)
        give(g, s, (NAME[c], AGE[c]))
        answer(g, "Play tactic")
        army = E.stats(g, s).army
        if expected is None:
            old_levels = [LEVEL[cid(OLD[k_])] for k_, k in t["units"].items() if k]
            outdated = LEVEL[c] >= 2 and any(x <= LEVEL[c] - 2 for x in old_levels)
            expected = t["outdated_strength"] if outdated else t["strength"]
        assert army == expected and g.p(s).tactic == c, (key, units)




@pytest.mark.parametrize("key", [mcard("hussars_ii")])
def test_hussars_two_plus_lower_cavalry_level(key):
    g, s, _ = game()
    mil(g, s, "Tanks", k=2)
    mil(g, s, "Knights", k=1)
    mil(g, s, "Cavalrymen", k=1)
    give(g, s, ("Hussars", "II"))
    answer(g, "Play tactic Hussars")
    assert E.stats(g, s).army == (2 + 3) + (2 + 1)                                 # tanks together, then knights


# ===================================================================================================== military bonus cards
@pytest.mark.parametrize("key", [mcard("military_bonus_i"), mcard("military_bonus_ii"), mcard("military_bonus_iii")])
def test_military_bonus_defense_and_colonization(key):
    c = BY_KEY[key]
    d, col = BONUS[c]["defense"], BONUS[c]["colonization"]
    g, s, (o,) = game()
    stronger(g, s, d // 2)                                                         # need exactly d
    give(g, s, ("Aggression: Spy", "II"))
    give(g, o, (NAME[c], AGE[c]))
    g.p(o).science = 10
    politics(g, s)
    answer(g, "Play an aggression")
    assert has(g, f"Defend with {NAME[c]} ({AGE[c]}) (+{d})")
    answer(g, "Defend with")
    assert g.p(o).science == 10                                                    # repelled
    units = {cid("Warriors"): 1}
    assert M.colonization_force(g, o, units, [c]) - M.colonization_force(g, o, units, []) == col
