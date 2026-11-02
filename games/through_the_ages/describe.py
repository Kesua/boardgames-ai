"""Readable texts and record rows (PLAN.md section 9): describe(a), record_info(a), text_state()."""
from __future__ import annotations

from . import economy as E
from .cards import AGE, BONUS, IS_TECH, KEY, KIND, NAME, SET, STAGE_COSTS


def _name(c) -> str:
    return f"{NAME[c]} ({AGE[c]})"


POLITICAL_TEXT = {"PREPARE": "Prepare an event", "AGGRESSION": "Play an aggression", "WAR": "Declare a war",
                  "PACT": "Offer a pact", "CANCEL_PACT": "Cancel a pact", "RESIGN": "Resign"}
MIX_TEXT = ("food", "resource")


def describe(g, a: int) -> str:
    from .engine import CODEC, ROW_COST, VERB_TEXT, VERBS
    s = g.s
    d = s.decisions.top
    kind = d.kind if d is not None else ""
    data = d.data if d is not None else {}
    seg, off = CODEC.decode(a)
    if seg == "END":
        return "Pass the political action" if kind == "POLITICS" else "End the action phase"
    if seg == "YES":
        if kind == "REVOLT":
            return f"Revolution to {_name(data['card'])}"
        if kind == "PACT_ANSWER":
            return f"Accept {_name(data['card'])} from P{data['offerer']}"
        if kind == "EVENT_CHOICE" and data.get("what") == "free_build":
            return f"Build {_name(data['target'])} for free"
        return "Yes"
    if seg == "NO":
        if kind == "REVOLT":
            return f"Peaceful change to {_name(data['card'])}"
        return {"PACT_ANSWER": "Refuse the pact", "DEFEND": "Do not defend", "BID": "Pass (no bid)",
                "SEND": "Stop sending", "MIX": "Stop taking", "TAKE_LOOP": "Stop taking cards",
                "KIDNAP": "Take no card", "STEAL_TECH": "Take the rest as science",
                "CHOOSE_TECH": "Move no worker", "SUB_ACTION": "Do nothing",
                "EVENT_CHOICE": "Do not build"}.get(kind, "No")
    if seg == "ROW":
        c = s.row[off]
        if c is None:
            return f"Take row slot {off + 1}"
        cost = g.take_cost(d.seat, off) if d is not None else ROW_COST[off]
        return f"Take {_name(c)} from row slot {off + 1} ({cost} civil action{'s' * (cost > 1)})"
    if seg == "VERB":
        verb = VERBS[off] if off < len(VERBS) else f"ability {off}"
        if kind == "SUB_ACTION":
            return {"BUILD": "Build (action card)", "UPGRADE": "Upgrade (action card)"}.get(verb, verb)
        if verb in POLITICAL_TEXT:
            return POLITICAL_TEXT[verb]
        if verb == "COPY_TACTIC":
            return "Copy a common tactic"
        return VERB_TEXT.get(verb, verb.replace("_", " ").capitalize())
    if seg == "CARD":
        c = off
        if kind == "ACTION":
            if KIND[c] == "tactic":
                return f"Play tactic {_name(c)}"
            if IS_TECH[c]:
                return f"Develop {_name(c)}" if KIND[c] != "government" else f"Change government to {_name(c)}"
            if KIND[c] == "leader":
                return f"Play leader {_name(c)}"
            if KIND[c] == "action":
                return f"Play action card {_name(c)}"
        if kind == "CHOOSE_TECH":
            verb = data.get("verb", "")
            text = {"BUILD": "Build on", "BUILD_UNIT": "Build a unit on", "UPGRADE": "Upgrade from",
                    "UPGRADE_UNIT": "Upgrade a unit from", "DESTROY": "Destroy a building on",
                    "DISBAND": "Disband a unit on", "MOVE_FROM": "Move a worker from"}.get(verb, verb)
            return f"{text} {_name(c)}"
        if kind == "UPGRADE_TO":
            if data.get("verb") == "MOVE_TO":
                return f"Move the worker from {_name(data['frm'])} to {_name(c)}"
            return f"Upgrade {_name(data['frm'])} to {_name(c)}"
        if kind == "SUB_ACTION":
            return f"Develop {_name(c)} (action card)"
        if kind == "DISCARD_MILITARY":
            return f"Discard military card {_name(c)}"
        if kind == "LOSE_BLUE":
            return f"Take a blue token from {_name(c)}"
        if kind == "POLITICS_CARD":
            return {"PREPARE": "Prepare", "AGGRESSION": "Aggression with", "WAR": "War with",
                    "PACT": "Pact"}[data["verb"]] + f" {_name(c)}"
        if kind == "CHOOSE_TACTIC":
            return f"Copy tactic {_name(c)}"
        if kind == "CANCEL_WHICH":
            return f"Cancel {_name(c)}"
        if kind == "DEFEND":
            return f"Defend with {_name(c)} (+{BONUS[c]['defense'] if KIND[c] == 'bonus' else 1})"
        if kind == "SEND":
            if KIND[c] == "bonus":
                return f"Play {_name(c)} (+{BONUS[c]['colonization']} colonization)"
            return f"Send a unit from {_name(c)}"
        if kind in ("LOSE_WORKER", "TERRORISM"):
            if data.get("what") == "destroy":
                return f"Destroy a building on {_name(c)} of P{data['victim']}"
            return f"Lose a worker from {_name(c)}"
        if kind == "STEAL_TECH":
            return f"Take {_name(c)} from P{data['victim']}"
        if kind == "KIDNAP":
            return f"Take {_name(c)} from P{data['victim']}'s hand"
        if kind == "INFILTRATE":
            return f"Remove {_name(c)} of P{data['victim']}"
        if kind == "ANNEX":
            return f"Annex {_name(c)} of P{data['victim']}"
        if kind == "EVENT_CHOICE":
            what = data.get("what")
            if what == "planning":
                return f"Apply {_name(c)} to my civilization"
            if what == "ravage":
                return f"Ruin {_name(c)}"
            if what == "lose_colony":
                return f"Lose colony {_name(c)}"
        return f"{_name(c)}"
    if seg == "AMOUNT":
        if kind == "STAGES":
            return f"Build {off + 1} stage{'s' * (off > 0)} of {_name(data['card'])}"
        if kind == "BID":
            return f"Bid {off + 1} for {_name(data['card'])}"
        return f"{off + 1}"
    if seg == "OPTION":
        if kind == "SUB_ACTION" and data.get("verb") == "GAIN":
            return "Gain " + ", ".join(f"{v} {k}" for k, v in data["options"][off].items())
        if kind == "SUB_ACTION" and data.get("verb") == "DEV_CIV":
            return ("Increase population (1 food less)", "Build (1 resource less)",
                    "Develop a technology (1 science less)")[off]
        if kind == "EVENT_CHOICE" and data.get("what") == "gain":
            return "Gain " + ", ".join(f"{v} {k}" for k, v in data["options"][off].items())
        if kind == "EVENT_CHOICE" and data.get("what") == "negotiate":
            return f"The weakest pays 3 {data['options'][off]}"
        if kind == "PACT_SIDE":
            return f"Take side {'AB'[off]} of {_name(data['card'])}"
        if kind == "MIX":
            verb = {"gain": "Gain", "lose": "Lose", "take": "Take"}[data["mode"]]
            return f"{verb} 1 {MIX_TEXT[off]}"
        return f"Option {off + 1}"
    if seg == "SEAT":
        target = (d.seat + 1 + off) % g.num_players
        if kind == "TARGET":
            return f"{_name(data['card'])} on P{target}"
        return f"Player P{target}"
    return f"{seg} {off}"


ACTION_OF_VERB = {"BUILD": "BUILD", "BUILD_UNIT": "BUILD_UNIT", "UPGRADE": "UPGRADE", "UPGRADE_UNIT": "UPGRADE_UNIT",
                  "DESTROY": "DESTROY", "DISBAND": "DISBAND"}
TARGET_ACTION = {"AGGRESSION": "AGGRESSION", "WAR": "WAR", "PACT": "PACT_OFFER"}


def record_info(g, a: int) -> dict:
    """Called before step_id. The card is recorded on the step that names it, a two-step action on its completing
    step (PLAN 9): prepare on POLITICS_CARD, aggressions/wars/pacts on TARGET, colonization on SEND's stop."""
    from .engine import CODEC, ROW_COST, VERBS
    s = g.s
    d = s.decisions.top
    kind = d.kind
    data = d.data
    seg, off = CODEC.decode(a)
    label, action, card, extra = None, seg, None, {}
    if kind == "POLITICS":
        action = "PASS" if seg == "END" else VERBS[off]
    elif kind == "ACTION":
        if seg == "END":
            action = "END"
        elif seg == "ROW":
            action, card = "TAKE", s.row[off]
            extra = {"slot": off + 1, "cost": g.take_cost(d.seat, off) if card is not None else ROW_COST[off]}
        elif seg == "VERB":
            action = VERBS[off]
            if action == "INCREASE_POP":
                extra = {"cost": E.pop_cost(g.p(d.seat).yellow_bank) or 0}
        elif seg == "CARD":
            card = off
            action = {"leader": "PLAY_LEADER", "action": "PLAY_ACTION", "tactic": "PLAY_TACTIC",
                      "government": "GOVERNMENT"}.get(KIND[off], "DEVELOP")
    elif kind == "CHOOSE_TECH":
        label = data.get("verb")
        action = ACTION_OF_VERB.get(label, label)
        if label in ("UPGRADE", "UPGRADE_UNIT", "MOVE_FROM"):
            action = "UPGRADE_FROM" if label != "MOVE_FROM" else ("MOVE_NONE" if seg == "NO" else "MOVE_FROM")
        else:
            card = off
    elif kind == "UPGRADE_TO":
        label = data.get("verb")
        action, card = label, off
    elif kind == "STAGES":
        label, action, card = "WONDER_STAGE", "WONDER_STAGE", data["card"]
        extra = {"stages": off + 1}
    elif kind == "REVOLT":
        action = "REVOLUTION" if seg == "YES" else "PEACEFUL_CHANGE"
    elif kind == "SUB_ACTION":
        label = data.get("verb")
        if seg == "CARD":
            action, card = "DEVELOP", off
        elif seg == "VERB":
            action = VERBS[off]
        elif seg == "NO":
            action = "NONE"
        else:
            action = "GAIN_CHOICE" if label == "GAIN" else f"{label}_OPTION"
    elif kind == "DISCARD_MILITARY":
        action, card = "DISCARD", off
    elif kind == "LOSE_BLUE":
        action = "LOSE_BLUE"
    elif kind == "POLITICS_CARD":
        label = data["verb"]
        action = "PREPARE" if label == "PREPARE" else f"{label}_CARD"
        card = off if label == "PREPARE" else None
    elif kind == "TARGET":
        label = data["verb"]
        action, card = TARGET_ACTION[label], data["card"]
        extra = {"target_offset": off}
    elif kind == "PACT_SIDE":
        action, extra = "PACT_SIDE", {"side": "AB"[off]}
    elif kind == "PACT_ANSWER":
        action = "PACT_ACCEPT" if seg == "YES" else "PACT_REFUSE"
    elif kind == "CANCEL_WHICH":
        action, card = "CANCEL_PACT", off
    elif kind == "CHOOSE_TACTIC":
        action, card = "COPY_TACTIC", off
    elif kind == "DEFEND":
        action, card = ("DEFEND", off) if seg == "CARD" else ("NO_DEFENSE", None)
    elif kind == "BID":
        action, extra = ("BID", {"amount": off + 1}) if seg == "AMOUNT" else ("BID_PASS", {})
    elif kind == "SEND":
        if seg == "NO":
            action, card = "COLONIZE", data["card"]
            extra = {"bid": data["bid"], "force": data["force"]}
        else:
            action = "SEND_BONUS" if KIND[off] == "bonus" else "SEND_UNIT"
            card = off if KIND[off] == "bonus" else None
    elif kind in ("MIX", "TAKE_LOOP", "STEAL_TECH", "KIDNAP", "INFILTRATE", "ANNEX", "LOSE_WORKER", "TERRORISM",
                  "EVENT_CHOICE"):
        action = kind if seg != "NO" else kind + "_NONE"
        label = data.get("what") or data.get("mode")
        if kind == "TAKE_LOOP" and seg == "ROW":
            card = s.row[off]
        elif kind in ("STEAL_TECH", "KIDNAP", "INFILTRATE", "ANNEX") and seg == "CARD":
            card = off
        elif kind == "EVENT_CHOICE" and data.get("what") == "planning":
            card = off
    tags = {"kind": KIND[card], "age": AGE[card], "set": SET[card]} if card is not None else {}
    return {"decision": kind, "decision_label": label, "action": action,
            "card": KEY[card] if card is not None else None, "item": KEY[card] if card is not None else None,
            "tags": tags, "extra": extra}


def text_state(g) -> str:
    """Full deterministic dump (hidden hands included) for logs and the clone check."""
    s = g.s
    lines = [f"Age {s.age}, round {s.round}, turn {s.turns}, P{s.turn_seat} ({s.phase}), start P{s.start_seat}"
             + (f", last round {s.last_round}" if s.last_round else "") + (" GAME OVER" if s.game_over else ""),
             "Row: " + " | ".join("-" if c is None else NAME[c] for c in s.row),
             f"Civil deck {len(s.civil_deck)}, military deck {len(s.military_deck)}, military discard "
             f"{len(s.military_discard)}, current events {[_name(c) for c, _ in s.current_events]}, future events "
             f"{[_name(c) for c, _ in s.future_events]}, past events {len(s.past_events)}",
             "Common tactics: " + (", ".join(_name(c) for c in s.common_tactics) or "-")]
    for p in s.players:
        st = E.compute_stats(g, p)
        lines.append(
            f"P{p.seat}: culture {p.culture} (+{st.culture}), science {p.science} (+{st.science}), "
            f"food {E.food(p)}, resources {E.resources(p)}, happiness {st.happiness}, strength {st.strength}, "
            f"civil {st.civil - p.civil_spent}/{st.civil}, military {st.military - p.military_spent}/{st.military}, "
            f"blue bank {p.blue_bank}, yellow bank {p.yellow_bank}, unused workers {p.pool}"
            + (" RESIGNED" if p.resigned_order is not None else ""))
        techs = ", ".join(f"{NAME[c]} w{p.workers.get(c, 0)}" + (f" t{p.tokens[c]}" if p.tokens.get(c) else "")
                          for c in p.techs)
        lines.append(f"    government {NAME[p.government]}; leader {NAME[p.leader] if p.leader is not None else '-'};"
                     f" specials {', '.join(NAME[c] for c in p.specials.values()) or '-'}")
        lines.append(f"    technologies: {techs}")
        unf = p.unfinished
        lines.append(f"    wonders: {', '.join(NAME[c] for c in p.wonders) or '-'}"
                     + (f"; ruined {', '.join(NAME[c] for c in p.ruined)}" if p.ruined else "")
                     + (f"; building {NAME[unf[0]]} {unf[1]}/{len(STAGE_COSTS[unf[0]])}" if unf else ""))
        lines.append(f"    tactic {_name(p.tactic) if p.tactic is not None else '-'}"
                     + (" (exclusive)" if p.exclusive_tactic is not None else "")
                     + f"; colonies {', '.join(NAME[c] for c in p.colonies) or '-'}"
                     + (f"; pact {_name(p.pact[0])} with P{p.pact[1]} side {p.pact[2]}" if p.pact else "")
                     + (f"; wars {', '.join(f'{_name(c)} on P{t}' for c, t in p.wars)}" if p.wars else ""))
        lines.append(f"    civil hand: {', '.join(NAME[c] for c in p.civil_hand) or '-'}; military hand: "
                     f"{', '.join(NAME[c] for c in p.military_hand) or '-'}")
    return "\n".join(lines)
