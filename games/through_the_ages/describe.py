"""Readable texts and record rows (PLAN.md section 9): describe(a), record_info(a), text_state()."""
from __future__ import annotations

from . import economy as E
from .cards import AGE, IS_TECH, KEY, KIND, NAME, SET, STAGE_COSTS


def _name(c) -> str:
    return f"{NAME[c]} ({AGE[c]})"


def describe(g, a: int) -> str:
    from .engine import CODEC, ROW_COST, VERB_TEXT, VERBS
    s = g.s
    d = s.decisions.top
    kind = d.kind if d is not None else ""
    seg, off = CODEC.decode(a)
    if seg == "END":
        return "Pass the political action" if kind == "POLITICS" else "End the action phase"
    if seg == "YES":
        return f"Revolution to {_name(d.data['card'])}" if kind == "REVOLT" else "Yes"
    if seg == "NO":
        return f"Peaceful change to {_name(d.data['card'])}" if kind == "REVOLT" else "No"
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
        return VERB_TEXT.get(verb, verb.replace("_", " ").capitalize())
    if seg == "CARD":
        c = off
        if kind == "ACTION":
            if IS_TECH[c]:
                return f"Develop {_name(c)}" if KIND[c] != "government" else f"Change government to {_name(c)}"
            if KIND[c] == "leader":
                return f"Play leader {_name(c)}"
            if KIND[c] == "action":
                return f"Play action card {_name(c)}"
        if kind == "CHOOSE_TECH":
            verb = d.data.get("verb", "")
            text = {"BUILD": "Build on", "BUILD_UNIT": "Build a unit on", "UPGRADE": "Upgrade from",
                    "UPGRADE_UNIT": "Upgrade a unit from", "DESTROY": "Destroy a building on",
                    "DISBAND": "Disband a unit on"}.get(verb, verb)
            return f"{text} {_name(c)}"
        if kind == "UPGRADE_TO":
            return f"Upgrade {_name(d.data['frm'])} to {_name(c)}"
        if kind == "SUB_ACTION":
            return f"Develop {_name(c)} (action card)"
        if kind == "DISCARD_MILITARY":
            return f"Discard military card {_name(c)}"
        if kind == "LOSE_BLUE":
            return f"Take a blue token from {_name(c)}"
        return f"{_name(c)}"
    if seg == "AMOUNT":
        if kind == "STAGES":
            return f"Build {off + 1} stage{'s' * (off > 0)} of {_name(d.data['card'])}"
        return f"{off + 1}"
    if seg == "OPTION":
        if kind == "SUB_ACTION" and d.data.get("verb") == "GAIN":
            return "Gain " + ", ".join(f"{v} {k}" for k, v in d.data["options"][off].items())
        return f"Option {off + 1}"
    if seg == "SEAT":
        return f"Player P{(d.seat + 1 + off) % g.num_players}"
    return f"{seg} {off}"


ACTION_OF_VERB = {"BUILD": "BUILD", "BUILD_UNIT": "BUILD_UNIT", "UPGRADE": "UPGRADE", "UPGRADE_UNIT": "UPGRADE_UNIT",
                  "DESTROY": "DESTROY", "DISBAND": "DISBAND"}


def record_info(g, a: int) -> dict:
    """Called before step_id. The card is recorded on the step that names it (PLAN 9)."""
    from .engine import CODEC, ROW_COST, VERBS
    s = g.s
    d = s.decisions.top
    kind = d.kind
    seg, off = CODEC.decode(a)
    label, action, card, extra = None, seg, None, {}
    if kind == "POLITICS":
        action = "PASS" if seg == "END" else seg
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
            action = {"leader": "PLAY_LEADER", "action": "PLAY_ACTION",
                      "government": "GOVERNMENT"}.get(KIND[off], "DEVELOP")
    elif kind == "CHOOSE_TECH":
        label = d.data.get("verb")
        action = ACTION_OF_VERB.get(label, label)
        if label in ("UPGRADE", "UPGRADE_UNIT"):
            action = "UPGRADE_FROM"               # the completing step (UPGRADE_TO) carries the card
        else:
            card = off
    elif kind == "UPGRADE_TO":
        label = d.data.get("verb")
        action, card = label, off
    elif kind == "STAGES":
        label, action, card = "WONDER_STAGE", "WONDER_STAGE", d.data["card"]
        extra = {"stages": off + 1}
    elif kind == "REVOLT":
        action = "REVOLUTION" if seg == "YES" else "PEACEFUL_CHANGE"
    elif kind == "SUB_ACTION":
        label = d.data.get("verb")
        if seg == "CARD":
            action, card = "DEVELOP", off
        elif seg == "VERB":
            action = VERBS[off]
        else:
            action = "GAIN_CHOICE"
    elif kind == "DISCARD_MILITARY":
        action, card = "DISCARD", off
    elif kind == "LOSE_BLUE":
        action = "LOSE_BLUE"
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
             f"{len(s.military_discard)}, current events {len(s.current_events)}, future events "
             f"{len(s.future_events)}, past events {len(s.past_events)}"]
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
                     + (f"; building {NAME[unf[0]]} {unf[1]}/{len(STAGE_COSTS[unf[0]])}" if unf else ""))
        lines.append(f"    civil hand: {', '.join(NAME[c] for c in p.civil_hand) or '-'}; military hand: "
                     f"{', '.join(NAME[c] for c in p.military_hand) or '-'}")
    return "\n".join(lines)
