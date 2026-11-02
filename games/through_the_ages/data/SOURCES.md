# Where the Through the Ages card data comes from, and how it was checked

`cards.json` (292 cards) holds card **data** only: names, ages, kinds, copies per player count, costs, the printed
bottom symbols (`yields`), tactics, bonus values and each ability as a structured effect (`card_effects.py`). It holds
no printed card text and no art. It describes the modelled game: base game + New Leaders and Wonders expansion with
its rebalanced cards and military decks (rules.md T15, maintainer decisions P1–P3).

## Sources

| | Source | Used for | Why independent |
|---|---|---|---|
| A | Board Game Arena's typed card data, `material.inc.php`, github.com/srussking/throughtheages @ `45b1c03` (read by `php_array.py`, never run) | base cards: every number, copies per player count | a licensed implementation's data entry |
| B | The printed base cards, read from BGA's card pictures `img/cards_big.jpg` (rows 0–7; the rest of that file is truncated in the repository) and `img/cards.jpg` (all 25 rows, 80×117 px per card) by an agent who never saw A | field-by-field check of A | read from the printed card faces, not from A's typed values |
| C | Fan wiki card list (digital edition), throughtheages.fandom.com `Card_List:_Digital_Edition` (CC-BY-SA), names per age | which cards are in the game | written by players of the official app |
| E | Expansion cards from text: the official expansion rulebook (card-count table, clarifications), CGE's designer notes texts, the fan wiki's card pages, a BoardGameGeek playtester's card-by-card overview (thread 2274464) and rules threads (via api.geekdo.com), NamuWiki (Korean, machine-translated) — sources listed per card in the list | all expansion cards | several separately written texts; the fan wiki's military-card texts copy the BGG post and were not counted as a separate source |
| P | The printed expansion cards: CGE's own card pictures of the 24 new leaders and 16 new wonders (throughtheages.com/tta2/img/cards/…), the fan wiki's pictures of the 12 rebalanced leaders and wonders; viewed in a browser, nothing saved | field-by-field check of E for those 52 cards | printed cards, read by an agent who never saw E |
| T | ptarjan/tta-ai `data/*.json` @ `36c07b2` (built from BGA, a Tabletop Simulator mod and BGG card files) | tie-breaker only (not independent of A) | — |

Downloads and extracted lists live in the git-ignored `inbox/through_the_ages/` (`bga/`, `ttaai/`, `list_B_base.json`,
`list_expansion.json`, `list_expansion_printed.json`, `wiki_card_list_digital.json`).

## How to rebuild

```bash
python games/through_the_ages/data/build_cards.py
```

The script compares A and B on every field (kind, science and revolution cost, resource cost, wonder stage costs,
urban limit, military action cost, bottom symbols, tactic units and strengths, bonus values, player-count marking
against A's copies), checks A's card set against C, compares E and P on every printed field of the 52 cards P covers,
merges the expansion (rules T15), attaches the structured effects and fails on any difference not listed with a
reason in `EXPECTED_DIFFS` / `EXPANSION_DECISIONS`. `tests/test_data.py` pins the totals.

Abilities: A's and B's texts are worded too differently to parse with one parser (B is an own-words paraphrase), so
the structured effects were written once by hand and then **reviewed card by card against B's printed reading** by a
separate agent who never saw A's texts (zooming the card pictures where a digit was unclear), and the expansion
effects against P and the official rulebook clarifications in the same way.

## Results of the checks

- **A vs B, 237 base card faces:** all fields agree except one, settled by re-reading the picture:
  - Aggression: Plunder I military action cost: A 1, B 2 → **1** (one red token at 4× zoom, like Raid I and Plunder
    II/III).
- **A vs C:** the same set of cards in every age, with digital-edition names mapped to printed names (Stock Pile =
  Stockpile, Development of Civil Life = Development of Civilization, Military Alliance = Military Pact, Space Flight =
  First Space Flight).
- **Light Cavalry (Age I tactic):** A has the card with 0 copies, B saw its picture, C does not list it; A's military
  total (10/45/50/45 at 4 players = 150) equals CGE's "149 base military cards" plus the rebalanced Wealthy Territory I
  only without it → **not in the game**.
- **Token symbols:** plain blue/yellow token symbols add tokens, a minus sign removes them (B's pictures of Justice
  System, Civil Service, Taj Mahal, the territories; A stores the same signs) — rules.md D17. Wealthy Territory I prints
  3 blue tokens (A's data 3; A's note text "+2" is a typo).
- **Effects review, base (162 effects):** 0 wrong numbers, 0 wrong targets; 5 missing conditions (Genghis Khan's
  infantry-as-cavalry and tie rule, Homer's forfeited civil action, Bill Gates' culture on leaving, Politics of
  Strength in Age IV, Impact of Population counting content workers) and 2 naming problems (Leonardo da Vinci,
  Inhabited Territory's free population) — all fixed; ambiguous parameter names renamed (Raid, War over Territory,
  construction discounts by age, Civil Unrest). Aggression: Raid destroys **urban** buildings only (seen on the card).
  B's own misreadings found by the review: Cold War gives science (not culture).
- **Impact of Science, 3-player row:** A 14/7/0; B read 12 but marked it uncertain and the review could not settle it at
  picture size; Impact of Strength prints 14/7/0 and T gives 14/7/0 for both → **14/7/0**.
- **E vs P, 52 expansion leaders and wonders:** every field agrees (stage costs, costs, bottom symbols), including the
  stage costs the text sources disputed (Silk Road 2/1/1/1/2, Suez Canal 4/3/2/2, Roman Roads 2/1/1/1, Acropolis 2/3).
  Transcontinental Railroad's stages were unknown in E → **3/3/3/3** from P.
- **Effects review, expansion (69 effects):** 1 wrong number (Sun Tzu draws 2 *extra* military cards, up to 5 — not
  "at least 2"), 12 missing conditions (Colossus only at Ages II/III, Silk Road active from its first stage, Red Cross
  limits for other players, Catherine and Coubertin once per game, Ian Fleming's timing and repeat limit, Darwin's
  minimum cost 1, Dietrich's unit kinds, Nobel's prize only after replacement, Arms Industry ties, Hippocrates' age
  ends, Confucius' revealed non-event cards — now rules.md T15.10), 11 ambiguous parameters renamed (Isabella,
  Watt, Nostradamus, Saladin, Call to Arms, Steve Jobs, United Nations, Dark Ages; Communism's +1 resource kept only in
  its yields so it cannot count twice) — all fixed.
- **Expansion values without a picture (decided from text, flagged):**
  - Republic revolution cost **2** (fan wiki, BGG playtester; NamuWiki 3).
  - Professional Sports resource cost **8** (base printed value; the rebalance changes its strength to 4; fan wiki 7,
    NamuWiki 8).
  - Communism 18 (1), +1 resource; Fundamentalism 16 (5), +6 strength; Military Theory's new 3+ copy assumed equal
    to the base card — from two or more text sources each.
  - New military cards (19): from the official rulebook clarifications plus the BGG overview and NamuWiki; Aggression:
    Kidnap's cost (1 military action) and the three extra Military Bonus cards' values (+2/+4/+6 defense, +1/+2/+3
    colonization, the base values of their age) rest on one source each.
- **Six new 3+ action cards:** only two identified (extra 3+ copies of Patriotism III and Revolutionary Idea III, one
  playtester's examples). The other four (Age I ×1, Age II ×2, Age III ×1) are named in no reachable source and are
  **left out** by the maintainer's decision (2026-11-02): 3–4 player civil decks are one card (Age I, III) or two cards
  (Age II) short of the official count; 2-player games are unaffected (3+ cards are removed there).

## Data changes during build-engine

Stage 3 (2026-11-02; `card_effects.py` edited, `cards.json` rebuilt with `build_cards.py` from the inbox sources —
only these three entries changed):
- **Aggression: Raid I/II/III:** new parameter `aggressor_gains_cost_divisor: 2` — the aggressor gains resources equal
  to the printed costs of the destroyed buildings divided by 2, rounded up. Printed on the card (B; T) but missing
  from the structured effect; stage 2 had it hard-coded in the handler (STATUS Q12), which now reads the parameter.
- **Trade Routes Agreement:** new parameter `uses_per_turn: 1` — each party may convert once per turn (any player's
  turn), the stage-2 reading (STATUS Q10); the engine reads it.
- **Maximilien Robespierre:** new parameter `revolution_spends_military_actions: True` — a revolution costs all
  military actions instead of all civil actions (B's reading of the base card); the structured effect had only the
  3 culture (STATUS Q23).

## Open

- Identify the four missing 3+ action cards (a photo of the cards or an official card list would settle it).
- Printed name of "Aggression: Occupy" (one BGG source says "Occupation"); the name does not change the game.
- Pictures of the rebalanced Republic, Communism, Fundamentalism, Professional Sports and Military Theory would turn
  their text-only values into checked values.
