## What this adds or changes
<!-- e.g. "Adds Azul (base game), engine only" or "Trains the 4-player Wingspan model" -->

## Evidence (tick what is included)
- [ ] `rules.md` with rule IDs, two independent sources, decisions table
- [ ] `data/SOURCES.md` with a field-by-field card comparison
- [ ] a test for every rule ID and every card (`tools/check_repo.py` passes)
- [ ] `checks/report.json`: 0 problems, 10,000 games per player count; `checks/review.md` by an independent reviewer
- [ ] model(s) with a finished strength card (or: engine-only pull request)
- [ ] experiments; `--verify 20` matches
- [ ] `notes.json` in every language of the manifest
- [ ] `STATUS.md` current; no PDFs, art or copied texts; `RIGHTS.md` present

## Review
Output of `python tools/review_pr.py --game <slug> --base main` (suggested verdict and anything marked FAIL):
