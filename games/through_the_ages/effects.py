"""Card effects (PLAN.md section 6): one handler per effect `type` of data/card_effects.py, registered per hook.

Hooks (the engine calls `fire(g, hook, first_seat, ...)`; the turn owner's cards first, then other players clockwise;
within a player the card that entered play first):
  passive                 statistics and cost modifiers (economy.compute_stats calls `passive`)
  on_enter_play / on_leave_play, start_of_turn, start_of_politics, start_of_action_phase, on_take_card, on_develop,
  on_prepare_event, on_colonize, on_wonder_stage, on_wonder_complete, on_leader_replaced, end_of_turn, age_start,
  game_end
  play_action / can_play_action   action cards (T5.10): push the tasks the card needs / can it be carried out now
  final_events            game end: evaluate Age III events left in the event decks (T14.2; stage 2)

A card whose effect type has no handler simply has no effect yet; it is still takeable and playable (T4, T5).
`UNIMPLEMENTED_EFFECT_TYPES` lists those types for the next build stages.
"""
from __future__ import annotations

from .cards import AGE, EFFECT, EFFECT_TYPE, IS_URBAN

HOOKS = ("passive", "on_enter_play", "on_leave_play", "start_of_turn", "start_of_politics", "start_of_action_phase",
         "on_take_card", "on_develop", "on_prepare_event", "on_colonize", "on_wonder_stage", "on_wonder_complete",
         "on_leader_replaced", "end_of_turn", "age_start", "game_end", "play_action", "can_play_action")
REGISTRY = {h: {} for h in HOOKS}


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
    return True if fn is None else fn(g, seat, card, EFFECT[card])


def play_action(g, seat: int, card: int) -> None:
    fn = REGISTRY["play_action"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, seat, card, EFFECT[card])


def final_events(g) -> None:
    """T14.2: evaluate every Age III event left in the current and future events decks (D8 order). Event effects
    come in stage 2; nothing to do until then."""
    return None


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


def urban_discount(st, card: int) -> int:
    return st.urban_discount.get(AGE[card], 0) if IS_URBAN[card] else 0


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


def _targets(eff) -> tuple:
    out = []
    for t in eff["targets"]:
        out += ["lab", "temple", "library", "theater", "arena"] if t == "urban" else [t]
    return tuple(out)


@handler("can_play_action", "build_or_upgrade")
def _can_build_or_upgrade(g, seat, card, eff):
    kinds = _targets(eff)
    return bool(g.build_options(seat, kinds, eff["discount"], True) or g.upgrade_from_options(seat, kinds,
                                                                                             eff["discount"], True))


@handler("play_action", "build_or_upgrade")
def _build_or_upgrade(g, seat, card, eff):
    g.s.tasks.append({"op": "sub_action", "seat": seat, "card": card, "kinds": _targets(eff),
                      "discount": eff["discount"]})


@handler("can_play_action", "upgrade")
def _can_upgrade(g, seat, card, eff):
    return bool(g.upgrade_from_options(seat, _targets(eff), eff["discount"], True))


@handler("play_action", "upgrade")
def _upgrade(g, seat, card, eff):
    g.s.tasks.append(g.upgrade_task(seat, _targets(eff), eff["discount"], True, card))


@handler("can_play_action", "wonder_stage")
def _can_wonder(g, seat, card, eff):
    return g.wonder_max_stages(seat, eff["discount"], True) > 0


@handler("play_action", "wonder_stage")
def _wonder(g, seat, card, eff):
    g.s.tasks.append({"op": "wonder", "seat": seat, "discount": eff["discount"], "free": True, "card": card})


@handler("can_play_action", "develop")
def _can_develop(g, seat, card, eff):
    return bool(g.develop_options(seat, free=True, exclude=card))


@handler("play_action", "develop")
def _develop(g, seat, card, eff):
    g.s.tasks.append({"op": "develop", "seat": seat, "card": None, "free": True, "then_gain": eff.get("then_gain"),
                      "source": card, "revolution_ok": g.s.players[seat].flags.get("all_civil_before_action", False)})


# ================================================================================================= bookkeeping
ALL_EFFECT_TYPES = sorted({t for t in EFFECT_TYPE if t is not None})
IMPLEMENTED_EFFECT_TYPES = sorted({t for table in REGISTRY.values() for t in table} & set(ALL_EFFECT_TYPES))
UNIMPLEMENTED_EFFECT_TYPES = [t for t in ALL_EFFECT_TYPES if t not in IMPLEMENTED_EFFECT_TYPES]
