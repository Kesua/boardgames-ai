---
name: run-experiment
description: Run the standard experiments for a finished model (2,000 mirror games per player count, plus versus the previous finished model), producing experiment.json + stats.json with a replay fingerprint, and feature them in the manifest. Use after train-model.
---

# Run the standard experiments

## Goal
The dashboard's numbers come only from experiments: fixed recipes (model, seats, seed, games) that anyone can replay
exactly. Mirror games (the same AI in every seat) show what wins when everyone plays equally well; versus games show
how much stronger a new model is.

## Steps
1. Mirror, per player count:
   ```bash
   python -m bgai.experiment --game <slug> --id p2-<model>-mirror --players 2 --seats <model id> --games 2000 \
       --seed 1000 --workers 6
   ```
   Seat order rotates every game; deals are seeded with `seed + game number`. Raw records go to `raw/` and are
   deleted after summarising (use `--keep-raw` while developing summaries).
2. Versus the previous finished model (same seed so deals compare):
   `--id p2-<new>-vs-<old> --seats <new id> <old id>`.
3. Check: `python -m bgai.experiment --game <slug> --id <id> --verify 20` must print "match".
4. Feature them in `manifest.json`: `"featured": {"2": {"main": "<mirror id>", "compare": "<old mirror id>",
   "versus": "<versus id>"}}` (compare/versus only when there is an earlier model).
5. Look at the numbers before writing notes: `python tools/build_site.py`, open the game's pages.

## Done when
Experiments committed (both JSON files), `--verify 20` matches, manifest featured, `tools/check_repo.py` passes.

## Notes
- Experiments are fixed: never merge two runs. More games = re-run with a bigger `--games`.
- A new summary metric later? Use the add-metric skill (regenerates all experiments, proving the same games).
- Game-specific statistics belong in `games/<slug>/summary.py` as standard shapes (`bgai/summary/SHAPES.md`).
