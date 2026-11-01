"""Forest Shuffle sections of stats.json: drawing from the clearing, clearing wipes, what makes a game long.

Shapes follow bgai/summary/SHAPES.md so the shared dashboard draws them without game code. Labels are keys into
i18n/<lang>.json "sections".

Clearing wipes are not recorded; they are inferred from the clearing size dropping from >= 8 to <= 1 between two
consecutive actions of a game (Brown Bear, which moves the clearing to the cave, counts too).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WIPE_FROM, WIPE_TO = 8, 1


def _wipes(actions: pd.DataFrame) -> pd.DataFrame:
    a = actions.sort_values(["game_id", "step"])
    nxt = a.groupby("game_id")["x_clearing"].shift(-1)
    hit = a[(a["x_clearing"] >= WIPE_FROM) & (nxt <= WIPE_TO)]
    return hit[["game_id", "step", "turn", "seat"]].reset_index(drop=True)


def _r2(x: np.ndarray, y: np.ndarray) -> float:
    x = np.column_stack([np.ones(len(y)), x])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ coef
    tot = ((y - y.mean()) ** 2).sum()
    return float(1 - (resid ** 2).sum() / tot) if tot else 0.0


def game_sections(frames: dict, manifest: dict) -> dict:
    g, a, seats = frames["game"].copy(), frames["action"], frames["seat"]
    top = a[a["decision"] == "CHOOSE_ACTION"]
    draws = top.groupby(["game_id", "action"]).size().unstack(fill_value=0)
    g["deck_left"] = g["game_id"].map(a.sort_values("step").groupby("game_id")["x_deck"].last())
    g["clear_draws"] = g["game_id"].map(draws.get("DRAW_CLEARING", pd.Series(dtype=int))).fillna(0)
    g["deck_draws"] = g["game_id"].map(draws.get("DRAW_DECK", pd.Series(dtype=int))).fillna(0)
    wipes = _wipes(a)
    g["wipes"] = g["game_id"].map(wipes.groupby("game_id").size()).fillna(0).astype(int)

    # drawing from the clearing: win rate by share of a player's draws taken from the clearing
    d = top.groupby(["game_id", "seat", "action"]).size().unstack(fill_value=0)
    clear = d.get("DRAW_CLEARING", 0)
    total = clear + d.get("DRAW_DECK", 0)
    share = (clear / total.where(total > 0)).rename("share")
    s = seats.join(share, on=["game_id", "seat"]).dropna(subset=["share"])
    s["group"] = np.minimum((s["share"] * 10).astype(int), 9)
    grp = s.groupby("group").agg(seats=("win", "size"), win_rate=("win", "mean"), mean_rank=("rank", "mean"),
                                 mean_score=("score", "mean")).reset_index()
    baseline = float(seats["win"].mean())
    clearing = {"shape": "bars", "title": "clearing_title", "note": "clearing_note",
                "x": "group", "x_format": "decile", "bars": "seats", "line": "win_rate", "line_format": "pct",
                "baseline": baseline, "x_label": "clearing_x", "bar_label": "clearing_bars", "line_label": "win_rate",
                "rows": [{k: (float(v) if k != "group" and k != "seats" else int(v)) for k, v in r.items()}
                         for r in grp.to_dict("records")],
                "facts": [{"label": "clearing_winners", "value": float(s[s["win"]]["share"].mean()), "format": "pct"},
                          {"label": "clearing_losers", "value": float(s[~s["win"]]["share"].mean()), "format": "pct"}]}

    # clearing wipes
    per_seat = wipes.groupby(["game_id", "seat"]).size().rename("triggered")
    w = seats.join(per_seat, on=["game_id", "seat"]).fillna({"triggered": 0})
    w["group"] = np.minimum(w["triggered"].astype(int), 3)
    by = w.groupby("group").agg(seats=("win", "size"), win_rate=("win", "mean"), mean_rank=("rank", "mean")).reset_index()
    wipe_sec = {"shape": "table", "title": "wipes_title", "note": "wipes_note",
                "columns": [{"key": "group", "label": "wipes_triggered", "format": "plus3"},
                            {"key": "seats", "label": "players_col", "format": "int"},
                            {"key": "win_rate", "label": "win_rate", "format": "pct"},
                            {"key": "mean_rank", "label": "mean_rank", "format": "num1"}],
                "rows": [{"group": int(r["group"]), "seats": int(r["seats"]), "win_rate": float(r["win_rate"]),
                          "mean_rank": float(r["mean_rank"])} for r in by.to_dict("records")],
                "facts": [{"label": "wipes_per_game", "value": float(g["wipes"].mean()), "format": "num1"},
                          {"label": "wipes_winners", "value": float(w[w["win"]]["triggered"].mean()), "format": "num2"},
                          {"label": "wipes_losers", "value": float(w[~w["win"]]["triggered"].mean()), "format": "num2"}]}

    # what makes a game long: chance (deck cards left when the third winter card came) vs clearing draws
    y = g["rounds"].to_numpy(float)
    deck = g["deck_left"].to_numpy(float)
    clear_pp = (g["clear_draws"] / g["players"]).to_numpy(float)
    x_edges = list(range(0, int(deck.max()) + 11, 10))
    y_edges = list(range(int(np.floor(y.min() / 5) * 5), int(np.ceil(y.max() / 5) * 5) + 5, 5))
    counts, _, _ = np.histogram2d(deck, y, bins=[x_edges, y_edges])
    drivers = {"shape": "grid", "title": "drivers_title", "note": "drivers_note", "x_label": "drivers_x",
               "y_label": "rounds_per_player", "x_edges": x_edges, "y_edges": y_edges,
               "counts": counts.astype(int).tolist(),
               "facts": [{"label": "r2_deck", "value": _r2(deck, y), "format": "pct"},
                         {"label": "r2_clearing", "value": _r2(clear_pp, y), "format": "pct"},
                         {"label": "r2_both", "value": _r2(np.column_stack([deck, clear_pp]), y), "format": "pct"}]}
    return {"clearing": clearing, "wipes": wipe_sec, "drivers": drivers}
