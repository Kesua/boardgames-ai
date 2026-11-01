"""Shared mechanics kit: small parts that mean the same thing in every game.

Rules (spec section 2, also in bgai/kit/README.md):
1. Extract, don't design: a part joins only when a second game needs the same behaviour.
2. No options for game-specific behaviour; a game that needs something different writes its own part.
3. Optional: games may use these parts; the game interface (bgai.game) is the only contract.
4. Frozen behaviour: tests/test_kit.py pins every output, including random draw order. A behaviour change is a new
   part (e.g. Deck2) or a regeneration of every experiment of every game that uses it.
5. Speed: no callbacks or option checks on hot paths.
"""
from .codec import CodecBuilder
from .decisions import Decision, DecisionStack
from .deck import Deck, Rng
from .encoding import add_counts, one_hot
from .scores import ranks, winners
from .textlog import TextLog

__all__ = ["CodecBuilder", "Decision", "DecisionStack", "Deck", "Rng", "add_counts", "one_hot", "ranks", "winners",
           "TextLog"]
