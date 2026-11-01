"""Publish a trained model into games/<slug>/models/<id>/ and measure its strength card.

python -m bgai.models publish --game <slug> --id <model id> --players 2 --checkpoint runs/<slug>/anchored/p2/ppo_best.zip \
    --logs runs/<slug>/open/p2/train_log.csv runs/<slug>/anchored/p2/train_log.csv --recipe "<command>" "<command>"
python -m bgai.models accept --game <slug> --id <model id> --vs <checkpoint or model id> [--vs ...] --deals 750

A model folder holds model.zip (the trainer checkpoint: the actor that picks moves plus the value network, so
training can resume), model.json (recipe, sha256, strength card) and the training logs. The strength card is the
acceptance test of the training recipe (train-model skill): paired games on the same deals against models it never
trained against, the previous finished model, and greedy. A model counts as finished when the card says so.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from .experiment import ROOT, code_commit, game_dir, sha256_file

MAX_BYTES = 50 * 2 ** 20                     # GitHub warns above 50 MB; models must stay below


def model_dir(slug: str, model_id: str) -> Path:
    return game_dir(slug) / "models" / model_id


def read(slug: str, model_id: str) -> dict:
    return json.loads((model_dir(slug, model_id) / "model.json").read_text(encoding="utf-8"))


def write(slug: str, model_id: str, meta: dict) -> None:
    (model_dir(slug, model_id) / "model.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def publish(slug, model_id, players, checkpoint, logs, recipe, notes=None, hours=None, hardware=None):
    from sb3_contrib import MaskablePPO
    d = model_dir(slug, model_id)
    d.mkdir(parents=True, exist_ok=True)
    m = MaskablePPO.load(checkpoint, device="cpu")
    m.policy.optimizer = m.policy.optimizer_class(m.policy.parameters(), lr=2.5e-4, **m.policy.optimizer_kwargs)
    m.save(d / "model.zip")                  # empty optimizer state: resumable, small
    if (d / "model.zip").stat().st_size > MAX_BYTES:
        raise SystemExit("model.zip is over 50 MB")
    for i, log in enumerate(logs or []):
        shutil.copyfile(log, d / (f"train_log_{i + 1}.csv" if len(logs) > 1 else "train_log.csv"))
    meta = {"id": model_id, "game": slug, "players": players, "sha256": sha256_file(d / "model.zip"),
            "observation_size": int(m.observation_space.shape[0]), "action_count": int(m.action_space.n),
            "checkpoint": str(checkpoint), "recipe": recipe or [], "logs": sorted(p.name for p in d.glob("train_log*.csv")),
            "code_commit": code_commit(), "hours": hours, "hardware": hardware, "notes": notes,
            "published": time.strftime("%Y-%m-%d"), "strength": {"finished": False, "games": []}}
    write(slug, model_id, meta)
    return d


def accept(slug, model_id, opponents, deals, workers, labels=None, required=None):
    """Paired games against each opponent; appends the results to the strength card."""
    from .rl.h2h import match, summary
    meta = read(slug, model_id)
    me = str(model_dir(slug, model_id) / "model.zip")
    rows = []
    for k, opp in enumerate(opponents):
        path = opp if opp in ("random", "greedy") or opp.endswith(".zip") else str(model_dir(slug, opp) / "model.zip")
        n = deals if opp not in ("random", "greedy") else max(1, deals * 2 // 3)
        s = summary(match(slug, me, path, meta["players"], range(20000, 20000 + n), workers))
        row = {"opponent": opp, "label": (labels or [None] * len(opponents))[k], "games": s["games"],
               "win": round(s["win"], 4), "win_se": round(s["win_se"], 4), "margin": round(s["margin"], 2),
               "margin_se": round(s["margin_se"], 2), "score": round(s["score"], 1), "other": round(s["other"], 1),
               "required": (required or [None] * len(opponents))[k]}
        print(row)
        rows.append(row)
    card = meta.setdefault("strength", {"games": []})
    card["games"] = [r for r in card.get("games", []) if r["opponent"] not in opponents] + rows
    card["finished"] = all(_passes(r) for r in card["games"] if r.get("required"))
    card["measured"] = time.strftime("%Y-%m-%d")
    write(slug, model_id, meta)
    return card


def _passes(r: dict) -> bool:
    req = r["required"]
    if req == "beats":                       # better than equal by two standard errors
        return r["win"] - 2 * r["win_se"] > 0.5
    if req.startswith(">="):
        return r["win"] >= float(req[2:])
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("--game", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--players", type=int, required=True)
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--logs", nargs="*", default=[])
    p.add_argument("--recipe", nargs="*", default=[])
    p.add_argument("--notes")
    p.add_argument("--hours", type=float)
    p.add_argument("--hardware")
    q = sub.add_parser("accept")
    q.add_argument("--game", required=True)
    q.add_argument("--id", required=True)
    q.add_argument("--vs", nargs="+", required=True, help="opponents: greedy, random, a model id or a checkpoint path")
    q.add_argument("--labels", nargs="*")
    q.add_argument("--required", nargs="*", help="per opponent: beats | >=0.95 | -")
    q.add_argument("--deals", type=int, default=750)
    q.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    if a.cmd == "publish":
        print(publish(a.game, a.id, a.players, a.checkpoint, a.logs, a.recipe, a.notes, a.hours, a.hardware))
    else:
        req = [None if x == "-" else x for x in (a.required or [])] or None
        print(json.dumps(accept(a.game, a.id, a.vs, a.deals, a.workers, a.labels, req), indent=2))


if __name__ == "__main__":
    main()
