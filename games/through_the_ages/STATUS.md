# Through the Ages: A New Story of Civilization — status

Edition modelled: second edition (CGE 2015), base game + the New Leaders and Wonders expansion, full game (Ages A–III).
Keep this file current; it is how another agent or person continues.

## Fit check (new-game step 1, 2026-11-02) — fits, with a size and training-strength risk

Facts marked (?) come from secondary sources and are confirmed in ingest-rules against the official rulebook.

- Players: 2–4. Smaller counts remove cards marked for more players (2 players: nine 3+/4 cards from each of civil
  decks I–III) and pact cards (?).
- Cards: 8 decks (civil + military for Ages A, I, II, III; Age IV has none); about 330 cards (?: one source says 179
  civil + 150 military). Many duplicates, so distinct cards are fewer — probably 150–200 (counted in build-card-db).
  Card kinds with their own effects: leaders, wonders, special technologies, actions, events, territories, tactics,
  aggressions, wars, pacts — the largest effect set on the platform so far (Wingspan: 30 power types).
- Hidden information: military cards in hand, the future-events deck, the face-down decks. Civil cards in hand: open
  or secret (?). The encoder must hide what is secret.
- Randomness: shuffled decks only (no dice) (?).
- Real-time or dexterity: none.
- Choices too large to number in one step: colonization bids and aggression defence (bid strength, then which units
  and bonus cards to sacrifice/play), "lose N population/resources/buildings" events, pact offers (3–4 players),
  build/upgrade/destroy across many building types and ages. All split into step-by-step decisions on the decision
  stack (plan-engine).
- Game length: many more decisions per game than Wingspan (each turn has several civil and military actions over
  roughly 15–20 rounds (?)); `max_steps` must be set high. This is the main training risk: one desktop and ≤ 24 h per
  player count may not reach a strong AI; train-model shows it honestly on the strength card if not.
- Rule sources: official CGE rulebook (PDF, 10+ MB, to download into `inbox/`), plus an independent second source
  (official FAQ / BoardGameGeek rulings / the Board Game Arena implementation's rules help).

- [x] ingest-rules: `rules.md` T1–T16 (97 rule IDs), decisions D1–D15 and proposed choices P1–P5 (section T17);
      two independent researchers: A = CGE rulebook (2015) + New Leaders and Wonders rulebook (CGE 2019, copy at
      cdn.1j1ju.com); B = Board Game Arena code (github.com/srussking/throughtheages @ 45b1c03), Unofficial FAQ v15,
      Misut Meeple walkthrough, RulesPal FAQ answers citing BoardGameGeek. All numbers agree. Maintainer choices
      (decision form round 2): public mix of leaders/wonders, rebalanced cards, expansion military decks, secret civil
      hands, resigning modelled.
- [x] build-card-db: `data/cards.json` (292 cards: 218 base, 18 rebalanced, 56 new), built by `data/build_cards.py`
      from BGA's typed data (A) checked field by field against the printed base cards (B, 237 faces, 1 difference
      settled) and the fan wiki card list (C); expansion from text sources (E) checked against the printed pictures of
      52 leaders/wonders (P, all agree). Structured effects in `data/card_effects.py`, reviewed card by card against
      the printed readings. `data/SOURCES.md`; `tests/test_data.py` pins the totals. Four new 3+ action cards left out
      (rules D18).
- [ ] plan-engine: PLAN.md (state, decisions, action numbering, effects, scoring)
- [ ] build-engine: engine + tests (every rule ID, every card)
- [ ] verify-engine: checks/report.json 0 problems (10,000 games per player count), independent review in checks/review.md
- [ ] design-rl: encoder, greedy, smoke training learns
- [ ] train-model: open run, anchored run, acceptance -> finished model
- [ ] run-experiment: mirror (+ versus) per player count, --verify passes
- [ ] write-notes: notes.json (en + other languages)
- [ ] publish-game: check_repo passes, publisher notice drafted, PR opened

## Scope decisions (maintainer, 2026-11-02, decision form)
- Full pipeline (not only up to a verified engine).
- Base game + New Leaders and Wonders expansion.
- Full game only (Ages A–III); no shorter variant.
- Engine supports 2–4 players; models trained for 2 and 4 players (2 first).
- Official rulebook downloaded from CGE into `inbox/through_the_ages/` (not committed).
- Round 2: public mix, rebalanced base cards, expansion military decks, secret civil hands, resigning modelled.
- Slug `through_the_ages`, name "Through the Ages: A New Story of Civilization".

## Open questions
- Missing: the four unidentified 3+ action cards; pictures of the rebalanced Republic, Communism,
  Fundamentalism, Professional Sports, Military Theory (text-only values, data/SOURCES.md).
- The scaffold still holds the template's toy game (engine, encoder, agents, rules tests); replaced from build-engine on.
