"""One test per civil card (base, rebalanced and expansion, 167 cards): technologies are developed and built through
the ACTION flow and their printed symbols checked; leaders are played from hand, wonders completed with a real wonder
stage, action cards played; then each card's own effect is triggered through the real flow and its change checked.
Every case is marked card("<key>") (tools/check_repo.py reads the marks).

Starting point (conftest.fresh): round 2, the starting player at ACTION after round 1's production (1 science, 2 food,
2 resources each); checks use differences."""
import numpy as np
import pytest

from games.through_the_ages import SPEC
from games.through_the_ages import economy as E
from games.through_the_ages import effects
from games.through_the_ages import engine as En
from games.through_the_ages import military as M
from games.through_the_ages import politics as P
from games.through_the_ages.cards import (AGE, AGRICULTURE, BRONZE, BY_KEY, DESPOTISM, EFFECT, EFFECT_TYPE, IS_STARTING,
                                          IS_UNIT, KIND, MILITARY_ACTION_COST, MILITARY_KINDS, NAME, RESOURCE_COST,
                                          S_CULT, S_HAPPY, S_STR, SCIENCE_COST, SPECIALS, STAGE_COSTS, STAT_YIELDS,
                                          TOKEN_SYMBOLS, TOKEN_VALUE, URBAN_LIMIT)
from games.through_the_ages.tests.conftest import (answer, cid, fresh, give, has, kind, mil, place, politics, refresh,
                                                   reveal_now, run_now, touch)

card = pytest.mark.card


def mcard(key, *extra):
    return pytest.param(key, *extra, marks=card(key), id=key)


def game(n=2, seed=0):
    g = fresh(n, seed)
    s = g.current_seat
    return g, s, [(s + k) % n for k in range(1, n)]


def res(g, s, n):
    """n resources on Bronze (owned blue tokens from the box, the bank untouched)."""
    p = g.p(s)
    p.tokens[BRONZE] = p.tokens.get(BRONZE, 0) + n
    p.blue_owned += n
    g._dirty = True


def food(g, s, n):
    p = g.p(s)
    p.tokens[AGRICULTURE] = p.tokens.get(AGRICULTURE, 0) + n
    p.blue_owned += n
    g._dirty = True


def hand(g, s, c):
    (g.p(s).military_hand if KIND[c] in MILITARY_KINDS else g.p(s).civil_hand).append(c)
    g._dirty = True
    return c


def st(g, s):
    return E.stats(g, s)


def vec(g, s):
    return list(E.stats(g, s).v)


def maybe(g, text):
    """Answer `text` unless that step was the only answer and already applied automatically."""
    if has(g, text):
        answer(g, text)


def lead(g, s, key):
    """Play the leader from hand through the ACTION flow."""
    c = BY_KEY[key]
    hand(g, s, c)
    answer(g, f"Play leader {NAME[c]} ({AGE[c]})")
    assert g.p(s).leader == c
    return c


def complete(g, s, key):
    """Complete the wonder with a real last wonder stage (the earlier stages already covered). Returns the blue tokens
    added for paying it."""
    c = BY_KEY[key]
    p = g.p(s)
    k = len(STAGE_COSTS[c])
    p.unfinished = [c, k - 1, k - 1]
    p.blue_bank -= k - 1
    (food if EFFECT_TYPE[c] == "red_cross" else res)(g, s, STAGE_COSTS[c][-1])
    answer(g, "Build a wonder stage")
    assert c in p.wonders
    return STAGE_COSTS[c][-1]


def advance(g, pred):
    """Pass (END) actions and political actions, first answers elsewhere, until pred(g)."""
    refresh(g)
    while not g.game_over and not pred(g):
        k = g.s.decisions.top.kind
        g.step_id(En.A_END if k in ("ACTION", "POLITICS") else g.legal_ids()[0])


def own_action(g, s, kinds=("ACTION",)):
    """End the current action phase, then advance to seat s's own next ACTION (or another kind of its turn)."""
    refresh(g)
    g.step_id(En.A_END)
    advance(g, lambda h: h.s.turn_seat == s and h.current_seat == s and h.s.decisions.top.kind in kinds)


def politics_of(g, s, kinds=("POLITICS",)):
    own_action(g, s, kinds)


def stronger(g, s, k=2):
    mil(g, s, "Swordsmen", k=k)


def take_from_row(g, s, name, age=None, slot=0):
    g.s.row[slot] = cid(name, age)
    g._dirty = True
    answer(g, f"Take {name}")


def benign_events(g, k=3):
    """The current events deck: k copies of Development of Crafts (each civilization gains 2 resources)."""
    g.s.current_events = [[cid("Development of Crafts"), None] for _ in range(k)]


def yields(c):
    out = {}
    for k, x in STAT_YIELDS[c]:
        out[k] = out.get(k, 0) + x
    return out


# ===================================================================================================== technologies
def technologies():
    return [k for k in sorted(BY_KEY, key=BY_KEY.get) if not IS_STARTING[BY_KEY[k]]
            and KIND[BY_KEY[k]] in ("farm", "mine", "lab", "temple", "library", "theater", "arena", "infantry",
                                    "cavalry", "artillery", "air_force", "government", "special_civil",
                                    "special_military", "special_colonization")]


TECHNOLOGIES = [
    mcard("irrigation_i"), mcard("iron_i"), mcard("alchemy_i"), mcard("theology_i"), mcard("printing_press_i"),
    mcard("drama_i"), mcard("bread_and_circuses_i"), mcard("swordsmen_i"), mcard("knights_i"),
    mcard("monarchy_i"), mcard("theocracy_i"), mcard("code_of_laws_i"), mcard("warfare_i"),
    mcard("cartography_i"), mcard("selective_breeding_ii"), mcard("coal_ii"), mcard("scientific_method_ii"),
    mcard("organized_religion_ii"), mcard("journalism_ii"), mcard("opera_ii"), mcard("team_sports_ii"),
    mcard("riflemen_ii"), mcard("cavalrymen_ii"), mcard("cannon_ii"), mcard("constitutional_monarchy_ii"),
    mcard("republic_ii"), mcard("justice_system_ii"), mcard("strategy_ii"), mcard("navigation_ii"),
    mcard("mechanized_agriculture_iii"), mcard("oil_iii"), mcard("computers_iii"), mcard("multimedia_iii"),
    mcard("movies_iii"), mcard("professional_sports_iii"), mcard("modern_infantry_iii"), mcard("tanks_iii"),
    mcard("rockets_iii"), mcard("air_forces_iii"), mcard("communism_iii"), mcard("democracy_iii"),
    mcard("fundamentalism_iii"), mcard("civil_service_iii"), mcard("military_theory_iii"),
    mcard("satellites_iii")]


@pytest.mark.parametrize("key", TECHNOLOGIES)
def test_technology_developed_and_its_symbols_take_effect(key):
    """Develop from hand (science paid), then (cards holding workers) build one worker on it: the statistics change by
    the printed symbols (per worker), farms/mines produce their token value, governments set actions and the urban
    limit, specials add their symbols and token symbols."""
    g, s, _ = game()
    p = g.p(s)
    c = BY_KEY[key]
    hand(g, s, c)
    p.science = SCIENCE_COST[c]
    before, blue0 = vec(g, s), p.blue_owned
    out0 = {k: E.output(g, s, k) for k in ("farm", "mine")}
    if KIND[c] == "government":
        answer(g, f"Change government to {NAME[c]}")
        maybe(g, "Peaceful change")
        assert p.government == c and p.science == 0
        exp = [0] * len(before)
        for k, x in STAT_YIELDS[DESPOTISM]:
            exp[k] -= x
        for k, x in STAT_YIELDS[c]:
            exp[k] += x
        assert [a - b for a, b in zip(vec(g, s), before)] == exp
        assert st(g, s).urban_limit == URBAN_LIMIT[c]
        return
    answer(g, f"Develop {NAME[c]} ({AGE[c]})")
    assert p.science == 0
    exp = [0] * len(before)
    for k, x in STAT_YIELDS[c]:
        exp[k] += x
    if KIND[c] in SPECIALS:
        assert p.specials[KIND[c]] == c
        assert [a - b for a, b in zip(vec(g, s), before)] == exp
        assert p.blue_owned - blue0 == TOKEN_SYMBOLS[c][0]
        return
    assert c in p.techs
    before = vec(g, s)
    res(g, s, RESOURCE_COST[c])
    answer(g, "Build a military unit" if IS_UNIT[c] else "Build a farm, mine or urban building")
    answer(g, f"on {NAME[c]}")
    assert p.workers[c] == 1
    assert [a - b for a, b in zip(vec(g, s), before)] == exp
    if KIND[c] in ("farm", "mine"):
        assert E.output(g, s, KIND[c]) == out0[KIND[c]] + TOKEN_VALUE[c]


@pytest.mark.parametrize("key", [
    mcard("agriculture_a"), mcard("bronze_a"), mcard("philosophy_a"), mcard("religion_a"), mcard("warriors_a"),
    mcard("despotism_a")])
def test_starting_technology(key):
    """T1.5, T2.3, T2.4: the printed starting technologies are in play with their workers and symbols."""
    g, s, _ = game()
    p = g.p(s)
    c = BY_KEY[key]
    x = st(g, s)
    if key == "despotism_a":
        assert p.government == c and (x.civil, x.military, x.urban_limit) == (4, 2, 2)
    elif key in ("agriculture_a", "bronze_a"):
        k = KIND[c]
        assert E.output(g, s, k) == 2 * TOKEN_VALUE[c] == 2
        f0 = E.total(p, k)
        g.production(s)
        assert E.total(p, k) == f0 + 2
    elif key == "philosophy_a":
        assert x.science == 1 and p.workers[c] == 1
    elif key == "warriors_a":
        assert x.strength == 1 and p.workers[c] == 1
    else:                                                                        # Religion: build a temple
        res(g, s, RESOURCE_COST[c])
        answer(g, "Build a farm, mine or urban building")
        answer(g, "on Religion")
        assert (st(g, s).culture, st(g, s).happiness) == (1, 1)


@pytest.mark.parametrize("key", [mcard("masonry_i"), mcard("architecture_ii"), mcard("engineering_iii")])
def test_construction_technologies(key):
    """Urban buildings cheaper by age; several wonder stages for one civil action."""
    g, s, _ = game()
    p = g.p(s)
    c = hand(g, s, BY_KEY[key])
    p.science = SCIENCE_COST[c]
    answer(g, f"Develop {NAME[c]}")
    eff = EFFECT[c]
    alch = place(g, s, "Alchemy")                                                 # Age I lab
    res(g, s, RESOURCE_COST[alch])
    r0 = E.resources(p)
    answer(g, "Build a farm, mine or urban building")
    answer(g, "on Alchemy")
    assert r0 - E.resources(p) == RESOURCE_COST[alch] - eff["urban_discount_by_age"]["I"]
    p.unfinished = [cid("Internet"), 0, 0]                                       # 5 stages
    res(g, s, 30)
    answer(g, "Build a wonder stage")
    k = eff["wonder_stages_per_action"]
    assert has(g, f"Build {k} stages") and not has(g, f"Build {k + 1} stages")
    answer(g, f"Build {k} stages")
    assert p.unfinished[1] == k


@pytest.mark.parametrize("key", [mcard("air_forces_iii")])
def test_air_forces_double_an_army(key):
    g, s, _ = game()
    p = g.p(s)
    p.tactic = cid("Fighting Band")
    g.s.common_tactics.append(p.tactic)
    mil(g, s, "Warriors", k=1)                                                    # 2 infantry: one army (+1)
    assert st(g, s).army == 1
    c = hand(g, s, BY_KEY[key])
    p.science = SCIENCE_COST[c]
    answer(g, f"Develop {NAME[c]}")
    res(g, s, RESOURCE_COST[c])
    answer(g, "Build a military unit")
    maybe(g, "on Air Forces")
    air = yields(c)[S_STR]
    assert st(g, s).army == 2 and st(g, s).strength == 2 + 2 + air               # the army doubled


# ===================================================================================================== action cards
def play(g, s, key):
    c = hand(g, s, BY_KEY[key])
    answer(g, f"Play action card {NAME[c]} ({AGE[c]})")
    return c


def snap(g, x):
    p = g.p(x)
    return {"food": E.food(p), "resources": E.resources(p), "science": p.science, "culture": p.culture,
            "population": p.pool, "military_cards": len(p.military_hand)}


def diff(a, b):
    return {k: b[k] - a[k] for k in a if b[k] != a[k]}


def nonzero(d):
    return {k: v for k, v in d.items() if v}


@pytest.mark.parametrize("key", [mcard("cultural_heritage_a"), mcard("cultural_heritage_i"), mcard("stockpile_a"),
                                 mcard("revolutionary_idea_ii"), mcard("revolutionary_idea_iii")])
def test_action_gain(key):
    g, s, _ = game()
    b = snap(g, s)
    play(g, s, key)
    assert diff(b, snap(g, s)) == EFFECT[BY_KEY[key]]["gain"]


@pytest.mark.parametrize("key", [mcard("reserves_i"), mcard("reserves_ii"), mcard("reserves_iii")])
def test_action_gain_choice(key):
    g, s, _ = game()
    b = snap(g, s)
    play(g, s, key)
    n = EFFECT[BY_KEY[key]]["options"][0]["resources"]
    assert kind(g) == "SUB_ACTION"
    answer(g, f"Gain {n} resources")
    assert diff(b, snap(g, s)) == {"resources": n}


@pytest.mark.parametrize("key", [mcard("frugality_a"), mcard("frugality_i"), mcard("frugality_ii")])
def test_action_frugality(key):
    g, s, _ = game()
    food(g, s, 5)
    b = snap(g, s)
    cost = E.pop_cost(g.p(s).yellow_bank)
    play(g, s, key)
    assert diff(b, snap(g, s)) == nonzero({"population": 1,
                                           "food": EFFECT[BY_KEY[key]]["then_gain"]["food"] - cost})


@pytest.mark.parametrize("key", [mcard("urban_growth_a"), mcard("urban_growth_i"), mcard("urban_growth_ii"),
                                 mcard("urban_growth_iii"), mcard("rich_land_a"), mcard("rich_land_i"),
                                 mcard("rich_land_ii")])
def test_action_build_or_upgrade_cheaper(key):
    g, s, _ = game()
    p = g.p(s)
    eff = EFFECT[BY_KEY[key]]
    target = place(g, s, "Theology" if "urban" in eff["targets"] else "Coal")
    res(g, s, 20)
    r0 = E.resources(p)
    play(g, s, key)
    maybe(g, "Build (action card)")
    answer(g, f"on {NAME[target]}")
    assert p.workers[target] == 1
    assert r0 - E.resources(p) == max(0, RESOURCE_COST[target] - eff["discount"])
    assert E.civil_available(g, s) == 3                                           # only the card's civil action


@pytest.mark.parametrize("key", [mcard("efficient_upgrade_ii"), mcard("efficient_upgrade_iii")])
def test_action_efficient_upgrade(key):
    g, s, _ = game()
    p = g.p(s)
    coal = place(g, s, "Coal")
    res(g, s, 20)
    r0 = E.resources(p)
    play(g, s, key)
    maybe(g, "Upgrade from Bronze")
    maybe(g, "to Coal")
    assert p.workers[coal] == 1
    assert r0 - E.resources(p) == max(0, RESOURCE_COST[coal] - RESOURCE_COST[BRONZE] - EFFECT[BY_KEY[key]]["discount"])


@pytest.mark.parametrize("key", [mcard("engineering_genius_a"), mcard("engineering_genius_i"),
                                 mcard("engineering_genius_ii"), mcard("engineering_genius_iii")])
def test_action_engineering_genius(key):
    g, s, _ = game()
    p = g.p(s)
    w = cid("Eiffel Tower")
    p.unfinished = [w, 0, 0]
    res(g, s, 10)
    r0 = E.resources(p)
    play(g, s, key)
    assert p.unfinished[1] == 1
    assert r0 - E.resources(p) == max(0, STAGE_COSTS[w][0] - EFFECT[BY_KEY[key]]["discount"])


@pytest.mark.parametrize("key", [mcard("patriotism_a"), mcard("patriotism_i"), mcard("patriotism_ii"),
                                 mcard("patriotism_iii")])
def test_action_patriotism(key):
    g, s, _ = game()
    p = g.p(s)
    m0 = E.military_available(g, s)
    play(g, s, key)
    eff = EFFECT[BY_KEY[key]]
    assert p.temp["unit"] == eff["resources"] and E.military_available(g, s) == m0 + eff["military_actions"]


@pytest.mark.parametrize("key", [mcard("breakthrough_i"), mcard("breakthrough_ii")])
def test_action_breakthrough(key):
    g, s, _ = game()
    p = g.p(s)
    iron = give(g, s, "Iron")[0]
    p.science = SCIENCE_COST[iron]
    play(g, s, key)
    maybe(g, "Develop Iron")
    assert iron in p.techs and p.science == EFFECT[BY_KEY[key]]["then_gain"]["science"]
    assert E.civil_available(g, s) == 3


@pytest.mark.parametrize("key", [mcard("wave_of_nationalism_ii"), mcard("military_build_up_iii")])
def test_action_resources_per_stronger_civilization(key):
    g, s, (o,) = game()
    stronger(g, o)
    play(g, s, key)
    assert g.p(s).temp["unit"] == EFFECT[BY_KEY[key]]["per_player"]["2"]


@pytest.mark.parametrize("key", [mcard("endowment_for_the_arts_iii")])
def test_action_culture_per_more_cultured(key):
    g, s, (o,) = game()
    g.p(o).culture = 5
    play(g, s, key)
    assert g.p(s).culture == EFFECT[BY_KEY[key]]["per_player"]["2"]


# ===================================================================================================== leaders: Age A
@pytest.mark.parametrize("key", [mcard("alexander_the_great_a")])
def test_alexander(key):
    g, s, _ = game()
    p = g.p(s)
    s0 = st(g, s).strength
    lead(g, s, key)
    assert st(g, s).strength == s0 + 1                                            # one unit (Warriors)
    y0 = p.yellow_bank
    politics(g)
    answer(g, "Alexander the Great: remove him")
    assert p.leader is None and p.yellow_bank == y0 + 1 and st(g, s).strength == s0


@pytest.mark.parametrize("key", [mcard("aristotle_a")])
def test_aristotle(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    sci = p.science
    take_from_row(g, s, "Iron")
    assert p.science == sci + 1
    take_from_row(g, s, "Cultural Heritage", "A")
    assert p.science == sci + 1


@pytest.mark.parametrize("key", [mcard("ashoka_a")])
def test_ashoka(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    p.civil_hand = [cid("Iron"), cid("Alchemy")]                                  # brown + grey
    assert (E.production_bonus(g, s, "farm"), E.production_bonus(g, s, "mine")) == (0, 1)
    p.civil_hand.append(cid("Monarchy"))                                          # + orange
    r0, f0 = E.resources(p), E.food(p)
    g.production(s)
    assert E.resources(p) == r0 + 2 + 1 and E.food(p) == f0 + 2 + 1
    enc = SPEC.encoder(2)
    h = g.clone()
    h.p(s).civil_hand = [cid("Iron")]
    assert not np.array_equal(enc.encode(g, o), enc.encode(h, o))                 # T16.2: the hand is open


@pytest.mark.parametrize("key", [mcard("boudica_a")])
def test_boudica(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    stronger(g, o)
    own_action(g, s)
    assert p.temp.get("unit") == 2                                                # the weaker
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    stronger(g, s)
    own_action(g, s, ("ABILITY", "ACTION"))
    assert kind(g) == "ABILITY"
    sci = p.science
    answer(g, "Gain 1 science")
    assert p.science == sci + 1 and kind(g) == "ACTION"


@pytest.mark.parametrize("key", [mcard("cleopatra_a")])
def test_cleopatra(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    assert p.temp == {"civic": 1}
    res(g, s, 2)
    r0 = E.resources(p)
    answer(g, "Build a farm, mine or urban building")
    answer(g, "on Religion")
    assert p.workers[cid("Religion")] == 1 and p.temp["civic"] == 0
    assert r0 - E.resources(p) == RESOURCE_COST[cid("Religion")] - 1


@pytest.mark.parametrize("key", [mcard("confucius_a")])
def test_confucius(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    tactic = give(g, s, "Legion")[0]
    benign_events(g)
    sci = p.science
    politics(g)
    answer(g, "Prepare an event")
    maybe(g, "Prepare Legion")
    assert p.science == sci + 1 and g.s.future_events[0][0] == tactic
    lead(g, s, "aristotle_a")
    assert p.science == sci + 2                                                   # once when he leaves play


@pytest.mark.parametrize("key", [mcard("hammurabi_a")])
def test_hammurabi(key):
    g, s, _ = game()
    lead(g, s, key)
    c0, m0 = E.civil_available(g, s), E.military_available(g, s)
    answer(g, "Hammurabi: use a military action")
    assert (E.civil_available(g, s), E.military_available(g, s)) == (c0 + 1, m0 - 1)
    assert not has(g, "Hammurabi")                                                # once per turn


@pytest.mark.parametrize("key", [mcard("hippocrates_a")])
def test_hippocrates(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    own_action(g, s)
    assert p.reminders == 1
    y0 = p.yellow_bank
    run_now(g, g.begin_age, "II")
    assert p.yellow_bank == y0 - 2 + 1 and p.reminders == 0


@pytest.mark.parametrize("key", [mcard("homer_a")])
def test_homer(key):
    g, s, _ = game()
    p = g.p(s)
    pyramids = place(g, s, "Pyramids")
    lead(g, s, key)
    assert p.temp == {"unit": 1} and st(g, s).happiness == 1
    res(g, s, 1)
    r0 = E.resources(p)
    answer(g, "Build a military unit")
    maybe(g, "on Warriors")
    assert p.workers[cid("Warriors")] == 2 and E.resources(p) == r0 - 1
    spent = p.civil_spent
    lead(g, s, "aristotle_a")
    assert kind(g) == "ABILITY"
    answer(g, "Tuck Homer under Pyramids")
    assert p.homer_wonder == pyramids and st(g, s).happiness == 1 and p.civil_spent == spent + 1


@pytest.mark.parametrize("key", [mcard("julius_caesar_a")])
def test_julius_caesar(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    a, b = give(g, s, ("Development of Science", "A"), ("Development of Settlement", "A"))
    benign_events(g, 5)
    politics_of(g, s)
    answer(g, "Prepare an event")
    answer(g, "Prepare Development of Science")
    assert kind(g) == "POLITICS" and g.current_seat == s                         # a second political action
    answer(g, "Prepare an event")
    maybe(g, "Prepare Development of Settlement")
    assert [e[0] for e in g.s.future_events if e[1] == s] == [b, a] and kind(g) == "ACTION"


@pytest.mark.parametrize("key", [mcard("moses_a")])
def test_moses(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    food(g, s, 5)
    f0 = E.food(p)
    answer(g, "Increase population")
    assert f0 - E.food(p) == E.pop_cost(18) - 1


@pytest.mark.parametrize("key", [mcard("sun_tzu_a")])
def test_sun_tzu(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    legion, band = give(g, s, "Legion", "Fighting Band")
    answer(g, "Play tactic Legion")
    own_action(g, s)
    assert p.exclusive_tactic == legion and legion not in g.s.common_tactics     # stays exclusive
    answer(g, "Play tactic Fighting Band")
    assert p.kept_tactics == [legion] and p.tactic == band
    p.military_spent = st(g, s).military                                          # no military actions left
    answer(g, "End the action phase")
    while kind(g) == "DISCARD_MILITARY" and g.current_seat == s:
        g.step_id(g.legal_ids()[0])
    h0 = min(len(p.military_hand), E.military_hand_limit(g, s))
    assert len(p.military_hand) in (h0, h0 + 2) and g.s.turn_seat != s
    advance(g, lambda h: h.s.turn_seat == s and h.s.decisions.top.kind == "ACTION")
    assert band in [p.exclusive_tactic] + p.kept_tactics
    mil(g, s, "Warriors", k=1)                                                    # 2 infantry: Fighting Band army
    p.tactic = band
    touch(g, s)
    army = st(g, s).army
    lead(g, s, "aristotle_a")                                                     # he leaves: under Fighting Band
    assert p.tactic_boost == band and st(g, s).army == army + 1
    own_action(g, s)
    assert band in g.s.common_tactics and legion in g.s.common_tactics and not p.kept_tactics


@pytest.mark.parametrize("key", [mcard("sun_tzu_a")])
def test_sun_tzu_draws_two_extra_military_cards(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    p.military_spent = st(g, s).military
    g.production = lambda seat: None                                              # isolate the draw
    answer(g, "End the action phase")
    assert len(p.military_hand) == 2


# ===================================================================================================== leaders: Age I
@pytest.mark.parametrize("key", [mcard("christopher_columbus_i")])
def test_columbus(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    terr = give(g, s, ("Historic Territory", "I"))[0]
    units = dict(p.workers)
    politics(g)
    answer(g, "Christopher Columbus")
    assert p.colonies == [terr] and p.leader is None and p.workers == units and p.culture == 6


@pytest.mark.parametrize("key", [mcard("eleanor_of_aquitaine_i")])
def test_eleanor(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    give(g, s, ("Development of Science", "A"))
    benign_events(g)
    politics(g)
    answer(g, "Prepare an event")
    assert len(p.military_hand) == 2                                              # drew 2
    give(g, s, "Legion", "Legion", "Legion")
    c0, rating = p.culture, st(g, s).culture
    answer(g, "End the action phase")
    while kind(g) == "DISCARD_MILITARY" and g.current_seat == s:
        g.step_id(g.legal_ids()[0])
    assert p.culture == c0 + (5 - 2) + rating                                     # 1 per card over the limit
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    p.civil_spent = 2
    lead(g, s, "aristotle_a")
    assert p.civil_spent == 0                                                     # 3 civil actions back


@pytest.mark.parametrize("key", [mcard("frederick_barbarossa_i")])
def test_barbarossa(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    f0, r0, m0, pool = E.food(p), E.resources(p), E.military_available(g, s), p.pool
    answer(g, "Frederick Barbarossa")
    maybe(g, "on Warriors")
    assert p.workers[cid("Warriors")] == 2 and p.pool == pool
    assert (f0 - E.food(p), r0 - E.resources(p)) == (E.pop_cost(18) - 1, RESOURCE_COST[cid("Warriors")] - 1)
    assert E.military_available(g, s) == m0 - 1


@pytest.mark.parametrize("key", [mcard("genghis_khan_i")])
def test_genghis_khan(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    c0, rating = p.culture, st(g, s).culture
    answer(g, "End the action phase")                                             # equal strength: ties to him
    assert p.culture == c0 + 3 + rating
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    p.tactic = cid("Medieval Army")                                               # 1 infantry + 1 cavalry
    g.s.common_tactics.append(p.tactic)
    mil(g, s, "Warriors", k=1)
    assert st(g, s).army == 2                                                     # an infantry counts as cavalry


@pytest.mark.parametrize("key", [mcard("isabella_of_castile_i")])
def test_isabella(key):
    g, s, (o,) = game()
    p = g.p(s)
    b0 = p.blue_owned
    lead(g, s, key)
    assert p.blue_owned == b0 + 2 and st(g, s).resource_bonus == 1
    res(g, s, 3)
    r0 = E.resources(p)
    terr = cid("Historic Territory", "I")
    assert M.max_colonization_force(g, s) == 1 + 2                               # Warriors + 3 resources: +2
    reveal_now(g, terr, seat=s)
    answer(g, "Bid 3")
    answer(g, "Isabella: pay 3 resources for +2")
    maybe(g, "Send a unit from Warriors")
    maybe(g, "Stop sending")
    assert terr in p.colonies and E.resources(p) == r0 - 3


@pytest.mark.parametrize("key", [mcard("jan_zizka_i")])
def test_zizka(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    p.tactic = cid("Defensive Army")                                              # 2 infantry + 1 artillery
    g.s.common_tactics.append(p.tactic)
    mil(g, s, "Warriors", k=1)
    x = st(g, s)
    assert x.army_count == 1 and x.army == 3                                      # farms as infantry/artillery
    assert x.culture == 1                                                         # 1 culture per army


@pytest.mark.parametrize("key", [mcard("joan_of_arc_i")])
def test_joan_of_arc(key):
    g, s, _ = game()
    lead(g, s, key)
    s0 = st(g, s).strength
    mil(g, s, "Religion", k=1)                                                    # a temple: 1 happy face
    assert st(g, s).strength == s0 + 1
    top = cid("Development of Crafts")
    g.s.current_events.insert(0, [top, None])
    politics_of(g, s)
    assert g.s.current_events[0][0] == top and s in P.known_by(g.s.current_events[0])


@pytest.mark.parametrize("key", [mcard("johannes_gutenberg_i")])
def test_gutenberg(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    res(g, s, 2)
    c0, cult, r0 = E.civil_available(g, s), p.culture, E.resources(p)
    answer(g, "Johannes Gutenberg")                                               # optional: chosen (D30)
    answer(g, "Build a farm, mine or urban building")
    maybe(g, "on Philosophy")                                                     # labs/libraries only
    assert p.workers[cid("Philosophy")] == 2 and r0 - E.resources(p) == RESOURCE_COST[cid("Philosophy")] - 1
    assert E.civil_available(g, s) == c0 and p.culture == cult + 2               # his extra action
    p.civil_spent = st(g, s).civil
    refresh(g)
    g._dirty = True
    assert not has(g, "Build a farm")                                             # used once per turn


@pytest.mark.parametrize("key", [mcard("leonardo_da_vinci_i"), mcard("isaac_newton_ii"), mcard("albert_einstein_iii")])
def test_best_lab_or_library_and_develop_bonus(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    sci0 = st(g, s).science
    mil(g, s, "Alchemy", k=1)                                                     # best lab: Age I
    assert st(g, s).science == sci0 + 2 + 1                                       # +2 Alchemy, +1 its level
    iron = give(g, s, "Iron")[0]
    p.science = SCIENCE_COST[iron]
    b, spent = snap(g, s), p.civil_spent
    answer(g, "Develop Iron")
    eff = EFFECT[BY_KEY[key]]
    if eff.get("on_develop_regain_civil_action"):
        assert p.civil_spent == spent
    else:
        assert diff(b, snap(g, s)) == dict({"science": -SCIENCE_COST[iron]}, **eff["on_develop"])


@pytest.mark.parametrize("key", [mcard("michelangelo_i")])
def test_michelangelo(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Religion", k=1)                                                    # 1 happy: +1 culture
    place(g, s, "Hanging Gardens")                                                # 2 happy: +2 culture
    assert st(g, s).culture == 1 + 1 + 1 + 2
    g.s.row[5] = cid("Eiffel Tower")                                              # slot 6: 2 civil actions
    r0 = E.resources(p)
    assert g.take_cost(s, 5) == 2                                                 # no surcharge for 1 wonder
    answer(g, "Take Eiffel Tower")
    assert E.resources(p) == r0 + 1


@pytest.mark.parametrize("key", [mcard("nostradamus_i")])
def test_nostradamus(key):
    g, s, (o1, o2) = game(3)
    p = g.p(s)
    lead(g, s, key)
    give(g, s, ("Development of Science", "A"))
    benign_events(g)
    politics(g)
    answer(g, "Prepare an event")
    assert p.culture == 3
    give(g, o1, ("Development of Settlement", "A"))
    run_now(g, P.prepare, g, o1, cid("Development of Settlement"))
    assert s in P.known_by(next(e for e in g.s.future_events if e[1] == o1))
    assert o2 not in P.known_by(next(e for e in g.s.future_events if e[1] == o1))
    assert M.top(g, "strength", "low") != s                                      # +3 when the weakest is checked
    assert M.top(g, "strength", "low", ) == M.rank_players(g, "strength", "low")[0]
    assert M.attack_strengths(g, o1, s, aggression=True)[1] == st(g, s).strength + 3
    assert M.attack_strengths(g, o1, s)[1] == st(g, s).strength                  # not in wars


@pytest.mark.parametrize("key", [mcard("saladin_i")])
def test_saladin(key):
    g, s, _ = game()
    lead(g, s, key)
    s0, c0 = st(g, s).strength, st(g, s).civil
    answer(g, "End the action phase")
    assert kind(g) == "ABILITY" and g.current_seat == s
    answer(g, "Saladin: +2 strength")
    assert st(g, s).strength == s0 + 2
    advance(g, lambda h: h.s.turn_seat == s and h.s.decisions.top.kind == "ACTION")
    answer(g, "End the action phase")
    answer(g, "Saladin: +1 civil action")
    assert st(g, s).civil == c0 + 1 and st(g, s).strength == s0


# ===================================================================================================== leaders: Age II
@pytest.mark.parametrize("key", [mcard("alfred_nobel_ii")])
def test_alfred_nobel(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    spent = p.civil_spent
    lead(g, s, "aristotle_a")
    assert p.civil_spent == spent + 1 and g.s.nobel_prize == BY_KEY[key]         # no civil action back
    give(g, s, "Iron", "Alchemy")
    p.science = 20
    answer(g, "Develop Iron")
    answer(g, "Develop Alchemy")
    c0, rating = p.culture, st(g, s).culture
    answer(g, "End the action phase")
    assert p.culture == c0 + 4 + rating


@pytest.mark.parametrize("key", [mcard("antoni_gaudi_ii")])
def test_gaudi(key):
    g, s, _ = game()
    lead(g, s, key)
    mil(g, s, "Religion", k=1)                                                    # temple + lab built
    assert st(g, s).culture == 1 + 2                                              # Religion 1, best of 2 types
    drama = give(g, s, "Drama")[0]
    assert g.science_cost(s, drama) == SCIENCE_COST[drama] - 2
    alch = give(g, s, "Alchemy")[0]
    assert g.science_cost(s, alch) == SCIENCE_COST[alch] - 1                      # own type ignored


@pytest.mark.parametrize("key", [mcard("catherine_the_great_ii")])
def test_catherine(key):
    g, s, (o1, o2) = game(3)
    lead(g, s, key)
    stronger(g, s)
    y = [g.p(x).yellow_bank for x in (s, o1, o2)]
    politics(g)
    answer(g, "Catherine the Great")
    assert [g.p(x).yellow_bank for x in (s, o1, o2)] == [y[0] + 1, y[1] - 1, y[2] - 1]
    politics(g)
    assert not has(g, "Catherine")                                                # once per game


@pytest.mark.parametrize("key", [mcard("charles_darwin_ii")])
def test_darwin(key):
    g, s, _ = game()
    lead(g, s, key)
    mil(g, s, "Theology", k=1)                                                    # 2 happy -> 1
    mil(g, s, "Printing Press", k=1)                                              # library: +1 culture
    x = st(g, s)
    assert x.happiness == 1 and x.culture == 1 + 1 + 1 + 1                        # + Philosophy (a lab)
    g.s.row[5] = cid("Iron")
    assert g.take_cost(s, 5) == 1
    g.s.row[0] = cid("Coal")
    assert g.take_cost(s, 0) == 1                                                 # minimum 1


@pytest.mark.parametrize("key", [mcard("james_cook_ii")])
def test_james_cook(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    give(g, s, "Legion", "Legion")
    terr = cid("Historic Territory", "I")
    assert M.max_colonization_force(g, s) == 1 + 2
    reveal_now(g, terr, seat=s)
    answer(g, "Bid 3")
    answer(g, "Discard Legion")
    answer(g, "Discard Legion")
    maybe(g, "Send a unit")
    maybe(g, "Stop sending")
    assert p.colonies == [terr] and not p.military_hand
    assert st(g, s).culture == 2                                                  # first colony +2
    vast = cid("Vast Territory", "I")
    p.colonies.append(vast)
    p.play_order.append(vast)
    touch(g, s)
    assert st(g, s).culture == 3                                                  # later colony +1


@pytest.mark.parametrize("key", [mcard("james_watt_ii")])
def test_james_watt(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    coal = place(g, s, "Coal")
    assert g.build_cost(s, coal) == RESOURCE_COST[coal] - 2
    oil = give(g, s, "Oil")[0]
    assert g.science_cost(s, oil) == SCIENCE_COST[oil] - 4
    c0 = p.culture
    lead(g, s, "aristotle_a")                                                     # leaves: best farm/mine production
    assert p.culture == c0 + 2


@pytest.mark.parametrize("key", [mcard("johann_sebastian_bach_ii")])
def test_bach(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    drama = place(g, s, "Drama")
    assert g.science_cost(s, give(g, s, "Opera")[0]) == SCIENCE_COST[cid("Opera")] - 2
    res(g, s, RESOURCE_COST[drama] - RESOURCE_COST[cid("Philosophy")])
    c0 = E.civil_available(g, s)
    answer(g, "Bach: upgrade")
    maybe(g, "from Philosophy")
    maybe(g, "to Drama")
    assert p.workers[drama] == 1 and p.workers[cid("Philosophy")] == 0 and E.civil_available(g, s) == c0 - 1
    assert st(g, s).culture == 2 + 2 + 1                                          # Bach 2, Drama 2, +1 per theater
    assert not has(g, "Bach")


@pytest.mark.parametrize("key", [mcard("maria_theresa_ii")])
def test_maria_theresa(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    food(g, s, 3)
    sci, cult = p.science, p.culture
    answer(g, "Increase population")
    assert (p.science, p.culture) == (sci + 1, cult + 1)
    stronger(g, o)
    own_action(g, s)
    assert p.temp.get("unit") == 3                                                # one of the two weakest


@pytest.mark.parametrize("key", [mcard("maximilien_robespierre_ii")])
def test_robespierre(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mon = give(g, s, "Monarchy")[0]
    p.science = 20
    p.civil_spent = 2                                                             # civil actions spent: still ok
    answer(g, "Change government to Monarchy")
    answer(g, "Revolution")
    assert p.government == mon and p.culture == 3
    assert E.military_available(g, s) == 0 and p.civil_spent == 2


@pytest.mark.parametrize("key", [mcard("napoleon_bonaparte_ii")])
def test_napoleon(key):
    g, s, _ = game()
    lead(g, s, key)
    s0 = st(g, s).strength
    mil(g, s, "Knights", k=1)
    assert st(g, s).strength == s0 + 2 + 2                                        # knight 2 + a second type 2


@pytest.mark.parametrize("key", [mcard("william_shakespeare_ii")])
def test_shakespeare(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Printing Press", k=1)
    drama = place(g, s, "Drama")
    assert g.build_cost(s, drama) == RESOURCE_COST[drama] - 2
    assert g.science_cost(s, give(g, s, "Opera")[0]) == SCIENCE_COST[cid("Opera")] - 3
    p.workers[drama] = 1
    p.yellow_bank -= 1
    touch(g, s)
    assert st(g, s).culture == 1 + 2 + 2                                          # library 1, theater 2, pair 2


# ===================================================================================================== leaders: Age III
@pytest.mark.parametrize("key", [mcard("bill_gates_iii")])
def test_bill_gates(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Alchemy", k=2)
    assert E.output(g, s, "mine") - E.output(g, s, "mine", bonuses=False) == 2       # labs produce (D31)
    c0 = p.culture
    lead(g, s, "aristotle_a")
    assert p.culture == c0 + 2                                                    # leaving: this production
    g, s, _ = game()
    lead(g, s, key)
    mil(g, s, "Alchemy", k=1)
    c0 = g.p(s).culture
    g.end_game()
    assert g.p(s).culture == c0 + 1                                               # game end


@pytest.mark.parametrize("key", [mcard("charlie_chaplin_iii")])
def test_chaplin(key):
    g, s, _ = game()
    lead(g, s, key)
    c0 = st(g, s).culture
    mil(g, s, "Drama", k=2)
    assert st(g, s).culture == c0 + 2 * 2 + 2                                     # best theater doubled


@pytest.mark.parametrize("key", [mcard("ian_fleming_iii")])
def test_ian_fleming(key):
    g, s, (o1, o2) = game(3)
    p = g.p(s)
    lead(g, s, key)
    c0 = st(g, s).culture
    mil(g, s, "Journalism", k=1)
    mil(g, s, "Drama", k=1)
    assert st(g, s).culture == c0 + 2 + 2 + 2 + 1                                 # symbols + levels 2 and 1
    politics_of(g, s, ("ABILITY",))
    answer(g, f"military cards of P{o1}")
    assert p.peek == [o1, sorted(g.p(o1).military_hand)] and p.fleming_last == o1
    enc = SPEC.encoder(3)
    h = g.clone()
    h.p(s).peek = None
    assert not np.array_equal(enc.encode(g, s), enc.encode(h, s))                 # only s sees it
    assert np.array_equal(enc.encode(g, o2), enc.encode(h, o2))
    politics_of(g, s, ("ABILITY", "POLITICS"))
    assert not has(g, f"military cards of P{o1}")                                 # not twice in a row


@pytest.mark.parametrize("key", [mcard("mahatma_gandhi_iii")])
def test_gandhi(key):
    g, s, (o,) = game()
    lead(g, s, key)
    stronger(g, s, 3)
    raid = give(g, s, ("Aggression: Raid", "I"))[0]
    assert P.aggression_targets(g, s, raid) == []                                 # he may not attack
    assert P.attack_cost(g, raid, s) == MILITARY_ACTION_COST[raid] + 3           # 3 more against him
    stronger(g, o, 6)
    assert P.aggression_targets(g, o, raid) == []                                 # 2 military actions < 1 + 3
    place(g, o, "Strategy")                                                       # +2 military actions
    assert P.aggression_targets(g, o, raid) == [s]


@pytest.mark.parametrize("key", [mcard("marie_curie_sklodowska_iii")])
def test_marie_curie(key):
    g, s, _ = game()
    lead(g, s, key)
    x0 = st(g, s)
    sci, stren, cult = x0.science, x0.strength, x0.culture
    mil(g, s, "Coal", k=1)
    mil(g, s, "Alchemy", k=1)
    x = st(g, s)
    assert (x.science, x.strength, x.culture) == (sci + 2 + 2, stren + 1, cult + 2)


@pytest.mark.parametrize("key", [mcard("marlene_dietrich_iii")])
def test_marlene_dietrich(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Drama", k=2)
    x = st(g, s)
    assert x.culture == 4 + 2 and x.happiness == 2 + 2
    p.tactic = cid("Fighting Band")                                               # 2 infantry; only 1 Warriors
    g.s.common_tactics.append(p.tactic)
    touch(g, s)
    assert st(g, s).army == 1                                                     # the unit counts twice


@pytest.mark.parametrize("key", [mcard("nelson_mandela_iii")])
def test_nelson_mandela(key):
    g, s, _ = game()
    p = g.p(s)
    g.s.row[0] = BY_KEY[key]
    assert g.take_cost(s, 0) == 1 + 3                                             # no discontent: 3 more
    lead(g, s, key)
    place(g, s, "Hanging Gardens")                                                # 2 happy, none required
    c0, rating = p.culture, st(g, s).culture
    answer(g, "End the action phase")
    assert p.culture == c0 + 2 + rating


@pytest.mark.parametrize("key", [mcard("pierre_de_coubertin_iii")])
def test_coubertin(key):
    g, s, (o,) = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Bread and Circuses", k=1)
    assert st(g, s).culture == 2 + 0                                              # +2 per arena
    politics(g)
    answer(g, "Pierre de Coubertin")
    assert p.culture == 8 and g.s.olympics == [s, BY_KEY[key]]                   # not a political action:
    maybe(g, "Pass the political action")                                         # (a lone pass is automatic)
    g.p(o).culture = 10
    stronger(g, o, 3)
    give(g, o, ("Aggression: Raid", "I"))
    politics(g, o)
    answer(g, "Play an aggression")
    maybe(g, "Aggression with")
    maybe(g, "on P")
    assert g.p(o).culture == 2                                                    # 8 lost for the aggression


@pytest.mark.parametrize("key", [mcard("sid_meier_iii")])
def test_sid_meier(key):
    g, s, _ = game()
    lead(g, s, key)
    mil(g, s, "Alchemy", k=1)
    x = st(g, s)
    assert x.culture == 1 and x.science == (1 - 1) + (2 - 1)                      # Philosophy, Alchemy


@pytest.mark.parametrize("key", [mcard("steve_jobs_iii")])
def test_steve_jobs(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    mil(g, s, "Alchemy", k=1)
    assert st(g, s).happiness == 1
    iron = give(g, s, "Iron")[0]
    p.science = SCIENCE_COST[iron]
    r0 = E.resources(p)
    answer(g, "Develop Iron")
    answer(g, "Pay 1 resource for 4 culture")
    assert p.culture == 4 and E.resources(p) == r0 - 1


@pytest.mark.parametrize("key", [mcard("winston_churchill_iii")])
def test_churchill(key):
    g, s, _ = game()
    p = g.p(s)
    lead(g, s, key)
    answer(g, "Winston Churchill")
    answer(g, "3 science and 3 resources")
    assert p.temp == {"unit_science": 3, "unit": 3}
    knights = give(g, s, "Knights")[0]
    p.science = SCIENCE_COST[knights] - 3
    answer(g, "Develop Knights")
    assert knights in p.techs and p.science == 0 and p.temp["unit_science"] == 0
    assert not has(g, "Winston Churchill")
    g, s, _ = game()
    lead(g, s, key)
    answer(g, "Winston Churchill")
    answer(g, "Score 3 culture")
    assert g.p(s).culture == 3


# ===================================================================================================== wonders
YIELD_ONLY = ("pyramids_a", "universitas_carolina_i", "eiffel_tower_ii", "kremlin_ii")
OWN_EFFECT_ON_SYMBOL = {"louvre_museum_ii": S_CULT, "st_peter_s_basilica_i": S_HAPPY}


WONDERS = [
    mcard("acropolis_a"), mcard("colosseum_a"), mcard("colossus_a"), mcard("hanging_gardens_a"),
    mcard("library_of_alexandria_a"), mcard("pyramids_a"), mcard("roman_roads_a"), mcard("stonehenge_a"),
    mcard("forbidden_city_i"), mcard("great_wall_i"), mcard("himeji_castle_i"), mcard("machu_picchu_i"),
    mcard("silk_road_i"), mcard("st_peter_s_basilica_i"), mcard("taj_mahal_i"), mcard("universitas_carolina_i"),
    mcard("eiffel_tower_ii"), mcard("harvard_college_ii"), mcard("kremlin_ii"), mcard("louvre_museum_ii"),
    mcard("ocean_liner_service_ii"), mcard("statue_of_liberty_ii"), mcard("suez_canal_ii"),
    mcard("transcontinental_railroad_ii"), mcard("empire_state_building_iii"), mcard("fast_food_chains_iii"),
    mcard("first_space_flight_iii"), mcard("hollywood_iii"), mcard("international_red_cross_iii"),
    mcard("internet_iii"), mcard("manhattan_project_iii"), mcard("united_nations_iii")]


@pytest.mark.parametrize("key", WONDERS)
def test_wonder_completed_symbols(key):
    """Every wonder: the last stage completes it and its printed symbols take effect, token symbols included."""
    g, s, _ = game()
    p = g.p(s)
    c = BY_KEY[key]
    before, b0, y0 = vec(g, s), p.blue_owned, p.yellow_bank
    added = complete(g, s, key)
    after = vec(g, s)
    for k, x in yields(c).items():
        if OWN_EFFECT_ON_SYMBOL.get(key) != k:
            assert after[k] - before[k] == x, (k, x)
    assert p.blue_owned - b0 - added == TOKEN_SYMBOLS[c][0]
    assert p.yellow_bank - y0 == TOKEN_SYMBOLS[c][1]
    if key in YIELD_ONLY:
        assert EFFECT_TYPE[c] is None
        assert [a - b for a, b in zip(after, before)] == [yields(c).get(i, 0) for i in range(len(before))]


@pytest.mark.parametrize("key", [mcard("acropolis_a")])
def test_acropolis(key):
    g, s, _ = game()
    complete(g, s, key)
    assert st(g, s).urban_limit == 3
    mon = give(g, s, "Monarchy")[0]
    assert g.science_cost(s, mon) == SCIENCE_COST[mon] - 1                       # 1 urban building (Philosophy)
    assert g.science_cost(s, mon, revolution=True) == En.REVOLUTION_COST[mon]    # peaceful only


@pytest.mark.parametrize("key", [mcard("colosseum_a")])
def test_colosseum(key):
    g, s, _ = game()
    p = g.p(s)
    complete(g, s, key)
    knights = give(g, s, "Knights")[0]
    p.science = SCIENCE_COST[knights] - 1
    answer(g, "Develop Knights")
    assert knights in p.techs and p.culture == 2


@pytest.mark.parametrize("key", [mcard("colossus_a")])
def test_colossus(key):
    g, s, _ = game()
    complete(g, s, key)
    run_now(g, g.begin_age, "II")
    assert len(g.p(s).military_hand) == 3 and all(AGE[c] == "II" for c in g.p(s).military_hand)


@pytest.mark.parametrize("key", [mcard("hanging_gardens_a")])
def test_hanging_gardens(key):
    g, s, _ = game()
    f0 = E.food(g.p(s))
    complete(g, s, key)
    assert E.food(g.p(s)) == f0 + 2


@pytest.mark.parametrize("key", [mcard("library_of_alexandria_a")])
def test_library_of_alexandria(key):
    g, s, _ = game()
    c0, m0 = E.civil_hand_limit(g, s), E.military_hand_limit(g, s)
    complete(g, s, key)
    assert (E.civil_hand_limit(g, s), E.military_hand_limit(g, s)) == (c0 + 1, m0 + 1)


@pytest.mark.parametrize("key", [mcard("roman_roads_a")])
def test_roman_roads(key):
    g, s, _ = game()
    complete(g, s, key)
    x0 = st(g, s)
    sci = x0.science
    assert g.s.age == "I" and x0.resource_bonus == 1
    run_now(g, g.begin_age, "II")
    assert st(g, s).science == sci + 1 and st(g, s).resource_bonus == 0
    run_now(g, g.begin_age, "III")
    assert st(g, s).culture == 2 and st(g, s).science == sci


@pytest.mark.parametrize("key", [mcard("stonehenge_a")])
def test_stonehenge(key):
    g, s, _ = game()
    c = BY_KEY[key]
    p = g.p(s)
    p.unfinished = [c, 0, 0]
    res(g, s, STAGE_COSTS[c][0])
    sci = p.science
    answer(g, "Build a wonder stage")
    assert p.science == sci + STAGE_COSTS[c][0]


@pytest.mark.parametrize("key", [mcard("forbidden_city_i")])
def test_forbidden_city(key):
    g, s, _ = game()
    p = g.p(s)
    p.yellow_bank -= 8                                                            # 10 left: 3 happy required
    p.pool += 8
    touch(g, s)
    assert E.discontent(g, s) == 3
    complete(g, s, key)
    assert E.discontent(g, s) == 1


@pytest.mark.parametrize("key", [mcard("great_wall_i")])
def test_great_wall(key):
    g, s, _ = game()
    s0 = st(g, s).strength
    complete(g, s, key)
    assert st(g, s).strength == s0 + 1                                            # Warriors
    mil(g, s, "Knights", k=1)
    assert st(g, s).strength == s0 + 1 + 2                                        # cavalry: only its own 2


@pytest.mark.parametrize("key", [mcard("himeji_castle_i")])
def test_himeji_castle(key):
    g, s, (o,) = game()
    complete(g, s, key)
    raid = give(g, s, ("Aggression: Raid", "I"))[0]
    stronger(g, o, 1)                                                             # o 3 vs s 1 + 2 = 3: equal
    assert P.aggression_targets(g, s, raid) == [o]                                # the sacrifice counts
    mil(g, o, "Alchemy", k=1)
    c0 = g.p(s).culture
    politics(g)
    answer(g, "Play an aggression")
    maybe(g, "Aggression with")
    maybe(g, "on P")
    maybe(g, "Sacrifice a unit from Warriors")
    assert g.p(s).workers[cid("Warriors")] == 0 and g.p(s).culture == c0 + 3


@pytest.mark.parametrize("key", [mcard("himeji_castle_i")])
def test_himeji_castle_defender(key):
    g, s, (o,) = game()
    complete(g, s, key)                                                           # s: 1 + 2 = 3
    stronger(g, o, 2)                                                             # o: 5
    g.p(o).military_hand = [cid("Aggression: Raid", "I")]
    politics(g, o)
    answer(g, "Play an aggression")
    maybe(g, "Aggression with")
    maybe(g, "on P")
    assert kind(g) == "DEFEND" and g.current_seat == s
    answer(g, "Sacrifice a unit from Warriors")                                   # 3 + 1 + 3 >= 5: repelled
    assert g.p(s).workers[cid("Warriors")] == 0 and any("repels" in x for x in g.s.log)


@pytest.mark.parametrize("key", [mcard("machu_picchu_i")])
def test_machu_picchu(key):
    g, s, _ = game()
    complete(g, s, key)
    p = g.p(s)
    assert E.output(g, s, "farm") == 3 and E.output(g, s, "mine") == 3
    f0, r0 = E.food(p), E.resources(p)
    g.production(s)
    assert (E.food(p), E.resources(p)) == (f0 + 3, r0 + 3)


@pytest.mark.parametrize("key", [mcard("silk_road_i")])
def test_silk_road(key):
    g, s, _ = game()
    p = g.p(s)
    c = BY_KEY[key]
    p.unfinished = [c, 0, 0]
    res(g, s, STAGE_COSTS[c][0])
    answer(g, "Build a wonder stage")                                             # active from the first stage
    b = snap(g, s)
    play(g, s, "cultural_heritage_a")
    assert diff(b, snap(g, s)) == {"science": 2, "culture": 5}
    b = snap(g, s)
    play(g, s, "stockpile_a")                                                     # only the first card each turn
    assert diff(b, snap(g, s)) == {"food": 1, "resources": 1}


@pytest.mark.parametrize("key", [mcard("st_peter_s_basilica_i")])
def test_st_peters_basilica(key):
    g, s, _ = game()
    mil(g, s, "Religion", k=2)                                                    # 2 happy
    complete(g, s, key)
    assert st(g, s).happiness == 2 + 2 + 1                                        # +1 per worker, +1 itself


@pytest.mark.parametrize("key", [mcard("taj_mahal_i")])
def test_taj_mahal(key):
    g, s, _ = game()
    g.s.row[9] = BY_KEY[key]                                                      # slot 10: 3 civil actions
    assert g.take_cost(s, 9) == 3
    lead(g, s, "aristotle_a")
    lead(g, s, "moses_a")
    assert g.take_cost(s, 9) == 1
    answer(g, "Take Taj Mahal")
    assert g.p(s).unfinished[0] == BY_KEY[key]


@pytest.mark.parametrize("key", [mcard("harvard_college_ii")])
def test_harvard_college(key):
    g, s, _ = game()
    complete(g, s, key)
    take_from_row(g, s, "Cultural Heritage", "A")
    assert has(g, "Play action card Cultural Heritage")
    answer(g, "Play action card Cultural Heritage")
    take_from_row(g, s, "Stockpile", "A", slot=1)
    assert not has(g, "Play action card Stockpile")                               # once per turn


@pytest.mark.parametrize("key", [mcard("louvre_museum_ii")])
def test_louvre(key):
    g, s, _ = game()
    p = g.p(s)
    complete(g, s, key)
    assert p.louvre_tokens == 3 and st(g, s).culture == 2 + 3
    r0, bank = E.resources(p), p.blue_bank
    answer(g, "Louvre Museum")
    assert p.louvre_tokens == 2 and E.resources(p) == r0 + 2 and st(g, s).culture == 2 + 2


@pytest.mark.parametrize("key", [mcard("ocean_liner_service_ii")])
def test_ocean_liner_service(key):
    g, s, _ = game()
    p = g.p(s)
    complete(g, s, key)
    c0, f0, pool = E.civil_available(g, s), E.food(p), p.pool
    answer(g, "Ocean Liner Service")
    assert p.pool == pool + 1 and E.civil_available(g, s) == c0 and E.food(p) == f0
    assert not has(g, "Ocean Liner")


@pytest.mark.parametrize("key", [mcard("statue_of_liberty_ii")])
def test_statue_of_liberty(key):
    g, s, _ = game()
    complete(g, s, key)
    assert st(g, s).culture == 0                                                  # Despotism: level 0
    place(g, s, "Monarchy")
    assert st(g, s).culture == 1


@pytest.mark.parametrize("key", [mcard("suez_canal_ii")])
def test_suez_canal(key):
    g, s, _ = game()
    p = g.p(s)
    terr = give(g, s, ("Developed Territory", "I"))[0]
    sci = p.science
    complete(g, s, key)
    assert kind(g) == "ABILITY"
    answer(g, "Colonize Developed Territory")
    assert p.colonies == [terr] and st(g, s).resource_bonus == 1 and p.science == sci + 3


@pytest.mark.parametrize("key", [mcard("transcontinental_railroad_ii")])
def test_transcontinental_railroad(key):
    g, s, _ = game()
    complete(g, s, key)
    mil(g, s, "Iron", k=1)
    assert E.output(g, s, "mine") == 2 + 2 + 2                                    # Bronze 2, Iron 2, +1 Iron token


@pytest.mark.parametrize("key", [mcard("empire_state_building_iii")])
def test_empire_state_building(key):
    g, s, (o,) = game()
    stronger(g, s)
    c0 = g.p(s).culture
    complete(g, s, key)
    assert g.p(s).culture == c0 + 7                                               # only strength is strictly higher


@pytest.mark.parametrize("key", [mcard("fast_food_chains_iii")])
def test_fast_food_chains(key):
    g, s, _ = game()
    complete(g, s, key)
    assert g.p(s).culture == 1 * 2 + 2 * 4                                        # Warriors, Philosophy; 4 farm/mine


@pytest.mark.parametrize("key", [mcard("first_space_flight_iii")])
def test_first_space_flight(key):
    g, s, _ = game()
    place(g, s, "Coal")
    place(g, s, "Monarchy")
    complete(g, s, key)
    assert g.p(s).culture == 2 + 1


@pytest.mark.parametrize("key", [mcard("hollywood_iii")])
def test_hollywood(key):
    g, s, _ = game()
    mil(g, s, "Drama", k=1)
    mil(g, s, "Printing Press", k=1)
    complete(g, s, key)
    assert g.p(s).culture == 2 * (2 + 1)


@pytest.mark.parametrize("key", [mcard("international_red_cross_iii")])
def test_international_red_cross(key):
    g, s, (o,) = game()
    c = BY_KEY[key]
    q = g.p(o)
    q.unfinished = [c, 4, 4]
    q.blue_bank -= 4
    food(g, s, 3)
    q.colonies.append(cid("Vast Territory", "I"))
    c0 = E.civil_available(g, s)
    answer(g, "International Red Cross")
    assert g.p(s).culture == 6 and c in q.wonders and q.culture == 1             # owner: 1 per colony in play
    assert E.civil_available(g, s) == c0 - 1
    g, s, _ = game()                                                              # the owner pays stages in food
    p = g.p(s)
    p.unfinished = [c, 0, 0]
    food(g, s, 3)
    f0, r0 = E.food(p), E.resources(p)
    answer(g, "Build a wonder stage")
    assert (f0 - E.food(p), E.resources(p), p.culture) == (3, r0, 6)


@pytest.mark.parametrize("key", [mcard("internet_iii")])
def test_internet(key):
    g, s, _ = game()
    mil(g, s, "Printing Press", k=1)
    complete(g, s, key)
    assert g.p(s).culture == 1 + (1 + 1)                                          # Philosophy 1 sci, PP 1+1


@pytest.mark.parametrize("key", [mcard("manhattan_project_iii")])
def test_manhattan_project(key):
    g, s, _ = game()
    complete(g, s, key)
    assert g.p(s).culture == st(g, s).science == 1


@pytest.mark.parametrize("key", [mcard("united_nations_iii")])
def test_united_nations(key):
    g, s, (o,) = game()
    give(g, s, ("Impact of Colonies", "III"))
    g.p(o).colonies.append(cid("Vast Territory", "I"))
    complete(g, s, key)
    assert g.p(s).culture == 4 * 1                                                # 1 wonder, 0 specials, 1 type
    answer(g, "Evaluate Impact of Colonies")
    assert g.p(o).culture == 3 and cid("Impact of Colonies") in g.p(s).military_hand


# ===================================================================================================== bookkeeping
def test_every_effect_type_has_a_handler():
    assert effects.unimplemented_effect_types() == []


def test_generated_card_lists_are_complete():
    """The literal lists (check_repo reads literal marks) match the card data."""
    assert [p.values[0] for p in TECHNOLOGIES] == technologies()
    assert [p.values[0] for p in WONDERS] == [k for k in sorted(BY_KEY, key=BY_KEY.get) if KIND[BY_KEY[k]] == "wonder"]
