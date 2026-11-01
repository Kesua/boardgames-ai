# Wingspan engine plan (as built)

1. **Kit parts used:** `Rng` (all randomness: deck, bonus deck, goal tiles and sides, dice, first player),
   `Deck` (bird deck and bonus deck, index 0 = top), `Decision`/`DecisionStack` (every choice, with the deciding
   seat — pink powers and "each player" powers decide outside their turn), `CodecBuilder` (action numbering),
   `TextLog` (log review), `add_counts`/`one_hot` (encoder), `winners`/`ranks` via the platform recorder (tiebreak =
   food left). Not used: nothing else exists in the kit. Dice and the bird tray are Wingspan-specific (engine.py).
2. **State** (`engine.State`, plain dataclasses): players (hand, bonus cards, food[5], three rows of `Placed`
   birds with eggs, cache[5], tucked count, pink-used flag), deck, discard, tray[3], feeder and outside dice faces,
   bonus deck/discard, 4 goals, goal points, round, first player, active player, turn counters, the task stack,
   pending decisions, log, Oystercatcher reveal, forced-move records, setup flag.
3. **Turn flow as a task stack.** Every piece of logic is a task dict (`setup`, `round`, `turn`, `choose_action`,
   `play_bird`, `gain_food`, `lay_eggs`, `draw_cards`, `brown_row`, `power`, `pink`, `take_die`, `eff_*`). `_run()`
   works on the top task until one asks for a decision; `step_id` hands the answer back. Chains (white power → play
   another bird → its white power → pink triggers) are just tasks pushed in the right order. Pink triggers push the
   other players' pink tasks in turn order from the left of the active player, above the active player's next step.
4. **Action numbering (frozen):** ACTION 4, BIRD 180, HABITAT 3, FOOD 5, DIE 6, SLOT 15, TRAY 3, DECK 1, BONUS 26,
   PLAYER 5, YES, NO, REROLL = 250 numbers. Food payment is one token per decision (with a two-for-one branch), eggs
   one per decision, dice one per decision with an optional reroll, cards one per decision.
5. **Optional vs mandatory:** NO (stop) wherever the rules allow taking less or declining (W6.2, W10.1); never for
   costs already committed (the forest trade's extra die). A decision with one legal answer is applied automatically
   and recorded through `drain_forced()`.
6. **Effects:** 30 effect types (`cards.power_kinds()`), parsed from both card sources into structured dicts;
   `powers.can_use` hides powers that could change nothing; `powers.start_effect` runs one; pink powers in
   `powers.pink_effect`. Repeat powers carry a chain to prevent loops.
7. **Scoring:** `scoring.breakdown` = birds, bonus, goals, eggs, cache, tucked; goals scored at each round end (green
   by default with shared places, or blue); tiebreak = food in the personal supply.
8. **Observation** (`encoder.py`, 1,659 floats for 2 players): global (round, goals, feeder, tray, deck sizes),
   decision context (kind, bird concerned, amounts, allowed foods), own private state (hand per bird id, bonus cards,
   food, 15 mat slots × 58 features, bonus-card progress, goal counts, score), other players' public state (food, hand
   size, rows, eggs, cache, tucks, goal counts, score without their secret bonus points, pink powers). Secret setup
   choices are hidden until everyone has chosen.
9. **Recording:** `record_info` names the decision, what happened (PLAY, TUCK, DISCARD, KEEP, USE/SKIP, TAKE_DIE,
   DRAW_TRAY/DECK …), the bird concerned and the habitat; `tableau` reports every bird with its total points (printed
   + eggs + cache + tucked) and tags (habitat, nest, power colour).
10. **Game length:** fixed (4 rounds, 26 turns per player): `SPEC.rounds = 4`, so the length section is skipped.
11. **Risks and how they are tested:** pink timing and re-arming, feeder rerolls and refills, payment with
    two-for-one, repeat and move powers, tray refill timing, green-goal ties — each has rule tests
    (`tests/test_rules.py`, `tests/test_rules_more.py`); every bird has a power test (`tests/test_cards.py`); an
    independent audit (`checks/review.md`).
