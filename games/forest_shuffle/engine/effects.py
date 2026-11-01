"""Effects, bonuses, permanent triggers and the decision option builders."""
from __future__ import annotations

from ..core.actions import Action, ActionKind
from ..core.enums import HAND_LIMIT
from ..core.state import Decision
from .filters import card_matches, count_cards


def half_matches(game, half, flt: dict) -> bool:
    return card_matches(game.db, game.db.half_types(half), half.species, "DWELLER", flt)


# ---------------------------------------------------------------------- effects
def apply_effect(game, seat: int, effect: dict, source: dict) -> None:
    s = game.state
    p = s.players[seat]
    t = effect["type"]
    if t == "draw":
        game.draw_to_hand(seat, effect["count"])
    elif t == "draw_per":
        game.draw_to_hand(seat, count_cards(game.db, p.forest, effect["filter"], False))
    elif t == "place_free":
        s.decisions.append(Decision("PLACE_FREE", {"filter": effect["filter"], "remaining": effect["count"],
                                                   "source_idx": source.get("idx"), "source": source}))
    elif t == "extra_turn":
        c = effect.get("condition")
        if c is None or count_cards(game.db, p.forest, c["filter"], True) >= c["count"]:
            s.extra_turns += 1
    elif t == "take_from_clearing":
        flt = effect.get("filter", {})
        if effect["count"] == "all":
            for c in [c for c in s.clearing if game.hand_card_matches(c, flt)]:
                if len(p.hand) >= HAND_LIMIT:
                    break
                s.clearing.remove(c)
                p.hand.append(c)
                p.known.add(c.uid)
        else:
            s.decisions.append(Decision("CHOOSE_CLEARING_CARD", {"remaining": effect["count"], "filter": flt,
                                                                 "dest": "HAND", "source": source}))
    elif t == "clearing_to_cave":
        flt = effect.get("filter", {})
        if effect["count"] == "all":
            for c in [c for c in s.clearing if game.hand_card_matches(c, flt)]:
                s.clearing.remove(c)
                p.cave.append(c)
        else:
            s.decisions.append(Decision("CHOOSE_CLEARING_CARD", {"remaining": effect["count"], "filter": flt,
                                                                 "dest": "CAVE", "source": source}))
    elif t == "hand_to_cave_draw_equal":
        s.decisions.append(Decision("CHOOSE_HAND_CARD", {"chosen": 0, "source": source}))
    elif t == "remove_clearing":
        s.removed.extend(s.clearing)
        s.clearing.clear()
    elif t == "play_cards":
        s.decisions.append(Decision("PLAY_MORE", {"source": source}))
    elif t == "play_saplings":
        s.decisions.append(Decision("SAPLING_MORE", {"source": source}))
    elif t == "sequence":
        for i, step in reversed(list(enumerate(effect["steps"]))):
            s.decisions.append(Decision("USE_OR_SKIP", {"effect": step, "source": source,
                                                        "label": f"{source.get('label', '')} step {i + 1}"}))
    else:
        raise ValueError(f"unknown effect type {t}")


# ---------------------------------------------------------------------- triggers
def _trigger_matches(trigger: dict, placed_types, position, host, is_tree_play) -> bool:
    flt = trigger.get("filter", {})
    if "types" in flt:
        return any(t in placed_types for t in flt["types"])
    if "kinds" in flt:
        return is_tree_play and "TREE" in flt["kinds"]
    if "slot" in flt:
        return position == flt["slot"] and host.kind in flt.get("host_kinds", ["TREE", "SHRUB"])
    return False


def matching_triggers(game, seat, placed_types, position, host, is_tree_play, allow_idx=None) -> list:
    s = game.state
    out = []
    for idx, w in enumerate(s.players[seat].forest):
        if w.species:
            sp = game.db.species[w.species]
            eff = sp.effect
            if eff and eff["type"] == "permanent" and (w.placed_turn < s.turn_index or idx == allow_idx):
                if _trigger_matches(eff["trigger"], placed_types, position, host, is_tree_play):
                    out.append((eff["action"], f"{sp.label} trigger"))
        for d in w.dwellers():
            sp = game.db.species[d.species]
            eff = sp.effect
            if eff and eff["type"] == "permanent" and d.placed_turn < s.turn_index:
                if _trigger_matches(eff["trigger"], placed_types, position, host, is_tree_play):
                    out.append((eff["action"], f"{sp.label} trigger"))
    return out


# ---------------------------------------------------------------------- decisions
def decision_options(game, d: Decision) -> list:
    s = game.state
    p = s.players[s.current]
    k = d.kind
    if k == "DRAW":
        return game._draw_actions()
    if k == "PAY":
        return game.pay_options(d)
    if k == "USE_OR_SKIP":
        return [Action(ActionKind.USE), Action(ActionKind.SKIP)]
    if k == "CHOOSE_CLEARING_CARD":
        if d.data["dest"] == "HAND" and len(p.hand) >= HAND_LIMIT:
            return []
        defs = sorted({c.def_id for c in s.clearing if game.hand_card_matches(c, d.data["filter"])})
        return [Action(ActionKind.CHOOSE_CARD, card=x) for x in defs]
    if k == "CHOOSE_HAND_CARD":
        return [Action(ActionKind.CHOOSE_CARD, card=x) for x in sorted({c.def_id for c in p.hand})] + [Action(ActionKind.DONE)]
    if k == "PLACE_FREE":
        return game.free_place_actions(d.data["filter"]) + [Action(ActionKind.DONE)]
    if k == "PLAY_MORE":
        return game._play_actions() + [Action(ActionKind.DONE)]
    if k == "SAPLING_MORE":
        return game.sapling_actions() + [Action(ActionKind.DONE)]
    if k == "CHOOSE_TARGET":
        return [Action(ActionKind.CHOOSE_TARGET, target=t) for t in d.data["targets"]]
    raise ValueError(k)


def finish_hand_to_cave(game, d: Decision) -> None:
    game.draw_to_hand(game.state.current, d.data["chosen"])


def handle_decision(game, d: Decision, action: Action) -> None:
    s = game.state
    p = s.players[s.current]
    k = d.kind
    if k == "USE_OR_SKIP":
        s.decisions.pop()
        if action.kind == ActionKind.USE:
            apply_effect(game, s.current, d.data["effect"], d.data.get("source", {}))
    elif k == "CHOOSE_CLEARING_CARD":
        card = game.take_from_clearing(action.card)
        if d.data["dest"] == "HAND":
            p.hand.append(card)
            p.known.add(card.uid)
        else:
            p.cave.append(card)
        d.data["remaining"] -= 1
        if d.data["remaining"] <= 0:
            s.decisions.pop()
    elif k == "CHOOSE_HAND_CARD":
        if action.kind == ActionKind.DONE:
            s.decisions.pop()
            finish_hand_to_cave(game, d)
        else:
            card = next(c for c in p.hand if c.def_id == action.card)
            p.hand.remove(card)
            p.cave.append(card)
            d.data["chosen"] += 1
    elif k == "PLACE_FREE":
        if action.kind == ActionKind.DONE:
            s.decisions.pop()
            return
        if d.data["remaining"] != "any":
            d.data["remaining"] -= 1
            if d.data["remaining"] <= 0:
                s.decisions.pop()
        game._start_play(action, free=True, source_idx=d.data.get("source_idx"))
    elif k == "CHOOSE_TARGET":
        s.decisions.pop()
        game._start_play(Action(ActionKind.PLAY_HALF, card=d.data["card"], half=d.data["half"], target=action.target),
                         free=d.data["free"], source_idx=d.data["source_idx"])
    elif k in ("PLAY_MORE", "SAPLING_MORE"):
        if action.kind == ActionKind.DONE:
            s.decisions.pop()
        else:
            game._start_play(action)
    else:
        raise ValueError(k)
