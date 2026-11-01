"""How the agents play, from recorded actions and final boards. Every table is keyed by agent."""
from __future__ import annotations

import re

import pandas as pd


def outcome(frames: dict) -> pd.DataFrame:
    """Win rate, score, mean points per score category (b_*) and mean seat numbers (x_*) per agent."""
    seat = frames["seat"]
    num = [c for c in seat.columns if (c.startswith("b_") or c.startswith("x_")) and pd.api.types.is_numeric_dtype(seat[c])]
    g = seat.groupby("agent").agg(seats=("win", "size"), win_rate=("win", "mean"), score=("score", "mean"),
                                  **{c: (c, "mean") for c in num})
    g["hand_left"] = seat.groupby("agent")["hand_left"].apply(lambda s: s.map(len).mean())
    return g.reset_index()


def action_mix(frames: dict, top_decision: str) -> pd.DataFrame:
    """Share of each top-level choice per agent (long format: agent, action, share)."""
    top = frames["action"][frames["action"]["decision"] == top_decision]
    t = top.groupby(["agent", "action"]).size().rename("n").reset_index()
    t["share"] = t["n"] / t.groupby("agent")["n"].transform("sum")
    return t


def optional_use(frames: dict, opt: dict) -> tuple:
    """Use rate of optional effects (decision kind opt['decision'], answers opt['use'] / opt['skip'])."""
    a = frames["action"]
    us = a[a["decision"] == opt["decision"]].copy()
    if us.empty:
        return pd.DataFrame(), pd.DataFrame()
    pattern = opt.get("group_pattern")
    if pattern:
        us["what"] = us["decision_label"].fillna("").map(lambda s: (re.match(pattern, s).group(1)
                                                                     if re.match(pattern, s) else "other"))
        for k, v in (opt.get("group_rename") or {}).items():
            us["what"] = us["what"].where(~us["what"].str.contains(k), v)
    else:
        us["what"] = "all"
    t = us.groupby(["agent", "what", "action"]).size().unstack(fill_value=0)
    for col in (opt["use"], opt["skip"]):
        if col not in t:
            t[col] = 0
    t = t.rename(columns={opt["use"]: "use", opt["skip"]: "skip"})
    t["use_rate"] = t["use"] / (t["use"] + t["skip"]).where(lambda s: s > 0, 1)
    sk = us[us["action"] == opt["skip"]]
    skipped = sk.groupby(["agent", "decision_label"]).size().rename("skips").reset_index()
    skipped = skipped.sort_values(["agent", "skips"], ascending=[True, False]).groupby("agent").head(6)
    return t[["use", "skip", "use_rate"]].reset_index(), skipped


def items_played(frames: dict, play_kinds: list, top: int = 15) -> pd.DataFrame:
    a = frames["action"]
    pl = a[a["action"].isin(play_kinds) & a["item"].notna()]
    s = pl.groupby(["agent", "item"]).size().rename("plays").reset_index()
    s["share"] = s["plays"] / s.groupby("agent")["plays"].transform("sum")
    return s.sort_values(["agent", "share"], ascending=[True, False]).groupby("agent").head(top)


def pay_vs_play(frames: dict, fate: dict, min_seen: int = 20) -> pd.DataFrame:
    """Per agent and physical card: times played vs used otherwise (second fate group, e.g. paid away)."""
    names = list(fate)
    if len(names) < 2:
        return pd.DataFrame()
    a = frames["action"]
    played = a[a["action"].isin(fate[names[0]])].groupby(["agent", "card"]).size().rename("played")
    other = a[a["action"].isin(fate[names[-1]])].groupby(["agent", "card"]).size().rename("other")
    pp = pd.concat([other, played], axis=1).fillna(0).astype(int)
    pp = pp[pp["other"] + pp["played"] >= min_seen].copy()
    pp["other_share"] = pp["other"] / (pp["other"] + pp["played"])
    return pp.reset_index().sort_values(["agent", "other_share"], ascending=[True, False])


def points_by_item(frames: dict, top: int = 15) -> pd.DataFrame:
    items, seat = frames["item"], frames["seat"]
    pts = items.groupby(["agent", "item"])["points"].sum().rename("points").reset_index()
    pts = pts.join(seat.groupby("agent").size().rename("boards"), on="agent")
    pts["points_per_board"] = pts["points"] / pts["boards"]
    return pts.sort_values(["agent", "points_per_board"], ascending=[True, False]).groupby("agent").head(top)


def tag_mix(frames: dict, kind: str) -> pd.DataFrame:
    col = "tag_" + kind
    items = frames["item"]
    if col not in items:
        return pd.DataFrame()
    t = items.dropna(subset=[col]).groupby(["agent", col]).size().rename("n").reset_index().rename(columns={col: "value"})
    t["share"] = t["n"] / t.groupby("agent")["n"].transform("sum")
    return t


def play_timing(frames: dict, play_kinds: list) -> pd.DataFrame:
    a = frames["action"]
    pl = a[a["action"].isin(play_kinds)]
    if pl.empty:
        return pd.DataFrame()
    q = pl.groupby("agent")["turn"].describe()[["25%", "50%", "75%", "max"]]
    q.columns = ["q25", "median", "q75", "max"]
    return q.reset_index()


def report(frames: dict, manifest: dict) -> dict:
    from . import records
    fate = manifest.get("fate") or {}
    play_kinds = fate.get(list(fate)[0], []) if fate else []
    out = {"outcome": records(outcome(frames)),
           "action_mix": records(action_mix(frames, manifest.get("top_decision", "CHOOSE_ACTION"))),
           "items_played": records(items_played(frames, play_kinds)),
           "points_by_item": records(points_by_item(frames)),
           "play_timing": records(play_timing(frames, play_kinds))}
    if len(fate) >= 2:
        out["pay_vs_play"] = records(pay_vs_play(frames, fate))
    if manifest.get("optional_decisions"):
        use, skipped = optional_use(frames, manifest["optional_decisions"])
        out["optional_use"] = records(use)
        out["top_skipped"] = records(skipped)
    for kind in manifest.get("tags", {}):
        out.setdefault("tag_mix", {})[kind] = records(tag_mix(frames, kind))
    return out
