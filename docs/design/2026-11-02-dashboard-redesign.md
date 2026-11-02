# Dashboard redesign: from generated look to a data-journalism page

Date: 2026-11-02. Decided by the maintainer in one decision form (16 questions); this file records the result.

## Why

The site read as AI-generated: noisy, every block in a card, nothing ranked. A review against 40 published
"AI-slop" design patterns (sources: impeccable.style/slop, Fountain Institute, Adrian Krebs's scoring of 1,590 Show HN
pages, Anthropic's frontend-design post, NN/g on info tips, Datawrapper's colour guide, GOV.UK design principles)
found 19 of them on the site: emoji game logos, small letter-spaced uppercase labels above headings, cards inside
cards, numbered-circle 1-2-3 steps, a 3×3 grid of equal findings, ✓/✗ lists, pills, coloured card edges, "?" icons,
"→" on every card, grey caveat boxes, KPI tiles, one headline formula everywhere, the system font, default blue/red
bars, an app-icon logo, one rhythm for every section and repeated texts.

Goal: a reader without technical knowledge sees at once what wins in each game, in a page that looks made by a
careful designer. Non-goals: new numbers, new features, a framework. Anti-goal: swapping one default for the
"less AI" default (cream page, serif, terracotta, newspaper hairlines).

## Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Direction | Explainer (data journalism): one reading column, headlines that state the finding, findings with their own small chart; wide tables (cards, forests, play style, lab) get a wider measure in a plain table style |
| 2 | Type | Source Serif 4 for headlines and big numbers, Source Sans 3 for text, tabular figures in tables |
| 3 | Font files | Self-hosted in `dashboard/fonts/` (woff2, latin + latin-ext), with the SIL Open Font License text; no request to Google |
| 4 | Chart colour | Grey first; the game's colour only on what the sentence is about. In overview charts, winning = game colour, losing = brick; checked for colour-blind readers |
| 5 | Theme | Light only; the theme toggle goes |
| 6 | Game header | Small line with the game, publisher and year; the game's main finding is the headline of the Discoveries tab (`notes.json` → `headline` en/cs); no emoji (`theme.emoji` is dropped from manifests and the schema) |
| 7 | Plan and Do/Avoid | One tinted block per player count: the plan sentence, then two plain lists headed Do and Avoid, no icons. The only tinted block on the page |
| 8 | Discoveries | A list, most important first (order in `notes.json`): headline = claim and link to the details, numbers for 2 and 4 players, text, and an optional small chart (`finding.chart`) |
| 9 | "Straight from the data" | Shown only for a game without written findings |
| 10 | "How it was made" | One paragraph at the end with the training and experiment game counts and a link to the Lab |
| 11 | "?" icons | Kept only for the two key measures (win-rate difference, strength test); every other explanation is visible text or lives on How to read |
| 12 | Home | Two or three sentences, then each game as a row: name, publisher, main finding, AI status; "Why trust the numbers" and "Add a game" as plain text |
| 13 | Logo | Word mark "boardgames.ai" set in the site's serif; favicon a plain letter |
| 14 | Language switch | Plain text "EN · CS" in the header |
| 15 | Copy | Pass over EN/CS site texts: no em dashes, no subtitle that repeats its heading, no bold lead words; finding numbers unchanged (`check_notes.py`) |
| 16 | Scope | The whole site at once; screenshots of every page (desktop and phone) before the commit |

## Visual system

- Page `#fbfbf9` (a cool, slightly green off-white, not cream), ink `#17191a`, secondary ink `#4d5257`, rules
  `#dde0dc`; game colour from `manifest.theme.accent`, losing bars burnt orange `#c9733f` (lighter than both game colours, checked for colour-blind readers), unclear values grey.
- Type scale (px): 13 · 15 · 17 (body) · 20 · 26 · 34 · 44; serif for h1/h2 and big numbers, sans elsewhere.
- Reading column 46rem; tables and charts may use up to 72rem.
- Separation by space and thin rules, not boxes. The single tinted block per page is the plan.
- Charts: no rounded bars, grey gridlines, values labelled at the bar, uncertainty as a thin line.

## Left to the builder

Exact spacing, the headline text of each game (written from its strongest finding), which findings get a chart and
which cards a chart highlights, and the wording of the copy pass.
