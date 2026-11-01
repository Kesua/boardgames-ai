"""Re-run stored experiments from their recipes (after a summary change, add-metric skill, or a platform upgrade).

python tools/regenerate.py --game <slug|all> [--id <experiment id>] [--workers N] [--check-only]

Each experiment is replayed with its seats, players, games, seed and options. The replay must reproduce the stored
fingerprint (same final scores of every game); only then is the new stats.json written. A mismatch stops with an
error: the games changed, which is an engine or model change, not a summary change (see upgrade-platform skill).
"""
from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def regenerate(slug: str, exp_id: str, workers: int, check_only: bool) -> bool:
    from bgai import experiment as X
    d = X.game_dir(slug) / "experiments" / exp_id
    rec = json.loads((d / "experiment.json").read_text(encoding="utf-8"))
    old = json.loads((d / "stats.json").read_text(encoding="utf-8"))
    if check_only:
        return X.verify(slug, exp_id, X.FIRST_GAMES)
    tmp_id = exp_id + ".regen"
    out = X.run(slug, tmp_id, rec["players"], rec["seats"], rec["games"], rec["seed"], rec["options"], workers)
    new = json.loads((out / "stats.json").read_text(encoding="utf-8"))
    if new["fingerprint"]["all"] != old["fingerprint"]["all"]:
        print(f"{slug}/{exp_id}: FINGERPRINT CHANGED — the games differ; not replacing (see {out})")
        return False
    (d / "stats.json").write_text((out / "stats.json").read_text(encoding="utf-8"), encoding="utf-8")
    rec2 = json.loads((out / "experiment.json").read_text(encoding="utf-8"))
    rec.update({k: rec2[k] for k in ("code_commit", "requirements_lock_sha256", "environment", "schema_version", "seconds")})
    rec["id"] = exp_id
    rec["replayed"] = {"games": rec["games"], "date": time.strftime("%Y-%m-%d"), "code_commit": rec2["code_commit"]}
    (d / "experiment.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    import shutil
    shutil.rmtree(out)
    print(f"{slug}/{exp_id}: regenerated, same games")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--id")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--check-only", action="store_true", help="only replay the first 20 games of each experiment")
    a = ap.parse_args()
    games = [p.name for p in (ROOT / "games").iterdir() if p.is_dir() and not p.name.startswith(("_", "."))] \
        if a.game == "all" else [a.game]
    ok = True
    for slug in games:
        exps = [a.id] if a.id else sorted(p.name for p in (ROOT / "games" / slug / "experiments").glob("*/")) \
            if (ROOT / "games" / slug / "experiments").exists() else []
        for e in exps:
            ok &= regenerate(slug, e, a.workers, a.check_only)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
