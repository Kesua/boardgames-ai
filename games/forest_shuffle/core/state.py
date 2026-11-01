"""Mutable game state."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bgai.kit import Decision, DecisionStack, TextLog

from .cards import CardDef, CardInstance, HalfDef
from .enums import SLOTS


@dataclass
class PlacedDweller:
    uid: int
    species: str
    tree_symbol: str
    types: tuple
    position: str
    placed_turn: int = 0


@dataclass
class PlacedWoody:
    uid: Optional[int]                 # None for a sapling
    species: Optional[str]             # None for a sapling
    kind: str                          # TREE | SHRUB
    tree_symbol: Optional[str]
    types: tuple
    placed_turn: int
    slots: dict = field(default_factory=lambda: {s: [] for s in SLOTS})

    def dwellers(self) -> list:
        return [d for s in SLOTS for d in self.slots[s]]

    def is_fully_occupied(self) -> bool:
        return all(self.slots[s] for s in SLOTS)


@dataclass
class PlayerState:
    seat: int
    hand: list = field(default_factory=list)
    forest: list = field(default_factory=list)
    cave: list = field(default_factory=list)
    mulligan_used: bool = False
    known: set = field(default_factory=set)     # uids of hand cards taken from the clearing (public)


@dataclass
class GameState:
    players: list
    deck: list
    clearing: list
    removed: list
    winter_revealed: int = 0
    current: int = 0
    turn_index: int = 0
    extra_turns: int = 0
    decisions: DecisionStack = field(default_factory=DecisionStack)     # stack, top = last
    game_over: bool = False
    log: TextLog = field(default_factory=TextLog)


def make_dweller(db, uid: int, half: HalfDef, turn: int = 0) -> PlacedDweller:
    sp = db.species[half.species]
    return PlacedDweller(uid=uid, species=half.species, tree_symbol=half.tree_symbol,
                         types=tuple(sp.types) + tuple(half.extra_types), position=half.position, placed_turn=turn)


def make_woody(db, uid: int, card_def: CardDef, turn: int) -> PlacedWoody:
    sp = db.species[card_def.species]
    return PlacedWoody(uid=uid, species=card_def.species, kind=sp.kind, tree_symbol=card_def.tree_symbol,
                       types=tuple(sp.types), placed_turn=turn)


def make_sapling(turn: int) -> PlacedWoody:
    return PlacedWoody(uid=None, species=None, kind="TREE", tree_symbol=None, types=("TREE",), placed_turn=turn)
