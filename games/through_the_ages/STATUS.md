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
- [x] plan-engine: `PLAN.md` (state, 27 decision kinds, 479 action numbers, effects, scoring, encoder, risks);
      independent review (51 findings) worked in; design choices C1–C5 confirmed (round 3: automatic payment,
      two-step actions, culture per card, bids up to 128, resigning off by default in checks).
- [ ] build-engine: engine + tests (every rule ID, every card)
  - [x] stage 1 (PLAN 13 steps 1-3, 2026-11-02): a complete peaceful game. Modules `cards.py`, `state.py`,
        `economy.py`, `effects.py` (hook registry; 10 of 150 effect types: `effects.UNIMPLEMENTED_EFFECT_TYPES`),
        `military.py` (draw, discard by age, strength without armies), `engine.py`, `describe.py`, first `encoder.py`
        and greedy `agents.py`. Military units (build/upgrade/disband, T6.1-T6.3) are in; tactics, armies,
        politics (only END offered), events, colonies, aggressions, wars, pacts, resignation are not.
        `bgai.checks --games 200`: 0 problems, greedy beats random 40/40. Random 2p game ~12 ms (209 decisions,
        ~20 rounds), 4p ~32 ms. Rule IDs still untested (later stages): T6.4, T7.x, T8.x, T9.x, T10.x, T11.3
        (armies part; unit strength works), T11.4, T12.9, T14.2 (stub `effects.final_events`), T15.1, T15.5,
        T15.7, T15.10, T16.2. No card tests yet (stage 6).
  - [ ] stage 2: military (tactics, armies, strength T11.3-T11.4, T6.4), politics (T7-T10), resignation
  - [ ] stage 3: card effects family by family (140 effect types left), card tests, expansion details
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
- Build-engine stage 1 readings (rules.md silent or unclear; the lead decides, then rules.md T17 gets a row):
  - Q1 Payment change (T12.3, C1): the engine lets change come from the blue bank as new smaller tokens (a 2-token
    paying 1 becomes a 1-token; a 5-token paying 1 can become 3+1), limited by the bank's tokens; with too few bank
    tokens for exact change it pays the smallest possible overpayment. rules.md only names returning tokens and
    moving a token to a lower-value card; its "paying more empties your blue bank" clause implies bank change.
  - Q2 Frugality (`increase_population` + `then_gain` food): implemented literally from card data: the player must
    afford the full food cost, then gains the food. If the printed card is a discount, the data should say so.
  - Q3 Engineering Genius (`wonder_stage` discount): with a construction technology it may build several stages in
    that action; the discount comes off their summed cost once.
  - Q4 Wonder stage with an empty blue bank (T5.7): the owner picks a farm/mine token (LOSE_BLUE decision); with no
    token anywhere the stage still counts, uncovered.
  - Q5 Developing a government with a lower urban limit than the buildings in play: nothing is destroyed (rules
    silent); so the invariants do not check the urban limit, only building legality does.
  - Q6 Revolution through a develop action card (T5.10): allowed when all civil actions were available before the
    card was played; the revolution then spends all of them.
  - Q7 T13.3: antiquated cards are discarded from both hands (civil and military).
  - Q8 Each age's civil and military decks are built when the age begins, for the players still in the game
    (T7.2); proxy counts follow the setup selection (6/4 or 7/5) even after a resignation.
