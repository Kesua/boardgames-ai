---
name: write-notes
description: Write games/<slug>/notes.json — the plain-language strategy interpretation and discovery cards players read on the dashboard — strictly from stats.json numbers, with honest caveats, in English and other languages. Use after run-experiment.
---

# Write the notes

## Goal
Most readers will never open a table. The notes turn the statistics into a few sentences a player can use at the
table — without overclaiming. They must be true to the numbers, say what is correlation, and be useful.

## Inputs
The featured experiments' `stats.json` (via `python tools/build_site.py` and the dashboard, or by reading the JSON with
a short script). Never invent a number: every number in the text is copied from stats (rounded).

## notes.json format
```json
{"written": "YYYY-MM-DD",
 "experiments": {"<experiment id>": {"games": 2000, "written": "YYYY-MM-DD",
   "en": {"summary": "one sentence: the winning plan", "works": ["3–5 bullets"], "avoid": ["2–4 bullets"],
          "order": "turn-order effect in one sentence", "length": ["optional bullets on game length"]},
   "cs": {...}}},
 "findings": [{"variant": "main", "id": "short-id", "link": "#strategy", "tag": "optional",
   "en": {"title": "6–8 words", "text": "2–3 sentences", "label": "what the numbers measure",
          "n2": "value for 2 players", "n4": "value for 4 players", "before": "optional: the earlier AI's value"},
   "cs": {...}}]}
```
Six findings per game is a good number; link each to the tab where its chart is (`#strategy`, `#items`, `#more`,
`#compare`, `#length`).

## Rules for the text
- Lead with what a player can do ("Few saplings, fill the trees").
- Use the dashboard's terms: effect on winning (percentage points), winner vs loser (copies), presence.
- Prefer findings that hold across player counts and are large compared with their uncertainty (> 2 standard errors;
  at least ~200 boards).
- Say "winners have more X", not "X makes you win". Mention when a finding may come from game length or from the AI's
  own style.
- Plain words; no jargon without explanation; short sentences.

## Keep the numbers checkable
Write a small script in the game folder that recomputes every number the notes cite from `stats.json`, rounded the way
the site rounds, and prints a MISMATCH line for each difference (example: `games/forest_shuffle/check_notes.py`).
Run it after every re-run of an experiment; notes with a stale number are false.

## Done when
`notes.json` validates (the site builds and shows the findings), every number traces to stats.json, at least English
and every language in the manifest are present.
