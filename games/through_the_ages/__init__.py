"""Through the Ages: A New Story of Civilization (CGE 2015) + New Leaders and Wonders (CGE 2019).
See rules.md (rule IDs), PLAN.md (engine design) and STATUS.md (what is built)."""
from __future__ import annotations

from bgai.game import GameSpec

DEFAULT_OPTIONS = {"allow_resign": False}            # PLAN choice C5


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


def catalog() -> dict:
    """One item per card key (292); count = copies in a 4-player game (starting technologies: one per player)."""
    from .cards import AGE, CARDS, KEY, KIND, NAME, SET, copies
    items, cards = {}, {}
    for c in CARDS:
        i = c["id"]
        count = 4 if c["starting"] else copies(i, 4)
        items[KEY[i]] = {"name": NAME[i], "age": AGE[i], "kind": KIND[i], "set": SET[i], "deck": c["deck"],
                         "tags": {"kind": [KIND[i]], "age": [AGE[i]], "set": [SET[i]]}, "cards": [KEY[i]]}
        cards[KEY[i]] = {"label": NAME[i], "items": [KEY[i]], "count": count}
    return {"items": items, "cards": cards, "count_note": "copies in a 4-player game"}


def invariants(g) -> list:
    from .engine import invariants as inv
    return inv(g)


SPEC = GameSpec(slug="through_the_ages", name="Through the Ages: A New Story of Civilization", players=(2, 3, 4),
                new_game=new_game, action_count=action_count, encoder=encoder, greedy=greedy,
                default_options=dict(DEFAULT_OPTIONS), rounds=lambda g: g.s.round, catalog=catalog,
                invariants=invariants, max_steps=30000)
