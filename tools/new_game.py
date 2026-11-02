"""Start a new game folder from games/_template (step 3 of the new-game skill).

python tools/new_game.py --slug ark_nova --name "Ark Nova"

Copies games/_template to games/<slug>, points every import and the manifest at the new slug (copied tests would
otherwise keep testing the template), and leaves the template's toy rules in place as a working example: replace
them step by step. Refuses to overwrite an existing folder.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="lowercase with underscores, e.g. ark_nova")
    ap.add_argument("--name", required=True, help='the published name, e.g. "Ark Nova"')
    a = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", a.slug):
        print("slug: lowercase letters, digits and underscores, starting with a letter")
        return 1
    src, dst = ROOT / "games" / "_template", ROOT / "games" / a.slug
    if dst.exists():
        print(f"{dst.relative_to(ROOT)} exists already")
        return 1
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for f in dst.rglob("*.py"):
        s = f.read_text(encoding="utf-8")
        s = s.replace("games._template", f"games.{a.slug}").replace('slug="_template"', f'slug="{a.slug}"')
        s = s.replace('name="Template (toy market game)"', f'name="{a.name}"')
        f.write_text(s, encoding="utf-8", newline="\n")
    m = json.loads((dst / "manifest.json").read_text(encoding="utf-8"))
    m.update({"slug": a.slug, "name": a.name, "rights": "RIGHTS.md"})
    (dst / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for f in ("STATUS.md", "PLAN.md", "RIGHTS.md"):
        p = dst / f
        p.write_text(p.read_text(encoding="utf-8").replace("<Game name>", a.name), encoding="utf-8", newline="\n")
    left = [str(f.relative_to(ROOT)) for f in dst.rglob("*.py") if "_template" in f.read_text(encoding="utf-8")]
    print(f"created {dst.relative_to(ROOT)}" + (f"; still mentions _template: {left}" if left else ""))
    print(f"next: fill STATUS.md (fit check), then the ingest-rules skill. Check: python -m pytest -q games/{a.slug}")
    print("note: tools/check_repo.py reports this game until verify-engine writes checks/report.json; that is expected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
