"""Fixed action numbering built from declared choice lists.

A game declares its choices once, in order, as (name, size) segments, e.g. [("DRAW_DECK", 1), ("PLAY", n_cards),
("TARGET", 40)]. Every possible answer to every decision then has one fixed number in [0, size). The agent's network
has one output per number; a mask marks the legal ones. Numbers never change while a game's models exist, so the
segment list is part of the game's frozen contract.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


class CodecBuilder:
    def __init__(self, segments: list):
        self.segments = list(segments)
        self.base: dict = {}
        pos = 0
        for name, size in self.segments:
            if name in self.base:
                raise ValueError(f"duplicate segment {name}")
            if size < 1:
                raise ValueError(f"segment {name} needs size >= 1")
            self.base[name] = (pos, size)
            pos += size
        self.size = pos

    def encode(self, name: str, offset: int = 0) -> int:
        b, size = self.base[name]
        if not 0 <= offset < size:
            raise IndexError(f"{name}: offset {offset} outside 0..{size - 1}")
        return b + offset

    def decode(self, action_id: int) -> tuple:
        """(segment name, offset) of an action number."""
        for name, (b, size) in self.base.items():
            if b <= action_id < b + size:
                return name, action_id - b
        raise IndexError(action_id)

    def mask(self, ids: Iterable[int]) -> np.ndarray:
        m = np.zeros(self.size, dtype=bool)
        for i in ids:
            m[i] = True
        return m
