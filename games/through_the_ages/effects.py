"""Card effects (PLAN.md section 6): one handler per effect `type` of data/card_effects.py, registered per hook.

Hooks (the engine calls `fire(g, hook, first_seat, ...)`; the turn owner's cards first, then other players clockwise;
within a player the card that entered play first):
  passive                 statistics and cost modifiers (economy.compute_stats calls `passive`)
  on_enter_play / on_leave_play, start_of_turn, start_of_politics, start_of_action_phase, on_take_card, on_develop,
  on_prepare_event, on_colonize, on_wonder_stage, on_wonder_complete, on_leader_replaced, end_of_turn, age_start,
  game_end
  play_action / can_play_action   action cards (T5.10): push the tasks the card needs / can it be carried out now
  event                   a revealed event (T8.2): fn(g, revealer, card, eff, players) applies or pushes tasks;
                          `players` limits it to some players (Development of Planning), None = everybody
  colonize                a territory's one-time effect after colonizing (T8.6)
  aggression / war        a successful aggression (T9.2) / a resolved war (T9.5)
  pact                    a pact's lasting effect for one party (economy.compute_stats)
  rank_bonus / tie_priority   card overrides in the T8.3 ranking helper (Nostradamus)
  defend_bonus            strength added when defending against an aggression (Nostradamus)
  take_cost               civil actions added to taking this card from the row (Taj Mahal, Nelson Mandela)
  final_events            game end: evaluate Age III events left in the event decks (T14.2, D8, D19)

Civil card effects (leaders, wonders, special technologies, action cards) are registered by civil.py, which engine.py
imports at its end; `unimplemented_effect_types()` lists effect types without any handler (empty: tested).
"""
from __future__ import annotations

from .cards import (AGE, EFFECT, EFFECT_TYPE, IS_URBAN, KIND, LEVEL, S_COLON, S_CULT, S_FOODB, S_MIL, S_RESB, S_STR,
                    S_UNHAPPY, SPECIALS, STAT_YIELDS, TOKEN_VALUE, UNITS, URBAN)

HOOKS = ("passive", "on_enter_play", "on_leave_play", "start_of_turn", "start_of_politics", "start_of_action_phase",
         "on_take_card", "on_develop", "on_prepare_event", "on_colonize", "on_wonder_stage", "on_wonder_complete",
         "on_leader_replaced", "end_of_turn", "age_start", "game_end", "play_action", "can_play_action",
         "event", "colonize", "aggression", "war", "pact", "army", "rank_bonus", "tie_priority", "defend_bonus",
         "take_cost", "ability", "rules")
# "ability": activated abilities (VERB answers, civil.ABILITIES); "rules": effects that change a rule where the rule
# is applied (engine/politics/military read them by type), registered for the bookkeeping only.
REGISTRY = {h: {} for h in HOOKS}
# passive effects that read the happy faces other cards give, run after all other cards, in this order
# (Darwin after St. Peter's Basilica: with both, temples give their printed faces, NLW p9, D21)
LATE_ORDER = ("steve_jobs", "marlene_dietrich", "st_peters_basilica", "darwin", "michelangelo", "joan_of_arc")


def leader_type(p):
    return EFFECT_TYPE[p.leader] if p.leader is not None else None


def after_armies(g, p, st) -> None:
    """Jan Zizka: each army produces culture (needs the army count, so it runs after army forming)."""
    if leader_type(p) == "zizka":
        k = EFFECT[p.leader]["culture_per_army"] * st.army_count
        st.v[S_CULT] += k
        st.culture_parts[p.leader] = st.culture_parts.get(p.leader, 0) + k


HAND_COLOUR = {"farm": 0, "mine": 0, "lab": 1, "temple": 1, "library": 1, "theater": 1, "arena": 1, "infantry": 2,
               "cavalry": 2, "artillery": 2, "air_force": 2, "special_civil": 3, "special_military": 3,
               "special_colonization": 3, "special_construction": 3, "government": 4, "leader": 5, "action": 6}


def hand_bonus(g, seat: int, kind: str) -> int:
    """Ashoka: production bonus by the number of colours among the civil cards in hand (brown production, grey
    urban, red military, blue special, orange government, green leader, yellow action)."""
    p = g.s.players[seat]
    if leader_type(p) != "ashoka":
        return 0
    n = len({HAND_COLOUR[KIND[c]] for c in p.civil_hand})
    eff = EFFECT[p.leader]
    gain = eff["three_plus_colors"] if n >= 3 else eff["two_colors"] if n == 2 else {}
    return gain.get("food" if kind == "farm" else "resources", 0)


def best_worker_card(p, kinds, ages=None):
    """T11.10 'best X': the highest-level card of these kinds with a worker (optionally only these ages)."""
    best = None
    for c in p.techs:
        if KIND[c] in kinds and p.workers.get(c, 0) and (ages is None or AGE[c] in ages):
            if best is None or LEVEL[c] > LEVEL[best]:
                best = c
    return best


def extra_token_cards(g, p, kind: str) -> list:
    """Farms/mines producing one extra blue token in production: Transcontinental Railroad (best mine), Machu Picchu
    (best Age A/I farm and best Age A/I mine)."""
    out = []
    for w in p.wonders:
        t = EFFECT_TYPE[w]
        if t == "best_mine_extra_token" and kind == "mine":
            c = best_worker_card(p, ("mine",))
            out += [c] * EFFECT[w]["extra_tokens"] if c is not None else []
        elif t == "machu_picchu":
            c = best_worker_card(p, (kind,), EFFECT[w]["ages"])
            out += [c] * EFFECT[w]["extra_tokens"] if c is not None else []
    return out


def handler(hook: str, *types):
    def deco(fn):
        for t in types:
            REGISTRY[hook][t] = fn
        return fn
    return deco


def passive(g, p, card: int, st) -> None:
    fn = REGISTRY["passive"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, p, card, EFFECT[card], st)


def fire(g, hook: str, first_seat: int, **kw) -> None:
    """Run `hook` for every card in play, in the order of PLAN section 6."""
    table = REGISTRY[hook]
    if not table:
        return
    n = g.num_players
    for k in range(n):
        seat = (first_seat + k) % n
        p = g.s.players[seat]
        if p.resigned_order is not None:
            continue
        for c in list(p.play_order):
            fn = table.get(EFFECT_TYPE[c])
            if fn is not None:
                fn(g, seat, c, EFFECT[c], **kw)


def fire_card(g, hook: str, seat: int, card: int, **kw) -> None:
    """Run `hook` for one card (entering/leaving play, a completed wonder, a played action card)."""
    fn = REGISTRY[hook].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, seat, card, EFFECT[card], **kw)


def can_play_action(g, seat: int, card: int) -> bool:
    fn = REGISTRY["can_play_action"].get(EFFECT_TYPE[card])
    return True if fn is None else fn(g, seat, card, action_effect(g, seat, card))


def play_action(g, seat: int, card: int, eff: dict = None) -> None:
    fn = REGISTRY["play_action"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, seat, card, EFFECT[card] if eff is None else eff)


SILK_KEYS = ("gain", "then_gain", "discount", "resources", "military_actions")


def silk_bump(eff: dict) -> dict:
    """Silk Road: each benefit of the action card +1 (food, resources incl. special-purpose ones, science, culture,
    military actions, discounts; benefits 'per other civilization' +1 in total: `bonus_total`)."""
    out = dict(eff)
    for k in SILK_KEYS:
        if isinstance(out.get(k), dict):
            out[k] = {x: v + 1 for x, v in out[k].items()}
        elif isinstance(out.get(k), int):
            out[k] = out[k] + 1
    if "options" in out:
        out["options"] = [{x: v + 1 for x, v in o.items()} for o in out["options"]]
    if "per_player" in out:
        out["bonus_total"] = 1
    return out


def action_effect(g, seat: int, card: int) -> dict:
    """The effect an action card would have if played now (bumped by Silk Road for the first card of the turn)."""
    if not g.p(seat).flags.get("silk_road_used") and g.silk_road_active(seat):
        return silk_bump(EFFECT[card])
    return EFFECT[card]


# ================================================================================================= civil card glue
def replace_refund(g, seat: int, old: int) -> int:
    """Civil actions back when a leader is replaced (T5.6): 1; Eleanor of Aquitaine up to 3; Alfred Nobel none."""
    eff = EFFECT[old] or {}
    if eff.get("no_civil_action_back"):
        return 0
    return eff.get("regain_on_replace", 1)


def political_actions(g, seat: int) -> int:
    """Political actions per Politics Phase: 1; Julius Caesar (rebalanced) 2."""
    p = g.s.players[seat]
    if leader_type(p) == "julius_caesar":
        return EFFECT[p.leader].get("political_actions_per_turn", 1)
    return 1


def extra_draw(g, seat: int) -> int:
    """Sun Tzu: military cards drawn at the end of turn on top of those for unused military actions."""
    p = g.s.players[seat]
    return EFFECT[p.leader]["extra_military_draw"] if leader_type(p) == "sun_tzu" else 0


def excess_discarded(g, seat: int) -> None:
    """Eleanor of Aquitaine: culture per military card discarded at the end of turn for exceeding the hand limit."""
    p = g.s.players[seat]
    if leader_type(p) == "eleanor":
        score(g, seat, EFFECT[p.leader]["culture_per_excess_discard"], p.leader, "leaders")


def nobel_prize(g, seat: int) -> None:
    """Alfred Nobel beside the culture track: a civilization that developed at least 2 technologies this turn scores
    4 culture at the end of the turn (once per turn)."""
    c = g.s.nobel_prize
    if c is not None and g.s.players[seat].flags.get("developed", 0) >= EFFECT[c]["prize_min_developments"]:
        score(g, seat, EFFECT[c]["prize_culture"], c, "leaders")


HIPPOCRATES = next((c for c in range(len(EFFECT_TYPE)) if EFFECT_TYPE[c] == "hippocrates"), None)


def hippocrates_age_end(g, seat: int) -> None:
    """Hippocrates' reminders (they stay after he leaves play): at the end of Age I, II and III, after the age
    change's yellow loss, one of them goes into the yellow bank."""
    p = g.s.players[seat]
    eff = EFFECT[HIPPOCRATES]
    ended = {"II": "I", "III": "II", "IV": "III"}.get(g.s.age)
    if p.reminders > 0 and ended in eff["age_ends"]:
        k = min(p.reminders, eff["yellow_tokens_per_age_end"])
        p.reminders -= k
        g.change_tokens(seat, 0, k)


def gandhi_extra(g, target: int) -> int:
    """Mahatma Gandhi (rebalanced): aggressions and wars against him cost 3 more military actions."""
    p = g.s.players[target]
    return EFFECT[p.leader].get("attack_extra_military_actions", 0) if leader_type(p) == "gandhi" else 0


def cannot_attack(g, seat: int) -> bool:
    p = g.s.players[seat]
    return leader_type(p) == "gandhi" and EFFECT[p.leader]["cannot_attack"]


def himeji(p):
    return next((w for w in p.wonders if EFFECT_TYPE[w] == "himeji_castle"), None)


def himeji_units(g, seat: int, defending: bool) -> list:
    """Himeji Castle: [(unit technology with a worker, strength it adds)] (printed strength, +3 when defending)."""
    p = g.s.players[seat]
    w = himeji(p)
    if w is None:
        return []
    extra = EFFECT[w]["defender_strength"] if defending else 0
    out = []
    for c in p.techs:
        if KIND[c] in UNITS and p.workers.get(c, 0):
            out.append((c, sum(x for k, x in STAT_YIELDS[c] if k == S_STR) + extra))
    return out


def himeji_best(g, seat: int) -> int:
    return max((x for _, x in himeji_units(g, seat, False)), default=0)


def himeji_sacrifice(g, seat: int, unit: int, defending: bool) -> int:
    """The unit adds its strength once more for this fight and is sacrificed (worker to the yellow bank); the
    aggressor scores 3 culture. Returns the strength added."""
    p = g.s.players[seat]
    w = himeji(p)
    add = dict(himeji_units(g, seat, defending))[unit]
    p.workers[unit] -= 1
    p.yellow_bank += 1
    g.touch(seat)
    if not defending:
        score(g, seat, EFFECT[w]["attacker_culture"], w, "wonders")
    g.s.log.add(seat, f"sacrifices a unit from {g.card_name(unit)} (Himeji Castle, +{add})")
    return add


def ability_verbs(g, seat: int, where: str) -> list:
    from . import civil
    return civil.ability_verbs(g, seat, where)


def use_ability(g, seat: int, verb: str) -> None:
    from . import civil
    civil.use_ability(g, seat, verb)


def leader_replaced(g, seat: int, old: int, refunded: int) -> None:
    from . import civil
    civil.leader_replaced(g, seat, old, refunded)


def query(g, hook: str, seat: int, **kw) -> int:
    """Sum of the answers of `hook` handlers on the cards `seat` has in play (0 without handlers)."""
    table = REGISTRY[hook]
    if not table:
        return 0
    out = 0
    for c in g.s.players[seat].play_order:
        fn = table.get(EFFECT_TYPE[c])
        if fn is not None:
            out += fn(g, seat, c, EFFECT[c], **kw)
    return out


def resolve_event(g, revealer: int, card: int, players=None) -> None:
    """T8.2 / T15.10: resolve a revealed event for `players` (None = every player still in the game, clockwise from
    the revealer). A military card that is not an event or territory gives every civilization 1 science."""
    order = players if players is not None else g.active_seats(revealer)
    if KIND[card] not in ("event", "territory"):
        for seat in order:
            g.apply_gain(seat, {"science": 1}, "events", card)
        return
    fn = REGISTRY["event"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, revealer, card, EFFECT[card], order)


def final_events(g) -> None:
    """T14.2: evaluate every Age III event left in the current events deck (top to bottom), then the future events
    deck (top to bottom) (D8); other ages and non-event cards are ignored (D19). The starting player counts as current
    for ties. Every Age III event resolves without decisions."""
    s = g.s
    s.game_end_eval = True
    for c in [e[0] for e in list(s.current_events) + list(s.future_events)]:
        if AGE[c] == "III" and KIND[c] == "event":
            s.log.add(None, f"Final evaluation: {g.card_name(c)}")
            resolve_event(g, s.start_seat, c)
    s.game_end_eval = False


def pact_and_war_passives(g, p, st) -> None:
    """Lasting effects of pacts the player is party to (in any play area, T10.2) and of wars it is in (Hybrid War)."""
    seat = p.seat
    for q in g.s.players:
        if q.pact is not None:
            card, partner, side = q.pact
            if seat == q.seat:
                fn = REGISTRY["pact"].get(EFFECT_TYPE[card])
                if fn is not None:
                    fn(g, p, card, EFFECT[card], st, side, partner)
            elif seat == partner:
                fn = REGISTRY["pact"].get(EFFECT_TYPE[card])
                if fn is not None:
                    fn(g, p, card, EFFECT[card], st, None if side is None else ("B" if side == "A" else "A"), q.seat)
        for card, target in q.wars:
            if (seat == q.seat or seat == target) and EFFECT_TYPE[card] == "hybrid_war":
                st.v[S_UNHAPPY] += EFFECT[card]["unhappy_while_pending"]


# ================================================================================================= passive modifiers
@handler("passive", "construction")
def _construction(g, p, card, eff, st):
    """Masonry / Architecture / Engineering: cheaper urban buildings by age, several wonder stages per action."""
    st.urban_discount = eff["urban_discount_by_age"]
    st.wonder_stages = max(st.wonder_stages, eff["wonder_stages_per_action"])


@handler("passive", "hand_limits")
def _hand_limits(g, p, card, eff, st):
    """Library of Alexandria: civil and military hand limits +1."""
    st.civil_limit_bonus += eff["civil"]
    st.military_limit_bonus += eff["military"]


def build_discount(st, card: int) -> int:
    """Resource discount on building this card (T5.2, T5.4 'after modifiers'): construction technologies for urban
    buildings by age, James Watt (farms/mines), William Shakespeare (theaters/libraries)."""
    d = st.urban_discount.get(AGE[card], 0) if IS_URBAN[card] else 0
    x = st.build_disc.get(KIND[card])
    return d + x.get(AGE[card], 0) if x else d


# ================================================================================================= wonders
@handler("on_wonder_complete", "on_complete_gain")
def _on_complete_gain(g, seat, card, eff):
    g.apply_gain(seat, eff["gain"], "wonders", card)


# ================================================================================================= action cards
@handler("play_action", "gain")
def _gain(g, seat, card, eff):
    g.apply_gain(seat, eff["gain"], "actions", card)


@handler("play_action", "gain_choice")
def _gain_choice(g, seat, card, eff):
    g.s.tasks.append({"op": "choose_gain", "seat": seat, "card": card, "options": eff["options"]})


@handler("can_play_action", "increase_population")
def _can_pop(g, seat, card, eff):
    return g.can_increase_population(seat, free_action=True)


@handler("play_action", "increase_population")
def _pop(g, seat, card, eff):
    g.increase_population(seat, free_action=True)
    g.apply_gain(seat, eff.get("then_gain", {}), "actions", card)


def action_targets(eff) -> tuple:
    out = []
    for t in eff["targets"]:
        out += ["lab", "temple", "library", "theater", "arena"] if t == "urban" else [t]
    return tuple(out)


_targets = action_targets


def gutenberg_card(g, seat: int, kinds: tuple, discount: int) -> tuple:
    """(kinds, discount) of an action card's build/upgrade/develop: when Johannes Gutenberg's action paid for the
    card (engine.play_action_card) only labs/libraries, with his discount added (NLW p8, D30)."""
    p = g.s.players[seat]
    if not p.flags.pop("gutenberg_card", False):
        return kinds, discount
    eff = EFFECT[p.leader]
    return tuple(k for k in kinds if k in eff["extra_civil_action_for"]), discount + eff["discount"]


@handler("can_play_action", "build_or_upgrade")
def _can_build_or_upgrade(g, seat, card, eff):
    kinds = _targets(eff)
    return bool(g.build_options(seat, kinds, eff["discount"], True) or g.upgrade_from_options(seat, kinds,
                                                                                             eff["discount"], True))


@handler("play_action", "build_or_upgrade")
def _build_or_upgrade(g, seat, card, eff):
    kinds, d = gutenberg_card(g, seat, _targets(eff), eff["discount"])
    g.s.tasks.append({"op": "sub_action", "seat": seat, "card": card, "kinds": kinds, "discount": d})


@handler("can_play_action", "upgrade")
def _can_upgrade(g, seat, card, eff):
    return bool(g.upgrade_from_options(seat, _targets(eff), eff["discount"], True))


@handler("play_action", "upgrade")
def _upgrade(g, seat, card, eff):
    kinds, d = gutenberg_card(g, seat, _targets(eff), eff["discount"])
    g.s.tasks.append(g.upgrade_task(seat, kinds, d, True, card))


@handler("can_play_action", "wonder_stage")
def _can_wonder(g, seat, card, eff):
    return g.wonder_max_stages(seat, eff["discount"], True, single=True) > 0


@handler("play_action", "wonder_stage")
def _wonder(g, seat, card, eff):
    """Engineering Genius: exactly one stage, even with a construction technology (D20)."""
    g.s.tasks.append({"op": "wonder", "seat": seat, "discount": eff["discount"], "free": True, "card": card,
                      "single": True})


@handler("play_action", "military_boost")
def _military_boost(g, seat, card, eff):
    """Patriotism: a temporary military action and resources usable only to build or upgrade military units this
    turn (T11.6 temporary actions, T12.9 temporary resources)."""
    p = g.s.players[seat]
    p.temp_military += eff["military_actions"]
    p.temp["unit"] = p.temp.get("unit", 0) + eff["resources"]


@handler("can_play_action", "develop")
def _can_develop(g, seat, card, eff):
    return bool(g.develop_options(seat, free=True, exclude=card))


@handler("play_action", "develop")
def _develop(g, seat, card, eff):
    task = {"op": "develop", "seat": seat, "card": None, "free": True, "then_gain": eff.get("then_gain"),
            "source": card, "revolution_ok": g.s.players[seat].flags.get("all_civil_before_action", False)}
    if g.s.players[seat].flags.get("gutenberg_card"):
        task["only"], task["sci_discount"] = gutenberg_card(g, seat, ("lab", "library"), 0)
    g.s.tasks.append(task)


# ================================================================================================= military helpers
def push(g, *tasks) -> None:
    """Push tasks so that the first one runs first."""
    g.s.tasks.extend(reversed(tasks))


def gain_task(seat: int, gain: dict, card: int, cat: str = "events") -> dict:
    return {"op": "gain", "seat": seat, "gain": gain, "cat": cat, "card": card}


def clockwise(g, first: int, seats) -> list:
    """`seats` in clockwise order from `first` (T8.2: choices go clockwise from the revealing player)."""
    return [x for x in g.active_seats(first) if x in seats]


def food_production(g, seat: int) -> int:
    from . import economy as E
    return E.output(g, seat, "farm")


def mine_production(g, seat: int) -> int:
    """Impact of Industry: mine production only (T15.6), extra tokens on mines included."""
    from . import economy as E
    return E.output(g, seat, "mine", bonuses=False)


def resource_production(g, seat: int) -> int:
    """T15.6: mine production plus all resource production bonuses."""
    from . import economy as E
    return E.output(g, seat, "mine")


def take_points(g, frm: int, to: int, kind: str, amount: int, card: int, cat: str = "military") -> int:
    """T12.3 / T12.4: `frm` loses up to `amount` of science, culture, food or resources; `to` gains what was lost."""
    from . import economy as E
    pf, pt = g.s.players[frm], g.s.players[to]
    if amount <= 0:
        return 0
    if kind == "science":
        lost = -E.add_science(pf, -amount)
        E.add_science(pt, lost)
    elif kind == "culture":
        lost = -E.add_culture(pf, -amount, cat, card)
        E.add_culture(pt, lost, cat, card)
    else:
        k = "farm" if kind == "food" else "mine"
        before = E.total(pf, k)
        E.lose(pf, k, amount)
        lost = min(amount, before - E.total(pf, k))
        lost = E.gain(pt, k, lost)
    return lost


def take_yellow(g, frm: int, to: int, n: int) -> int:
    """T11.9: take yellow tokens from a player's yellow bank (at most what it holds) into your yellow bank."""
    pf, pt = g.s.players[frm], g.s.players[to]
    k = max(0, min(n, pf.yellow_bank))
    pf.yellow_bank -= k
    pf.yellow_owned -= k
    pt.yellow_bank += k
    pt.yellow_owned += k
    return k


def score(g, seat: int, culture: int, card: int, cat: str = "events") -> None:
    from . import economy as E
    E.add_culture(g.s.players[seat], culture, cat, card)


# ================================================================================================= events (T8)
@handler("event", "each_gain")
def _ev_each_gain(g, rev, card, eff, order):
    """Development of Agriculture/Crafts/Politics/Science/Settlement/Trade Routes, Pestilence."""
    push(g, *[gain_task(seat, eff["gain"], card) for seat in order])


@handler("event", "each_produce_choice")
def _ev_markets(g, rev, card, eff, order):
    """Development of Markets: each chooses 2 food or 2 resources."""
    push(g, *[{"op": "gain_option", "seat": seat, "options": eff["options"], "card": card, "cat": "events"}
              for seat in order])


@handler("event", "each_free_build")
def _ev_free_build(g, rev, card, eff, order):
    """Development of Religion / Warfare: each player with an unused worker may build an Age A temple / Warriors."""
    push(g, *[{"op": "free_build", "seat": seat, "kind": eff["kind"], "age": eff["age"], "card": card}
              for seat in order])


@handler("event", "development_of_civilization")
def _ev_dev_civ(g, rev, card, eff, order):
    push(g, *[{"op": "dev_civ", "seat": seat, "discount": eff["discount"], "card": card} for seat in order])


@handler("event", "development_of_planning")
def _ev_planning(g, rev, card, eff, order):
    push(g, {"op": "planning", "seat": rev, "card": card, "order": list(order), "shown": None, "i": 0,
             "n": eff["draw_unused_age_a"]})


@handler("event", "barbarians")
def _ev_barbarians(g, rev, card, eff, order):
    from .military import top, top_two
    most = top(g, "culture_points")
    if most in top_two(g, "strength", "low"):
        push(g, {"op": "lose_pop", "seat": most, "n": eff["population_loss"], "card": card})


@handler("event", "border_conflict")
def _ev_border_conflict(g, rev, card, eff, order):
    from .military import top
    weak, strong = top(g, "strength", "low"), top(g, "strength")
    push(g, {"op": "destroy_bld", "owner": weak, "chooser": weak, "kinds": ("farm", "mine") + URBAN, "slots": [9],
             "card": card, "decision": "LOSE_WORKER", "raid": False, "costs": []},
         gain_task(strong, eff["strongest_gain"], card))


@handler("event", "strongest_weakest")
def _ev_strongest_weakest(g, rev, card, eff, order):
    """Crusades, Reign of Terror, Independence Declaration, Refugees."""
    from .military import top
    strong, weak = top(g, "strength"), top(g, "strength", "low")
    tasks = []
    if eff.get("strongest"):
        tasks.append(gain_task(strong, eff["strongest"], card))
    if eff.get("weakest"):
        tasks.append(gain_task(weak, eff["weakest"], card))
    if eff.get("weakest_loses_colony") and g.s.players[weak].colonies:
        tasks.append({"op": "pick", "what": "lose_colony", "seat": weak, "victim": weak, "card": card})
    push(g, *tasks)


@handler("event", "each_score_own_rating")
def _ev_own_rating(g, rev, card, eff, order):
    """Cultural Influence (culture = culture rating), Scientific Breakthrough (science = science rating)."""
    from . import economy as E
    for seat in order:
        st = E.stats(g, seat)
        if eff["rating"] == "culture":
            score(g, seat, st.culture, card)
        else:
            E.add_science(g.s.players[seat], st.science)


@handler("event", "each_score_other_rating")
def _ev_other_rating(g, rev, card, eff, order):
    """Popularization of Science: culture = science rating."""
    from . import economy as E
    for seat in order:
        score(g, seat, E.stats(g, seat).science, card)


@handler("event", "top_two_gain_mix")
def _ev_top_two_mix(g, rev, card, eff, order):
    """Foray (two strongest gain 3 food/resources in any mix), Raiders (two weakest lose 2 in any mix)."""
    from .military import top_two
    n = eff["food_or_resources"]
    sel = top_two(g, "strength", "high" if eff["strongest"] else "low")
    push(g, *[{"op": "mix", "seat": seat, "victim": seat, "n": abs(n), "mode": "gain" if n > 0 else "lose",
               "stop_ok": False, "card": card, "cat": "events"} for seat in clockwise(g, rev, sel)])


@handler("event", "each_produce")
def _ev_each_produce(g, rev, card, eff, order):
    """Good Harvest (food), New Deposits (resources), Economic Progress (corruption, food, consumption, resources);
    production bonuses count (T15.6)."""
    from . import economy as E
    for seat in order:
        p = g.s.players[seat]
        for step in eff["steps"]:
            if step == "food":
                E.produce_step(g, seat, "farm")
            elif step == "resources":
                E.produce_step(g, seat, "mine")
            elif step == "corruption":
                missing = E.lose(p, "mine", E.corruption(p.blue_bank))
                if missing:
                    E.lose(p, "farm", missing)
            elif step == "consumption":
                missing = E.lose(p, "farm", E.consumption(p.yellow_bank))
                if missing:
                    E.add_culture(p, -4 * missing, "famine")


@handler("event", "most_happy_gain")
def _ev_immigration(g, rev, card, eff, order):
    from .military import all_with_most
    push(g, *[gain_task(seat, eff["gain"], card) for seat in all_with_most(g, "happiness")])


@handler("event", "each_lose_all_food")
def _ev_rats(g, rev, card, eff, order):
    from . import economy as E
    for seat in order:
        p = g.s.players[seat]
        E.lose(p, "farm", E.food(p))


@handler("event", "rebellion")
def _ev_rebellion(g, rev, card, eff, order):
    """Each civilization spends 2 civil actions (without effect) per discontent worker."""
    from . import economy as E
    for seat in order:
        k = min(eff["civil_actions_per_discontent"] * E.discontent(g, seat), E.civil_available(g, seat))
        E.spend_civil(g.s.players[seat], k)


@handler("event", "uncertain_borders")
def _ev_uncertain_borders(g, rev, card, eff, order):
    from .military import top
    strong, weak = top(g, "strength"), top(g, "strength", "low")
    if strong != weak:
        take_yellow(g, weak, strong, eff["yellow_tokens"])


@handler("event", "civil_unrest")
def _ev_civil_unrest(g, rev, card, eff, order):
    from . import economy as E
    disc = {seat: E.discontent(g, seat) for seat in order}
    if not any(disc.values()):
        return
    most = max(disc.values())
    tasks = []
    for seat in order:
        score(g, seat, -eff["culture_lost_per_discontent"] * disc[seat], card)
        if disc[seat] == most:
            tasks.append({"op": "call", "fn": "tokens",
                          "kw": {"seat": seat, "blue": -eff["most_discontent_blue_tokens_lost"], "yellow": 0}})
    push(g, *tasks)


@handler("event", "top_two_gain")
def _ev_top_two_gain(g, rev, card, eff, order):
    """Cold War (two strongest score 6 science), Crime Wave (two weakest lose 3 culture and 1 blue token)."""
    from .military import top_two
    sel = clockwise(g, rev, top_two(g, "strength", "high" if eff["strongest"] else "low"))
    tasks = []
    for seat in sel:
        tasks.append(gain_task(seat, eff["gain"], card))
        if eff.get("blue_tokens_lost"):
            tasks.append({"op": "call", "fn": "tokens",
                          "kw": {"seat": seat, "blue": -eff["blue_tokens_lost"], "yellow": 0}})
    push(g, *tasks)


@handler("event", "emigration")
def _ev_emigration(g, rev, card, eff, order):
    """Each civilization loses half its discontent workers, rounded up."""
    from . import economy as E
    push(g, *[{"op": "lose_pop", "seat": seat, "n": (E.discontent(g, seat) + 1) // 2, "card": card}
              for seat in order if E.discontent(g, seat)])


@handler("event", "iconoclasm")
def _ev_iconoclasm(g, rev, card, eff, order):
    for seat in order:
        p = g.s.players[seat]
        if p.leader is not None and AGE[p.leader] != g.s.age:
            g.remove_leader(seat)


@handler("event", "international_agreement")
def _ev_international_agreement(g, rev, card, eff, order):
    from .military import top
    push(g, {"op": "take_loop", "seat": top(g, "strength"), "budget": eff["civil_actions"], "taken": 0,
             "card": card})


@handler("event", "food_per_happy")
def _ev_prosperity(g, rev, card, eff, order):
    from . import economy as E
    for seat in order:
        E.gain(g.s.players[seat], "farm", min(eff["max_happy"], E.stats(g, seat).happiness))


@handler("event", "most_culture_points_gain")
def _ev_national_pride(g, rev, card, eff, order):
    from .military import top
    g.apply_gain(top(g, "culture_points"), eff["gain"], "events", card)


@handler("event", "ravages_of_time")
def _ev_ravages(g, rev, card, eff, order):
    push(g, *[{"op": "pick", "what": "ravage", "seat": seat, "victim": seat, "card": card} for seat in order
              if any(AGE[w] in eff["ages"] for w in g.s.players[seat].wonders)])


@handler("event", "politics_of_strength")
def _ev_politics_of_strength(g, rev, card, eff, order):
    """Strongest draws 5 military cards, weakest discards 3; in Age IV culture is scored (+5) and lost (-3)."""
    from .military import draw, top
    strong, weak = top(g, "strength"), top(g, "strength", "low")
    if g.s.age == "IV":
        score(g, strong, eff["strongest_cards"], card)
        score(g, weak, -eff["weakest_discard"], card)
        return
    draw(g, strong, eff["strongest_cards"])
    push(g, {"op": "discard_n", "seat": weak, "n": eff["weakest_discard"], "card": card})


@handler("event", "terrorism")
def _ev_terrorism(g, rev, card, eff, order):
    """The civilization with the fewest culture points destroys 1 urban building of each other civilization."""
    from .military import top
    least = top(g, "culture_points", "low")
    push(g, *[{"op": "destroy_bld", "owner": v, "chooser": least, "kinds": URBAN, "slots": [9], "card": card,
               "decision": "TERRORISM", "raid": False, "costs": []} for v in order if v != least])


@handler("event", "call_to_arms")
def _ev_call_to_arms(g, rev, card, eff, order):
    """Weakest loses 2 civil actions (this turn) and draws 2 military cards, second weakest 1 and 1; 2 players: the
    weaker 2 and 2. Cards only for actions actually lost; none in Age IV."""
    from . import economy as E
    from .military import draw, rank_players
    weak = rank_players(g, "strength", "low")
    plan = [(weak[0], eff["weakest_lose_civil_draw_military"])]
    if len(weak) >= 3:
        plan.append((weak[1], eff["second_weakest_lose_civil_draw_military"]))
    for seat, n in plan:
        lost = min(n, E.civil_available(g, seat))
        E.spend_civil(g.s.players[seat], lost)
        draw(g, seat, lost)


@handler("event", "dark_ages")
def _ev_dark_ages(g, rev, card, eff, order):
    from . import economy as E
    k = eff["lose_half_rounded_up_of_science_above"]
    for seat in order:
        p = g.s.players[seat]
        if p.science > k:
            E.add_science(p, -((p.science - k + 1) // 2))


@handler("event", "knowledge_of_the_ancestors")
def _ev_knowledge(g, rev, card, eff, order):
    """1 science per completed wonder, 1 resource per unfinished wonder; Age A wonders count double."""
    for seat in order:
        p = g.s.players[seat]
        sci = sum(eff["age_a_counts"] if AGE[w] == "A" else 1 for w in p.wonders + p.ruined)
        res = 0
        if p.unfinished is not None:
            res = eff["age_a_counts"] if AGE[p.unfinished[0]] == "A" else 1
        g.apply_gain(seat, {"science": sci * eff["per_completed_wonder"]["science"],
                            "resources": res * eff["per_unfinished_wonder"]["resources"]}, "events", card)


@handler("event", "arms_industry")
def _ev_arms_industry(g, rev, card, eff, order):
    """For infantry, cavalry, artillery: 2 resources to every player whose highest technology of that type in play
    (units not needed) is the highest or tied; a player without such a technology gets nothing for it. Gained at
    once."""
    total = {seat: 0 for seat in order}
    for kind in eff["kinds"]:
        lv = {seat: max([LEVEL[c] for c in g.s.players[seat].techs if KIND[c] == kind], default=None)
              for seat in order}
        have = [x for x in lv.values() if x is not None]
        if not have:
            continue
        for seat, x in lv.items():
            if x == max(have):
                total[seat] += eff["resources_per_type"]
    for seat in order:
        if total[seat]:
            g.apply_gain(seat, {"resources": total[seat]}, "events", card)


@handler("event", "freedom_of_movement")
def _ev_freedom_of_movement(g, rev, card, eff, order):
    push(g, *[{"op": "move_worker", "seat": seat, "frm": None, "card": card} for seat in order])


@handler("event", "international_negotiations")
def _ev_negotiations(g, rev, card, eff, order):
    from .military import top
    strong, weak = top(g, "strength"), top(g, "strength", "low")
    if strong != weak:
        push(g, {"op": "negotiate", "seat": rev, "strong": strong, "weak": weak, "amount": eff["amount"],
                 "options": eff["options"], "card": card})


# ------------------------------------------------------------------------------------- Age III events (no decisions)
def _culture_each(g, order, card, fn) -> None:
    for seat in order:
        score(g, seat, fn(seat), card)


@handler("event", "impact_of_balance")
def _ev_balance(g, rev, card, eff, order):
    from . import economy as E
    _culture_each(g, order, card, lambda s: eff["multiplier"] * min(
        E.stats(g, s).science, E.stats(g, s).culture, food_production(g, s), resource_production(g, s)))


@handler("event", "impact_of_variety")
def _ev_variety(g, rev, card, eff, order):
    """2 culture per unit type and urban building type with at least one worker, and per special technology."""
    def n(seat):
        p = g.s.players[seat]
        kinds = {KIND[c] for c, k in p.workers.items() if k and KIND[c] not in ("farm", "mine")}
        return eff["culture_per_type"] * (len(kinds) + len(p.specials))
    _culture_each(g, order, card, n)


@handler("event", "impact_of_agriculture")
def _ev_agriculture(g, rev, card, eff, order):
    from . import economy as E

    def n(seat):
        f = food_production(g, seat)
        return f + (eff["bonus_if_above_consumption"] if f > E.consumption(g.s.players[seat].yellow_bank) else 0)
    _culture_each(g, order, card, n)


def _of_kinds(of) -> tuple:
    out = []
    for t in of:
        out += list(URBAN) if t == "urban" else list(SPECIALS) if t == "special" else [t]
    return tuple(out)


@handler("event", "culture_per_level")
def _ev_per_level(g, rev, card, eff, order):
    """Impact of Architecture (urban buildings), Competition (units and arenas): per level of each building/unit;
    Impact of Progress: per level of the government and each special technology."""
    kinds = _of_kinds(eff["of"])

    def n(seat):
        p = g.s.players[seat]
        lv = sum(LEVEL[c] * k for c, k in p.workers.items() if KIND[c] in kinds)
        if "government" in kinds:
            lv += LEVEL[p.government]
        lv += sum(LEVEL[c] for c in p.specials.values() if KIND[c] in kinds)
        return eff["per_level"] * lv
    _culture_each(g, order, card, n)


@handler("event", "culture_per_count")
def _ev_per_count(g, rev, card, eff, order):
    """Impact of Colonies (3 per colony), Impact of Technology (4 per Age III technology in play)."""
    def n(seat):
        p = g.s.players[seat]
        if eff["of"] == "colony":
            return eff["per"] * len(p.colonies)
        cards = list(p.techs) + list(p.specials.values()) + [p.government]
        return eff["per"] * sum(1 for c in cards if AGE[c] == "III")
    _culture_each(g, order, card, n)


@handler("event", "impact_of_government")
def _ev_government(g, rev, card, eff, order):
    from . import economy as E
    _culture_each(g, order, card, lambda s: eff["per_civil_action"] * E.stats(g, s).civil
                  + eff["per_military_action"] * E.stats(g, s).military)


@handler("event", "impact_of_happiness")
def _ev_happiness(g, rev, card, eff, order):
    from . import economy as E
    _culture_each(g, order, card, lambda s: eff["per_happy"] * min(eff["max_happy"], E.stats(g, s).happiness)
                  + eff["per_discontent"] * E.discontent(g, s))


@handler("event", "impact_of_industry")
def _ev_industry(g, rev, card, eff, order):
    _culture_each(g, order, card, lambda s: mine_production(g, s))


@handler("event", "impact_of_population")
def _ev_population(g, rev, card, eff, order):
    from . import economy as E
    _culture_each(g, order, card, lambda s: eff["culture_per_content_worker_above"] * max(
        0, g.workers_total(s) - E.discontent(g, s) - eff["threshold"]))


@handler("event", "ranked_culture")
def _ev_ranked(g, rev, card, eff, order):
    """Impact of Science / Strength / Culture: culture by rank (ties by T8.3, no sharing)."""
    from .military import rank_players
    ranked = rank_players(g, eff["by"], "high")
    table = eff["table"][str(max(2, len(ranked)))]
    for i, seat in enumerate(ranked):
        if seat in order and i < len(table):
            score(g, seat, table[i], card)


@handler("event", "culture_per_wonder_age")
def _ev_wonders(g, rev, card, eff, order):
    _culture_each(g, order, card, lambda s: sum(eff["by_age"][AGE[w]] for w in g.s.players[s].wonders
                                                + g.s.players[s].ruined))


@handler("event", "impact_of_harmony")
def _ev_harmony(g, rev, card, eff, order):
    """4 culture per worker in whichever group holds the fewest workers: units; farms and mines; urban buildings."""
    def n(seat):
        p = g.s.players[seat]
        groups = [0, 0, 0]
        for c, k in p.workers.items():
            kind = KIND[c]
            groups[0 if kind in ("infantry", "cavalry", "artillery", "air_force") else 1 if kind in ("farm", "mine")
                   else 2] += k
        return eff["culture_per_worker"] * min(groups)
    _culture_each(g, order, card, n)


# ------------------------------------------------------------------------------------- territories (T8.4-T8.7)
@handler("event", "territory", "territory_choice")
def _ev_territory(g, rev, card, eff, order):
    push(g, {"op": "auction", "card": card, "order": g.active_seats(rev), "in": g.active_seats(rev), "bid": 0,
             "leader": None, "pos": 0})


@handler("colonize", "territory")
def _col_territory(g, seat, card, eff):
    push(g, gain_task(seat, eff["once"], card, "colonies"))


@handler("colonize", "territory_choice")
def _col_territory_choice(g, seat, card, eff):
    push(g, {"op": "gain_option", "seat": seat, "options": eff["once_options"], "card": card, "cat": "colonies"})


# ================================================================================================= aggressions (T9.2)
@handler("aggression", "aggression_trade")
def _ag_enslave(g, att, card, eff, target):
    push(g, gain_task(target, eff["rival"], card, "military"), gain_task(att, eff["aggressor"], card, "military"))


@handler("aggression", "plunder")
def _ag_plunder(g, att, card, eff, target):
    push(g, {"op": "mix", "seat": att, "victim": target, "n": eff["amount"], "mode": "take", "stop_ok": True,
             "card": card, "cat": "military"})


AGE_LEVEL = {"A": 0, "I": 1, "II": 2, "III": 3}


@handler("aggression", "raid")
def _ag_raid(g, att, card, eff, target):
    """Destroy urban buildings (one per listed age or older, the aggressor chooses); the aggressor gains resources
    equal to their printed costs divided by `aggressor_gains_cost_divisor`, rounded up."""
    push(g, {"op": "destroy_bld", "owner": target, "chooser": att, "kinds": URBAN,
             "slots": [AGE_LEVEL[a] for a in eff["destroy_urban_max_ages"]], "card": card, "decision": "LOSE_WORKER",
             "raid": True, "costs": []})


@handler("aggression", "annex")
def _ag_annex(g, att, card, eff, target):
    if g.s.players[target].colonies:
        push(g, {"op": "pick", "what": "annex", "seat": att, "victim": target, "card": card})


@handler("aggression", "infiltrate")
def _ag_infiltrate(g, att, card, eff, target):
    q = g.s.players[target]
    if q.leader is not None or q.unfinished is not None:
        push(g, {"op": "pick", "what": "infiltrate", "seat": att, "victim": target, "card": card,
                 "per_level": eff["culture_per_level"]})


@handler("aggression", "steal")
def _ag_steal(g, att, card, eff, target):
    """Spy (science), Armed Intervention (culture)."""
    take_points(g, target, att, eff["what"], eff["amount"], card)


@handler("aggression", "kidnap")
def _ag_kidnap(g, att, card, eff, target):
    push(g, {"op": "kidnap", "seat": att, "victim": target, "card": card})


@handler("aggression", "steal_bundle")
def _ag_occupy(g, att, card, eff, target):
    for kind in ("resources", "science", "food", "culture"):
        take_points(g, target, att, kind, eff["amounts"][kind], card)


# ================================================================================================= wars (T9.5, T9.6)
@handler("war", "war_over_technology")
def _war_technology(g, declarer, card, eff, victor, loser, adv):
    push(g, {"op": "steal_tech", "seat": victor, "victim": loser, "left": adv, "card": card})


@handler("war", "war_over_territory")
def _war_territory(g, declarer, card, eff, victor, loser, adv):
    take_yellow(g, loser, victor, eff["base"] + adv // eff["extra_per_full_advantage_of"])


@handler("war", "war_over_culture")
def _war_culture(g, declarer, card, eff, victor, loser, adv):
    take_points(g, loser, victor, "culture", eff["base"] + adv, card)


@handler("war", "hybrid_war")
def _war_hybrid(g, declarer, card, eff, victor, loser, adv):
    take_points(g, loser, victor, "culture", adv, card)


# ================================================================================================= pacts (T10)
PACT_STAT = {"military_actions": S_MIL, "strength": S_STR, "culture": S_CULT, "resource_production": S_RESB,
             "food_production": S_FOODB, "colonization": S_COLON}


def _pact_yields(p, card, ylds, st) -> None:
    for k, x in ylds.items():
        i = PACT_STAT.get(k)
        if i is None:
            continue                                     # blue_tokens: entering/leaving play (T11.9)
        st.v[i] += x
        if i == S_CULT:
            st.culture_parts[card] = st.culture_parts.get(card, 0) + x


@handler("pact", "pact_symmetric")
def _pact_symmetric(g, p, card, eff, st, side, other):
    """Open Borders Agreement, Military Pact, Peace Treaty: the same lasting effect for both parties."""
    _pact_yields(p, card, eff["both"], st)


@handler("pact", "pact_ab")
def _pact_ab(g, p, card, eff, st, side, other):
    """Acceptance of Supremacy, International Trade Agreement, Promise of Military Protection, Loss of Sovereignty,
    Naval Trade Agreement: side A / side B effects."""
    _pact_yields(p, card, eff["a" if side == "A" else "b"], st)


@handler("pact", "pact_international_tourism")
def _pact_tourism(g, p, card, eff, st, side, other):
    q = g.s.players[other]
    k = eff["culture_per_partner_wonder"] * (len(q.wonders) + len(q.ruined))       # ruins count (D28)
    st.v[S_CULT] += k
    st.culture_parts[card] = st.culture_parts.get(card, 0) + k


@handler("pact", "pact_trade_routes", "pact_scientific_cooperation")
def _pact_rules(g, p, card, eff, st, side, other):
    """No statistic: Trade Routes acts in payment (engine.pay), Scientific Cooperation in developing."""
    return None


def pact_tokens(card: int, side) -> int:
    """Blue token symbols of a pact side (Naval Trade Agreement), applied when the pact enters / leaves play."""
    from .military import pact_side_yields
    return pact_side_yields(card, side).get("blue_tokens", 0)


# ================================================================================================= tactics and units
@handler("army", "hussars")
def _army_hussars(g, *a, **kw):
    """Hussars: army strength 2 + level of its lower cavalry (military.army_strength)."""
    return 0


@handler("passive", "air_force")
def _air_force(g, p, card, eff, st):
    """Air Forces: one per army doubles its tactical strength (military.army_strength)."""
    return None


# ================================================================================================= bookkeeping
ALL_EFFECT_TYPES = sorted({t for t in EFFECT_TYPE if t is not None})


def unimplemented_effect_types() -> list:
    """Effect types of cards.json with no handler in any hook (civil.py registers when engine.py is imported)."""
    done = {t for table in REGISTRY.values() for t in table}
    return [t for t in ALL_EFFECT_TYPES if t not in done]
