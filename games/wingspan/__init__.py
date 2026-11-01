"""Wingspan (base game), Stonemaier Games 2019. See README.md, rules.md and PLAN.md here."""
from __future__ import annotations

from bgai.game import GameSpec

DEFAULT_OPTIONS = {"swift_start_birds": True, "goal_side": "green"}


def new_game(num_players: int, seed: int, options: dict = None):
    from .engine import Game
    return Game(num_players, seed, {**DEFAULT_OPTIONS, **(options or {})}).reset()


def action_count(num_players: int) -> int:
    from .engine import CODEC
    return CODEC.size


def encoder(num_players: int, version: int = None):
    from .encoder import StateEncoder
    return StateEncoder(num_players)


def greedy(seed: int = None):
    from .agents import GreedyAgent
    return GreedyAgent(seed)


def summary(frames: dict, manifest: dict) -> dict:
    from .summary import game_sections
    return game_sections(frames, manifest)


def catalog() -> dict:
    from .cards import FOODS, HABITATS, birds, bonus_cards
    from .describe import power_text
    items, cards = {}, {}
    for b in birds():
        cost = {FOODS[i]: n for i, n in enumerate(b.food) if n}
        items[b.key] = {"points": b.points, "habitats": [HABITATS[h] for h in b.habitats], "nest": b.nest,
                        "egg_limit": b.egg_limit, "wingspan": b.wingspan, "food": cost, "wild": b.wild,
                        "alternative": b.alternative, "food_total": b.food_total, "power_color": b.color,
                        "power": b.power["type"] if b.power else None, "predator": b.predator,
                        "flocking": b.flocking, "swift_start": b.swift_start, "power_text": power_text(b.power, b.color),
                        "tags": {"habitat": [HABITATS[h] for h in b.habitats], "nest": [b.nest], "power": [b.color]},
                        "cards": [b.key]}
        cards[b.key] = {"label": b.name, "items": [b.key], "count": 1}
    return {"items": items, "cards": cards, "bonus": [{"id": c.id, "name": c.name} for c in bonus_cards()]}


def invariants(g) -> list:
    """Card, die and token conservation and limits, checked by bgai.checks during random games."""
    s = g.s
    out = []
    total = len(s.deck) + len(s.discard) + sum(c is not None for c in s.tray) + len(s.reveal)
    for p in s.players:
        total += len(p.hand) + len(p.offer) + sum(len(r) + sum(x.tucked for x in r) for r in p.rows)
        if any(f < 0 for f in p.food):
            out.append(f"P{p.seat} negative food {p.food}")
        if any(len(r) > 5 for r in p.rows):
            out.append(f"P{p.seat} row over 5 birds")
        for _, _, x in p.placed():
            if not 0 <= x.eggs <= g.bird(x.bird).egg_limit:
                out.append(f"P{p.seat} {g.bird(x.bird).name} eggs {x.eggs}")
    expected = 180 if g.options.get("swift_start_birds", True) else 170
    if total != expected:
        out.append(f"bird cards {total} != {expected}")
    if len(s.feeder) + len(s.outside) != 5 or not s.feeder:
        out.append(f"dice feeder {s.feeder} outside {s.outside}")
    bonus = len(s.bonus_deck) + len(s.bonus_discard) + sum(len(p.bonus) + len(p.offer_bonus) for p in s.players)
    pending = [t for t in s.tasks if t.get("op") == "eff_bonus" and t.get("drawn")]
    bonus += sum(len(t["drawn"]) for t in pending)
    if bonus != 26:
        out.append(f"bonus cards {bonus} != 26")
    return out


SPEC = GameSpec(slug="wingspan", name="Wingspan", players=(2, 3, 4, 5), new_game=new_game,
                action_count=action_count, encoder=encoder, greedy=greedy, default_options=dict(DEFAULT_OPTIONS),
                rounds=lambda g: 4.0, summary=summary, catalog=catalog, invariants=invariants, max_steps=6000)
