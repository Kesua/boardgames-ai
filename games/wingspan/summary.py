"""Wingspan sections of stats.json (shapes from bgai/summary/SHAPES.md; labels are keys into i18n/<lang>.json
"sections"): how winners score, which bonus cards win, round goals, what players do each round, what is left over."""
from __future__ import annotations

import numpy as np
import pandas as pd

CATS = ["birds", "bonus", "goals", "eggs", "cache", "tucked"]


def _se(p, n):
    return float(np.sqrt(max(p * (1 - p), 0) / n)) if n else None


def game_sections(frames: dict, manifest: dict) -> dict:
    seats, actions = frames["seat"], frames["action"]
    base = float(seats["win"].mean())
    win, lose = seats[seats["win"]], seats[~seats["win"]]

    # 1. how winners score: mean points per category, winners vs the rest
    rows = [{"category": c, "winners": float(win["b_" + c].mean()), "others": float(lose["b_" + c].mean())}
            for c in CATS]
    score_mix = {"shape": "table", "title": "score_mix_title", "note": "score_mix_note",
                 "columns": [{"key": "category", "label": "category", "format": "category"},
                             {"key": "winners", "label": "winners", "format": "num1"},
                             {"key": "others", "label": "others", "format": "num1"}],
                 "rows": rows, "bars": {"x": "category", "series": ["winners", "others"]}}

    # 2. bonus cards: win rate of players holding each card
    held = seats[["game_id", "seat", "win", "x_bonus_held", "b_bonus"]].explode("x_bonus_held").dropna(subset=["x_bonus_held"])
    g = held.groupby("x_bonus_held").agg(holders=("win", "size"), win_rate=("win", "mean"),
                                          points=("b_bonus", "mean")).reset_index()
    bonus = {"shape": "table", "title": "bonus_title", "note": "bonus_note",
             "columns": [{"key": "card", "label": "bonus_card", "format": "text"},
                         {"key": "holders", "label": "holders", "format": "int"},
                         {"key": "win_lift", "label": "win_lift", "format": "pp"},
                         {"key": "points", "label": "bonus_points", "format": "num1"}],
             "rows": sorted([{"card": r["x_bonus_held"], "holders": int(r["holders"]),
                              "win_lift": float(r["win_rate"] - base), "win_lift_se": _se(r["win_rate"], r["holders"]),
                              "points": float(r["points"])} for r in g.to_dict("records")],
                            key=lambda r: -r["win_lift"]),
             "facts": [{"label": "bonus_cards_winners", "value": float(win["x_bonus_cards"].mean()), "format": "num2"},
                       {"label": "bonus_cards_others", "value": float(lose["x_bonus_cards"].mean()), "format": "num2"}]}

    # 3. round goals: points per round, winners vs others
    gp = pd.DataFrame(seats["x_goal_points"].tolist(), columns=["r1", "r2", "r3", "r4"])
    gp["win"] = seats["win"].values
    goal_rows = [{"round": i + 1, "winners": float(gp[gp["win"]][f"r{i + 1}"].mean()),
                  "others": float(gp[~gp["win"]][f"r{i + 1}"].mean())} for i in range(4)]
    goals = {"shape": "table", "title": "goals_title", "note": "goals_note",
             "columns": [{"key": "round", "label": "round", "format": "int"},
                         {"key": "winners", "label": "winners", "format": "num2"},
                         {"key": "others", "label": "others", "format": "num2"}],
             "rows": goal_rows, "bars": {"x": "round", "series": ["winners", "others"]}}

    # 4. what players do each round: share of each action, winners vs others
    top = actions[actions["decision"] == "CHOOSE_ACTION"].merge(seats[["game_id", "seat", "win"]], on=["game_id", "seat"])
    t = top.groupby(["x_round", "win", "action"]).size().rename("n").reset_index()
    t["share"] = t["n"] / t.groupby(["x_round", "win"])["n"].transform("sum")
    mix_rows = []
    for (r, w), part in t.groupby(["x_round", "win"]):
        row = {"round": int(r), "who": "winners" if w else "others"}
        for a in ("PLAY_BIRD", "GAIN_FOOD", "LAY_EGGS", "DRAW_CARDS"):
            row[a] = float(part.loc[part["action"] == a, "share"].sum())
        mix_rows.append(row)
    actions_sec = {"shape": "table", "title": "actions_title", "note": "actions_note",
                   "columns": [{"key": "round", "label": "round", "format": "int"},
                               {"key": "who", "label": "who", "format": "label"},
                               {"key": "PLAY_BIRD", "label": "PLAY_BIRD", "format": "pct"},
                               {"key": "GAIN_FOOD", "label": "GAIN_FOOD", "format": "pct"},
                               {"key": "LAY_EGGS", "label": "LAY_EGGS", "format": "pct"},
                               {"key": "DRAW_CARDS", "label": "DRAW_CARDS", "format": "pct"}],
                   "rows": mix_rows}

    # 5. how many birds winners end with, and what is left over
    birds_by = seats.groupby("x_birds").agg(players=("win", "size"), win_rate=("win", "mean")).reset_index()
    board = {"shape": "bars", "title": "birds_title", "note": "birds_note", "x": "birds", "x_format": "int",
             "bars": "players", "line": "win_rate", "line_format": "pct", "baseline": base, "x_label": "birds_x",
             "bar_label": "players_col", "line_label": "win_rate",
             "rows": [{"birds": int(r["x_birds"]), "players": int(r["players"]), "win_rate": float(r["win_rate"])}
                      for r in birds_by.to_dict("records")],
             "facts": [{"label": "birds_winners", "value": float(win["x_birds"].mean()), "format": "num1"},
                       {"label": "birds_others", "value": float(lose["x_birds"].mean()), "format": "num1"},
                       {"label": "food_left_winners", "value": float(win["x_food_left"].mean()), "format": "num1"},
                       {"label": "hand_left_winners", "value": float(win["hand_left"].map(len).mean()), "format": "num1"}]}
    return {"score_mix": score_mix, "bonus": bonus, "goals": goals, "actions": actions_sec, "birds": board}
