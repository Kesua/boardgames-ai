"""Copy the skills from .agents/skills (canonical: Codex, Cursor and other Agent Skills tools read it) to
.claude/skills (Claude Code reads it; Grok Build reads Claude skills too).

python tools/sync_skills.py           # write the copy
python tools/sync_skills.py --check   # exit 1 if the copy differs (CI)
Edit skills only in .agents/skills.
"""
from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC, DST = ROOT / ".agents" / "skills", ROOT / ".claude" / "skills"


def differences() -> list:
    out = []
    src = {p.relative_to(SRC) for p in SRC.rglob("*") if p.is_file()} if SRC.exists() else set()
    dst = {p.relative_to(DST) for p in DST.rglob("*") if p.is_file()} if DST.exists() else set()
    out += [f"missing in .claude/skills: {p}" for p in sorted(src - dst)]
    out += [f"extra in .claude/skills: {p}" for p in sorted(dst - src)]
    out += [f"differs: {p}" for p in sorted(src & dst) if not filecmp.cmp(SRC / p, DST / p, shallow=False)]
    return out


if __name__ == "__main__":
    if "--check" in sys.argv:
        d = differences()
        if d:
            print("skills out of sync (run python tools/sync_skills.py): " + "; ".join(d[:5]))
            sys.exit(1)
        print("skills in sync")
        sys.exit(0)
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    print(f"copied {sum(1 for p in SRC.rglob('*') if p.is_file())} files to .claude/skills")
