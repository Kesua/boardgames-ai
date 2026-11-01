"""Small helpers for writing a game state into the agent's observation vector (a float32 numpy array)."""
from __future__ import annotations

from typing import Iterable

import numpy as np


def add_counts(v: np.ndarray, offset: int, indices: Iterable[int], scale: float, limit: int = None) -> None:
    """For each index i: v[offset + i] += scale. Indices >= limit (when given) are skipped."""
    for i in indices:
        if limit is None or i < limit:
            v[offset + i] += scale


def one_hot(v: np.ndarray, offset: int, index: int) -> None:
    v[offset + index] = 1.0
