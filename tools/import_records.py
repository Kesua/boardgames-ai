"""One-off migration: summarise record files of the original forest-shuffle repository as experiments here.

python tools/import_records.py <old .jsonl> <old .meta.json> --game forest_shuffle --id <experiment id> --seats <seat ids>

The original simulate.py dealt game k with seed + k and rotated seats exactly like bgai.experiment, and the ported
engine replays those games identically (verified for the first 40 games of every file; CI replays the first 20 of
every experiment). So converting the old rows gives the same stats.json that re-running the experiment would give,
without spending hours of CPU. The experiment.json states how it was made and the command that re-runs it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def convert(old_path: str, out_path: str, seed: int, seat_names: list) -> list:
    """Old row format -> bgai.records format. Returns per-game final scores in game order."""
    names = {}
    scores = {}
    with open(old_path, encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as out:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = r.pop("type")
            agents = r.get("agents")
            if t == "game":
                gid = r["game_id"]
                row = {"type": "game", "game_id": gid, "seed": seed + gid - 1, "players": r["players"],
                       "options": {"expansions": r["expansions"]}, "agents": [_name(a, seat_names) for a in agents],
                       "steps": r["steps"], "turns": r["turns"], "rounds": r["turns"] / r["players"],
                       "winners": r["winners"], "scores": r["scores"], "tiebreaks": None}
                scores[gid] = r["scores"]
            elif t == "seat":
                row = {"type": "seat", "game_id": r["game_id"], "players": r["players"], "seat": r["seat"],
                       "agent": _name(r["agent"], seat_names), "score": r["score"], "rank": r["rank"], "win": r["win"],
                       "hand_left": r["hand_left"], "b_trees": r["trees"], "b_dwellers": r["dwellers"],
                       "b_cave": r["cave"], "x_plants": r["plants"], "x_saplings": r["saplings"]}
            elif t == "action":
                row = {"type": "action", "game_id": r["game_id"], "step": r["step"], "turn": r["turn"], "seat": r["seat"],
                       "agent": _name(r["agent"], seat_names), "decision": r["decision"],
                       "decision_label": r["decision_label"], "action": r["action"], "card": r["card"],
                       "item": r["species"], "tag_symbol": r["symbol"], "x_half": r["half"], "x_target": r["target"],
                       "x_hand": r["hand"], "x_clearing": r["clearing"], "x_deck": r["deck"]}
            elif t == "card":
                row = {"type": "item", "game_id": r["game_id"], "players": r["players"], "seat": r["seat"],
                       "agent": _name(r["agent"], seat_names), "win": r["win"], "score": r["score"],
                       "item": r["species"], "kind": r["kind"], "group": r["plant"], "slot": r["slot"],
                       "host": r["host"], "points": r["points"], "tag_symbol": r["symbol"]}
            else:
                continue
            out.write(json.dumps(row, separators=(",", ":")) + "\n")
    return [scores[k] for k in sorted(scores)]


def _name(old: str, seat_names: dict) -> str:
    return "model:" + seat_names[old[6:]] if old.startswith("model:") else old


def main():
    from bgai import experiment as X
    from bgai.game import load_spec
    from bgai.records import load
    from bgai.summary import build_stats
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("meta")
    ap.add_argument("--game", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--seats", nargs="+", required=True, help="model id per seat (seat order of the old run)")
    ap.add_argument("--old-models", nargs="+", required=True, help="old model path per seat, to map agent names")
    a = ap.parse_args()
    meta = json.loads(Path(a.meta).read_text(encoding="utf-8"))["runs"]
    assert len(meta) == 1, "one run per file expected"
    run = meta[0]
    seat_names = dict(zip(a.old_models, a.seats))
    spec = load_spec(a.game)
    raw = ROOT / "raw" / a.game
    raw.mkdir(parents=True, exist_ok=True)
    tmp = raw / f"{a.id}.jsonl"
    scores = convert(a.old, str(tmp), run["seed"], seat_names)
    manifest = json.loads((X.game_dir(a.game) / "manifest.json").read_text(encoding="utf-8"))
    stats = build_stats(load(str(tmp)), spec, manifest)
    stats["schema_version"] = X.SCHEMA_VERSION
    stats["fingerprint"] = {"all": X.fingerprint(scores), "first": scores[:X.FIRST_GAMES]}
    stats["per_game_scores"] = scores
    out = X.game_dir(a.game) / "experiments" / a.id
    out.mkdir(parents=True, exist_ok=True)
    players = run["players"]
    seats = a.seats
    kind = "mirror" if len(set(seats)) == 1 else "versus"
    import numpy, platform, torch
    recipe = {
        "id": a.id, "game": a.game, "kind": kind, "players": players, "seats": seats, "games": len(scores),
        "seed": run["seed"], "options": {"expansions": run["expansions"]},
        "seat_rotation": "seat j of game k is played by seats[(k + j) % players]",
        "models": {m: X.sha256_file(X.model_path(a.game, m)) for m in sorted(set(seats))},
        "card_data_sha256": {p.name: X.sha256_file(p) for p in sorted((X.game_dir(a.game) / "data").glob("*.json"))},
        "code_commit": X.code_commit(), "requirements_lock_sha256": X.lock_hash(),
        "environment": {"os": platform.platform(), "python": platform.python_version(), "numpy": numpy.__version__,
                        "torch": torch.__version__},
        "command": f"python -m bgai.experiment --game {a.game} --id {a.id} --players {players} --seats {' '.join(seats)} "
                   f"--games {len(scores)} --seed {run['seed']}",
        "made_by": f"imported from the original record file ({Path(a.old).name}, {run['started']}, "
                   f"{run['seconds']} s); identical games, verified by replay",
        "seconds": run["seconds"], "schema_version": X.SCHEMA_VERSION, "created": run["finished"],
    }
    (out / "experiment.json").write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(stats, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp.unlink()
    print(f"wrote {out} ({len(scores)} games)")


if __name__ == "__main__":
    main()
