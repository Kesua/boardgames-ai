"""Readable text: own-words power descriptions, move descriptions, game state, record fields."""
from __future__ import annotations

from .cards import FACES, FOODS, HABITATS

N = {"invertebrate": "invertebrate", "seed": "seed", "fish": "fish", "fruit": "fruit", "rodent": "rodent"}


def power_text(pw: dict, color: str) -> str:
    """Own-words description of a structured power (never the printed card text)."""
    if not pw:
        return "No power."
    t = pw["type"]
    pre = {"brown": "When activated: ", "white": "When played: ", "pink": "Once between turns: "}.get(color, "")
    f = lambda xs: " or ".join(xs)
    if t == "gain_feeder":
        if len(pw["foods"]) == 5:
            return pre + "take any 1 die from the birdfeeder and gain its food."
        return pre + f"take a {f(pw['foods'])} die from the birdfeeder if there is one" + \
            ("; you may cache it on this bird." if pw["may_cache"] else ".")
    if t == "gain_supply":
        if pw["cache"]:
            return pre + f"cache {pw['count']} {f(pw['foods'])} from the supply on this bird."
        return pre + f"gain {pw['count']} {f(pw['foods'])} from the supply."
    if t == "all_gain_supply":
        return pre + f"every player gains 1 {pw['food']} from the supply."
    if t == "lay_egg":
        return pre + ("lay 1 egg on this bird." if pw["target"] == "this" else "lay 1 egg on any of your birds.")
    if t == "lay_each_nest":
        return pre + f"lay 1 egg on each of your birds with a {pw['nest']} nest."
    if t == "all_lay_nest":
        return pre + f"every player lays 1 egg on one {pw['nest']}-nest bird; you may lay a second egg on another one."
    if t == "draw":
        s = f"draw {pw['count']} card{'s' if pw['count'] > 1 else ''}"
        return pre + s + ("; then discard 1 card at the end of your turn." if pw["discard_end"] else ".")
    if t == "all_draw_deck":
        return pre + "every player draws 1 card from the deck."
    if t == "fewest_draw":
        return pre + f"the player(s) with the fewest {pw['habitat']} birds draw 1 card."
    if t == "fewest_die":
        return pre + f"the player(s) with the fewest {pw['habitat']} birds take 1 die from the birdfeeder."
    if t == "each_gain_die":
        return pre + "every player takes 1 die from the birdfeeder, starting with the player you choose."
    if t == "tuck_hand":
        th = pw["then"]
        then = {"draw": "draw 1 card", "lay_egg": "lay 1 egg on this bird" if th.get("target") == "this"
                else "lay 1 egg on any bird", "gain_supply": f"gain 1 {f(th.get('foods', []))}"}[th["type"]]
        return pre + f"tuck 1 card from your hand under this bird; if you do, {then}."
    if t == "food_for_tucks":
        return pre + f"pay 1 {pw['food']} to tuck 2 cards from the deck under this bird."
    if t == "egg_for_wild":
        return pre + f"remove 1 egg from another of your birds to gain {pw['count']} food of your choice."
    if t == "egg_for_cards":
        return pre + "remove 1 egg from one of your birds to draw 2 cards."
    if t == "hunt_card":
        return pre + f"predator: reveal the deck's top card; if its wingspan is under {pw['below']} cm, tuck it here."
    if t == "hunt_dice":
        return pre + f"predator: roll the dice outside the birdfeeder; if any shows {pw['food']}, cache 1 {pw['food']} here."
    if t == "move":
        return pre + "if this is the rightmost bird of its row, move it to another row."
    if t == "repeat":
        return pre + ("use the power of another predator in this row again." if pw["predator_only"]
                      else "use the brown power of another bird in this row again.")
    if t == "trade_food":
        return pre + "swap 1 of your food for any other food from the supply."
    if t == "draw_bonus":
        return pre + "draw 2 bonus cards and keep 1."
    if t == "gain_all_feeder":
        return pre + f"take every {pw['food']} die from the birdfeeder."
    if t == "play_another":
        where = "this bird's row" if pw["habitat"] == "this" else f"your {pw['habitat']}"
        return pre + f"play another bird into {where}, paying its normal cost."
    if t == "oystercatcher":
        return pre + "draw one card more than there are players; each player picks 1, you keep the extra one."
    if t == "take_tray":
        return pre + "take all 3 face-up cards from the bird tray."
    if t == "pink_play":
        th = pw["then"]
        then = f"gain 1 {th['foods'][0]}" if th["type"] == "gain_supply" else "tuck 1 card from your hand under this bird"
        return pre + f"when another player plays a {pw['habitat']} bird, {then}."
    if t == "pink_lay_eggs":
        other = "another" if pw["other"] else "a"
        return pre + f"when another player lays eggs as their action, lay 1 egg on {other} {pw['nest']}-nest bird."
    if t == "pink_gain_food_rodent":
        return pre + "when another player gains a rodent with the gain food action, cache 1 rodent here."
    if t == "pink_predator":
        return pre + "when another player's predator succeeds, take 1 die from the birdfeeder."
    return pre + t


def describe_action(g, a: int) -> str:
    from . import engine as E
    seg, off = E.CODEC.decode(a)
    d = g.s.decisions.top
    kind = d.kind if d else ""
    if seg == "ACTION":
        return ("Play a bird", "Gain food (forest)", "Lay eggs (grassland)", "Draw cards (wetland)")[off]
    if seg == "BIRD":
        verb = {"PLAY_BIRD": "Play", "TUCK": "Tuck", "END_DISCARD": "Discard", "TRADE_DISCARD_CARD": "Discard",
                "PICK_CARD": "Pick"}.get(kind, "Choose")
        return f"{verb} {g.bird(off).name}"
    if seg == "HABITAT":
        return ("Move to " if kind == "MOVE" else "Into ") + HABITATS[off]
    if seg == "FOOD":
        verb = {"PAY_FOOD": "Pay", "PAY_PAIR": "Pay (two for one)", "SETUP_FOOD": "Discard", "TRADE_PAY_FOOD": "Pay",
                "TRADE_GIVE": "Give", "TRADE_GET": "Get"}.get(kind, "Take")
        return f"{verb} {FOODS[off]}"
    if seg == "DIE":
        return f"Take the {FACES[off].replace('_or_', '-or-')} die"
    if seg == "SLOT":
        h, c = divmod(off, 5)
        p = g.at(d.seat if d else g.s.active, h, c)
        name = g.bird(p.bird).name if p else "?"
        verb = {"LAY_EGG": "Lay an egg on", "PAY_EGG": "Pay an egg from", "DISCARD_EGG": "Remove an egg from",
                "TRADE_DISCARD_EGG": "Remove an egg from", "REPEAT": "Repeat"}.get(kind, "Choose")
        return f"{verb} {name} ({HABITATS[h]} {c + 1})"
    if seg == "TRAY":
        card = g.s.tray[off]
        return f"Draw {g.bird(card).name} from the tray" if card is not None else "Draw from the tray"
    if seg == "DECK":
        return "Draw from the deck"
    if seg == "BONUS":
        return f"Keep bonus card {g.bonus[off].name}"
    if seg == "PLAYER":
        return f"Start with the player {off} seats to the left"
    if seg == "YES":
        if kind == "SETUP_KEEP":
            return f"Keep {g.bird(d.data['bird']).name}"
        if kind == "USE_POWER":
            return f"Use {g.bird(d.data['bird']).name}"
        return {"TRADE": "Use the trade", "CACHE": "Cache it", "PAY_FOOD": "Pay two food for one"}.get(kind, "Yes")
    if seg == "NO":
        if kind == "SETUP_KEEP":
            return f"Discard {g.bird(d.data['bird']).name}"
        return {"USE_POWER": "Skip the power", "TRADE": "No trade", "CACHE": "Keep it"}.get(kind, "Stop / skip")
    if seg == "REROLL":
        return "Reroll the birdfeeder"
    return f"{seg} {off}"


def record_info(g, a: int) -> dict:
    """Recorded before the action is applied. action = what happened, in words the summaries can count."""
    from . import engine as E
    seg, off = E.CODEC.decode(a)
    d = g.s.decisions.top
    kind = d.kind
    card = item = None
    action = seg
    tags = {}
    if seg == "ACTION":
        action = E.ACTIONS[off]
    elif seg == "BIRD":
        item = card = g.bird(off).key
        action = {"PLAY_BIRD": "PLAY", "TUCK": "TUCK", "END_DISCARD": "DISCARD", "TRADE_DISCARD_CARD": "DISCARD",
                  "PICK_CARD": "PICK"}.get(kind, "BIRD")
    elif seg in ("YES", "NO"):
        if kind == "SETUP_KEEP":
            item = card = g.bird(d.data["bird"]).key
            action = "KEEP" if seg == "YES" else "SETUP_DISCARD"
        elif kind == "USE_POWER":
            item = card = g.bird(d.data["bird"]).key
            action = "USE" if seg == "YES" else "SKIP"
        else:
            action = kind + "_" + seg
    elif seg == "HABITAT":
        action = "HABITAT"
        tags["habitat"] = HABITATS[off]
        if "bird" in d.data:
            item = card = g.bird(d.data["bird"]).key
    elif seg == "DIE":
        action = "TAKE_DIE"
        tags["food"] = FACES[off]
    elif seg in ("TRAY", "DECK"):
        action = "DRAW_" + seg
    label = None
    if kind == "USE_POWER":
        label = g.bird(d.data["bird"]).power["type"]
    elif kind == "TRADE":
        label = d.data.get("action")
    pl = g.p(d.seat)
    return {"decision": kind, "decision_label": label, "action": action, "card": card, "item": item, "tags": tags,
            "extra": {"round": g.s.round + 1, "hand": len(pl.hand), "food": sum(pl.food),
                      "birds": sum(len(r) for r in pl.rows)}}


def text_state(g) -> str:
    s = g.s
    lines = [f"Round {s.round + 1}, turn {s.turns}, active P{s.active}, first P{s.first}",
             "Goals: " + ", ".join(x["id"] for x in s.goals) + f" ({s.goal_side}); points so far {s.goal_points}",
             "Feeder: " + ", ".join(FACES[x] for x in s.feeder) + f" | outside: {len(s.outside)}",
             "Tray: " + ", ".join(g.bird(c).name if c is not None else "-" for c in s.tray) +
             f" | deck {len(s.deck)}, discard {len(s.discard)}"]
    d = s.decisions.top
    if d:
        lines.append(f"Decision {d.kind} for P{d.seat}: " + ", ".join(describe_action(g, a) for a in d.data["legal"]))
    for p in s.players:
        lines.append(f"P{p.seat}: food {dict(zip(FOODS, p.food))}, hand {[g.bird(b).name for b in p.hand]}, "
                     f"bonus {[g.bonus[b].name for b in p.bonus]}, score {g.breakdowns()[p.seat]}")
        for h, row in enumerate(p.rows):
            cells = [f"{g.bird(x.bird).name} (eggs {x.eggs}/{g.bird(x.bird).egg_limit}, cache {sum(x.cache)}, "
                     f"tucked {x.tucked})" for x in row]
            lines.append(f"  {HABITATS[h]}: " + "; ".join(cells))
    return "\n".join(lines)
