"""TEMPLATE — a tiny, complete game that shows every part a game needs. The new-game skill copies this folder.

Toy rules ("Market", rules.md here): a deck of cards numbered 1..15 in three colours. Each turn the player takes one
of the 3 face-up market cards or the deck's top card. When the deck and market are empty the game ends. Score = the
sum of the numbers taken + 5 for each colour of which the player holds at least 3 cards.

Replace everything game-specific; keep the shape: SPEC, engine with the bgai.game.Game methods, encoder, greedy,
manifest.json, rules.md with rule IDs, tests marked with @pytest.mark.rule.
"""
from __future__ import annotations

from bgai.game import GameSpec

from .engine import CODEC, Game, invariants


def new_game(num_players: int, seed: int, options: dict = None):
    return Game(num_players, seed).reset()


def encoder(num_players: int, version: int = None):
    from .encoder import StateEncoder
    return StateEncoder(num_players)


def greedy(seed: int = None):
    from .agents import GreedyAgent
    return GreedyAgent(seed)


SPEC = GameSpec(slug="_template", name="Template (toy market game)", players=(2, 3, 4), new_game=new_game,
                action_count=lambda n: CODEC.size, encoder=encoder, greedy=greedy, rounds=lambda g: 1.0,
                invariants=invariants, max_steps=200)
