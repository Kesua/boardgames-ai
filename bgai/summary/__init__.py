"""Turn the records of one experiment into stats.json sections. Works for any game through manifest.json terms.

An "item" is what a game scores and what players want to learn about (a card type, a species, a bird). A "board" is
one player's final tableau in one game. Win rate counts ties as wins (bgai.kit.scores). "Win lift" = win rate of
boards that contain the item minus the overall win rate of all boards (the baseline, about 1 / players): positive =
boards with it win more often than average. It is correlation, not cause; every text built on it says so.

Sections (all JSON-safe):
  meta, results, seat_order, items, cards (fate of physical cards), tags, archetypes, length, style, samples, game
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import length as length_mod
from . import style as style_mod


def records(df: pd.DataFrame) -> list:
    """DataFrame -> JSON-safe list of dicts (NaN -> null)."""
    return json.loads(df.to_json(orient="records", double_precision=6))


def _se(p: pd.Series, n: pd.Series) -> pd.Series:
    return np.sqrt((p * (1 - p)).clip(lower=0) / n.where(n > 0))


def group_stats(items: pd.DataFrame, seats: pd.DataFrame, key: str) -> pd.DataFrame:
    """Presence, win and points metrics per value of `key` (item or a tag column)."""
    baseline = seats["win"].mean()
    c = items.dropna(subset=[key])
    per_seat = c.groupby(["game_id", "seat", key]).agg(
        copies=("points", "size"), points=("points", "sum"), win=("win", "first"), score=("score", "first")).reset_index()
    g = per_seat.groupby(key).agg(
        boards_with=("copies", "size"), copies_per_board=("copies", "mean"), win_rate=("win", "mean"),
        mean_owner_score=("score", "mean"), points_per_board=("points", "mean")).reset_index()
    g["presence_rate"] = g["boards_with"] / len(seats)
    g["points_per_copy"] = g["points_per_board"] / g["copies_per_board"]
    g["win_lift"] = g["win_rate"] - baseline
    g["win_lift_se"] = _se(g["win_rate"], g["boards_with"])
    total = items["points"].sum()
    pts = c.groupby(key)["points"].sum().rename("total_points")
    g = g.join(pts, on=key)
    g["points_share"] = g["total_points"] / total if total else 0.0
    return g.drop(columns=["total_points"]).sort_values("win_lift", ascending=False)


def winner_edge(items: pd.DataFrame, seats: pd.DataFrame, key: str = "item") -> pd.DataFrame:
    """Per item, over games with both a winner and a loser: mean over those games of (mean copies on winners' boards -
    mean copies on losers' boards), games without the item counting 0. Same deal and same game length on both sides,
    so unlike win lift it does not credit an item for coming up in long games."""
    s = seats[["game_id", "seat", "win"]]
    side = s.groupby("game_id")["win"].agg(["any", "all"])
    mixed = side.index[side["any"] & ~side["all"]]
    s = s[s["game_id"].isin(mixed)]
    n_games = s["game_id"].nunique()
    copies = items[items["game_id"].isin(mixed)].dropna(subset=[key]).groupby(
        ["game_id", "seat", key]).size().rename("n").reset_index()
    if copies.empty or not n_games:
        return pd.DataFrame(columns=[key, "winner_edge", "edge_games"])
    grid = copies[["game_id", key]].drop_duplicates().merge(s, on="game_id")
    grid = grid.merge(copies, on=["game_id", "seat", key], how="left").fillna({"n": 0})
    by_side = grid.groupby([key, "game_id", "win"])["n"].mean().unstack("win")
    diff = (by_side[True] - by_side[False]).rename("diff").reset_index()
    out = diff.groupby(key).agg(edge_sum=("diff", "sum"), edge_games=("diff", "size")).reset_index()
    out["winner_edge"] = out["edge_sum"] / n_games
    return out[[key, "winner_edge", "edge_games"]]


def card_fate(actions: pd.DataFrame, seats: pd.DataFrame, fate: dict) -> pd.DataFrame:
    """Per physical card: how often it was played, used otherwise (fate names from the manifest), left in hand."""
    parts = []
    for name, kinds in fate.items():
        parts.append(actions[actions["action"].isin(kinds)].groupby("card").size().rename(name))
    left = seats.explode("hand_left").dropna(subset=["hand_left"]).groupby("hand_left").size().rename("left_in_hand")
    left.index = left.index.rename("card")
    df = pd.concat(parts + [left], axis=1).fillna(0).astype(int).reset_index().rename(columns={"index": "card"})
    cols = list(fate) + ["left_in_hand"]
    for c in cols:
        if c not in df:
            df[c] = 0
    seen = df[cols].sum(axis=1)
    first = list(fate)[0]
    df["play_share"] = df[first] / seen.where(seen > 0, 1)
    return df.sort_values("play_share", ascending=False)


def board_archetypes(items: pd.DataFrame, seats: pd.DataFrame, arch: dict) -> pd.DataFrame:
    """Archetype per board: its most frequent value of the manifest's archetype tag (extra counts from seat numbers,
    e.g. saplings, count as cards of that value); MIXED on a tie or below min_share, NONE without tags."""
    col = "tag_" + arch["tag"]
    counts = items.dropna(subset=[col]).groupby(["game_id", "seat", col]).size().rename("n").reset_index()
    counts = counts.rename(columns={col: "value"})
    for value, seat_col in (arch.get("extra_counts") or {}).items():
        x = seats.loc[seats["x_" + seat_col] > 0, ["game_id", "seat", "x_" + seat_col]].rename(columns={"x_" + seat_col: "n"})
        counts = pd.concat([counts, x.assign(value=value)], ignore_index=True)
    counts["share"] = counts["n"] / counts.groupby(["game_id", "seat"])["n"].transform("sum")
    counts = counts.sort_values(["game_id", "seat", "n"], ascending=[True, True, False])
    counts["rank"] = counts.groupby(["game_id", "seat"]).cumcount()
    first = counts[counts["rank"] == 0].set_index(["game_id", "seat"])
    second = counts[counts["rank"] == 1].set_index(["game_id", "seat"])["n"].reindex(first.index)
    label = first["value"].where((first["share"] >= arch.get("min_share", 0.0)) & (first["n"] != second), "MIXED")
    out = seats[["game_id", "seat", "agent", "win", "score", "rank"]].join(label.rename("archetype"), on=["game_id", "seat"])
    out["archetype"] = out["archetype"].fillna("NONE")
    return out


def archetype_stats(boards: pd.DataFrame, seats: pd.DataFrame) -> pd.DataFrame:
    g = boards.groupby("archetype").agg(boards=("win", "size"), win_rate=("win", "mean"),
                                        mean_score=("score", "mean")).reset_index()
    g["share"] = g["boards"] / g["boards"].sum()
    g["win_lift"] = g["win_rate"] - seats["win"].mean()
    g["win_lift_se"] = _se(g["win_rate"], g["boards"])
    return g.sort_values("win_lift", ascending=False)


def results(seats: pd.DataFrame) -> pd.DataFrame:
    agents = seats.groupby("agent").agg(seats=("win", "size"), win_rate=("win", "mean"), mean_score=("score", "mean"),
                                        mean_rank=("rank", "mean")).reset_index()
    ranks = seats.groupby("agent")["rank"].value_counts(normalize=True).unstack(fill_value=0)
    ranks.columns = [f"rank_{int(c)}" for c in ranks.columns]
    return agents.join(ranks, on="agent")


def seat_order(seats: pd.DataFrame) -> pd.DataFrame:
    """Seat 0 moves first; seat order rotates agents every game, so this isolates the turn-order effect."""
    return seats.groupby("seat").agg(seats=("win", "size"), win_rate=("win", "mean"), mean_score=("score", "mean"),
                                     mean_rank=("rank", "mean")).reset_index()


def _clean(v):
    """pandas NaN / numpy numbers -> JSON-safe Python values (NaN becomes None)."""
    if v is None:
        return None
    try:
        if v != v:
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(v, "item"):
        return v.item()
    return v


def samples(frames: dict, n_top: int = 4, n_mid: int = 3, n_low: int = 3) -> list:
    """About 10 final boards per experiment: highest, middle and lowest winner scores; all seats of those games."""
    g = frames["game"].copy()
    g["best"] = g["scores"].map(max)
    g = g.sort_values(["best", "game_id"], ascending=[False, True]).reset_index(drop=True)
    mid = len(g) // 2
    picks = list(range(min(n_top, len(g)))) + list(range(max(0, mid - n_mid // 2), min(len(g), mid - n_mid // 2 + n_mid))) \
        + list(range(max(0, len(g) - n_low), len(g)))
    picks = sorted(set(picks))
    seats, items = frames["seat"], frames["item"]
    out = []
    for i in picks:
        row = g.iloc[i]
        gid = int(row["game_id"])
        boards = []
        for s in seats[seats["game_id"] == gid].sort_values("seat").to_dict("records"):
            rows = items[(items["game_id"] == gid) & (items["seat"] == s["seat"])]
            tag_cols = [c for c in rows.columns if c.startswith("tag_")]
            boards.append({
                "seat": int(s["seat"]), "agent": s["agent"], "score": int(s["score"]), "rank": int(s["rank"]),
                "win": bool(s["win"]), "breakdown": {k[2:]: v for k, v in s.items() if k.startswith("b_")},
                "extra": {k[2:]: _clean(v) for k, v in s.items() if k.startswith("x_") and not isinstance(v, list)},
                "hand_left": list(s.get("hand_left") or []),
                "items": [{"item": _clean(r["item"]), "kind": _clean(r["kind"]), "group": _clean(r["group"]),
                           "slot": _clean(r["slot"]), "host": _clean(r["host"]), "points": int(r["points"]),
                           "tags": {c[4:]: _clean(r[c]) for c in tag_cols if _clean(r[c]) is not None}}
                          for r in rows.to_dict("records")]})
        out.append({"game_id": gid, "seed": int(row["seed"]) if row.get("seed") is not None else None,
                    "turns": int(row["turns"]), "rounds": float(row["rounds"]), "scores": list(row["scores"]),
                    "position": "top" if i < n_top else "bottom" if i >= len(g) - n_low else "middle",
                    "boards": boards})
    return out


def build_stats(frames: dict, spec, manifest: dict) -> dict:
    seats, items, actions, games = frames["seat"], frames["item"], frames["action"], frames["game"]
    item_stats = group_stats(items, seats, "item").merge(winner_edge(items, seats), on="item", how="left")
    tags = {}
    for kind in manifest.get("tags", {}):
        col = "tag_" + kind
        if col in items:
            tags[kind] = records(group_stats(items, seats, col).rename(columns={col: "value"}))
    out = {
        "meta": {"players": int(games["players"].iloc[0]), "games": len(games), "boards": len(seats),
                 "agents": sorted(seats["agent"].unique()), "mirror": seats["agent"].nunique() == 1,
                 "baseline_win_rate": float(seats["win"].mean()), "mean_turns": float(games["turns"].mean()),
                 "rounds_mean": float(games["rounds"].mean()), "rounds_min": float(games["rounds"].min()),
                 "rounds_max": float(games["rounds"].max()), "best_score": int(seats["score"].max()),
                 "winner_score": float(games["scores"].map(max).mean()),
                 "loser_score": float(games["scores"].map(min).mean()),
                 "mean_score": float(seats["score"].mean()),
                 "ties": float((games["winners"].map(len) > 1).mean())},
        "results": records(results(seats)),
        "seat_order": records(seat_order(seats)),
        "items": records(item_stats),
        "tags": tags,
        "style": style_mod.report(frames, manifest),
        "samples": samples(frames),
    }
    if manifest.get("fate"):
        out["cards"] = records(card_fate(actions, seats, manifest["fate"]))
    if manifest.get("archetype"):
        boards = board_archetypes(items, seats, manifest["archetype"])
        out["archetypes"] = records(archetype_stats(boards, seats))
    else:
        boards = None
    if manifest.get("length", {}).get("show", True) and games["rounds"].nunique() > 1:
        out["length"] = length_mod.report(frames, boards)
    if spec.summary:
        out["game"] = spec.summary(frames, manifest)
    return out
