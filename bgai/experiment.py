"""Run a standard experiment: play N games with fixed seeds, summarise them, write experiment.json + stats.json.

python -m bgai.experiment --game <slug> --id <experiment id> --players 2 --seats <seat> <seat> --games 2000 --seed 1000
python -m bgai.experiment --game <slug> --id <experiment id> --verify 20      # replay the first 20 games, compare

A seat is "random", "greedy" or a model id (games/<slug>/models/<id>/model.zip). Game k (0-based) is dealt with
seed + k and the seat order rotates every game: seat j of game k is played by agent (k + j) mod players, so every
agent sits in every seat equally often. Models pick their most likely legal action, so the same code, weights and
seeds give the same games. Random and greedy seats are reseeded every game from (seed + k), so results do not
depend on how games are split over worker processes.

Kinds: "mirror" = every seat the same model (card statistics); "versus" = two different agents (who is stronger).
Output: games/<slug>/experiments/<id>/experiment.json (the recipe) and stats.json (summary + fingerprint). The raw
record file lives in raw/ (git-ignored) and is deleted unless --keep-raw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import os
import platform
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
FIRST_GAMES = 20


def game_dir(slug: str) -> Path:
    return ROOT / "games" / slug


def model_path(slug: str, model_id: str) -> Path:
    return game_dir(slug) / "models" / model_id / "model.zip"


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(per_game_scores: list) -> str:
    return hashlib.sha256(json.dumps(per_game_scores, separators=(",", ":")).encode()).hexdigest()


def make_agent(slug: str, seat_spec: str, players: int, seed: int):
    from .agents import PolicyAgent, RandomAgent
    from .game import load_spec
    spec = load_spec(slug)
    if seat_spec == "random":
        return RandomAgent(seed)
    if seat_spec == "greedy":
        return spec.greedy(seed)
    return PolicyAgent(str(model_path(slug, seat_spec)), spec, players, name=f"model:{seat_spec}")


def _play_range(job) -> tuple:
    """Play games [lo, hi) of an experiment; write their records to part_path; return their final scores."""
    slug, seats, players, seed, options, lo, hi, part_path, threads = job
    import torch
    torch.set_num_threads(threads)
    from .agents import play_game
    from .game import load_spec
    from .records import GameRecorder
    spec = load_spec(slug)
    models = {s: make_agent(slug, s, players, 0) for s in set(seats) if s not in ("random", "greedy")}
    rec = GameRecorder(part_path, rounds_fn=spec.rounds) if part_path else None
    scores = []
    for k in range(lo, hi):
        agents = []
        for j in range(players):
            s = seats[(k + j) % players]
            agents.append(models[s] if s in models else make_agent(slug, s, players, (seed + k) * 10 + j))
        g = spec.new_game(players, seed + k, options)
        if rec:
            rec.game_id = k              # start_game adds 1: game ids are 1-based game numbers
            rec.seed = seed + k
            rec.options = options
        scores.append(play_game(g, agents, recorder=rec, max_steps=spec.max_steps))
    if rec:
        rec.close()
    return lo, scores


def play(slug, seats, players, seed, options, n_games, raw_path=None, workers=1):
    """Play games 0..n_games-1; returns the per-game final scores (in game order) and writes raw_path if given."""
    workers = max(1, min(workers, n_games))
    bounds = [(n_games * i // workers, n_games * (i + 1) // workers) for i in range(workers)]
    parts = [f"{raw_path}.part{i}" if raw_path else None for i in range(workers)]
    threads = 1 if workers > 1 else max(1, (os.cpu_count() or 2) // 2)
    jobs = [(slug, list(seats), players, seed, options, lo, hi, parts[i], threads) for i, (lo, hi) in enumerate(bounds)]
    if workers == 1:
        results = [_play_range(jobs[0])]
    else:
        with mp.get_context("spawn").Pool(workers) as pool:
            results = pool.map(_play_range, jobs)
    scores = [s for _, part in sorted(results) for s in part]
    if raw_path:
        with open(raw_path, "w", encoding="utf-8") as out:
            for p in parts:
                with open(p, encoding="utf-8") as f:
                    shutil.copyfileobj(f, out)
                os.remove(p)
    return scores


def lock_hash() -> str:
    p = ROOT / "requirements.lock"
    return sha256_file(p) if p.exists() else None


def code_commit() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def run(slug, exp_id, players, seats, n_games, seed, options=None, workers=None, keep_raw=False):
    from .game import load_spec
    from .records import load
    from .summary import build_stats
    spec = load_spec(slug)
    options = options if options is not None else dict(spec.default_options)
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    out_dir = game_dir(slug) / "experiments" / exp_id
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = ROOT / "raw" / slug
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{exp_id}.jsonl"
    model_ids = sorted({s for s in seats if s not in ("random", "greedy")})
    kind = "mirror" if len(set(seats)) == 1 else "versus"
    t0 = time.time()
    scores = play(slug, seats, players, seed, options, n_games, str(raw_path), workers)
    seconds = round(time.time() - t0, 1)
    manifest = json.loads((game_dir(slug) / "manifest.json").read_text(encoding="utf-8"))
    frames = load(str(raw_path))
    stats = build_stats(frames, spec, manifest)
    stats["schema_version"] = SCHEMA_VERSION
    stats["fingerprint"] = {"all": fingerprint(scores), "first": scores[:FIRST_GAMES]}
    stats["per_game_scores"] = scores
    import numpy, torch
    recipe = {
        "id": exp_id, "game": slug, "kind": kind, "players": players, "seats": list(seats), "games": n_games,
        "seed": seed, "options": options, "seat_rotation": "seat j of game k is played by seats[(k + j) % players]",
        "models": {m: sha256_file(model_path(slug, m)) for m in model_ids},
        "card_data_sha256": {p.name: sha256_file(p) for p in sorted((game_dir(slug) / "data").glob("*.json"))},
        "code_commit": code_commit(), "requirements_lock_sha256": lock_hash(),
        "environment": {"os": platform.platform(), "python": platform.python_version(), "numpy": numpy.__version__,
                        "torch": torch.__version__},
        "command": "python -m bgai.experiment " + " ".join(sys.argv[1:]) if sys.argv[0].endswith("experiment.py")
        else f"python -m bgai.experiment --game {slug} --id {exp_id} --players {players} --seats {' '.join(seats)} "
             f"--games {n_games} --seed {seed}",
        "seconds": seconds, "schema_version": SCHEMA_VERSION, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "experiment.json").write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "stats.json").write_text(json.dumps(stats, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    if not keep_raw:
        raw_path.unlink()
    return out_dir


def verify(slug, exp_id, n=FIRST_GAMES) -> bool:
    """Replay the first n games of a stored experiment and compare their final scores with the fingerprint."""
    d = game_dir(slug) / "experiments" / exp_id
    rec = json.loads((d / "experiment.json").read_text(encoding="utf-8"))
    stats = json.loads((d / "stats.json").read_text(encoding="utf-8"))
    for m, h in rec["models"].items():
        if sha256_file(model_path(slug, m)) != h:
            print(f"MODEL CHANGED: {m}")
            return False
    n = min(n, len(stats["fingerprint"]["first"]))
    scores = play(slug, rec["seats"], rec["players"], rec["seed"], rec["options"], n, None, 1)
    ok = scores == stats["fingerprint"]["first"][:n]
    print(f"{slug}/{exp_id}: first {n} games {'match' if ok else 'DIFFER'}")
    if not ok:
        for k, (a, b) in enumerate(zip(scores, stats["fingerprint"]["first"])):
            if a != b:
                print(f"  game {k}: replay {a} stored {b}")
                break
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--id", required=True, help="experiment id, e.g. p2-<model>-mirror")
    ap.add_argument("--players", type=int)
    ap.add_argument("--seats", nargs="+", help="random | greedy | model id, one per seat (or one for all seats)")
    ap.add_argument("--games", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--options", default=None, help="JSON game options; default: the game's default options")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--verify", type=int, default=None, metavar="N", help="replay the first N games of a stored experiment")
    a = ap.parse_args(argv)
    if a.verify:
        sys.exit(0 if verify(a.game, a.id, a.verify) else 1)
    seats = a.seats * a.players if len(a.seats) == 1 else a.seats
    assert len(seats) == a.players, "--seats: one per seat, or one for all seats"
    out = run(a.game, a.id, a.players, seats, a.games, a.seed, json.loads(a.options) if a.options else None, a.workers,
              a.keep_raw)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
