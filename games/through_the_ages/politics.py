"""Politics phase and military decisions as tasks (PLAN.md sections 3-5): political actions (T7), events and
colonization (T8), aggressions and wars (T9), pacts (T10), resignation (T7.2), and the decisions card effects need
(BID, SEND, DEFEND, MIX, EVENT_CHOICE, LOSE_WORKER, TERRORISM, STEAL_TECH, KIDNAP, INFILTRATE, ANNEX, TAKE_LOOP ...).

Handlers follow engine.py: handler(game, task, answer); answer None = make progress (ask, push, finish).
Registered into engine.HANDLERS at import (engine imports this module at its end).
"""
from __future__ import annotations

from . import economy as E
from . import effects
from . import military as M
from .cards import (AGE, BONUS, BUILDINGS, EFFECT, EFFECT_TYPE, IS_TECH, KEY, KIND, LEVEL, MILITARY_ACTION_COST,
                    NAME, RESOURCE_COST, SCIENCE_COST, SET, UNITS, URBAN)
from . import engine as En
from .engine import A_AMOUNT, A_CARD, A_END, A_NO, A_OPTION, A_ROW, A_SEAT, A_VERB, A_YES, V, VERBS

push = effects.push
PREPARABLE = ("event", "territory")


def seat_id(g, decider: int, target: int) -> int:
    """SEAT answer for `target`: offset clockwise from the decider (PLAN 4)."""
    return A_SEAT + (target - decider - 1) % g.num_players


def id_seat(g, decider: int, a: int) -> int:
    return (decider + 1 + a - A_SEAT) % g.num_players


def forced_record(g, seat: int, decision: str, action: str, card=None, **extra) -> None:
    """Automatic events (revealed events, war resolutions) are recorded through drain_forced (PLAN 9)."""
    tags = {"kind": KIND[card], "age": AGE[card], "set": SET[card]} if card is not None else {}
    g.s.forced.append({"decision": decision, "decision_label": None, "action": action,
                       "card": KEY[card] if card is not None else None, "item": KEY[card] if card is not None else None,
                       "tags": tags, "extra": extra, "seat": seat, "forced": True})


def last_round(g) -> bool:
    return g.s.last_round is not None and g.s.round >= g.s.last_round


# ===================================================================================================== legality (T7)
def aggression_targets(g, seat: int, card: int) -> list:
    """T9.1: rivals weaker than you (attack bonuses counted, ending pacts not), no pact forbidding the attack; you
    must have the card's military actions."""
    if E.military_available(g, seat) < MILITARY_ACTION_COST[card]:
        return []
    out = []
    for t in g.active_seats(seat)[1:]:
        if M.forbids_attack(g, seat, t):
            continue
        a, d = M.attack_strengths(g, seat, t)
        if a > d:
            out.append(t)
    return out


def war_targets(g, seat: int, card: int) -> list:
    """T9.4: any rival a card does not protect; not in the last round."""
    if last_round(g) or E.military_available(g, seat) < MILITARY_ACTION_COST[card]:
        return []
    return [t for t in g.active_seats(seat)[1:] if not M.forbids_attack(g, seat, t) and not M.forbids_war_on(g, t)]


def pact_targets(g, seat: int, card: int) -> list:
    if len(g.active_seats()) < 3:
        return []
    return g.active_seats(seat)[1:]


def my_pacts(g, seat: int) -> list:
    return [x for x in M.pacts_in_play(g) if seat in (x[0], x[2])]


def card_targets(g, seat: int, verb: str, card: int) -> list:
    if verb == "AGGRESSION":
        return aggression_targets(g, seat, card) if KIND[card] == "aggression" else []
    if verb == "WAR":
        return war_targets(g, seat, card) if KIND[card] == "war" else []
    if verb == "PACT":
        return pact_targets(g, seat, card) if KIND[card] == "pact" else []
    return []


def verb_cards(g, seat: int, verb: str) -> list:
    """Cards of the military hand that complete the political verb."""
    hand = sorted(set(g.p(seat).military_hand))
    if verb == "PREPARE":
        return [c for c in hand if KIND[c] in PREPARABLE]
    return [c for c in hand if card_targets(g, seat, verb, c)]


def politics_legal(g, seat: int) -> list:
    legal = [A_END]
    for verb in ("PREPARE", "AGGRESSION", "WAR", "PACT"):
        if verb_cards(g, seat, verb):
            legal.append(A_VERB + V[verb])
    if my_pacts(g, seat):
        legal.append(A_VERB + V["CANCEL_PACT"])
    if g.options.get("allow_resign") and g.s.age != "IV":
        legal.append(A_VERB + V["RESIGN"])
    return legal


# ===================================================================================================== politics (T7)
def h_politics(g, t: dict, a):
    """POLITICS verb -> POLITICS_CARD -> TARGET -> (PACT_SIDE -> PACT_ANSWER) / CANCEL_WHICH."""
    seat = t["seat"]
    p = g.p(seat)
    st = t.setdefault("stage", "verb")
    if st == "verb":
        if a is None:
            g._ask("POLITICS", seat, politics_legal(g, seat))
            return
        if a == A_END:
            g._finish(t)
            return
        t["verb"] = VERBS[a - A_VERB]
        if t["verb"] == "RESIGN":
            resign(g, seat, t)
        else:
            t["stage"] = "cancel" if t["verb"] == "CANCEL_PACT" else "card"
        return
    if st == "card":
        if a is None:
            g._ask("POLITICS_CARD", seat, [A_CARD + c for c in verb_cards(g, seat, t["verb"])], verb=t["verb"])
            return
        t["card"] = a - A_CARD
        if t["verb"] == "PREPARE":
            g._finish(t)
            prepare(g, seat, t["card"])
        else:
            t["stage"] = "target"
        return
    if st == "target":
        if a is None:
            g._ask("TARGET", seat, [seat_id(g, seat, x) for x in card_targets(g, seat, t["verb"], t["card"])],
                   verb=t["verb"], card=t["card"])
            return
        t["target"] = id_seat(g, seat, a)
        if t["verb"] == "AGGRESSION":
            g._finish(t)
            push(g, {"op": "aggress", "seat": seat, "card": t["card"], "target": t["target"], "stage": "start"})
        elif t["verb"] == "WAR":
            g._finish(t)
            declare_war(g, seat, t["card"], t["target"])
        else:
            t["stage"] = "side" if EFFECT_TYPE[t["card"]] in ("pact_ab", "pact_trade_routes") else "answer"
            t["side"] = None
        return
    if st == "side":                                                    # T10.1: the side each party takes
        if a is None:
            g._ask("PACT_SIDE", seat, [A_OPTION, A_OPTION + 1], card=t["card"], target=t["target"])
            return
        t["side"] = "A" if a == A_OPTION else "B"
        t["stage"] = "answer"
        return
    if st == "answer":
        if a is None:
            g._ask("PACT_ANSWER", t["target"], [A_YES, A_NO], card=t["card"], offerer=seat, side=t["side"])
            return
        g._finish(t)
        if a == A_YES:
            accept_pact(g, seat, t["card"], t["target"], t["side"])
        else:
            g.s.log.add(t["target"], f"refuses {NAME[t['card']]}")           # the card stays in the offerer's hand
        return
    if st == "cancel":                                                  # T10.3
        pacts = my_pacts(g, seat)
        if len(pacts) > 1:
            if a is None:
                g._ask("CANCEL_WHICH", seat, [A_CARD + x[1] for x in pacts])
                return
            owner = next(x[0] for x in pacts if x[1] == a - A_CARD)
        else:
            owner = pacts[0][0]
        g._finish(t)
        remove_pact(g, owner, "cancelled")


# ===================================================================================================== events (T8)
def prepare(g, seat: int, card: int) -> None:
    """T8.1: the card goes face down on top of the future events deck; culture equal to its age; reveal the top card
    of the current events deck and resolve it."""
    s, p = g.s, g.p(seat)
    p.military_hand.remove(card)
    s.future_events.insert(0, [card, seat])
    E.add_culture(p, LEVEL[card], "events", card)
    effects.fire(g, "on_prepare_event", seat, card=card, preparer=seat)
    reveal(g, seat)


def reveal(g, seat: int) -> None:
    s = g.s
    c, _ = s.current_events.pop(0)
    s.resolving.append(c)
    s.log.add(seat, f"reveals the current event {g.card_name(c)}")
    forced_record(g, seat, "EVENT", "EVENT", c)
    push(g, {"op": "event_done", "card": c, "seat": seat})
    effects.resolve_event(g, seat, c)


def h_event_done(g, t: dict, a):
    """The resolved card goes to the past events (a colonized territory is already a colony); if the current events
    deck is empty, the future events deck is shuffled, ordered by age (older above) and becomes current (T8.1)."""
    s = g.s
    g._finish(t)
    c = t["card"]
    if c in s.resolving:
        s.resolving.remove(c)
        s.past_events.append(c)
    if not s.current_events and s.future_events:
        fut = list(s.future_events)
        g.rng.shuffle(fut)
        fut.sort(key=lambda x: LEVEL[x[0]])                             # stable: random order within an age
        s.current_events, s.future_events = fut, []
        s.log.add(None, "The future events deck becomes the current events deck")


# ===================================================================================================== colonization (T8.4-T8.6)
def h_auction(g, t: dict, a):
    """T8.4: bids clockwise from the revealer, higher than the current bid or pass (leave); one bidder left wins."""
    if a is not None:
        seat = t["asking"]
        if a == A_NO:
            t["in"].remove(seat)
        else:
            t["bid"], t["leader"] = a - A_AMOUNT + 1, seat
    while True:
        if t["leader"] is not None and t["in"] == [t["leader"]]:
            g._finish(t)
            push(g, {"op": "send", "seat": t["leader"], "card": t["card"], "bid": t["bid"], "sent": {}, "bonus": []})
            return
        if not t["in"]:
            g._finish(t)
            g.s.log.add(None, f"Nobody colonizes {g.card_name(t['card'])}")
            return
        seat = t["order"][t["pos"] % len(t["order"])]
        t["pos"] += 1
        if seat not in t["in"] or seat == t["leader"]:
            continue
        top = min(128, M.max_colonization_force(g, seat))                   # choice C4
        t["asking"] = seat
        g._ask("BID", seat, [A_NO] + [A_AMOUNT + k - 1 for k in range(t["bid"] + 1, top + 1)], card=t["card"],
               bid=t["bid"])
        return


def send_force(g, t: dict) -> int:
    return M.colonization_force(g, t["seat"], t["sent"], t["bonus"])


def h_send(g, t: dict, a):
    """T8.5: send units one at a time (at least one) and play bonus cards until the force reaches the bid; more
    units may still be sent (NO = stop)."""
    seat = t["seat"]
    p = g.p(seat)
    if a is not None:
        if a == A_NO:
            g._finish(t)
            colonize(g, seat, t["card"], t["sent"], t["bonus"])
            return
        c = a - A_CARD
        if KIND[c] == "bonus":
            p.military_hand.remove(c)
            g.s.resolving.append(c)
            t["bonus"].append(c)
        else:
            t["sent"][c] = t["sent"].get(c, 0) + 1
    force = send_force(g, t)
    legal = [A_CARD + c for c, k in sorted(p.workers.items())
             if k > t["sent"].get(c, 0) and KIND[c] in UNITS]
    if force < t["bid"]:
        legal += [A_CARD + c for c in sorted(set(p.military_hand)) if KIND[c] == "bonus" and BONUS[c]["colonization"]]
    if t["sent"] and force >= t["bid"]:
        legal.append(A_NO)
    g._ask("SEND", seat, legal, card=t["card"], bid=t["bid"], force=force)


def colonize(g, seat: int, card: int, sent: dict, bonus: list) -> None:
    """T8.6: sent units' workers go to the yellow bank, bonus cards are discarded, the territory enters play (its
    permanent effect first), then its one-time effect."""
    s, p = g.s, g.p(seat)
    for c, k in sent.items():
        p.workers[c] -= k
        p.yellow_bank += k
    for c in bonus:
        s.resolving.remove(c)
        M.discard(g, c)
    s.resolving.remove(card)
    before = E.totals(g, seat)
    p.colonies.append(card)
    g.enter_play(seat, card)
    E.settle_totals(g, seat, before)
    s.log.add(seat, f"colonizes {g.card_name(card)} (force {M.colonization_force(g, seat, sent, bonus)})")
    effects.fire_card(g, "colonize", seat, card)
    effects.fire(g, "on_colonize", seat, card=card, colonizer=seat)


# ===================================================================================================== aggressions (T9.1-T9.3)
def remove_ending_pacts(g, a: int, b: int) -> None:
    for owner, card, partner, side in M.pacts_between(g, a, b):
        if M.pact_flag(card, "ends_on_attack"):
            remove_pact(g, owner, "ends on attack")


def defense_value(c: int) -> int:
    return BONUS[c]["defense"] if KIND[c] == "bonus" else 1


def defend_reachable(values: list, cap: int, need: int) -> bool:
    return need <= 0 or (cap > 0 and sum(sorted(values, reverse=True)[:cap]) >= need)


def defend_legal(g, t: dict) -> list:
    """DEFEND (T9.2, D4): NO only before the first card; a card only if a tie stays reachable within the card cap."""
    q = g.p(t["target"])
    cap = E.stats(g, t["target"]).military - t["played"]
    need = t["att"] - t["def"] - t["added"]
    hand = q.military_hand
    legal = []
    for c in sorted(set(hand)):
        rest = list(hand)
        rest.remove(c)
        if cap >= 1 and defend_reachable([defense_value(x) for x in rest], cap - 1, need - defense_value(c)):
            legal.append(A_CARD + c)
    if not t["played"]:
        legal.append(A_NO)
    return legal


def h_aggress(g, t: dict, a):
    """T9.1-T9.2: pay, remove pacts that end on attack, the rival defends (or not), resolve as printed; the card is
    discarded either way."""
    s, seat, card, target = g.s, t["seat"], t["card"], t["target"]
    if t["stage"] == "start":
        p = g.p(seat)
        E.spend_military(p, MILITARY_ACTION_COST[card])
        p.military_hand.remove(card)
        s.resolving.append(card)
        remove_ending_pacts(g, seat, target)
        t["att"], t["def"] = M.attack_strengths(g, seat, target)
        t["played"], t["added"] = 0, 0
        t["stage"] = "defend"
        s.log.add(seat, f"plays {g.card_name(card)} against P{target} (strength {t['att']} vs {t['def']})")
        if t["def"] >= t["att"]:
            t["stage"] = "failed"
        return
    if t["stage"] == "defend":
        if a is None:
            g._ask("DEFEND", target, defend_legal(g, t), card=card, attacker=seat, need=t["att"] - t["def"] - t["added"])
            return
        if a == A_NO:
            t["stage"] = "success"
            return
        c = a - A_CARD
        g.p(target).military_hand.remove(c)
        M.discard(g, c)
        t["played"] += 1
        t["added"] += defense_value(c)
        if t["def"] + t["added"] >= t["att"]:
            t["stage"] = "failed"
        return
    g._finish(t)
    push(g, {"op": "call", "fn": "discard_resolving", "kw": {"card": card}})
    if t["stage"] == "failed":
        s.log.add(target, f"repels {g.card_name(card)}")
        return
    s.log.add(seat, f"{g.card_name(card)} succeeds against P{target}")
    fn = effects.REGISTRY["aggression"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, seat, card, EFFECT[card], target)


# ===================================================================================================== wars (T9.4-T9.6)
def declare_war(g, seat: int, card: int, target: int) -> None:
    p = g.p(seat)
    E.spend_military(p, MILITARY_ACTION_COST[card])
    p.military_hand.remove(card)
    remove_ending_pacts(g, seat, target)
    p.wars.append([card, target])
    g.touch(seat)
    g.touch(target)
    g.s.log.add(seat, f"declares {g.card_name(card)} on P{target}")


def resolve_wars(g, seat: int) -> None:
    """T9.5: at the start of the declarer's next turn compare current strengths (attack bonuses against this rival);
    the higher is the victor, the difference the advantage; a tie has no effect; the war is discarded."""
    s, p = g.s, g.p(seat)
    tasks = []
    for card, target in list(p.wars):
        p.wars.remove([card, target])
        s.resolving.append(card)
        g.touch(seat)
        g.touch(target)
        att, dfn = M.attack_strengths(g, seat, target)
        forced_record(g, seat, "WAR_RESOLUTION", "WAR_RESOLVED", card, attacker=att, defender=dfn)
        tasks.append({"op": "call", "fn": "war_effect", "kw": {"seat": seat, "card": card, "target": target,
                                                               "att": att, "dfn": dfn}})
        tasks.append({"op": "call", "fn": "discard_resolving", "kw": {"card": card}})
    push(g, *tasks)


def war_effect(g, seat: int, card: int, target: int, att: int, dfn: int) -> None:
    s = g.s
    if att == dfn:
        s.log.add(seat, f"{g.card_name(card)} on P{target}: tie ({att}), no effect")
        return
    victor, loser = (seat, target) if att > dfn else (target, seat)
    s.log.add(seat, f"{g.card_name(card)} on P{target}: P{victor} wins by {abs(att - dfn)}")
    fn = effects.REGISTRY["war"].get(EFFECT_TYPE[card])
    if fn is not None:
        fn(g, seat, card, EFFECT[card], victor, loser, abs(att - dfn))


# ===================================================================================================== pacts (T10)
def accept_pact(g, seat: int, card: int, partner: int, side) -> None:
    """T10.2: a pact already in the offerer's own play area is removed; the new one enters with its sides."""
    p = g.p(seat)
    if p.pact is not None:
        remove_pact(g, seat, "replaced")
    p.military_hand.remove(card)
    b0, b1 = E.totals(g, seat), E.totals(g, partner)
    p.pact = [card, partner, side]
    g.change_tokens(seat, effects.pact_tokens(card, side), 0)
    g.change_tokens(partner, effects.pact_tokens(card, M.side_of(seat, partner, side, partner)), 0)
    g.touch(seat)
    g.touch(partner)
    E.settle_totals(g, seat, b0)
    E.settle_totals(g, partner, b1)
    g.s.log.add(partner, f"accepts {g.card_name(card)} from P{seat}" + (f" (P{seat} side {side})" if side else ""))


def remove_pact(g, owner: int, why: str) -> None:
    """T10.3: the pact leaves play (token symbols reversed, T11.9) and is discarded."""
    q = g.p(owner)
    card, partner, side = q.pact
    b0, b1 = E.totals(g, owner), E.totals(g, partner)
    q.pact = None
    for x, sd, before in ((owner, side, b0), (partner, M.side_of(owner, partner, side, partner), b1)):
        g.touch(x)
        if g.p(x).resigned_order is None:               # no token changes for a player who left the game
            g.change_tokens(x, -effects.pact_tokens(card, sd), 0)
            E.settle_totals(g, x, before)
    M.discard(g, card)
    g.s.log.add(owner, f"{g.card_name(card)} with P{partner} ends ({why})")


# ===================================================================================================== resignation (T7.2)
def resign(g, seat: int, t: dict) -> None:
    """T7.2: hands discarded, the player's cards leave play (the technologies, government and wonders stay frozen on
    the board for the record; nothing reads them), pacts with the player removed, wars on the player removed with 7
    culture for their declarers. One player left: the game ends at once. Ranking T7.3 via scores (PLAN 7)."""
    s, p = g.s, g.p(seat)
    p.resigned_order = s.resigned
    s.resigned += 1
    p.hand_at_resign = list(p.civil_hand) + list(p.military_hand)
    s.removed_civil += [c for c in p.civil_hand]
    for c in p.military_hand:
        M.discard(g, c)
    p.civil_hand, p.military_hand = [], []
    for owner, card, partner, side in M.pacts_in_play(g):
        if seat in (owner, partner):
            remove_pact(g, owner, "resignation")
    for c in list(p.colonies):                          # no token changes for a player who left the game
        p.colonies.remove(c)
        p.play_order.remove(c)
        M.discard(g, c)
    if p.exclusive_tactic is not None:
        M.discard(g, p.exclusive_tactic)
        p.exclusive_tactic = None
    p.tactic = None
    for card, target in p.wars:
        M.discard(g, card)
        g.touch(target)
    p.wars = []
    for q in s.players:
        for w in list(q.wars):
            if w[1] == seat:
                q.wars.remove(w)
                M.discard(g, w[0])
                E.add_culture(q, 7, "military", w[0])
                g.touch(q.seat)
    g.touch(seat)
    s.log.add(seat, "resigns")
    g._finish(t)
    s.tasks = [x for x in s.tasks if not (x["op"] in ("politics", "actions") and x.get("seat") == seat)]
    turn = next(x for x in reversed(s.tasks) if x["op"] == "turn" and x["seat"] == seat)
    turn["stage"] = "done"                                                  # the rest of the turn is skipped
    if len(g.active_seats()) <= 1:
        g.end_game(evaluate=False)


# ===================================================================================================== generic effect tasks
def h_gain(g, t: dict, a):
    g._finish(t)
    g.apply_gain(t["seat"], t["gain"], t["cat"], t["card"])


CALLS = {}


def call(fn):
    CALLS[fn.__name__] = fn
    return fn


@call
def tokens(g, seat: int, blue: int, yellow: int) -> None:
    g.change_tokens(seat, blue, yellow)


@call
def discard_resolving(g, card: int) -> None:
    if card in g.s.resolving:
        g.s.resolving.remove(card)
        M.discard(g, card)


CALLS["war_effect"] = war_effect


@call
def raid_gain(g, seat: int, cost: int, card: int) -> None:
    g.apply_gain(seat, {"resources": (cost + 1) // 2}, "military", card)


def h_call(g, t: dict, a):
    g._finish(t)
    CALLS[t["fn"]](g, **t["kw"])


def h_gain_option(g, t: dict, a):
    """EVENT_CHOICE among gains (Development of Markets, Autonomous Territory)."""
    if a is None:
        g._ask("EVENT_CHOICE", t["seat"], [A_OPTION + i for i in range(len(t["options"]))], options=t["options"],
               card=t["card"], what="gain")
        return
    g._finish(t)
    g.apply_gain(t["seat"], t["options"][a - A_OPTION], t["cat"], t["card"])


def h_lose_pop(g, t: dict, a):
    """T11.7: lose population: an unused worker to the yellow bank; with none, a worker from a card of the owner's
    choice (LOSE_WORKER)."""
    p = g.p(t["seat"])
    if a is not None:
        c = a - A_CARD
        p.workers[c] -= 1
        p.yellow_bank += 1
        t["n"] -= 1
        g.touch(t["seat"])
    while t["n"] > 0:
        if p.pool:
            p.pool -= 1
            p.yellow_bank += 1
            t["n"] -= 1
            g.touch(t["seat"])
            continue
        cands = [A_CARD + c for c in p.techs if p.workers.get(c, 0)]
        if not cands:
            break
        g._ask("LOSE_WORKER", t["seat"], cands, what="population", card=t["card"])
        return
    g._finish(t)


def h_destroy_bld(g, t: dict, a):
    """Destroy buildings (worker to the owner's pool, T5.5): Border Conflict (own choice), Terrorism and Raid (the
    other player chooses). `slots` = highest level allowed per building, in order."""
    owner = g.p(t["owner"])
    if a is not None:
        c = a - A_CARD
        owner.workers[c] -= 1
        owner.pool += 1
        g.touch(t["owner"])
        t["costs"].append(RESOURCE_COST[c] or 0)
        t["slots"].pop(0)
    while t["slots"]:
        lvl = t["slots"][0]
        cands = [A_CARD + c for c in owner.techs if owner.workers.get(c, 0) and KIND[c] in t["kinds"]
                 and LEVEL[c] <= lvl]
        if cands:
            g._ask(t["decision"], t["chooser"], cands, what="destroy", victim=t["owner"], card=t["card"])
            return
        t["slots"].pop(0)
    g._finish(t)
    if t["raid"] and t["costs"]:
        raid_gain(g, t["chooser"], sum(t["costs"]), t["card"])


def mix_options(g, t: dict) -> list:
    who = g.p(t["victim"])
    if t["mode"] == "gain":
        return [A_OPTION, A_OPTION + 1]
    return [A_OPTION + i for i, k in enumerate(("farm", "mine")) if E.total(who, k) >= 1]


def h_mix(g, t: dict, a):
    """MIX: one food or resource at a time (Foray gains, Raiders losses, Plunder takes; Plunder may stop)."""
    seat = t["seat"]
    if a is not None:
        if a == A_NO:
            g._finish(t)
            return
        kind = ("farm", "mine")[a - A_OPTION]
        p = g.p(seat)
        if t["mode"] == "gain":
            E.gain(p, kind, 1)
        elif t["mode"] == "lose":
            E.lose(p, kind, 1)
        else:
            effects.take_points(g, t["victim"], seat, "food" if kind == "farm" else "resources", 1, t["card"])
        t["n"] -= 1
    opts = mix_options(g, t) if t["n"] > 0 else []
    if not opts:
        g._finish(t)
        return
    g._ask("MIX", seat, opts + ([A_NO] if t["stop_ok"] else []), mode=t["mode"], left=t["n"], victim=t["victim"],
           card=t["card"])


def h_free_build(g, t: dict, a):
    """Development of Religion / Warfare: may build the Age A temple / Warriors for free (urban limit applies)."""
    seat = t["seat"]
    p = g.p(seat)
    target = next((c for c in p.techs if KIND[c] == t["kind"] and AGE[c] == t["age"]), None)
    if a is None:
        ok = target is not None and p.pool >= 1 and not (
            t["kind"] in URBAN and E.urban_workers(p, t["kind"]) >= g.stats(seat).urban_limit)
        if not ok:
            g._finish(t)
            return
        g._ask("EVENT_CHOICE", seat, [A_YES, A_NO], what="free_build", card=t["card"], target=target)
        return
    g._finish(t)
    if a == A_YES:
        p.pool -= 1
        p.workers[target] = p.workers.get(target, 0) + 1
        g.touch(seat)


def h_dev_civ(g, t: dict, a):
    """Development of Civilization: may increase population, build a farm/mine/urban building, or develop a
    technology, each 1 food / resource / science cheaper (SUB_ACTION; no actions spent)."""
    seat, d = t["seat"], t["discount"]
    if a is None:
        legal = [A_NO]
        if g.can_increase_population(seat, free_action=True, discount=d):
            legal.append(A_OPTION)
        if g.build_options(seat, BUILDINGS, d, True):
            legal.append(A_OPTION + 1)
        if g.develop_options(seat, free=True, revolution_ok=False, sci_discount=d):
            legal.append(A_OPTION + 2)
        g._ask("SUB_ACTION", seat, legal, verb="DEV_CIV", source=t["card"])
        return
    g._finish(t)
    if a == A_OPTION:
        g.increase_population(seat, free_action=True, discount=d)
    elif a == A_OPTION + 1:
        push(g, {"op": "build", "seat": seat, "kinds": BUILDINGS, "discount": d, "free": True, "card": t["card"]})
    elif a == A_OPTION + 2:
        push(g, {"op": "develop", "seat": seat, "card": None, "free": True, "then_gain": None, "source": t["card"],
                 "revolution_ok": False, "sci_discount": d})


def h_planning(g, t: dict, a):
    """Development of Planning: 3 random Age A military cards set aside at setup are shown; each player (revealer
    first) picks one, applied to their own civilization only; then the 3 go back to the set-aside pile (Q9)."""
    s = g.s
    if t["shown"] is None:
        k = min(t["n"], len(s.age_a_unused))
        idx = sorted(g.rng.sample(range(len(s.age_a_unused)), k), reverse=True)
        t["shown"] = [s.age_a_unused.pop(i) for i in idx]
        s.resolving += t["shown"]
        s.log.add(None, "Development of Planning shows " + ", ".join(g.card_name(c) for c in t["shown"]))
    if a is not None:
        seat = t["order"][t["i"]]
        t["i"] += 1
        push(g, dict(t))                                     # continue with the next player afterwards
        g._finish(t)
        effects.resolve_event(g, seat, a - A_CARD, players=[seat])
        return
    if t["i"] < len(t["order"]) and t["shown"]:
        g._ask("EVENT_CHOICE", t["order"][t["i"]], [A_CARD + c for c in t["shown"]], what="planning",
               card=t["card"], shown=list(t["shown"]))
        return
    g._finish(t)
    for c in t["shown"]:
        s.resolving.remove(c)
        s.age_a_unused.append(c)


def h_discard_n(g, t: dict, a):
    """Politics of Strength: the weakest discards military cards of its choice."""
    p = g.p(t["seat"])
    if a is not None:
        p.military_hand.remove(a - A_CARD)
        M.discard(g, a - A_CARD)
        t["n"] -= 1
    if t["n"] <= 0 or not p.military_hand:
        g._finish(t)
        return
    g._ask("DISCARD_MILITARY", t["seat"], [A_CARD + c for c in p.military_hand], purpose="event", card=t["card"])


def move_from_options(g, seat: int) -> list:
    p = g.p(seat)
    return [c for c in p.techs if p.workers.get(c, 0) and KIND[c] in BUILDINGS + UNITS and move_to_options(g, seat, c)]


def move_to_options(g, seat: int, frm: int) -> list:
    """Freedom of Movement destinations: any other farm/mine/urban/unit technology in play, paying the cost
    difference as for upgrading (if positive), within the urban building limit."""
    p = g.p(seat)
    limit = g.stats(seat).urban_limit
    out = []
    for c in p.techs:
        if c == frm or KIND[c] not in BUILDINGS + UNITS:
            continue
        if KIND[c] in URBAN and E.urban_workers(p, KIND[c]) - (KIND[c] == KIND[frm]) >= limit:
            continue
        if g.afford(seat, "mine", g.move_cost(seat, frm, c)):
            out.append(c)
    return out


def h_move_worker(g, t: dict, a):
    seat = t["seat"]
    p = g.p(seat)
    if t["frm"] is None:
        if a is None:
            opts = move_from_options(g, seat)
            if not opts:
                g._finish(t)
                return
            g._ask("CHOOSE_TECH", seat, [A_CARD + c for c in opts] + [A_NO], verb="MOVE_FROM", card=t["card"])
            return
        if a == A_NO:
            g._finish(t)
            return
        t["frm"] = a - A_CARD
        a = None
    if a is None:
        g._ask("UPGRADE_TO", seat, [A_CARD + c for c in move_to_options(g, seat, t["frm"])], verb="MOVE_TO",
               frm=t["frm"], card=t["card"])
        return
    g._finish(t)
    to = a - A_CARD
    g.pay(seat, "mine", g.move_cost(seat, t["frm"], to))
    p.workers[t["frm"]] -= 1
    p.workers[to] = p.workers.get(to, 0) + 1
    g.touch(seat)


def h_take_loop(g, t: dict, a):
    """International Agreement: the strongest may take cards worth up to 5 civil actions (T4.3-T4.6 apply) by giving
    up its next political action; then the row slides left and is refilled without discards."""
    seat = t["seat"]
    if a is not None and a != A_NO:
        slot = a - A_ROW
        t["budget"] -= g.take_cost(seat, slot)
        g.take(seat, slot, pay=False)
        t["taken"] += 1
        if t["taken"] == 1:
            g.p(seat).forfeit_politics += 1
    if a != A_NO:
        legal = [A_ROW + i for i in g.take_slots(seat, budget=t["budget"])]
        if legal:
            g._ask("TAKE_LOOP", seat, legal + [A_NO], budget=t["budget"], card=t["card"])
            return
    g._finish(t)
    if t["taken"]:
        g.slide_and_deal()


def h_negotiate(g, t: dict, a):
    """International Negotiations: the revealer chooses science, resources or food the weakest has at least 3 of;
    the weakest pays 3 of it to the strongest."""
    weak = g.p(t["weak"])
    have = {"science": weak.science, "resources": E.resources(weak), "food": E.food(weak)}
    opts = [i for i, k in enumerate(t["options"]) if have[k] >= t["amount"]]
    if a is None:
        if not opts:
            g._finish(t)
            return
        g._ask("EVENT_CHOICE", t["seat"], [A_OPTION + i for i in opts], what="negotiate", options=t["options"],
               card=t["card"])
        return
    g._finish(t)
    effects.take_points(g, t["weak"], t["strong"], t["options"][a - A_OPTION], t["amount"], t["card"], "events")


def pick_options(g, t: dict) -> list:
    v = g.p(t["victim"])
    w = t["what"]
    if w in ("annex", "lose_colony"):
        return sorted(set(v.colonies))
    if w == "infiltrate":
        return ([v.leader] if v.leader is not None else []) + ([v.unfinished[0]] if v.unfinished else [])
    if w == "ravage":
        return [c for c in v.wonders if AGE[c] in EFFECT[t["card"]]["ages"]]
    raise KeyError(w)


PICK_KIND = {"annex": "ANNEX", "lose_colony": "EVENT_CHOICE", "infiltrate": "INFILTRATE", "ravage": "EVENT_CHOICE"}


def h_pick(g, t: dict, a):
    """One card choice: Annex (a colony of the rival), Independence Declaration (own colony), Infiltrate (the rival's
    leader or unfinished wonder), Ravages of Time (own Age A/I wonder)."""
    if a is None:
        opts = pick_options(g, t)
        if not opts:
            g._finish(t)
            return
        g._ask(PICK_KIND[t["what"]], t["seat"], [A_CARD + c for c in opts], what=t["what"], victim=t["victim"],
               card=t["card"])
        return
    g._finish(t)
    c, v, w = a - A_CARD, t["victim"], t["what"]
    q = g.p(v)
    if w in ("annex", "lose_colony"):
        before = E.totals(g, v)
        q.colonies.remove(c)
        g.leave_play(v, c)
        E.settle_totals(g, v, before)
        if w == "lose_colony":
            M.discard(g, c)
        else:                                                   # T8.7: moves with its permanent effect only
            me = t["seat"]
            b2 = E.totals(g, me)
            g.p(me).colonies.append(c)
            g.enter_play(me, c)
            E.settle_totals(g, me, b2)
    elif w == "infiltrate":
        if q.leader == c:
            g.remove_leader(v)
        else:
            card, _, tok = q.unfinished
            q.blue_bank += tok
            q.unfinished = None
            g.s.removed_civil.append(card)
        E.add_culture(g.p(t["seat"]), t["per_level"] * LEVEL[c], "military", t["card"])
    elif w == "ravage":
        g.ruin_wonder(v, c)


def kidnap_options(g, seat: int, victim: int) -> list:
    """Aggression: Kidnap candidates from the rival's hand: hand limit, no same-named technology, one leader per age."""
    p, v = g.p(seat), g.p(victim)
    if len(p.civil_hand) >= E.civil_hand_limit(g, seat):
        return []
    names = g.names_owned(seat)
    out = []
    for c in sorted(set(v.civil_hand)):
        if IS_TECH[c] and NAME[c] in names:
            continue
        if KIND[c] == "leader" and AGE[c] in p.leaders_taken:
            continue
        out.append(c)
    return out


def h_kidnap(g, t: dict, a):
    seat, victim = t["seat"], t["victim"]
    if a is None:
        g._ask("KIDNAP", seat, [A_CARD + c for c in kidnap_options(g, seat, victim)] + [A_NO], victim=victim,
               card=t["card"], candidates=kidnap_options(g, seat, victim))
        return
    g._finish(t)
    if a == A_NO:
        return
    c = a - A_CARD
    p = g.p(seat)
    g.p(victim).civil_hand.remove(c)
    p.civil_hand.append(c)
    if KIND[c] == "leader":
        p.leaders_taken.append(AGE[c])
    p.flags["kidnapped"] = [c, t["card"], EFFECT[t["card"]]["culture_if_used_this_turn"]]


def steal_options(g, seat: int, victim: int, left: int) -> list:
    """T9.6: the loser's special technologies costing at most the advantage left, not identical to a card the victor
    has in hand or play."""
    names = g.names_owned(seat)
    return [c for c in g.p(victim).specials.values() if SCIENCE_COST[c] <= left and NAME[c] not in names]


def h_steal_tech(g, t: dict, a):
    """War over Technology: take special technologies (their science cost counts against the advantage) or NO to take
    the rest of the advantage as science."""
    seat, victim = t["seat"], t["victim"]
    if a is not None and a != A_NO:
        c = a - A_CARD
        g.steal_special(seat, victim, c)
        t["left"] -= SCIENCE_COST[c]
    if a != A_NO:
        opts = steal_options(g, seat, victim, t["left"])
        if opts:
            g._ask("STEAL_TECH", seat, [A_CARD + c for c in opts] + [A_NO], victim=victim, left=t["left"],
                   card=t["card"])
            return
    g._finish(t)
    effects.take_points(g, victim, seat, "science", t["left"], t["card"])


for _name, _fn in {"politics": h_politics, "event_done": h_event_done, "auction": h_auction, "send": h_send,
                   "aggress": h_aggress, "gain": h_gain, "call": h_call, "gain_option": h_gain_option,
                   "lose_pop": h_lose_pop, "destroy_bld": h_destroy_bld, "mix": h_mix, "free_build": h_free_build,
                   "dev_civ": h_dev_civ, "planning": h_planning, "discard_n": h_discard_n,
                   "move_worker": h_move_worker, "take_loop": h_take_loop, "negotiate": h_negotiate, "pick": h_pick,
                   "kidnap": h_kidnap, "steal_tech": h_steal_tech}.items():
    En.HANDLERS[_name] = _fn
