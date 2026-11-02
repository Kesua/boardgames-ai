"""Civil card effects (build stage 3, PLAN.md section 6): leaders, wonders, special technologies and action cards of
the base game, the rebalanced cards and the New Leaders and Wonders expansion.

One handler per effect type of data/card_effects.py, registered into effects.REGISTRY:
- passive statistics (economy.compute_stats; types in effects.LATE_ORDER run after all other cards because they
  read the happy faces other cards give),
- hooks (start of turn / politics / action phase, take card, develop, prepare event, wonder stage / completion,
  leaving play, end of turn, age start, game end),
- activated abilities as VERB answers (ABILITIES; numbers 15-25 of the frozen VERB segment),
- "rules": effects applied where the rule itself is computed (engine, politics, military: Gutenberg's action,
  Gandhi, Himeji Castle, Isabella, James Cook, Genghis Khan / Jan Zizka / Marlene Dietrich army forming, Sun Tzu's
  tactics, Silk Road, Harvard College, Machu Picchu, Transcontinental Railroad, Ashoka, Julius Caesar, Nobel); they
  are registered here for the bookkeeping with a pointer to the code.

Task handlers (decisions these cards need) follow engine.py: handler(game, task, answer). Registered into
engine.HANDLERS at import (engine imports this module at its end).
"""
from __future__ import annotations

from . import economy as E
from . import effects
from . import engine as En
from . import military as M
from . import politics as P
from .cards import (AGE, EFFECT, EFFECT_TYPE, HOLDS_WORKERS, IS_TECH, IS_UNIT, KIND, LEVEL, S_CIVIL, S_CULT, S_HAPPY,
                    S_RESB, S_SCI, S_STR, SPECIALS, STAGE_COSTS, STAT_YIELDS, TOKEN_VALUE, UNITS, URBAN)
from .engine import A_CARD, A_NO, A_OPTION, A_SEAT, A_VERB, A_YES, V

handler = effects.handler
push = effects.push
score = effects.score
LT = effects.leader_type
ALL_AGES = ("A", "I", "II", "III")


def _culture(st, card: int, k: int) -> None:
    """Culture rating from an effect, booked to the card with the text (PLAN C3)."""
    if k:
        st.v[S_CULT] += k
        st.culture_parts[card] = st.culture_parts.get(card, 0) + k


def _happy(st, card: int, k: int) -> None:
    if k:
        st.v[S_HAPPY] += k
        st.happy_parts[card] = st.happy_parts.get(card, 0) + k


def _workers(p, kinds) -> int:
    return sum(k for c, k in p.workers.items() if k and KIND[c] in kinds)


def _yield(c: int, stat: int) -> int:
    return sum(x for k, x in STAT_YIELDS[c] if k == stat)


def _best(p, kinds, ages=None):
    return effects.best_worker_card(p, kinds, ages)


def _level(c) -> int:
    return LEVEL[c] if c is not None else 0


def _add_disc(table: dict, kind: str, by_age: dict) -> None:
    cur = table.setdefault(kind, {})
    for a, x in by_age.items():
        cur[a] = cur.get(a, 0) + x


def _temp(p, key: str, n: int) -> None:
    if n:
        p.temp[key] = p.temp.get(key, 0) + n


def _rules(*types):
    """Bookkeeping registration for effects applied inside the rule code (see the module docstring)."""
    for t in types:
        effects.REGISTRY["rules"][t] = True


_rules("gandhi", "himeji_castle", "isabella", "zizka", "gutenberg", "julius_caesar", "ashoka", "best_mine_extra_token",
       "machu_picchu", "silk_road", "harvard", "nobel")


# ===================================================================================================== passive
@handler("passive", "alexander")
def _alexander(g, p, card, eff, st):
    """+1 strength per military unit."""
    st.v[S_STR] += eff["strength_per_unit"] * _workers(p, UNITS)


@handler("passive", "strength_per_unit_kind")
def _great_wall(g, p, card, eff, st):
    """Great Wall: +1 strength per infantry and artillery unit (Jan Zizka's farms are not units)."""
    st.v[S_STR] += eff["per_unit"] * _workers(p, tuple(eff["kinds"]))


@handler("passive", "napoleon")
def _napoleon(g, p, card, eff, st):
    """+2 strength per different type of military unit."""
    st.v[S_STR] += eff["strength_per_unit_type"] * len({KIND[c] for c, k in p.workers.items() if k and IS_UNIT[c]})


@handler("passive", "moses")
def _moses(g, p, card, eff, st):
    st.pop_discount += eff["population_food_discount"]


@handler("passive", "best_lab_or_library_bonus_science")
def _best_lab_library(g, p, card, eff, st):
    """Leonardo da Vinci, Isaac Newton, Albert Einstein: the best lab or library produces extra science = its level."""
    st.v[S_SCI] += _level(_best(p, ("lab", "library")))


@handler("passive", "shakespeare")
def _shakespeare(g, p, card, eff, st):
    """Library-theater pairs produce culture; with a library theaters are cheaper (build, develop), and vice versa."""
    lib, th = _workers(p, ("library",)), _workers(p, ("theater",))
    _culture(st, card, eff["culture_per_pair"] * min(lib, th))
    for have, kind in ((lib, "theater"), (th, "library")):
        if have:
            _add_disc(st.build_disc, kind, {a: eff["theater_library_discount_resources"] for a in ALL_AGES})
            _add_disc(st.sci_disc, kind, {a: eff["theater_library_discount_science"] for a in ALL_AGES})


@handler("passive", "bach")
def _bach(g, p, card, eff, st):
    """Each theater +1 culture; theater technologies 2 science cheaper (the upgrade ability: ABILITIES)."""
    _culture(st, card, eff["theater_culture"] * _workers(p, ("theater",)))
    _add_disc(st.sci_disc, "theater", {a: eff["theater_science_discount"] for a in ALL_AGES})


@handler("passive", "chaplin")
def _chaplin(g, p, card, eff, st):
    """The best theater produces twice its printed culture (one building; Q24)."""
    best = _best(p, ("theater",))
    if best is not None:
        _culture(st, card, (eff["best_theater_culture_multiplier"] - 1) * _yield(best, S_CULT))


@handler("passive", "sid_meier")
def _sid_meier(g, p, card, eff, st):
    """Each lab produces culture = its level and 1 science less."""
    for c in p.techs:
        k = p.workers.get(c, 0)
        if k and KIND[c] == "lab":
            _culture(st, card, eff["lab_culture_per_level"] * LEVEL[c] * k)
            st.v[S_SCI] += eff["lab_science_change"] * k


@handler("passive", "bill_gates")
def _bill_gates(g, p, card, eff, st):
    """Each lab produces resources = its level (a resource production bonus, T15.6; Q25)."""
    st.v[S_RESB] += gates_production(p, eff)


def gates_production(p, eff) -> int:
    return eff["lab_resources_per_level"] * sum(LEVEL[c] * k for c, k in p.workers.items() if k and KIND[c] == "lab")


@handler("passive", "gaudi")
def _gaudi(g, p, card, eff, st):
    """Urban technologies 1 science cheaper per other urban type built; the best building of each type +1 culture."""
    kinds = tuple(sorted({KIND[c] for c, k in p.workers.items() if k and KIND[c] in URBAN}))
    st.gaudi = kinds
    _culture(st, card, eff["best_urban_each_type_culture"] * len(kinds))


@handler("passive", "watt")
def _watt(g, p, card, eff, st):
    """Farms, mines and their technologies cheaper by age (resources and science)."""
    by_age = eff["farm_mine_resource_and_science_discount_by_age"]
    for kind in ("farm", "mine"):
        _add_disc(st.build_disc, kind, by_age)
        _add_disc(st.sci_disc, kind, by_age)


@handler("passive", "ian_fleming")
def _fleming(g, p, card, eff, st):
    """The best library and the best theater each produce extra culture = their level."""
    per = eff["best_library_and_theater_culture_per_level"]
    _culture(st, card, per * (_level(_best(p, ("library",))) + _level(_best(p, ("theater",)))))


@handler("passive", "marie_curie")
def _curie(g, p, card, eff, st):
    """Best mine: science = its level; best lab: strength = its level; culture = the higher of the two levels."""
    mine, lab = _best(p, ("mine",)), _best(p, ("lab",))
    st.v[S_SCI] += _level(mine)
    st.v[S_STR] += _level(lab)
    _culture(st, card, max(_level(mine), _level(lab)))


@handler("passive", "coubertin")
def _coubertin(g, p, card, eff, st):
    _culture(st, card, eff["arena_culture"] * _workers(p, ("arena",)))


@handler("passive", "james_cook")
def _cook(g, p, card, eff, st):
    """First colony +2 culture, each later one +1 (colonization discards: politics.h_send)."""
    n = len(p.colonies)
    _culture(st, card, eff["first_colony_culture"] + eff["later_colony_culture"] * (n - 1) if n else 0)


@handler("passive", "saladin")
def _saladin(g, p, card, eff, st):
    if p.saladin == 0:
        st.v[S_STR] += eff["choice_each_turn"][0]["strength"]
    elif p.saladin == 1:
        st.v[S_CIVIL] += eff["choice_each_turn"][1]["civil_actions"]


@handler("passive", "acropolis")
def _acropolis(g, p, card, eff, st):
    """Urban building limit +1; a peaceful government change 1 science cheaper per urban building."""
    st.urban_limit += eff["urban_limit"]
    st.gov_disc += eff["peaceful_government_discount_per_urban"] * _workers(p, URBAN)


@handler("passive", "colosseum")
def _colosseum(g, p, card, eff, st):
    """Infantry and cavalry technologies cost science equal to their level less."""
    for kind in eff["kinds"]:
        _add_disc(st.sci_disc, kind, {a: eff["science_discount_per_level"] * i for i, a in enumerate(ALL_AGES)})


@handler("passive", "roman_roads")
def _roman_roads(g, p, card, eff, st):
    """Production by the current age: Age I 1 resource (bonus), II 1 science, III and IV 2 culture."""
    y = eff["by_age"].get(g.s.age, {})
    st.v[S_RESB] += y.get("resource_production", 0)
    st.v[S_SCI] += y.get("science", 0)
    _culture(st, card, y.get("culture", 0))


@handler("passive", "forbidden_city")
def _forbidden_city(g, p, card, eff, st):
    st.ignore_discontent += eff["ignore_discontent"]


@handler("passive", "louvre")
def _louvre(g, p, card, eff, st):
    _culture(st, card, eff["culture_per_token"] * p.louvre_tokens)


@handler("passive", "statue_of_liberty")
def _statue(g, p, card, eff, st):
    _culture(st, card, eff["government_culture_per_level"] * LEVEL[p.government])


@handler("passive", "suez_canal")
def _suez(g, p, card, eff, st):
    st.v[S_RESB] += eff["resource_production_per_colony"] * len(p.colonies)


# ------------------------------------------------------------------------- late passives (effects.LATE_ORDER)
@handler("passive", "darwin")
def _darwin(g, p, card, eff, st):
    """Temples 1 happy face less each; labs and libraries 1 culture more each; technologies from the row 1 civil
    action cheaper (minimum 1, engine.take_cost)."""
    for c in p.techs:
        k = p.workers.get(c, 0)
        if not k:
            continue
        if KIND[c] == "temple":
            _happy(st, c, eff["temple_happy_change"] * k)
        elif KIND[c] in ("lab", "library"):
            _culture(st, card, eff["lab_library_culture"] * k)
    st.take_disc += eff["technology_take_discount"]


@handler("passive", "steve_jobs")
def _jobs(g, p, card, eff, st):
    """The best lab gives happy faces = its level (the develop bonus: on_develop)."""
    best = _best(p, ("lab",))
    if best is not None:
        _happy(st, best, eff["best_lab_happy_per_level"] * LEVEL[best])


@handler("passive", "marlene_dietrich")
def _dietrich(g, p, card, eff, st):
    """Each highest-level theater +1 culture and +1 happy face (the tactic bonus: military.army_flags)."""
    best = _best(p, ("theater",))
    if best is None:
        return
    for c in p.techs:
        k = p.workers.get(c, 0)
        if k and KIND[c] == "theater" and LEVEL[c] == LEVEL[best]:
            _culture(st, card, eff["top_theaters"]["culture"] * k)
            _happy(st, c, eff["top_theaters"]["happy"] * k)


@handler("passive", "st_peters_basilica")
def _st_peters(g, p, card, eff, st):
    """Every other card (per worker for buildings) giving at least 1 happy face gives 1 more."""
    for c, h in list(st.happy_parts.items()):
        if h > 0 and c != card:
            _happy(st, c, eff["extra_happy"] * (p.workers.get(c, 0) if HOLDS_WORKERS[c] else 1))


@handler("passive", "michelangelo")
def _michelangelo(g, p, card, eff, st):
    """Urban buildings (rebalanced: all types) and wonders produce 1 culture per happy face they give; no wonder
    surcharge when taking a wonder."""
    kinds = set()
    for x in eff["culture_per_happy_on"]:
        kinds |= set(URBAN) if x == "urban" else {x}
    _culture(st, card, sum(h for c, h in st.happy_parts.items() if h > 0 and KIND[c] in kinds))
    st.no_wonder_surcharge = st.no_wonder_surcharge or eff["no_wonder_surcharge"]


@handler("passive", "joan_of_arc")
def _joan(g, p, card, eff, st):
    """Temples and the government give +1 strength per happy face they give (the peek: start_of_politics)."""
    per = eff["strength_per_happy_face_on_temples_and_government"]
    st.v[S_STR] += per * sum(h for c, h in st.happy_parts.items()
                             if h > 0 and (KIND[c] == "temple" or c == p.government))


# ===================================================================================================== hooks
def _own(seat, owner) -> bool:
    return seat == owner


@handler("start_of_turn", "hippocrates")
def _hippocrates(g, seat, card, eff, owner):
    """A reminder (yellow token from the box) above the government each turn, at most 3 (age ends:
    effects.hippocrates_age_end)."""
    if seat == owner:
        p = g.p(seat)
        p.reminders = min(eff["max_reminders"], p.reminders + eff["reminders_per_turn"])


def _grant_once(g, seat, card, key, n) -> None:
    """A per-turn temporary amount (T12.9), given at most once per turn per card."""
    p = g.p(seat)
    flag = f"granted_{card}"
    if not p.flags.get(flag):
        p.flags[flag] = True
        _temp(p, key, n)


def _own_action_phase(g, seat) -> bool:
    return g.s.phase == "actions" and g.s.turn_seat == seat


@handler("start_of_action_phase", "homer", "cleopatra")
def _turn_temp(g, seat, card, eff, owner):
    """Homer: 1 resource for military units each turn; Cleopatra: 1 resource for wonder stages and urban buildings."""
    if seat == owner:
        if EFFECT_TYPE[card] == "homer":
            _grant_once(g, seat, card, "unit", eff["military_build_resources_per_turn"])
        else:
            _grant_once(g, seat, card, "civic", eff["wonder_or_urban_resources_per_turn"])


@handler("on_enter_play", "homer", "cleopatra")
def _turn_temp_enter(g, seat, card, eff):
    """Played during the own action phase: the per-turn resource is available this turn already."""
    if _own_action_phase(g, seat):
        _turn_temp(g, seat, card, eff, seat)


@handler("start_of_action_phase", "boudica")
def _boudica(g, seat, card, eff, owner):
    """One of the two weakest (2 players: the weaker; Nostradamus does not count): 2 resources for military units;
    otherwise a choice of 1 food, 1 resource or 1 science."""
    if seat != owner:
        return
    if seat in M.top_two(g, "strength", "low", events=False):
        _temp(g.p(seat), "unit", eff["if_two_weakest"]["military_build_resources"])
    else:
        push(g, {"op": "ability", "seat": seat, "what": "gain", "card": card, "options": eff["otherwise_choice"]})


@handler("start_of_action_phase", "maria_theresa")
def _maria(g, seat, card, eff, owner):
    """1 resource for military units each turn, 3 if one of the two weakest (population bonus:
    engine.population_gained)."""
    if seat == owner:
        weak = seat in M.top_two(g, "strength", "low", events=False)
        _temp(g.p(seat), "unit", eff["military_build_resources_if_two_weakest" if weak else "military_build_resources"])


@handler("start_of_politics", "joan_of_arc")
def _joan_peek(g, seat, card, eff, owner):
    """Looks at the top card of the current events deck (free information: always taken)."""
    if seat == owner and g.s.current_events:
        entry = g.s.current_events[0]
        if len(entry) < 3:
            entry.append([])
        if seat not in entry[2]:
            entry[2].append(seat)


@handler("start_of_politics", "ian_fleming")
def _fleming_peek(g, seat, card, eff, owner):
    """May look at one player's military cards; not the same player two turns in a row."""
    if seat != owner:
        return
    p = g.p(seat)
    last, p.fleming_last = p.fleming_last, None
    targets = [x for x in g.active_seats(seat)[1:] if x != last]
    if targets:
        push(g, {"op": "ability", "seat": seat, "what": "fleming", "card": card, "targets": targets})


@handler("on_take_card", "aristotle")
def _aristotle(g, seat, me, eff, taker, card):
    """1 science per technology card taken from the row."""
    if seat == taker and IS_TECH[card]:
        E.add_science(g.p(seat), eff["on_take_technology"]["science"])


@handler("on_take_card", "michelangelo")
def _michelangelo_take(g, seat, me, eff, taker, card):
    """Rebalanced: 1 resource when taking a wonder."""
    if seat == taker and KIND[card] == "wonder" and eff.get("on_take_wonder"):
        g.apply_gain(seat, eff["on_take_wonder"], "leaders", me)


@handler("on_develop", "best_lab_or_library_bonus_science")
def _develop_bonus(g, seat, me, eff, developer, card, revolution):
    """Leonardo: 1 resource, Isaac Newton: a spent civil action back, Albert Einstein: 3 culture per development."""
    if seat != developer:
        return
    if eff.get("on_develop"):
        g.apply_gain(seat, eff["on_develop"], "leaders", me)
    if eff.get("on_develop_regain_civil_action"):
        p = g.p(seat)
        p.civil_spent = max(0, p.civil_spent - eff["on_develop_regain_civil_action"])


@handler("on_develop", "colosseum")
def _colosseum_develop(g, seat, me, eff, developer, card, revolution):
    if seat == developer and KIND[card] in eff["kinds"]:
        score(g, seat, eff["on_develop_culture"], me, "wonders")


@handler("on_develop", "robespierre")
def _robespierre(g, seat, me, eff, developer, card, revolution):
    """3 culture per revolution (it costs all military actions instead: engine.can_revolution / develop)."""
    if seat == developer and revolution:
        score(g, seat, eff["revolution_culture"], me, "leaders")


@handler("on_develop", "steve_jobs")
def _jobs_develop(g, seat, me, eff, developer, card, revolution):
    """May pay 1 resource to score 4 culture."""
    if seat == developer and g.afford(seat, "mine", eff["on_develop_may_pay"]["resources"]):
        push(g, {"op": "ability", "seat": seat, "what": "jobs", "card": me})


@handler("on_prepare_event", "confucius", "eleanor", "nostradamus")
def _prepare_bonus(g, seat, me, eff, preparer, card):
    """Confucius 1 science, Eleanor of Aquitaine 2 military cards, Nostradamus 3 culture per prepared event."""
    if seat == preparer:
        g.apply_gain(seat, eff["on_prepare_event"], "leaders", me)


@handler("on_leave_play", "confucius")
def _confucius_leave(g, seat, card, eff):
    g.apply_gain(seat, eff["on_leave"], "leaders", card)


@handler("on_leave_play", "watt")
def _watt_leave(g, seat, card, eff):
    """Culture = production of the best farm or mine (the one producing most)."""
    p = g.p(seat)
    best = max((p.workers.get(c, 0) * TOKEN_VALUE[c] for c in p.techs if KIND[c] in ("farm", "mine")), default=0)
    score(g, seat, best, card, "leaders")


@handler("on_leave_play", "bill_gates")
def _gates_leave(g, seat, card, eff):
    score(g, seat, gates_production(g.p(seat), eff), card, "leaders")


@handler("game_end", "bill_gates")
def _gates_end(g, seat, card, eff):
    score(g, seat, gates_production(g.p(seat), eff), card, "leaders")


@handler("on_leave_play", "sun_tzu")
def _sun_tzu_leave(g, seat, card, eff):
    """Tucked under the current tactic: it gives +1 strength per army while the marker stays on it (Q26)."""
    p = g.p(seat)
    if p.tactic is not None:
        p.tactic_boost = p.tactic
        g.touch(seat)


@handler("on_leave_play", "saladin")
def _saladin_leave(g, seat, card, eff):
    g.p(seat).saladin = None


@handler("end_of_turn", "saladin")
def _saladin_end(g, seat, card, eff, owner):
    if seat == owner:
        push(g, {"op": "ability", "seat": seat, "what": "saladin", "card": card})


@handler("end_of_turn", "genghis_khan")
def _genghis_end(g, seat, card, eff, owner):
    """3 culture if one of the two strongest (2 players: the stronger), ties go to him."""
    if seat != owner:
        return
    me = E.stats(g, seat).strength
    higher = sum(1 for x in g.active_seats() if x != seat and E.stats(g, x).strength > me)
    if higher < (2 if len(g.active_seats()) >= 3 else 1):
        score(g, seat, eff["end_turn_culture_if_top2_strength"], card, "leaders")


@handler("end_of_turn", "mandela")
def _mandela_end(g, seat, card, eff, owner):
    """After discarding: 1 culture per surplus happy face (happiness above the faces required)."""
    if seat == owner:
        p = g.p(seat)
        surplus = max(0, E.stats(g, seat).happiness - E.happy_required(p.yellow_bank))
        score(g, seat, eff["culture_per_surplus_happy"] * surplus, card, "leaders")


@handler("take_cost", "taj_mahal")
def _taj_cost(g, seat, card, eff):
    return -eff["take_discount_after_leader_replace"] if g.p(seat).flags.get("leader_replaced") else 0


@handler("take_cost", "mandela")
def _mandela_cost(g, seat, card, eff):
    return eff["take_surcharge_without_discontent"] if E.discontent(g, seat) == 0 else 0


@handler("rank_bonus", "nostradamus")
def _nostradamus_rank(g, seat, card, eff, stat, mode):
    """+3 strength when an event determines the weakest civilization(s)."""
    return eff["strength_when_weakest_checked_or_defending_aggression"] if stat == "strength" and mode == "low" else 0


@handler("defend_bonus", "nostradamus")
def _nostradamus_defend(g, seat, card, eff):
    return eff["strength_when_weakest_checked_or_defending_aggression"]


@handler("age_start", "colossus")
def _colossus(g, seat, card, eff, age):
    if age in eff["ages"]:
        M.draw(g, seat, eff["military_cards_at_age_start"])


@handler("on_wonder_stage", "stonehenge")
def _stonehenge(g, seat, card, eff, builder):
    """Each stage built scores science equal to its cost."""
    paid = g.p(seat).unfinished[1]
    E.add_science(g.p(seat), STAGE_COSTS[card][paid - 1])


@handler("on_wonder_stage", "red_cross")
def _red_cross_stage(g, seat, card, eff, builder):
    """Whoever builds a stage scores 6 culture."""
    score(g, builder, eff["culture_per_stage"], card, "wonders")


# ------------------------------------------------------------------------- wonders: on completion
@handler("on_wonder_complete", "fast_food_chains")
def _ffc(g, seat, card, eff):
    p = g.p(seat)
    score(g, seat, eff["culture_per_military_or_urban_worker"] * _workers(p, UNITS + URBAN)
          + eff["culture_per_farmer_or_miner"] * _workers(p, ("farm", "mine")), card, "wonders")


def technologies_in_play(p) -> list:
    return list(p.techs) + list(p.specials.values()) + [p.government]


@handler("on_wonder_complete", "first_space_flight")
def _fsf(g, seat, card, eff):
    p = g.p(seat)
    score(g, seat, eff["culture_per_technology_level"] * sum(LEVEL[c] for c in technologies_in_play(p)), card,
          "wonders")


@handler("on_wonder_complete", "hollywood")
def _hollywood(g, seat, card, eff):
    """Twice the (printed) culture produced by theaters and libraries (Q24)."""
    p = g.p(seat)
    k = sum(_yield(c, S_CULT) * n for c, n in p.workers.items() if n and KIND[c] in eff["of"])
    score(g, seat, eff["culture_multiplier"] * k, card, "wonders")


@handler("on_wonder_complete", "internet")
def _internet(g, seat, card, eff):
    """Culture and science produced by urban buildings plus the strength they give (printed symbols, Q24)."""
    p = g.p(seat)
    k = sum((_yield(c, S_CULT) + _yield(c, S_SCI) + _yield(c, S_STR)) * n for c, n in p.workers.items()
            if n and KIND[c] in URBAN)
    score(g, seat, k, card, "wonders")


@handler("on_wonder_complete", "manhattan_project")
def _manhattan(g, seat, card, eff):
    score(g, seat, E.stats(g, seat).science, card, "wonders")


ESB_CATEGORIES = (lambda g, s: E.stats(g, s).science, lambda g, s: E.stats(g, s).culture,
                  lambda g, s: E.stats(g, s).strength, lambda g, s: E.output(g, s, "farm"),
                  lambda g, s: E.output(g, s, "mine"))


@handler("on_wonder_complete", "empire_state_building")
def _esb(g, seat, card, eff):
    """Science rating, culture rating, strength, food and resource production: culture per category where strictly
    higher than every opponent."""
    rivals = [x for x in g.active_seats() if x != seat]
    per = eff["culture_per_category"][str(max(2, len(g.active_seats())))]
    wins = sum(1 for f in ESB_CATEGORIES if all(f(g, seat) > f(g, x) for x in rivals))
    score(g, seat, per * wins, card, "wonders")


@handler("on_wonder_complete", "united_nations")
def _un(g, seat, card, eff):
    """4 culture x the highest of: wonders (itself included), special technologies, urban building types; then may
    evaluate an Age III event from hand for everybody (it stays in hand)."""
    p = g.p(seat)
    kinds = len({KIND[c] for c, k in p.workers.items() if k and KIND[c] in URBAN})
    score(g, seat, eff["culture_multiplier"] * max(len(p.wonders), len(p.specials), kinds), card, "wonders")
    if eff["may_evaluate_age_iii_event_from_hand"] and _age_iii_events(p):
        push(g, {"op": "ability", "seat": seat, "what": "un_event", "card": card})


def _age_iii_events(p) -> list:
    return sorted({c for c in p.military_hand if AGE[c] == "III" and KIND[c] == "event"})


@handler("on_wonder_complete", "suez_canal")
def _suez_complete(g, seat, card, eff):
    """May colonize a territory from hand (no units)."""
    if eff["colonize_on_complete"] and _territories(g.p(seat)):
        push(g, {"op": "ability", "seat": seat, "what": "colonize", "card": card, "optional": True})


@handler("on_wonder_complete", "red_cross")
def _red_cross_complete(g, seat, card, eff):
    """The owner scores 1 culture per colony in play (all players)."""
    n = sum(len(q.colonies) for q in g.s.players if q.resigned_order is None)
    score(g, seat, eff["on_complete_culture_per_colony_in_play"] * n, card, "wonders")


def _territories(p) -> list:
    return sorted({c for c in p.military_hand if KIND[c] == "territory"})


# ===================================================================================================== action cards
@handler("play_action", "military_resources_per_stronger")
def _per_stronger(g, seat, card, eff):
    """Wave of Nationalism, Military Build-Up: resources for military units this turn per stronger civilization."""
    me = E.stats(g, seat).strength
    n = sum(1 for x in g.active_seats() if x != seat and E.stats(g, x).strength > me)
    k = eff["per_player"][str(max(2, len(g.active_seats())))] * n + (eff.get("bonus_total", 0) if n else 0)
    _temp(g.p(seat), "unit", k)


@handler("play_action", "culture_per_more_cultured")
def _per_more_cultured(g, seat, card, eff):
    """Endowment for the Arts: culture per civilization with more culture points."""
    me = g.p(seat).culture
    n = sum(1 for x in g.active_seats() if x != seat and g.p(x).culture > me)
    k = eff["per_player"][str(max(2, len(g.active_seats())))] * n + (eff.get("bonus_total", 0) if n else 0)
    score(g, seat, k, card, "actions")


# ===================================================================================================== abilities
def _can_hammurabi(g, seat):
    p = g.p(seat)
    return LT(p) == "hammurabi" and E.military_available(g, seat) >= 1 and \
        p.flags.get("hammurabi", 0) < EFFECT[p.leader]["military_as_civil_per_turn"]


def _use_hammurabi(g, seat):
    p = g.p(seat)
    p.flags["hammurabi"] = p.flags.get("hammurabi", 0) + 1
    E.spend_military(p, 1)
    p.temp_civil += 1


def _barbarossa_units(g, seat, eff) -> list:
    p = g.p(seat)
    return [c for c in p.techs if IS_UNIT[c] and g.afford(seat, "mine", g.build_cost(seat, c, eff["resource_discount"]),
                                                          "unit")]


def _can_barbarossa(g, seat):
    p = g.p(seat)
    if LT(p) != "barbarossa":
        return False
    eff = EFFECT[p.leader]
    if not (E.military_available(g, seat) >= eff["military_actions"] and
            g.can_increase_population(seat, free_action=True, discount=eff["food_discount"]) and
            _barbarossa_units(g, seat, eff)):
        return False
    if g.trade_conversion(seat, "farm") or g.trade_conversion(seat, "mine"):
        h = g.clone()                                      # Trade Routes: paying the food may use a resource
        h.increase_population(seat, free_action=True, discount=eff["food_discount"])
        return bool(_barbarossa_units(h, seat, eff))
    return True


def _use_barbarossa(g, seat):
    """1 military action: increase population and build a military unit, 1 food and 1 resource cheaper."""
    p = g.p(seat)
    eff = EFFECT[p.leader]
    E.spend_military(p, eff["military_actions"])
    g.increase_population(seat, free_action=True, discount=eff["food_discount"])
    push(g, {"op": "build", "seat": seat, "kinds": UNITS, "discount": eff["resource_discount"], "free": True,
             "card": p.leader})


def _ocean_liner(p):
    return next((w for w in p.wonders if EFFECT_TYPE[w] == "free_increase_population_per_turn"), None)


def _can_ocean_liner(g, seat):
    p = g.p(seat)
    return _ocean_liner(p) is not None and not p.flags.get("ocean_liner") and p.yellow_bank > 0


def _use_ocean_liner(g, seat):
    """Once per turn: increase population without a civil action or food."""
    p = g.p(seat)
    p.flags["ocean_liner"] = True
    for _ in range(EFFECT[_ocean_liner(p)]["population"]):
        if p.yellow_bank > 0:
            g.increase_population(seat, free_action=True, free_food=True)


def bach_from(g, seat) -> list:
    p = g.p(seat)
    return [c for c in p.techs if p.workers.get(c, 0) and KIND[c] in URBAN and bach_to(g, seat, c)]


def bach_to(g, seat, frm) -> list:
    """Theaters of the same or a higher age (a theater only to a higher one), within the urban limit, paying the
    cost difference after modifiers."""
    p = g.p(seat)
    limit = g.stats(seat).urban_limit
    if KIND[frm] != "theater" and E.urban_workers(p, "theater") >= limit:
        return []
    return [c for c in p.techs if KIND[c] == "theater" and c != frm
            and (LEVEL[c] > LEVEL[frm] if KIND[frm] == "theater" else LEVEL[c] >= LEVEL[frm])
            and g.afford(seat, "mine", g.move_cost(seat, frm, c), "civic")]


def _can_bach(g, seat):
    p = g.p(seat)
    return LT(p) == "bach" and not p.flags.get("bach") and \
        E.civil_available(g, seat) >= EFFECT[p.leader]["upgrade_civil_actions"] and bool(bach_from(g, seat))


def _use_bach(g, seat):
    g.p(seat).flags["bach"] = True
    push(g, {"op": "bach", "seat": seat, "frm": None})


def _can_churchill(g, seat):
    p = g.p(seat)
    return LT(p) == "churchill" and not p.flags.get("churchill")


def _use_churchill(g, seat):
    p = g.p(seat)
    p.flags["churchill"] = True
    push(g, {"op": "ability", "seat": seat, "what": "churchill", "card": p.leader})


def _louvre(p):
    return next((w for w in p.wonders if EFFECT_TYPE[w] == "louvre"), None)


def _can_louvre(g, seat):
    p = g.p(seat)
    return p.louvre_tokens > 0 and _louvre(p) is not None


def _use_louvre(g, seat):
    """Return one token from the Louvre to the blue bank for 2 resources (no action)."""
    p = g.p(seat)
    w = _louvre(p)
    p.louvre_tokens -= 1
    p.blue_bank += 1
    g.touch(seat)
    g.apply_gain(seat, {"resources": EFFECT[w]["resources_per_token"]}, "wonders", w)


def red_cross_owner(g, seat):
    """Another player's unfinished International Red Cross: (owner, card) or None."""
    for q in g.s.players:
        if q.seat != seat and q.resigned_order is None and q.unfinished is not None and \
                EFFECT_TYPE[q.unfinished[0]] == "red_cross":
            return q.seat, q.unfinished[0]
    return None


def _can_red_cross(g, seat):
    rc = red_cross_owner(g, seat)
    if rc is None or g.p(seat).flags.get("red_cross", 0) >= EFFECT[rc[1]]["others_stages_per_turn"]:
        return False
    cost = EFFECT[rc[1]]["others_stage_cost"]
    return E.civil_available(g, seat) >= cost["civil_actions"] and g.afford(seat, "farm", cost["food"])


def _use_red_cross(g, seat):
    owner, card = red_cross_owner(g, seat)
    p = g.p(seat)
    p.flags["red_cross"] = p.flags.get("red_cross", 0) + 1
    cost = EFFECT[card]["others_stage_cost"]
    E.spend_civil(p, cost["civil_actions"])
    g.pay(seat, "farm", cost["food"])
    push(g, {"op": "rc_stage", "seat": seat, "owner": owner})


def _can_alexander(g, seat):
    return LT(g.p(seat)) == "alexander"


def _use_alexander(g, seat):
    """Political action: remove Alexander from play, 1 yellow token from the box into the yellow bank."""
    p = g.p(seat)
    y = EFFECT[p.leader]["political_remove_gain"]["yellow_tokens"]
    g.remove_leader(seat)
    g.change_tokens(seat, 0, y)


def _can_columbus(g, seat):
    p = g.p(seat)
    return LT(p) == "columbus" and bool(_territories(p))


def _use_columbus(g, seat):
    push(g, {"op": "ability", "seat": seat, "what": "colonize", "card": g.p(seat).leader, "optional": False})


def _can_catherine(g, seat):
    p = g.p(seat)
    return LT(p) == "catherine" and "catherine" not in p.used


def _use_catherine(g, seat):
    """Once per game: every civilization weaker than you loses 1 yellow token (yellow bank); if enough were lost
    (1, or 2 with 4 players) you gain 1."""
    p = g.p(seat)
    eff = EFFECT[p.leader]
    p.used.append("catherine")
    me = E.stats(g, seat).strength
    lost = 0
    for x in g.active_seats(seat)[1:]:
        if E.stats(g, x).strength < me and g.p(x).yellow_bank > 0:
            g.change_tokens(x, 0, -eff["weaker_lose_yellow"])
            lost += 1
    if lost >= eff["gain_needs_lost"][str(max(2, len(g.active_seats())))]:
        g.change_tokens(seat, 0, eff["gain_yellow"])


def _can_olympics(g, seat):
    p = g.p(seat)
    return LT(p) == "coubertin" and "olympics" not in p.used


def _use_olympics(g, seat):
    """Once per game, before the political action: 8 culture; until before the owner's next Politics Phase whoever
    plays a war or aggression loses 8 culture (politics.olympics_penalty)."""
    p = g.p(seat)
    p.used.append("olympics")
    score(g, seat, EFFECT[p.leader]["olympics_culture"], p.leader, "leaders")
    g.s.olympics = [seat, p.leader]


ABILITIES = {          # verb: (decision, card types, legal, use)
    "ALEXANDER": ("POLITICS", ("alexander",), _can_alexander, _use_alexander),
    "COLUMBUS": ("POLITICS", ("columbus",), _can_columbus, _use_columbus),
    "CATHERINE": ("POLITICS", ("catherine",), _can_catherine, _use_catherine),
    "OLYMPICS": ("POLITICS", ("coubertin",), _can_olympics, _use_olympics),
    "HAMMURABI": ("ACTION", ("hammurabi",), _can_hammurabi, _use_hammurabi),
    "BARBAROSSA": ("ACTION", ("barbarossa",), _can_barbarossa, _use_barbarossa),
    "OCEAN_LINER": ("ACTION", ("free_increase_population_per_turn",), _can_ocean_liner, _use_ocean_liner),
    "BACH": ("ACTION", ("bach",), _can_bach, _use_bach),
    "CHURCHILL": ("ACTION", ("churchill",), _can_churchill, _use_churchill),
    "LOUVRE": ("ACTION", ("louvre",), _can_louvre, _use_louvre),
    "RED_CROSS": ("ACTION", ("red_cross",), _can_red_cross, _use_red_cross),
}
for _verb, (_where, _types, _can, _use) in ABILITIES.items():
    for _t in _types:
        effects.REGISTRY["ability"][_t] = _verb
BY_DECISION = {w: [v for v, x in ABILITIES.items() if x[0] == w] for w in ("POLITICS", "ACTION")}


def ability_verbs(g, seat: int, where: str) -> list:
    """VERB answers of activated abilities legal now (every one uses up a bounded thing: a once-per-turn or
    once-per-game flag, a military/civil action, the leader himself, a Louvre token)."""
    if g.s.round == 1:
        return []
    return [A_VERB + V[v] for v in BY_DECISION[where] if ABILITIES[v][2](g, seat)]


def use_ability(g, seat: int, verb: str) -> None:
    ABILITIES[verb][3](g, seat)


def leader_replaced(g, seat: int, old: int, refunded: int) -> None:
    """T5.6 replacement effects of the old leader: Alfred Nobel goes beside the culture track (his prize starts);
    Homer may be tucked under a completed wonder (+1 happy face) giving up the civil action back."""
    t = EFFECT_TYPE[old]
    if t == "nobel" and EFFECT[old]["prize_starts_when_replaced"]:
        g.s.nobel_prize = old
        g.s.log.add(seat, "Alfred Nobel goes beside the culture track")
    elif t == "homer" and g.p(seat).wonders:
        push(g, {"op": "ability", "seat": seat, "what": "homer", "card": old, "refunded": refunded})


# ===================================================================================================== tasks
def ability_legal(g, t: dict) -> list:
    seat, w = t["seat"], t["what"]
    p = g.p(seat)
    if w in ("gain", "churchill", "saladin"):
        n = len(t["options"]) if w == "gain" else 2
        return [A_OPTION + i for i in range(n)]
    if w == "fleming":
        return [P.seat_id(g, seat, x) for x in t["targets"]] + [A_NO]
    if w == "jobs":
        return [A_YES, A_NO] if g.afford(seat, "mine", EFFECT[t["card"]]["on_develop_may_pay"]["resources"]) else []
    if w == "colonize":
        return [A_CARD + c for c in _territories(p)] + ([A_NO] if t["optional"] else [])
    if w == "un_event":
        return [A_CARD + c for c in _age_iii_events(p)] + [A_NO]
    if w == "homer":
        return [A_CARD + c for c in p.wonders] + [A_NO]
    raise KeyError(w)


def h_ability(g, t: dict, a):
    """ABILITY decisions of civil cards (PLAN 3): Boudica's gain, Churchill's and Saladin's choice, Ian Fleming's
    look, Steve Jobs' payment, Columbus / Suez Canal colonizing from hand, United Nations' event, Homer's tuck."""
    seat, w = t["seat"], t["what"]
    if a is None:
        legal = ability_legal(g, t)
        if not legal or (legal == [A_NO]):
            g._finish(t)
            return
        g._ask("ABILITY", seat, legal, what=w, card=t["card"], options=t.get("options"))
        return
    g._finish(t)
    p = g.p(seat)
    card = t["card"]
    eff = EFFECT[card]
    if w == "gain":
        g.apply_gain(seat, t["options"][a - A_OPTION], "leaders", card)
    elif w == "churchill":
        if a == A_OPTION:
            score(g, seat, eff["culture"], card, "leaders")
        else:
            _temp(p, "unit_science", eff["military_science"])
            _temp(p, "unit", eff["military_resources"])
    elif w == "saladin":
        before = E.totals(g, seat)
        p.saladin = a - A_OPTION
        g.touch(seat)
        E.settle_totals(g, seat, before)
    elif w == "fleming":
        if a != A_NO:
            target = P.id_seat(g, seat, a)
            p.peek = [target, sorted(g.p(target).military_hand)]
            p.fleming_last = target
    elif w == "jobs":
        if a == A_YES:
            g.pay(seat, "mine", eff["on_develop_may_pay"]["resources"])
            g.apply_gain(seat, eff["then_gain"], "leaders", card)
    elif w == "colonize":
        if a != A_NO:
            terr = a - A_CARD
            if EFFECT_TYPE[card] == "columbus":
                g.remove_leader(seat)
            p.military_hand.remove(terr)
            g.s.resolving.append(terr)
            P.colonize(g, seat, terr, {}, [])
    elif w == "un_event":
        if a != A_NO:
            ev = a - A_CARD
            g.s.log.add(seat, f"evaluates {g.card_name(ev)} from hand (United Nations)")
            effects.resolve_event(g, seat, ev)
    elif w == "homer":
        if a != A_NO:
            p.homer_wonder = a - A_CARD
            p.civil_spent += t["refunded"]                         # no civil action back
            g.touch(seat)


def h_bach(g, t: dict, a):
    """Bach: 1 civil action, upgrade any urban building to a theater of the same or a higher age."""
    seat = t["seat"]
    if t["frm"] is None:
        if a is None:
            g._ask("CHOOSE_TECH", seat, [A_CARD + c for c in bach_from(g, seat)], verb="BACH_FROM")
            return
        t["frm"] = a - A_CARD
        a = None
    if a is None:
        g._ask("UPGRADE_TO", seat, [A_CARD + c for c in bach_to(g, seat, t["frm"])], verb="BACH_TO", frm=t["frm"])
        return
    g._finish(t)
    p = g.p(seat)
    frm, to = t["frm"], a - A_CARD
    E.spend_civil(p, EFFECT[p.leader]["upgrade_civil_actions"])
    g.pay(seat, "mine", g.move_cost(seat, frm, to), "civic")
    p.workers[frm] -= 1
    p.workers[to] = p.workers.get(to, 0) + 1
    g.touch(seat)


def h_rc_stage(g, t: dict, a):
    """A stage of another player's International Red Cross (paid already): the stage's blue token comes from the
    owner's blue bank (a token in play of the owner's choice if empty), 6 culture to the builder, complete?"""
    owner = t["owner"]
    q = g.p(owner)
    if a is not None:                                               # LOSE_BLUE answer of the owner
        c = a - A_CARD
        q.tokens[c] -= 1
        if not q.tokens[c]:
            del q.tokens[c]
        q.unfinished[2] += 1
    elif q.blue_bank > 0:
        q.blue_bank -= 1
        q.unfinished[2] += 1
    elif any(q.tokens.values()):
        g._ask("LOSE_BLUE", owner, [A_CARD + c for c, k in q.tokens.items() if k], purpose="wonder")
        return
    g._finish(t)
    q.unfinished[1] += 1
    effects.fire_card(g, "on_wonder_stage", owner, q.unfinished[0], builder=t["seat"])
    if q.unfinished[1] >= len(STAGE_COSTS[q.unfinished[0]]):
        g.complete_wonder(owner)


for _name, _fn in {"ability": h_ability, "bach": h_bach, "rc_stage": h_rc_stage}.items():
    En.HANDLERS[_name] = _fn
