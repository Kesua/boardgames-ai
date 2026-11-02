"""Run the mechanical part of reviewing a game (review-game-pr skill) and print what a human must still look at.

python tools/review_pr.py --game <slug> [--base main] [--seed 7] [--log-lines 80]

Prints, step by step (PASS / FAIL / CHECK = a human looks):
  1. the game's tests                       5. strength card of every model
  2. tools/check_repo.py (this game)        6. files changed outside games/<slug>/ against --base
  3. checks/report.json                     7. 5 random rule IDs and 5 random items to compare with the real game
  4. --verify 20 of every experiment        8. one game played by the greedy agent, as text
Then a suggested verdict. Takes a few minutes (the replays dominate); nothing is written.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(cmd: list) -> tuple:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def head(title: str):
    print(f"\n=== {title}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--base", default="main", help="branch the pull request goes into")
    ap.add_argument("--seed", type=int, default=7, help="seed for the random picks and the printed game")
    ap.add_argument("--log-lines", type=int, default=80)
    a = ap.parse_args(argv)
    g, py, rng = ROOT / "games" / a.game, sys.executable, random.Random(a.seed)
    results = {}

    head("1. Tests")
    code, out = run([py, "-m", "pytest", "-q", f"games/{a.game}"])
    results["tests"] = code == 0
    print(("PASS " if code == 0 else "FAIL ") + out.splitlines()[-1])

    head("2. Repository rules")
    code, out = run([py, "tools/check_repo.py"])
    mine = [l for l in out.splitlines() if l.startswith("PROBLEM") and (f" {a.game}" in l or a.game + "/" in l
                                                                        or "skills" in l or "PDF" in l)]
    results["repo"] = not mine
    print("PASS no problems for this game" if not mine else "FAIL\n" + "\n".join(mine))

    head("3. Engine checks (checks/report.json)")
    rp = g / "checks" / "report.json"
    if rp.exists():
        rep = json.loads(rp.read_text(encoding="utf-8"))
        ok = rep.get("problem_count") == 0
        results["checks"] = ok
        print(("PASS " if ok else "FAIL ") + f"{rep.get('problem_count')} problems; games per player count "
              f"{rep.get('games_per_player_count')}; greedy vs random {rep.get('greedy_vs_random')}; "
              f"commit {str(rep.get('code_commit'))[:10]}")
    else:
        results["checks"] = False
        print("FAIL missing; run python -m bgai.checks --game " + a.game)
    rv = g / "checks" / "review.md"
    print(("CHECK read " if rv.exists() else "FAIL missing ") + "checks/review.md: every finding has a resolution")

    head("4. Experiments replay (--verify 20)")
    exps = sorted(p.name for p in (g / "experiments").glob("*/") if (p / "experiment.json").exists()) \
        if (g / "experiments").exists() else []
    results["replay"] = True
    for e in exps:
        code, out = run([py, "-m", "bgai.experiment", "--game", a.game, "--id", e, "--verify", "20"])
        results["replay"] &= code == 0
        print(("PASS " if code == 0 else "FAIL ") + f"{e}: {out.splitlines()[-1] if out else ''}")
    if not exps:
        print("none (an engine-only pull request)")

    head("5. Models (strength cards)")
    models = sorted((g / "models").glob("*/model.json")) if (g / "models").exists() else []
    results["models"] = bool(models) and all(
        json.loads(m.read_text(encoding="utf-8")).get("strength", {}).get("finished") or
        json.loads(m.read_text(encoding="utf-8")).get("legacy") for m in models)
    for m in models:
        meta = json.loads(m.read_text(encoding="utf-8"))
        st = meta.get("strength", {})
        state = "finished" if st.get("finished") else "legacy" if meta.get("legacy") else "NOT finished"
        print(f"{meta['id']}: {state}")
        for r in st.get("games", []):
            se = f" ± {2 * r['win_se']:.1%}" if r.get("win_se") else ""
            print(f"   vs {r.get('label') or r['opponent']}: {r['games']} games, win {r['win']:.1%}{se}, "
                  f"required {r.get('required') or '-'}")
    if not models:
        print("none (an engine-only pull request)")
    print("CHECK the training curve in each model's train_log*.csv did not collapse (win against greedy keeps rising, "
          "then levels off)")

    head(f"6. Files changed outside games/{a.game}/ (against {a.base})")
    code, out = run(["git", "diff", "--name-only", f"{a.base}...HEAD"])
    if code:
        print(f"CHECK cannot diff against {a.base}: {out.splitlines()[-1] if out else ''}")
    else:
        other = [f for f in out.split() if not f.startswith(f"games/{a.game}/")]
        print("PASS none" if not other else "CHECK platform or other games changed (upgrade-platform skill rules):\n  "
              + "\n  ".join(other))

    head("7. Spot checks against the official rulebook and cards (a human does these)")
    rules = (g / "rules.md").read_text(encoding="utf-8") if (g / "rules.md").exists() else ""
    lines = [l.strip() for l in rules.splitlines() if re.match(r"\s*- \*\*[A-Z]\d+\.\d+\*\*", l)]
    for l in rng.sample(lines, min(5, len(lines))):
        print("CHECK rule  " + l[:220])
    try:
        from bgai.game import load_spec
        spec = load_spec(a.game)
        cat = spec.catalog() if callable(spec.catalog) else (spec.catalog or {})
        items = cat.get("items", {})
        i18n = g / "i18n" / "en.json"
        texts = json.loads(i18n.read_text(encoding="utf-8")).get("items", {}) if i18n.exists() else {}
        for k in rng.sample(sorted(items), min(5, len(items))):
            info = {x: y for x, y in items[k].items() if x not in ("cards", "tags")}
            print(f"CHECK card  {k}: {json.dumps(info, ensure_ascii=False)} {json.dumps(texts.get(k, {}), ensure_ascii=False)}"[:400])
    except Exception as e:
        print(f"FAIL cannot load the game's catalog: {e}")

    head("8. One game played by the greedy agent (does it look like the real game?)")
    code, out = run([py, "-m", "bgai.show", "--game", a.game, "--seed", str(a.seed), "--max-lines", str(a.log_lines)])
    print(out[-12000:])

    head("Suggested verdict")
    engine_ok = results["tests"] and results["repo"] and results["checks"]
    if engine_ok and results["replay"] and results["models"] and exps:
        print("APPROVE if the CHECK items (spot checks, game log, training curve, notes) look right.")
    elif engine_ok and not exps and not models:
        print("APPROVE AS ENGINE ONLY if the spot checks and the game log look right: the game is listed as "
              "'engine ready, AI not trained yet'; training can follow in a later pull request.")
    else:
        print("REQUEST CHANGES: " + ", ".join(k for k, v in results.items() if not v) + " failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
