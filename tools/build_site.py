"""Build the static dashboard into site/: the pages from dashboard/ plus JSON data from every games/<slug>/.

python tools/build_site.py            # then open site/index.html through a static server:
python -m http.server -d site 8000    # http://127.0.0.1:8000

site/data/index.json            all games: name, publisher, players, intro, theme, headline numbers
site/data/<slug>/game.json      manifest, translations, item catalog, notes, models (with training logs),
                                experiment recipes, comparisons of new vs original model
site/data/<slug>/exp/<id>.json  one experiment's stats.json (without the per-game score list)
Nothing here computes game statistics: they come from stats.json; this only joins and reshapes.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def read_csv(p: Path) -> list:
    with open(p, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        row = {}
        for k, v in r.items():
            if v in ("", None):
                row[k] = None
                continue
            try:
                row[k] = float(v) if any(c in v for c in ".e") else int(v)
            except ValueError:
                row[k] = v
        out.append(row)
    return out


def se(r: dict) -> float:
    n = r.get("boards_with") or r.get("boards") or 0
    p = r.get("win_rate") or 0
    return (p * (1 - p) / n) ** 0.5 if n else 0.0


def compare(main: dict, old: dict, versus: dict, rec_main: dict, rec_old: dict) -> dict:
    """New vs original model on the same game (both mirror experiments)."""
    o = {r["item"]: r for r in old["items"]}
    items = []
    for r in main["items"]:
        a = o.get(r["item"])
        if not a or min(r["boards_with"], a["boards_with"]) < 30:
            continue
        err = (se(r) ** 2 + se(a) ** 2) ** 0.5
        change = r["win_lift"] - a["win_lift"]
        items.append({"item": r["item"], "lift_old": a["win_lift"], "lift_new": r["win_lift"], "boards_old": a["boards_with"],
                      "boards_new": r["boards_with"], "change": change, "se": err, "clear": abs(change) > 2 * err,
                      "edge_old": a.get("winner_edge"), "edge_new": r.get("winner_edge")})
    items.sort(key=lambda x: -x["change"])
    arch = {}
    for side, st in (("new", main), ("old", old)):
        for r in st.get("archetypes", []):
            arch.setdefault(r["archetype"], {"archetype": r["archetype"]}).update(
                {f"share_{side}": r["share"], f"win_{side}": r["win_rate"], f"boards_{side}": r["boards"]})
    deals = None
    if rec_main["seed"] == rec_old["seed"] and main.get("per_game_scores") and old.get("per_game_scores"):
        n = min(len(main["per_game_scores"]), len(old["per_game_scores"]))
        wn = [max(s) for s in main["per_game_scores"][:n]]
        wo = [max(s) for s in old["per_game_scores"][:n]]
        diff = [a - b for a, b in zip(wn, wo)]
        lo, hi = (min(diff) // 20) * 20, (max(diff) // 20) * 20
        deals = {"deals": n, "winner_new": sum(wn) / n, "winner_old": sum(wo) / n,
                 "loser_new": sum(min(s) for s in main["per_game_scores"][:n]) / n,
                 "loser_old": sum(min(s) for s in old["per_game_scores"][:n]) / n,
                 "new_higher": sum(d > 0 for d in diff) / n, "diff_mean": sum(diff) / n,
                 "hist": [{"from": b, "to": b + 20, "deals": sum(1 for d in diff if b <= d < b + 20)}
                          for b in range(int(lo), int(hi) + 20, 20)]}
    style = {}
    for side, st in (("new", main), ("old", old)):
        out = st["style"]["outcome"][0] if st["style"]["outcome"] else {}
        style[side] = {k: v for k, v in out.items() if k not in ("agent",)}
        style[side]["winner_score"] = st["meta"]["winner_score"]
        style[side]["first_seat_win"] = st["seat_order"][0]["win_rate"] if st["seat_order"] else None
    return {"items": items, "archetypes": list(arch.values()), "deals": deals, "style": style,
            "versus": versus["results"] if versus else None}


def build_game(slug: str, out: Path) -> dict:
    g = ROOT / "games" / slug
    from bgai.game import load_spec
    spec = load_spec(slug)
    manifest = read_json(g / "manifest.json")
    i18n = {p.stem: read_json(p) for p in sorted((g / "i18n").glob("*.json"))} if (g / "i18n").exists() else {}
    catalog = spec.catalog() if spec.catalog else {"items": {}, "cards": {}}
    notes = read_json(g / "notes.json") if (g / "notes.json").exists() else {}
    models = {}
    for d in sorted((g / "models").glob("*/")) if (g / "models").exists() else []:
        if not (d / "model.json").exists():
            continue
        m = read_json(d / "model.json")
        m["log_rows"] = {name: read_csv(d / name) for name in m.get("logs", []) if (d / name).exists()}
        m["size_mb"] = round((d / "model.zip").stat().st_size / 2 ** 20, 1) if (d / "model.zip").exists() else None
        models[d.name] = m
    experiments, stats = {}, {}
    exp_out = out / slug / "exp"
    exp_out.mkdir(parents=True, exist_ok=True)
    for d in sorted((g / "experiments").glob("*/")) if (g / "experiments").exists() else []:
        if not (d / "stats.json").exists():
            continue
        rec = read_json(d / "experiment.json")
        st = read_json(d / "stats.json")
        stats[d.name] = st
        experiments[d.name] = rec
        slim = {k: v for k, v in st.items() if k != "per_game_scores"}
        (exp_out / f"{d.name}.json").write_text(json.dumps(slim, separators=(",", ":")), encoding="utf-8")
    comparisons = {}
    for p, f in (manifest.get("featured") or {}).items():
        if "main" in f and "compare" in f and f["main"] in stats and f["compare"] in stats:
            comparisons[p] = compare(stats[f["main"]], stats[f["compare"]], stats.get(f.get("versus")),
                                     experiments[f["main"]], experiments[f["compare"]])
    rights = (g / "RIGHTS.md").read_text(encoding="utf-8") if (g / "RIGHTS.md").exists() else ""
    game = {"slug": slug, "manifest": manifest, "i18n": i18n, "catalog": catalog, "notes": notes, "models": models,
            "experiments": experiments, "compare": comparisons, "rights": rights}
    (out / slug).mkdir(parents=True, exist_ok=True)
    (out / slug / "game.json").write_text(json.dumps(game, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    headline = {}
    for p, f in (manifest.get("featured") or {}).items():
        st = stats.get(f.get("main"))
        if st:
            mid = experiments[f["main"]]["seats"][0]
            m = models.get(mid, {})
            headline[p] = {"experiment": f["main"], "games": st["meta"]["games"], "boards": st["meta"]["boards"],
                           "winner_score": st["meta"]["winner_score"], "best_score": st["meta"]["best_score"],
                           "model": mid, "steps": m.get("steps"), "finished": m.get("strength", {}).get("finished")}
    return {"slug": slug, "name": manifest["name"], "publisher": manifest.get("publisher"), "year": manifest.get("year"),
            "designer": manifest.get("designer"), "players": manifest.get("players"), "theme": manifest.get("theme"),
            "intro": manifest.get("intro"), "edition": manifest.get("edition"), "headline": headline,
            "models": len(models), "experiments": len(experiments)}


def main():
    site = ROOT / "site"
    if site.exists():
        shutil.rmtree(site)
    shutil.copytree(ROOT / "dashboard", site)
    data = site / "data"
    data.mkdir(exist_ok=True)
    games = [build_game(d.name, data) for d in sorted((ROOT / "games").iterdir())
             if d.is_dir() and not d.name.startswith(("_", ".")) and (d / "manifest.json").exists()]
    index = {"generated": time.strftime("%Y-%m-%d %H:%M"), "games": games}
    (data / "index.json").write_text(json.dumps(index, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    total = sum(f.stat().st_size for f in site.rglob("*") if f.is_file())
    print(f"site/: {len(games)} games, {total / 2 ** 20:.1f} MB")


if __name__ == "__main__":
    main()
