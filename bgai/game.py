"""The contract between the shared platform and a game.

Every game package games/<slug>/ exposes `SPEC = GameSpec(...)`. The platform (training, experiments, summaries,
checks, dashboard build) only talks to a game through `GameSpec` and the `Game` protocol below. Keep this file
small: a new requirement here is a change for every game.

Action numbers: every answer to every decision has one fixed number in [0, spec.action_count(players)) (build them
with bgai.kit.CodecBuilder). `legal_ids()` lists the legal numbers for the decision at hand, in a fixed order.

Determinism: `spec.new_game(players, seed, options)` plus the same sequence of action numbers must always give the
same game. All randomness comes from the game's own seeded random source.

Score direction: scores() must be HIGHER-IS-BETTER, because winners, ranks and the training reward all take the
maximum. For a game where the lowest score wins, return the negated official score (and say so in rules.md and the
manifest's intro). bgai.checks fails when the greedy agent does not clearly beat random players, which catches an
inverted score.

Recorded fields (bgai/records.py turns them into rows; bgai/summary into statistics):
  card    a physical card's id (a split card is one card carrying two items)
  item    the thing that is scored and analysed: a species, bird or tile key (keys of catalog()["items"])
  kind    an item's role on the board (TREE, DWELLER, BIRD ...), free text per game
  group   where on the board: a habitat row, a tree slot side; slot = position inside the group (int or None)
  host    the item this one is attached to (Forest Shuffle dweller -> its tree), else None
  points  whole points this item scored at the end; per seat the tableau points need not sum to the score
          (bonus cards, goals and leftovers are breakdown categories without a tableau row)
  tags    {tag name: value} (tag names from the manifest), e.g. {"habitat": "FOREST"}; become tag_<name> columns
  extra   {key: number} per action, become x_<key> columns
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol


class Game(Protocol):
    num_players: int

    # --- flow
    @property
    def current_seat(self) -> int: ...            # who answers the decision at hand (may differ from turn owner)
    @property
    def game_over(self) -> bool: ...
    @property
    def turns(self) -> int: ...                   # turns completed so far, all players together
    def legal_ids(self) -> list: ...              # legal action numbers, fixed order
    def step_id(self, action_id: int) -> None: ...
    def clone(self) -> "Game": ...                # independent copy, random state included

    # --- results
    def scores(self) -> list: ...                 # final (or current) score per seat
    def tiebreaks(self) -> Optional[list]: ...    # official tiebreak value per seat (higher wins) or None
    def breakdowns(self) -> list: ...             # per seat {category: points}; categories from the manifest

    # --- recording and reviewing
    def record_info(self, action_id: int) -> dict: ...
    #   called BEFORE step_id; returns {"decision": kind, "decision_label": str|None, "action": kind,
    #   "card": physical card id|None, "item": scored item key|None, "tags": {tag_kind: value}, "extra": {...}}
    def tableau(self, seat: int) -> list: ...
    #   final board rows: {"item", "kind", "group", "slot", "points", "tags": {...}, "host"}
    def seat_extra(self, seat: int) -> dict: ...  # per-seat end-of-game numbers, plus "hand_left": [card ids]
    def describe(self, action_id: int) -> str: ...
    def text_state(self) -> str: ...
    # --- optional
    # def drain_forced(self) -> list: ...
    #   When the game applies a decision with only one legal answer by itself, it must still report it, or the
    #   statistics miss those moves (e.g. a card "played" without a choice). Return and forget the moves applied
    #   since the last call, each a record_info() dict plus "seat"; bgai.records writes them with forced=true.
    #   Games that never auto-apply decisions do not need it.


@dataclass
class GameSpec:
    """What the platform needs to run a game. Callables keep games free to structure their code."""
    slug: str
    name: str
    players: tuple                                      # supported player counts
    new_game: Callable                                  # (num_players, seed, options) -> Game, ready to play
    action_count: Callable                              # (num_players) -> int
    encoder: Callable                                   # (num_players, version=None) -> Encoder (.size, .version, .encode(game, seat))
    greedy: Callable                                    # (seed) -> Agent with .act(game, seat) -> action number
    default_options: dict = field(default_factory=dict)
    rounds: Optional[Callable] = None                   # (game) -> rounds per player; default turns / players.
                                                        # Fixed-length games may return a constant (this also hides
                                                        # the game-length section, which needs varying lengths)
    summary: Optional[Callable] = None                  # (frames, manifest) -> {section: shape}; game-specific stats
    catalog: Optional[Callable] = None                  # () -> {"items": {key: {attributes..., "cards": [card ids]}},
                                                        #        "cards": {card id: {"label": str, "items": [keys]}}}
    invariants: Optional[Callable] = None               # (game) -> list of problems (card conservation, limits ...)
    max_steps: int = 5000                               # safety cap on decisions per game
    encoder_versions: tuple = ()                        # older observation versions still loadable (newest first);
                                                        # a newer version must extend an older one as a prefix


def load_spec(slug: str) -> GameSpec:
    return importlib.import_module(f"games.{slug}").SPEC


def rounds_of(spec: GameSpec, game) -> float:
    return spec.rounds(game) if spec.rounds else game.turns / game.num_players
