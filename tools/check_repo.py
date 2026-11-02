"""Repository rules that CI enforces (python tools/check_repo.py; exit code 1 on any problem).

- no rulebook PDFs and no file over 50 MB anywhere in git
- every game has manifest.json (valid against bgai/manifest.schema.json), rules.md, RIGHTS.md and tests
- every game (not the _template) has the pipeline files: STATUS.md, PLAN.md, data/SOURCES.md, checks/review.md
- every rule ID in a game's rules.md has a test marked @pytest.mark.rule("<ID>")
- every item of the game's catalog has a test marked @pytest.mark.card("<ID>") (or one test marked card("*") that
  is parametrized over the whole catalog)
- checks/report.json: 0 problems, at least 10,000 games for every supported player count, and no engine file changed
  since the commit it was made on (rerun python -m bgai.checks --game <slug> after any engine change)
- every experiment records the code commit that produced (or replayed) it
- every experiment's models exist with the recorded sha256; every model is used by an experiment (or the game's
  featured list) or marked in training
- featured experiments exist
- .claude/skills is an exact copy of .agents/skills (tools/sync_skills.py)
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX = 50 * 2 ** 20
SCHEMA = ROOT / "bgai" / "manifest.schema.json"
PIPELINE_FILES = ["STATUS.md", "PLAN.md", "data/SOURCES.md", "checks/review.md"]
MIN_CHECK_GAMES = 10000
# files of a game folder that do not change how games are played (everything else is "engine")
NOT_ENGINE = ("tests/", "checks/", "models/", "experiments/", "i18n/", "notes.json", "manifest.json", "summary.py")


def tracked_files() -> list:
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.split("\n")
        return [ROOT / f for f in out if f]
    except Exception:
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rule_ids(rules_md: str) -> list:
    return sorted(set(re.findall(r"\*\*([A-Z]\d+\.\d+)\*\*", rules_md)))


def tested_ids(test_dir: Path) -> set:
    ids = set()
    for f in test_dir.rglob("test_*.py"):
        ids |= set(re.findall(r'rule\("([A-Z]\d+\.\d+)"\)', f.read_text(encoding="utf-8")))
    return ids


def tested_cards(test_dir: Path) -> set:
    ids = set()
    for f in test_dir.rglob("test_*.py"):
        ids |= set(re.findall(r'card\("([^"]+)"\)', f.read_text(encoding="utf-8")))
    return ids


def engine_changed_since(slug: str, commit: str):
    """Engine files (game folder minus NOT_ENGINE, plus the mechanics kit and game contract) changed since commit;
    None when the commit is unknown (e.g. a shallow clone)."""
    paths = [f"games/{slug}", "bgai/kit", "bgai/game.py"]
    r = subprocess.run(["git", "diff", "--name-only", commit, "--", *paths], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        return None
    changed = [f for f in r.stdout.split() if f]
    return [f for f in changed if not (f.startswith(f"games/{slug}/") and
                                       (f[len(f"games/{slug}/"):].startswith(NOT_ENGINE) or f.endswith(".md")))]


def check_report(g: Path, players: list) -> list:
    name, rp = g.name, g / "checks" / "report.json"
    if not rp.exists():
        return [f"{name}: checks/report.json missing (python -m bgai.checks --game {name})"]
    rep = json.loads(rp.read_text(encoding="utf-8"))
    out = []
    if rep.get("problem_count"):
        out.append(f"{name}: checks/report.json reports {rep['problem_count']} problem(s)")
    counts = rep.get("games_per_player_count", {})
    short = [str(p) for p in players if counts.get(str(p), 0) < MIN_CHECK_GAMES]
    if short:
        out.append(f"{name}: checks/report.json has fewer than {MIN_CHECK_GAMES:,} games for player count(s) {', '.join(short)}")
    if not rep.get("code_commit"):
        out.append(f"{name}: checks/report.json lacks code_commit (rerun python -m bgai.checks)")
    elif rep["code_commit"].endswith("-dirty"):
        out.append(f"{name}: checks/report.json was made with uncommitted engine changes; commit them and rerun")
    else:
        changed = engine_changed_since(name, rep["code_commit"])
        if changed is None:
            out.append(f"{name}: cannot find commit {rep['code_commit'][:10]} of checks/report.json (full git history needed)")
        elif changed:
            out.append(f"{name}: engine changed since checks/report.json ({', '.join(changed[:3])}); rerun python -m bgai.checks")
    return out


def check() -> list:
    import jsonschema
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    problems = []
    for f in tracked_files():
        if not f.exists():
            continue
        if f.suffix.lower() == ".pdf":
            problems.append(f"PDF in the repository: {f.relative_to(ROOT)} (rulebooks are never committed)")
        if f.stat().st_size > MAX:
            problems.append(f"file over 50 MB: {f.relative_to(ROOT)}")
    for g in sorted((ROOT / "games").iterdir()):
        if not g.is_dir() or g.name.startswith(".") or g.name == "__pycache__":
            continue
        name = g.name
        for req in ("manifest.json", "rules.md", "__init__.py"):
            if not (g / req).exists():
                problems.append(f"{name}: missing {req}")
        if not name.startswith("_") and not (g / "RIGHTS.md").exists():
            problems.append(f"{name}: missing RIGHTS.md")
        if not (g / "manifest.json").exists():
            continue
        m = json.loads((g / "manifest.json").read_text(encoding="utf-8"))
        for err in sorted(jsonschema.Draft7Validator(schema).iter_errors(m), key=lambda e: list(e.path)):
            where = "/".join(str(x) for x in err.path) or "(top)"
            problems.append(f"{name}: manifest.json {where}: {err.message}")
        if not name.startswith("_"):
            for f in PIPELINE_FILES:
                if not (g / f).exists():
                    problems.append(f"{name}: missing {f} (see the new-game skill)")
            problems += check_report(g, m.get("players", []))
        try:
            sys.path.insert(0, str(ROOT))
            from bgai.game import load_spec
            spec = load_spec(name)
            items = list((spec.catalog() if callable(spec.catalog) else spec.catalog or {}).get("items", {}))
        except Exception as e:                       # a game that does not import fails its tests anyway
            items = []
            problems.append(f"{name}: cannot load the game spec ({e})")
        cards = tested_cards(g / "tests")
        if items and "*" not in cards:
            missing = [i for i in items if i not in cards]
            if missing:
                problems.append(f"{name}: {len(missing)} item(s) without a test marked card(\"<ID>\"): {', '.join(missing[:8])}"
                                + (" ..." if len(missing) > 8 else ""))
        if (g / "rules.md").exists():
            missing = [i for i in rule_ids((g / "rules.md").read_text(encoding="utf-8")) if i not in tested_ids(g / "tests")]
            if missing:
                problems.append(f"{name}: rule IDs without a test: {', '.join(missing)}")
        used = set()
        for e in sorted((g / "experiments").glob("*/")) if (g / "experiments").exists() else []:
            if not (e / "experiment.json").exists() or not (e / "stats.json").exists():
                problems.append(f"{name}/{e.name}: experiment.json and stats.json are both required")
                continue
            rec = json.loads((e / "experiment.json").read_text(encoding="utf-8"))
            if not rec.get("code_commit"):
                problems.append(f"{name}/{e.name}: experiment.json lacks code_commit (replay it: tools/regenerate.py)")
            for mid, h in rec.get("models", {}).items():
                used.add(mid)
                mz = g / "models" / mid / "model.zip"
                if not mz.exists():
                    problems.append(f"{name}/{e.name}: model {mid} missing")
                elif sha(mz) != h:
                    problems.append(f"{name}/{e.name}: model {mid} changed since the experiment (sha256)")
        for p, f in (m.get("featured") or {}).items():
            for role in ("main", "compare", "versus"):
                if role in f and not (g / "experiments" / f[role] / "stats.json").exists():
                    problems.append(f"{name}: featured {p}/{role} experiment {f[role]} missing")
        for d in sorted((g / "models").glob("*/")) if (g / "models").exists() else []:
            if not (d / "model.json").exists():
                problems.append(f"{name}: model {d.name} lacks model.json")
            elif d.name not in used:
                meta = json.loads((d / "model.json").read_text(encoding="utf-8"))
                if not meta.get("in_progress"):
                    problems.append(f"{name}: model {d.name} is used by no experiment (retire it or add one)")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_skills.py"), "--check"], capture_output=True, text=True)
    if r.returncode:
        problems.append(r.stdout.strip() or "skills out of sync")
    return problems


if __name__ == "__main__":
    probs = check()
    for p in probs:
        print("PROBLEM:", p)
    print(f"check_repo: {len(probs)} problem(s)")
    sys.exit(1 if probs else 0)
