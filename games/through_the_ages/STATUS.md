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
- [x] build-engine: engine + tests (every rule ID, every card)
  - [x] stage 1 (PLAN 13 steps 1-3, 2026-11-02): a complete peaceful game. Modules `cards.py`, `state.py`,
        `economy.py`, `effects.py` (hook registry; 10 of 150 effect types: `effects.UNIMPLEMENTED_EFFECT_TYPES`),
        `military.py` (draw, discard by age, strength without armies), `engine.py`, `describe.py`, first `encoder.py`
        and greedy `agents.py`. Military units (build/upgrade/disband, T6.1-T6.3) are in; tactics, armies,
        politics (only END offered), events, colonies, aggressions, wars, pacts, resignation are not.
        `bgai.checks --games 200`: 0 problems, greedy beats random 40/40. Random 2p game ~12 ms (209 decisions,
        ~20 rounds), 4p ~32 ms. Rule IDs still untested (later stages): T6.4, T7.x, T8.x, T9.x, T10.x, T11.3
        (armies part; unit strength works), T11.4, T12.9, T14.2 (stub `effects.final_events`), T15.1, T15.5,
        T15.7, T15.10, T16.2. No card tests yet (stage 6).
  - [x] stage 2 (PLAN 13 steps 4-5, 2026-11-02): military and politics. New module `politics.py` (the politics
        phase and every military decision as tasks: POLITICS verbs PREPARE / AGGRESSION / WAR / PACT / CANCEL_PACT /
        RESIGN, events with the T8.1 flip, colonization auction BID/SEND, DEFEND, war resolution at the start of the
        declarer's turn, pacts with sides and answers, resignation, MIX, EVENT_CHOICE, LOSE_WORKER, TERRORISM,
        STEAL_TECH, KIDNAP, INFILTRATE, ANNEX, TAKE_LOOP); `military.py` now holds armies (T11.4, memoised, checked
        against a brute force), strength, colonization force, attack strengths with pact rules and the T8.3 ranking
        helper `rank_players` (hook points `rank_bonus` / `tie_priority` for Nostradamus / Genghis Khan, stage 3);
        tactics play/copy/sharing (T6.4, T3.3) in `engine.py`; all 125 military-deck cards' effects in `effects.py`
        (hooks `event`, `colonize`, `aggression`, `war`, `pact`, `army`) incl. the final Age III evaluation (T14.2).
        Also Patriotism (`military_boost`, the T12.9 example) and the Q1 payment fix. 76 of 150 effect types
        implemented (74 left in `effects.UNIMPLEMENTED_EFFECT_TYPES`, all civil: leaders, wonders, a few action
        cards). Tests: `tests/test_rules_military.py` (every stage-2 rule ID), `tests/test_cards_military.py` (125
        card tests). `bgai.checks --games 300`: 0 problems for 2/3/4 players, greedy beats random 95 %. Random game
        ~16 / 28 / 45 ms for 2 / 3 / 4 players (231 / 409 / 664 decisions). Hook points left for stage 3: Isabella,
        James Cook, Columbus (colonization), Himeji Castle, Gandhi, Julius Caesar's extra political action, Sun Tzu,
        Confucius (prepare any military card), Joan of Arc / Ian Fleming / Nostradamus (seen events, `known`).
  - [x] stage 3 (PLAN 13 steps 6-7, 2026-11-02): every civil card effect. New module `civil.py` (74 effect types:
        passive statistics incl. the happy-face chain `effects.LATE_ORDER`, hooks, ABILITY decisions, activated
        abilities as VERB 15-25: ALEXANDER, COLUMBUS, CATHERINE, OLYMPICS in POLITICS; HAMMURABI, BARBAROSSA,
        OCEAN_LINER, BACH, CHURCHILL, LOUVRE, RED_CROSS in ACTION; numbering still 479). Rule-level effects live where
        the rule is computed: Gutenberg's action, Darwin/Michelangelo/Taj Mahal/Mandela take costs, Moses, science
        and build discounts (`Stats.sci_disc`, `build_disc`, Gaudi, Acropolis), temporary resources by purpose
        ('unit', 'civic', 'unit_science'), Robespierre's revolution, Harvard, Silk Road, Louvre tokens, Red Cross food
        stages, Machu Picchu / Transcontinental extra tokens (`economy.produce_step`), Ashoka's hand bonus, Genghis
        Khan / Jan Zizka / Marlene Dietrich army forming (`military.army_forming`, exact flow solver), Sun Tzu's
        tactics and boost, Julius Caesar's second political action, Nostradamus (events' weakest checks, aggression
        defense), Himeji Castle (aggressor, DEFEND, war resolution), Gandhi, Isabella / James Cook in SEND, Coubertin's
        Olympics, Nobel's prize, Hippocrates' reminders. Seen information: event deck entries carry `known_by`
        (Nostradamus, Joan of Arc), `Player.peek` (Ian Fleming), Ashoka's open hand; encoder version 2 shows each
        only to the players who may see it (test). `effects.unimplemented_effect_types()` is empty (test). Data: Raid's
        resource gain, Trade Routes' uses per turn, Robespierre's military-action revolution moved into the card data
        (SOURCES.md). Tests: `tests/test_cards_civil.py` (167 civil cards, 244 cases), hiding test for revealing
        cards. `bgai.checks --games 1000`: 0 problems for 2/3/4 players; own stress run 1,000 games per player count
        with resigning off and on, invariants every 4 steps: 0 problems (with resigning on random players resign within
        ~10-30 decisions, choice C5). Random game ~19 / 32 / 55 ms for 2 / 3 / 4 players (238 / 411 / 668 decisions;
        a quiet-machine run; stage 2 measured 16 / 28 / 45). Greedy beats random 40/40.
- [x] verify-engine: `checks/report.json` 0 problems over 10,000 random games per player count (2/3/4, 52 min, code
      964aca4); independent review in `checks/review.md` (20 findings: 18 fixed with tests, 2 notes; rules D20–D33).
  - [x] independent review (2026-11-02, an agent that did not write the engine): 20 findings (1 bug-high, 12 bug-low,
        5 doubtful, 2 info); every bug and all five doubtful findings fixed the reviewer's way (lead's decision: the
        official rulebooks support them), each with a test in `tests/test_review_fixes.py` that failed before;
        readings recorded as rules.md D20–D33, Q3/Q10/Q17/Q22–Q26/Q29/Q30/Q34/Q38/Q39 corrected below; one card data
        change (Trade Routes Agreement). Ruined wonders also count for International Tourism and United Nations
        (F10, D28); Columbus / Suez Canal colonizations record the territory (F13). Details: checks/review.md.
  - [ ] checks/report.json over 10,000 games per player count on the current engine
- [x] design-rl (2026-11-02): encoder, greedy, smoke training learns
  - Encoder version 1 (older versions dropped, no model existed): 3,385 / 3,705 / 4,025 floats for 2 / 3 / 4 players
    (global 1,427 incl. 13 row slots x 47 = take cost for the decider, discard flag and 45 printed card features;
    decision 651 incl. the card concerned + its features and the decider-only candidate vector; own 667; per player
    320, decider first then clockwise; static card features precomputed once). ~0.15 / 0.2 ms per observation (2p / 4p).
    Hiding tests unchanged and green; `tests/test_learning.py` pins sizes, range, row slots, decision context.
  - Greedy: plays each answer out to the end of the turn in a clone (completion steps by best value, depth 2; rest of
    the turn: end/pass), value = own position value - best other's (agents.py docstring). Paired seats, seeds 5000+:
    2p vs random 0.995 +- 0.005 (200 games, score 182 vs 16); 2p vs old greedy 0.990 +- 0.007 (200 games, 218 vs 93);
    4p vs random 1.000 (120 games, 349 vs 59; old greedy: 0.942, 198 vs 68); 4p vs old greedy 0.975 +- 0.014
    (120 games, 398 vs 238). Mirror scores: new 166 (2p), old 105. Speed (one process): 1.6 s per 2p greedy-mirror
    game (old 1.1 s), 8.4 s per 4p mirror game (~2 s of thinking per seat). `bgai.checks --games 300 --no-write`:
    0 problems, greedy beats random 40/40.
    Lead's change after merge: the look-ahead copy reshuffles the hidden orders first (civil, military and current
    events decks, the copy's random source), so greedy no longer reads the next event or its military draw; the
    strength numbers above were measured before this change.
  - Smoke run (2p, `--timesteps 1000000 --chunk 200000 --envs 8 --eval-workers 3`, runs/through_the_ages/smoke):

    | steps | games | win_vs_random | win_vs_greedy (40 g) | win_vs_anchor |
    |---|---|---|---|---|
    | 200k | 983 | 0.925 | 0.000 | |
    | 400k | 1,854 | 0.950 (random retired) | 0.025 | |
    | 600k | 2,688 | | 0.125 | |
    | 800k | 3,510 | | 0.225 | 0.500 |
    | 1M | 4,330 | | 0.300 | 0.650 |

    Paired h2h vs greedy, 150 deals (300 games): ppo_200000 0.010 +- 0.006 (margin -135), ppo_1000000 0.187 +- 0.023
    (margin -52): +0.177, 7.4 standard errors. Pass (random > 0.9 at 200k; greedy gain > 2 SE).
  - Throughput (22 cores, CUDA update; a `bgai.checks` job ran in parallel): `--envs 8`: 7.3M learned steps/h
    (31,700 games/h, ~230 learned decisions per 2p game, rising as play improves), 5.9M/h with evaluation.
    `--envs 16 --eval-workers 4` (400k-step runs): 2p 10.0M steps/h (46,000 games/h), 4p 9.6M steps/h (15,300
    games/h, ~630 decisions per game); 4p evaluation is slow (greedy games ~8 s; 1.4 min per chunk with 40 greedy games).
    Model-vs-model paired games: ~0.3 s (2p) / ~1.1 s (4p) per game per evaluation worker.
  - Budget estimate (train-model recipe, `--chunk 500000`, `--envs 16 --eval-workers 4`): 2p ~7.5M steps/h open,
    ~6M/h anchored (750-deal reference) -> 40M open in ~5.5 h + 30M anchored in ~5 h; ~150M steps would fit in 24 h.
    4p: ~4.7M/h open, ~2.3M/h anchored with the default 750 reference deals (3,000 games per evaluation); with
    `--greedy-games 8 --reference-deals 250` ~5.7M/h open and ~4M/h anchored -> ~100M steps in 24 h (40M open ~7 h,
    30M anchored ~7.5 h).
- [ ] train-model: open run, anchored run, acceptance -> finished model
  - 2p (2026-11-03): **`models/p2-29m` finished.** Open run plateaued at 12M (win against 3M older 0.510, 0.527),
    best = 8M. Anchored run from it rebased at 7M (0.806) and stopped at 24M (3 evaluations without a 0.02 gain;
    `win_vs_3m` 0.55 at the stop); best = 21M = the model (29M steps, 105,808 games, 5.5 h on 16 game workers +
    RTX 4070 Laptop). Acceptance (paired, 750 deals): greedy 0.971 (1,000 games, bar 0.95), open 12M never
    trained against 0.917, open 8M 0.921. `clipped` 0.41-0.43 through the open run (lr 2.5e-4, 10 epochs),
    0.07-0.13 anchored.
  - Engine fix during training (8b6c859): the anchored run crashed at 22M on a misrouted answer (War over
    Technology took Justice System from a loser with an empty blue bank; the loser's LOSE_BLUE sat above the steal
    task and received the victor's next STEAL_TECH answer). Decisions now remember the asking task; the loser's
    LOSE_BLUE resolves after the victor's steal choices (nothing in them touches the loser's farms and mines).
    Random play never reaches the path (0 misrouted questions in 3,000 games), so the open-run and earlier
    anchored checkpoints were kept; the run resumed with `--resume`.
  - 4p: open run started 2026-11-03 (`--greedy-games 8`).
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
  - Q1 Payment change (T12.3, C1) — RESOLVED (lead's review, fixed in stage 2): moving a token to a lower-value card
    moves the token itself (pays the difference, needs no bank token, works with an empty bank); breaking a token
    into several smaller ones takes the extra tokens from the blue bank (rulebook "pay and take change back").
    Paying more is allowed only when no exact payment exists AND the payment leaves the blue bank empty; the
    smallest such overpayment is chosen (`economy.plan_payment`, test T12.3 in test_rules_military.py).
  - Q2 Frugality (`increase_population` + `then_gain` food): implemented literally from card data: the player must
    afford the full food cost, then gains the food. If the printed card is a discount, the data should say so.
  - Q3 Engineering Genius (`wonder_stage` discount) — REVERSED after the review (F1, rules D20): it builds exactly one
    stage with its discount, even with a construction technology (was: several stages).
  - Q4 Wonder stage with an empty blue bank (T5.7): the owner picks a farm/mine token (LOSE_BLUE decision); with no
    token anywhere the stage still counts, uncovered.
  - Q5 Developing a government with a lower urban limit than the buildings in play: nothing is destroyed (rules
    silent); so the invariants do not check the urban limit, only building legality does.
  - Q6 Revolution through a develop action card (T5.10): allowed when all civil actions were available before the
    card was played; the revolution then spends all of them.
  - Q7 T13.3: antiquated cards are discarded from both hands (civil and military).
  - Q8 Each age's civil and military decks are built when the age begins, for the players still in the game
    (T7.2); proxy counts follow the setup selection (6/4 or 7/5) even after a resignation.
- Build-engine stage 2 readings (rules.md and card data silent or unclear; the lead decides):
  - Q9 Development of Planning: after every player picked, the 3 shown cards go back to the Age A cards set aside
    (rulebooks silent); while shown they are in `State.resolving`.
  - Q10 Trade Routes Agreement — REVERSED after the review (F17, rules D33): each party converts 1 for 1 only during
    its own turn, with no per-turn limit (was: any player's turn, once per turn); still automatic only when the tokens
    are not enough (C1). Card data: `uses_per_turn` removed (data/SOURCES.md).
  - Q11 Arms Industry: a player with no technology of a unit type gets nothing for that type (nobody "ties at none").
  - Q12 Aggression: Raid: the aggressor chooses the buildings, mandatory as far as possible; Raid II/III fill the
    "Age II (III) or older" slot first, then the "Age I (II) or older" slot; the aggressor gains half the printed
    costs of the destroyed buildings rounded up. That gain is printed on the card (sources B and T) but missing in
    `card_effects.py` (only `destroy_urban_max_ages`): implemented in the `raid` handler — suspected card-data gap.
  - Q13 Counting: Impact of Variety counts unit and urban types with at least one worker plus each special
    technology; Impact of Wonders and Knowledge of the Ancestors count ruined wonders (Ravages of Time) as completed
    wonders of their age; Impact of Technology counts Age III technology cards in play (unit/building technologies,
    specials, government); Impact of Population: content workers = all workers − discontent workers.
  - Q14 Taking food/resources/points (Plunder, Spy, Occupy, wars): the taker gains what the victim actually lost, at
    most the amount named (change a victim loses by overpaying is not gained).
  - Q15 Resignation: the resigned player's technologies, government and wonders stay frozen in its area (nothing
    reads them; the tableau shows them); hands, colonies, own pact, wars and exclusive tactic leave play. When one
    player is left the game ends at once without the final Age III evaluation (T14.2 is "after the last round").
  - Q16 Scientific Cooperation applies to every development incl. revolutions; if the partner has no science to
    pay, the party cannot develop at all (literal reading of "is possible only if").
  - Q17 Development of Religion / Warfare: the free build respects the urban building limit. Second part REVERSED
    after the review (F5, rules D23): Development of Civilization's development may be a revolution (1 science
    cheaper, all civil actions spent, only with all of them available).
  - Q18 Defense (T9.2, D4): the card cap is the defender's military action total; the defense ends automatically
    when the tie is reached; an aggression is legal even when its effect would find nothing to take (Annex without
    colonies, Infiltrate without leader or unfinished wonder): rules.md gives only the strength and pact conditions.
  - Q19 Freedom of Movement: from any farm/mine/urban building/unit to any other such card in play, paying
    max(0, cost difference after modifiers), urban limit on the destination; optional, clockwise from the revealer.
  - Q20 Rebellion / Call to Arms: lost civil actions are spent from the available ones now; players other than the
    revealer thus have fewer on their next turn. Politics of Strength's "game-ending age" is read as Age IV.
  - Q21 SEND: military bonus cards are offered only while the force is below the bid; units may still be sent after
    it (T8.5 overpaying).
- Build-engine stage 3 readings (card texts in the sources leave these open; the lead decides):
  - Q22 Johannes Gutenberg — REVERSED after the review (F14, rules D30): his extra civil action is optional; the
    ACTION verb GUTENBERG (frozen number 26, a former spare; numbering still 479) chooses it for the next action,
    which must be a lab/library take, develop, build or upgrade, or an action card used for one of these (the card's
    task is then limited to labs/libraries and his discount adds to the card's); 1 science / 1 resource discount and
    2 culture as before.
  - Q23 Maximilien Robespierre: a revolution spends all military actions instead of all civil actions (data flag);
    the new government's added military actions arrive spent, added civil actions arrive available (T5.9 mirrored).
    Corrected after the review (F6, rules D24): Patriotism's temporary military action is not spent; a revolution
    through Breakthrough gives the card's civil action back. Likewise (F18, D25) any revolution keeps temporary civil
    actions (Hammurabi).
  - Q24 "Produces culture" of other cards: Charlie Chaplin doubles the best theater's printed culture. Hollywood and
    Internet part REVERSED after the review (F4, rules D22): they count everything the buildings add incl. effects of
    other cards on them (statistics with minus without those buildings' workers).
  - Q25 Bill Gates — REVERSED after the review (F15, rules D31): Age I+ labs work as mines while he is in play (1 blue
    token per worker in mine production, worth the lab's level; they store and make change; tokens stay usable after
    he leaves); Impact of Industry does not count them; culture on leaving / at game end = their production.
  - Q26 Sun Tzu tucked under a tactic — REVERSED after the review (F16, rules D32): the marked card is its own special
    tactic, never merged, with +1 per army (air forces double it) for whoever has the marker on it; copying that
    tactic takes the marked card (`State.sun_tzu_tactic`, `Player.tactic_boost`). Kept tactics become common on the
    first turn without him.
  - Q27 Himeji Castle: the sacrificed unit adds its printed strength once more (+3 when defending); the aggressor
    decides after naming the target (the T9.1 check counts the best sacrifice; lost even if repelled; +3 culture);
    the defender's sacrifice is a DEFEND answer outside the card cap (D4 still applies); in a war the declarer then
    the rival decide at resolution, strengths taken before any sacrifice.
  - Q28 Genghis Khan's "ties go to you" applies to his own end-of-turn check only.
  - Q29 Nostradamus: +3 also in the T9.1 legality check of an aggression against him, not in wars; events other
    players prepare while he is in play stay known to his owner while they lie in an event deck (also after he
    leaves). Encoder corrected after the review (F12): Joan of Arc's look is kept apart (`peeked_by`), so Nostradamus'
    known cards no longer reveal their position after the future deck became the shuffled current deck.
  - Q30 Silk Road: active from the first stage (unfinished) and when completed; +1 to each benefit of the first action
    card of the turn, Patriotism's military action included. "Per civilization" part REVERSED after the review (F8,
    rules D27): +1 in total always, also when the count is 0.
  - Q31 Louvre's token exchange is an ACTION verb (own action phase only), not "at any time" (review F19: kept as a
    documented simplification, small effect).
  - Q32 Ian Fleming's look is optional (NO), the snapshot lasts until the end of his owner's turn; a turn without a
    look lifts the "not the same player twice in a row" limit. Joan of Arc's look is automatic (free information).
  - Q33 Winston Churchill's choice is an ACTION verb once per turn (no forced choice); Saladin's mode is chosen at
    every end of turn (keeping it is one of the two answers).
  - Q34 Happy-face chain — corrected after the review (F3, rules D21): Steve Jobs, Marlene Dietrich and Homer's tuck
    first, then St. Peter's Basilica (+1 per worker on a building), then Darwin (so with both, temples give their
    printed faces), then Michelangelo and Joan of Arc read the result. Homer's face stays on a ruined wonder (F9,
    D28).
  - Q35 International Red Cross for other players: 1 civil action + 3 food, once per turn; the stage token comes from
    the owner's blue bank, else a farm/mine token of the owner's choice (LOSE_BLUE asked to the owner), else none
    (Q4).
  - Q36 Catherine the Great: the gain needs that many tokens actually lost (a weaker player with an empty yellow bank
    does not count); legal even when nobody is weaker (once per game).
  - Q37 Isabella / James Cook in SEND: offered only while the force is below the bid (as Q21); Isabella buys once and
    only purchases that keep the bid reachable are offered; Cook discards any military card that is not a
    colonization bonus card, at most 2. The bid limit counts Cook's discards and Isabella's best affordable purchase.
  - Q38 Nelson Mandela: the take surcharge counts discontent after Forbidden City; surplus = happiness − faces
    required. James Watt part REVERSED after the review (F11, rules D29): on leaving, best
    farm/mine production includes Machu Picchu's / Transcontinental Railroad's extra tokens.
  - Q39 Julius Caesar with International Agreement: the forfeit takes one of his two political actions. Coubertin's
    Olympic Games also cost their owner 8 culture for an attack and end at the owner's next Politics Phase (forfeited
    or not) or when he resigns. Added after the review (F7, rules D26): the Games can be declared even when the
    political action was given up to International Agreement.
  - Q40 Ashoka's colours by card kind: farm/mine brown, urban grey, unit red, special blue, government orange, leader
    green, action yellow. Frederick Barbarossa is legal only when both steps can be paid (with a Trade Routes pact
    the check simulates the food payment first).
