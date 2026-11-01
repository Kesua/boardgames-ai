"""Effect of items and board archetypes by game length (only for games whose length varies).

Length is rounds per player (turns / players unless the game defines it), so 2- and 4-player experiments compare.
Games are split into five equal-size groups by length (quintiles of the rank, so ties do not merge groups).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N_BINS = 5


def game_table(games: pd.DataFrame) -> pd.DataFrame:
    g = games.copy()
    g["bin"] = pd.qcut(g["rounds"].rank(method="first"), min(N_BINS, len(g)), labels=False)
    g["winner_score"] = g["scores"].map(max)
    return g


def bins(games: pd.DataFrame, seats: pd.DataFrame) -> pd.DataFrame:
    s = seats.merge(games[["game_id", "bin"]], on="game_id")
    b = games.groupby("bin").agg(rounds_min=("rounds", "min"), rounds_max=("rounds", "max"), rounds_mean=("rounds", "mean"),
                                 turns_min=("turns", "min"), turns_max=("turns", "max"), games=("game_id", "size"),
                                 winner_score=("winner_score", "mean"))
    b = b.join(s.groupby("bin").agg(baseline_win=("win", "mean"), mean_rank=("rank", "mean")))
    return b.reset_index()


def by_length(boards: pd.DataFrame, seats: pd.DataFrame, games: pd.DataFrame, key: str) -> pd.DataFrame:
    """Per (item or archetype, length group): boards, win rate, win lift, mean rank, placement gain."""
    s = seats.merge(games[["game_id", "bin"]], on="game_id")
    base = s.groupby("bin").agg(baseline_win=("win", "mean"), bin_rank=("rank", "mean"))
    f = boards[["game_id", "seat", key]].drop_duplicates()
    f = f.merge(s[["game_id", "seat", "bin", "win", "rank"]], on=["game_id", "seat"])
    t = f.groupby([key, "bin"]).agg(boards=("win", "size"), win_rate=("win", "mean"), mean_rank=("rank", "mean")).reset_index()
    t = t.join(base, on="bin")
    t["win_lift"] = t["win_rate"] - t["baseline_win"]
    t["place_gain"] = t["bin_rank"] - t["mean_rank"]
    return t.drop(columns=["bin_rank"])


def default_items(table: pd.DataFrame, n: int = 6, min_boards: int = 100) -> list:
    """Items with >= min_boards in the shortest and longest group whose win rate changes most reliably between them
    (change divided by its standard error, so rare items with noisy swings do not crowd out real trends)."""
    lo, hi = table["bin"].min(), table["bin"].max()
    cols = ["win_rate", "boards"]
    first = table[(table["bin"] == lo) & (table["boards"] >= min_boards)].set_index("item")[cols]
    last = table[(table["bin"] == hi) & (table["boards"] >= min_boards)].set_index("item")[cols]
    both = first.join(last, lsuffix="_lo", rsuffix="_hi", how="inner")
    var = lambda p, k: (p * (1 - p)).clip(lower=0.01 * 0.99) / k
    se = np.sqrt(var(both["win_rate_lo"], both["boards_lo"]) + var(both["win_rate_hi"], both["boards_hi"]))
    z = (both["win_rate_hi"] - both["win_rate_lo"]) / se
    return list(z.abs().sort_values(ascending=False).index[:n])


def report(frames: dict, archetype_boards) -> dict:
    from . import records
    games = game_table(frames["game"])
    seats, items = frames["seat"], frames["item"]
    per_item = by_length(items, seats, games, "item")
    hist = games["rounds"].round().astype(int).value_counts().sort_index()
    out = {"bins": records(bins(games, seats)), "items": records(per_item), "default_items": default_items(per_item),
           "histogram": [{"rounds": int(r), "games": int(n)} for r, n in hist.items()]}
    if archetype_boards is not None:
        out["archetypes"] = records(by_length(archetype_boards, seats, games, "archetype"))
    return out
