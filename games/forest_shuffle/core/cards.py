"""Immutable card definitions loaded from cards.json."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Species:
    key: str
    name: str
    kind: str                      # TREE | SHRUB | DWELLER
    position: Optional[str]        # TOP | BOTTOM | LEFT_RIGHT | None
    expansion: str
    types: tuple
    cost: int
    effect: Optional[dict]
    bonus: Optional[dict]
    scoring: dict
    slot_sharing: Optional[dict] = None
    counts_as: Optional[str] = None
    grants_host_slot_sharing: Optional[dict] = None
    modifiers: Optional[dict] = None
    tree_species: Optional[str] = None
    display_name: Optional[str] = None

    @property
    def label(self) -> str:
        return self.display_name or self.name


@dataclass(frozen=True)
class HalfDef:
    position: str                  # TOP | BOTTOM | LEFT | RIGHT
    species: str
    tree_symbol: str
    extra_types: tuple = ()


@dataclass(frozen=True)
class CardDef:
    def_id: int
    card_code: str
    layout: str                    # WOODY_PLANT | TOP_BOTTOM | LEFT_RIGHT | WINTER
    expansion: str
    count: int
    species: Optional[str] = None
    tree_symbol: Optional[str] = None
    halves: tuple = ()


@dataclass(frozen=True)
class CardInstance:
    uid: int
    def_id: int
