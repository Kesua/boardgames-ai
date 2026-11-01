---
name: retire-model
description: Remove a model that no published experiment needs any more, together with its experiments and the notes that cite them, and update the manifest. Use when a newer finished model replaces an older one and the comparison is no longer shown.
---

# Retire a model

## Goal
The repository keeps only models that published numbers depend on (git history keeps the rest). Retiring keeps the
clone small and the dashboard focused.

## Steps
1. Find what uses it: `grep -r "<model id>" games/<slug>/experiments games/<slug>/manifest.json games/<slug>/notes.json`.
2. Remove those experiments (or keep them and keep the model — a comparison shown on the dashboard needs both models).
3. Update `manifest.json` featured entries and remove notes entries for removed experiments.
4. `git rm -r games/<slug>/models/<model id>`.
5. `python tools/check_repo.py` (no experiment may point to a missing model), `python tools/build_site.py`.

## Done when
check_repo passes and the dashboard shows no reference to the retired model.
