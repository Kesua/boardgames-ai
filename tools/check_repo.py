"""Repository rules that CI enforces (python tools/check_repo.py; exit code 1 on any problem).

- no rulebook PDFs and no file over 50 MB anywhere in git
- every game has manifest.json (required keys), rules.md, RIGHTS.md and tests
- every rule ID in a game's rules.md has a test marked @pytest.mark.rule("<ID>")
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
REQUIRED = ["slug", "name", "players", "terms", "score_categories", "top_decision", "featured", "languages"]


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


def check() -> list:
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
        for k in REQUIRED:
            if k not in m:
                problems.append(f"{name}: manifest.json lacks '{k}'")
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
