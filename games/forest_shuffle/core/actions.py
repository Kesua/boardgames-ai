"""Actions and the fixed-size action id codec (built on bgai.kit.CodecBuilder; segment order is frozen)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional

import numpy as np

from bgai.kit import CodecBuilder

from .enums import MAX_WOODY


class ActionKind(str, Enum):
    DRAW_DECK = "DRAW_DECK"
    DRAW_CLEARING = "DRAW_CLEARING"
    PLAY_WOODY = "PLAY_WOODY"
    PLAY_SAPLING = "PLAY_SAPLING"
    PLAY_HALF = "PLAY_HALF"
    PAY = "PAY"
    CHOOSE_CARD = "CHOOSE_CARD"
    CHOOSE_TARGET = "CHOOSE_TARGET"
    USE = "USE"
    SKIP = "SKIP"
    DONE = "DONE"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    card: Optional[int] = None     # def_id
    half: Optional[int] = None     # 0 or 1
    target: Optional[int] = None   # forest index


class ActionCodec:
    def __init__(self, num_play_defs: int, max_woody: int = MAX_WOODY):
        self.n = n = num_play_defs
        self.w = w = max_woody
        self.builder = CodecBuilder([
            (ActionKind.DRAW_DECK, 1), (ActionKind.DRAW_CLEARING, n), (ActionKind.PLAY_WOODY, n),
            (ActionKind.PLAY_SAPLING, n), (ActionKind.PLAY_HALF, 2 * n), (ActionKind.PAY, n),
            (ActionKind.CHOOSE_CARD, n), (ActionKind.CHOOSE_TARGET, w), (ActionKind.USE, 1),
            (ActionKind.SKIP, 1), (ActionKind.DONE, 1)])
        self.base = self.builder.base
        self.size = self.builder.size

    def encode(self, a: Action) -> int:
        if a.kind == ActionKind.PLAY_HALF:
            return self.builder.encode(a.kind, a.card * 2 + a.half)
        if a.kind == ActionKind.CHOOSE_TARGET:
            return self.builder.encode(a.kind, a.target)
        return self.builder.encode(a.kind, a.card if a.card is not None else 0)

    def decode(self, i: int) -> Action:
        kind, off = self.builder.decode(i)
        if kind == ActionKind.PLAY_HALF:
            card, half = divmod(off, 2)
            return Action(kind, card=card, half=half)
        if kind == ActionKind.CHOOSE_TARGET:
            return Action(kind, target=off)
        if self.base[kind][1] == 1:
            return Action(kind)
        return Action(kind, card=off)

    def mask(self, actions: Iterable[Action]) -> np.ndarray:
        return self.builder.mask(self.encode(a) for a in actions)
