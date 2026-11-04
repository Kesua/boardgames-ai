# Through the Ages: A New Story of Civilization (+ New Leaders and Wonders) — engine plan

Design before code (plan-engine skill). Rule IDs (`T4.2`) refer to `rules.md`, card data to `data/cards.json`
(292 cards, `id` 0–291) and `data/card_effects.py`. An independent review (51 findings, 2026-11-02) is worked in.
Section 12 lists the design choices (confirmed by the maintainer, decision form round 3, 2026-11-02); section 13 the
build order.

## 1. Kit parts used

| Part | Use |
|---|---|
| `Rng` | the only random source: deck shuffles, starting player (T2.7), current-events deal (T2.5), leader/wonder selection and board assignment (T15.4, T15.9), future-events shuffle (T8.1), Development of Planning's 3 cards |
| `Deck` | civil deck, military deck, current events deck, future events deck (index 0 = top) |
| `Decision`, `DecisionStack` | every choice, with the deciding seat (defending, accepting a pact, bidding, event choices and Terrorism happen outside the turn) |
| `CodecBuilder` | the frozen action numbering (section 4) |
| `TextLog` | `P<seat>: …` lines for the log review (verify-engine) |
| `add_counts`, `one_hot` | encoder |
| `winners`, `ranks` | via the platform recorder; resignation ranking through scores (section 7) |

Nothing else exists in the kit. The card row, token banks, payment with change, army forming, events and all card
effects are game code.

## 2. State (plain data; `clone()` is a pickle)

Modules: `engine.py` (Game, flow, tasks), `state.py` (dataclasses), `economy.py` (banks, payment, production,
statistics), `military.py` (armies, strength, colonization force, aggressions, wars, the T8.3 ranking helper),
`effects.py` (one handler per effect type), `cards.py` (loads cards.json once; lookups by id/kind/age), `encoder.py`,
`agents.py`.

`Player`:
- `blue_bank`, `yellow_bank` (ints; may exceed 16/18, T1.9), `pool` (unused workers).
- `workers: dict[card_id, int]` on farm/mine/urban/unit technologies; `tokens: dict[card_id, int]` blue tokens on
  farm/mine technologies (food/resources, T12.1; with Bill Gates also on labs).
- `techs: list[card_id]` in play (incl. the 6 printed starting ones, T1.5), `government`, `specials: dict[kind,
  card_id]`, `leader`, `leaders_taken: set[age]` (T4.5), `wonders` (completed, entry order) + `ruined`, `unfinished:
  (card_id, stages_paid)|None`, `colonies`, `pact` (own-area pact: card, partner, sides), `wars: [(card_id, target)]`,
  `exclusive_tactic`, `tactic` (current, own or common), Sun Tzu's kept tactics, `homer_wonder`, Louvre tokens,
  Hippocrates reminders, Saladin mode, once-per-game flags (Catherine, Coubertin), Nobel prize state,
  `fleming_last_target`.
- `civil_hand`, `military_hand` (card ids, copies repeat), `taken_this_phase` (T5.10).
- Actions: only **spent** counts, temporary actions and forfeits are stored (`civil_spent`, `military_spent`,
  `temp_civil`, `temp_military`, `forfeit_next_politics` for International Agreement); totals are computed from the
  cards in play (T11.6); when a total falls, spent is clamped. Round 1: `civil_spent` preset so seat order gives 1, 2,
  3, 4 available (T2.8).
- Temporary resources by purpose (`temp: dict[purpose, amount]`, T12.9), vanishing at end of turn.
- `science`, `culture` points; per-turn flags (tactic played/copied T6.4, political actions used, leader replaced
  for Taj Mahal, Harvard, Gutenberg, Silk Road first card, Ocean Liner, Bach, Hammurabi, developments for Nobel).
- `known: dict[card_id, count]` cards this player knows outside its own hand (Ian Fleming's peek, Joan of Arc's top
  event), cleared when the knowledge goes stale.
- `resigned_order: int|None`; `culture_book: dict[(category, card_id|None), int]` (section 7).

`State`: `players`, `age` ("A"…"IV"), `round`, `start_seat`, `turn_seat`, `turns`, `last_round: int|None`, `row`
(13 × card_id|None), `civil_deck`, `military_deck`, `military_discard` (current age only, see T6.5 note below),
`age_a_unused` (Age A military cards set aside at setup, T2.5; never cleared by an age change; Development of
Planning draws from it), `current_events` and `future_events` as lists of `(card_id, preparer, known_by: set[seat])`,
`past_events`, `common_tactics`, the selected leaders/wonders and proxy boards (T15.8–T15.9), `tasks`, `decisions`,
`log`, `forced`, `rng`, `version` (a counter bumped on every change, the key of the statistics cache), `game_over`.

Discards (T6.5, D7): a military card goes to `military_discard` only if its age is the current age; a card of an
older age leaves the game (its pile left with its age). Invariant + test.

Statistics (strength, happiness, ratings, action totals, discontent, production) are pure functions of the state,
cached per player and `version` so the many strongest/weakest checks and encoder calls stay cheap (timed at build
step 3; army forming is memoised by (unit counts per type and level, tactic)).

## 3. Turn flow as decisions

All logic runs as a task stack (as in `games/wingspan/engine.py`): `_run()` works on the top task until one needs a
choice; the choice becomes the pending `Decision` (kind, seat, legal ids, data); `step_id` gives the answer to the
top task. A decision with exactly one legal answer is applied automatically and reported via `drain_forced()`. A
decision with **no** legal answer (a forced loss with nothing to lose, an effect with no target) is skipped and
logged; it never reaches a player.

Rounds: a round starts with the first seat still in the game clockwise from `start_seat` (so resignations, T7.2, keep
rounds and the last round working, T14.1). Task order per turn (T3): `start_of_turn` (T4.1 refill with age change T13
→ resolve war T9.5 → move exclusive tactic T3.3 → start-of-turn effects) → `politics` (T7; skipped in round 1; skipped
once after International Agreement) → `action_phase` → `end_of_turn` (T3.6: discard → end-of-turn effects (Genghis
Khan, Mandela, Eleanor) → uprising check → production → draw → reset). Round 1: only take-card actions (T3.2).

Decision kinds ("turn" = the player whose turn it is; "context" = data the encoder also sees):

| Kind | Decider | Answers | Notes |
|---|---|---|---|
| `POLITICS` | turn | PREPARE / AGGRESS / WAR / PACT verb, CANCEL_PACT, RESIGN, ability verbs (Alexander, Columbus, Catherine), END | a verb is legal only if some completion is legal (a card with a legal target and enough military actions, Gandhi +3) |
| `POLITICS_CARD` | turn | CARD from the military hand | after a political verb |
| `TARGET` | turn | SEAT | only legal rivals (T9.1, T9.4, pacts) |
| `PACT_SIDE` | turn | OPTION A/B | pacts with sides (T10.1) |
| `PACT_ANSWER` | partner | YES / NO | T10.1 |
| `CANCEL_WHICH` | turn | CARD (pact) | only when party to several pacts (T10.3) |
| `DEFEND` | rival | CARD (bonus card: its defense value; other military card: +1), NO | NO legal only before the first card; afterwards only cards that keep the tie reachable within the card cap (T9.2, D4) |
| `ACTION` | turn | ROW slot (take), CARD from hand (develop / leader / action card / tactic), verbs (INCREASE_POP, BUILD, UPGRADE, DESTROY, BUILD_UNIT, UPGRADE_UNIT, DISBAND, WONDER_STAGE, COPY_TACTIC, abilities: Hammurabi, Barbarossa, Ocean Liner, Bach, Gutenberg, Red Cross for other players, Louvre), END | every listed answer has a legal completion |
| `CHOOSE_TECH` | turn | CARD (technology in play) | build on / destroy from / upgrade from; Freedom of Movement "from" (with NO) |
| `UPGRADE_TO` | turn | CARD | upgrade target (T5.4); Bach (any urban → theater); Freedom of Movement "to" (any type) |
| `STAGES` | turn | AMOUNT 1..k | stages in one action with Masonry/Architecture/Engineering (T5.7), k = stages allowed and payable |
| `REVOLT` | turn | YES / NO | after choosing a government (from hand or a develop action card / event) when both ways are legal |
| `SUB_ACTION` | turn | verb (BUILD/UPGRADE/…), then CHOOSE_TECH / UPGRADE_TO / hand CARD | action cards with a choice (Rich Land, Urban Growth: build or upgrade; Breakthrough: which card), Development of Civilization (OPTION first) |
| `CHOOSE_TACTIC` | turn | CARD (common tactic) | COPY_TACTIC; Sun Tzu's kept tactics are not offered |
| `DISCARD_MILITARY` | turn | CARD | end of turn, one card per decision down to the limit (T3.6) |
| `BID` | each bidder clockwise | AMOUNT, NO | colonization auction (T8.4); max = largest force the player can send (incl. Isabella, James Cook) |
| `SEND` | winner | CARD unit technology (send one unit), CARD bonus card (its colonization value), CARD other military card (James Cook discard, +1, at most 2), OPTION 1–3 (Isabella purchase, once), STOP | at least one unit; STOP legal once force ≥ bid, more units may still be sent (T8.5: their workers go to the yellow bank) |
| `MIX` | per effect | OPTION food / resource, STOP | one unit at a time: Plunder (STOP allowed), Foray, Raiders, International Negotiations' type |
| `EVENT_CHOICE` | each affected player clockwise from the revealer | OPTION / CARD / ROW | Development of Markets, Ravages of Time (which wonder), Development of Planning (CARD among the 3 shown; the chosen event then applies to the chooser only, possibly nested), Autonomous Territory's reward |
| `TAKE_LOOP` | strongest | ROW, NO | International Agreement: takes against a budget of 5 civil actions, each take checked by T4.3–T4.6, then slide and refill without discards (may change the age and start the last round) |
| `LOSE_WORKER` | per effect (owner, or attacker for Raid/Border Conflict choices stated per effect) | CARD | lose population with no unused worker (T11.7); destroy a building |
| `TERRORISM` | the fewest-culture player | CARD | one decision per victim clockwise; victim seat in the context |
| `LOSE_BLUE` | owner | CARD | blue tokens lost beyond the bank (T11.9) |
| `STEAL_TECH` | victor | CARD, NO | War over Technology: special techs (cost ≤ remaining advantage, T9.6) in a loop; NO takes the rest as science |
| `KIDNAP` | aggressor | CARD, NO | candidates (from the target's hand, filtered by T4.3–T4.5) shown in the context |
| `INFILTRATE`, `ANNEX` | aggressor | CARD | leader/unfinished wonder; colony |
| `ABILITY` | owner | OPTION / CARD / SEAT / YES / NO | Churchill's choice, Saladin's mode, Boudica's choice, Homer's tuck, Himeji sacrifice (attacker after TARGET — counts for the T9.1 check, lost even if the aggression fails; defender inside DEFEND; at war resolution declarer then rival), Ian Fleming's SEAT, Columbus / Suez Canal territory from hand, United Nations event from hand (on completion), Steve Jobs, Louvre |

## 4. Action numbering (frozen once a model exists)

`CodecBuilder` segments, in this order:

| Segment | Size | Meaning |
|---|---|---|
| `END` | 1 | end the action phase / pass the political action |
| `NO` | 1 | decline, stop, give up |
| `YES` | 1 | accept, confirm |
| `ROW` | 13 | card-row slot |
| `VERB` | 32 | action and political verbs without a card (increase population, build, upgrade, destroy, build/upgrade/disband unit, wonder stage, copy tactic, prepare, aggression, war, pact, cancel pact, resign, one verb per activated card ability; spare numbers reserved) |
| `CARD` | 292 | a card by `cards.json` id: in a hand, in play (own or, with the victim fixed in the context, another player's), a common tactic, a shown card |
| `SEAT` | 3 | another player, offset clockwise from the decider |
| `AMOUNT` | 128 | a number 1–128 (bids, stages) |
| `OPTION` | 8 | the i-th listed option of the decision |

Total 479, the same for every player count. Copies of a card share the id. A two-step action records its card on the
completing step (section 9).

## 5. Optional vs mandatory

- Optional (END/NO): the political action, every action-phase action, bidding, defending (before the first card),
  pact acceptance, abilities that say "may", events that say "may" (Development of Religion/Warfare/Civilization,
  Freedom of Movement), stopping a plunder below its maximum, Kidnap, stopping International Agreement's takes,
  sending more colonization force than the bid.
- Mandatory: discarding excess military cards, choosing what to lose when an effect forces a loss (Foray's gain and
  Raiders' loss are full), the last bidder's colonization, war resolution, production, corruption, consumption,
  age-change losses (T13.4).
- Automatic (no decision): payments of food and resources (choice C1), army forming for the highest strength (T11.4),
  Trade Routes conversions when they are needed to pay (C1). (Gutenberg's action: an ACTION verb, rules D30.)
- Every answer other than END must use up something bounded (actions, a once-per-turn flag, tokens, cards), so turns
  end; tested.

## 6. Effects

`effects.py` has one handler per effect `type` in `card_effects.py` (about 200 types; family types serve many cards):
- **Passive modifiers**, read by the cached statistics: strength, culture/science/happiness, action totals, hand
  limits, urban limit, cost changes (construction, Moses, Shakespeare, Watt, Gaudí, Colosseum, Darwin, Acropolis),
  army forming (Genghis Khan, Žižka, Dietrich, Hussars, air forces), production bonuses (T15.6:
  `economy.produce_resources` = mine production, then all bonuses summed at once, may be negative; Impact of Industry
  counts mines only).
- **Hooks**, in this order when several fire at once: the turn owner's cards first, then other players clockwise;
  within a player, the card that entered play first. Hooks: `on_enter_play` / `on_leave_play` for every kind
  (token symbols T11.9 — gain or lose, LOSE_BLUE when the bank runs short —, action totals T11.6, pacts and colonies;
  Annex = leave for the loser, enter for the winner without the one-time effect, T8.7), start of turn, start of
  politics (Joan of Arc, Ian Fleming), start of action phase (Boudica, Maria Theresa, Cleopatra), on take card, on
  develop (also on revolution), on prepare event, on colonize, on wonder stage, on wonder complete (Age III wonders,
  Suez Canal, United Nations, Hanging Gardens), on leader replaced, end of turn, age start (Colossus, Hippocrates,
  Roman Roads), game end (Bill Gates).
- **Activated abilities** are `VERB` answers in `ACTION` or `POLITICS`.
- **One-shot effects** (events, action cards, territories, aggressions, wars): a handler pushes the tasks and
  decisions it needs. Event handlers take the list of players they apply to (Development of Planning applies an event
  to one player).
- **Ranking helper** `rank_players(stat, mode, game_end)` implements T8.3 once (current player counts higher, then
  clockwise; starting player at game end; "all with most" keeps ties; with 2 players "two strongest" = the stronger),
  with card overrides (Genghis Khan wins ties, Nostradamus +3 only in weakest checks and defense against aggressions).
Every card gets a card test (`@pytest.mark.card`) in build-engine.

## 7. Scoring

- `scores()`: culture points (T14.3); higher is better. Resigned players (T7.2–T7.3): `-1 - k`, where k is the number
  of players who resigned after them (choice C5).
- `tiebreaks()`: `None` (ties share the win).
- `breakdowns()` categories (manifest `score_categories`), each the **actual** change of culture points it caused
  (losses capped at what the player had, T12.4): `production` (culture rating each turn), `leaders`, `wonders`,
  `events` (prepared events, event effects, the final Age III evaluation), `military` (aggressions, wars, the 7 culture
  for wars on a resigned player), `colonies`, `actions` (action cards), `famine` (negative), `resigned` (for a resigned
  player: its score minus the sum of the other categories). The categories always sum to `scores()`.
- Per-card culture (choice C3): every culture change caused by a card is booked to that card; each turn's culture
  rating is booked to its sources with their exact signed contributions (per worker on buildings, wonders, leader,
  government, colonies, pact sides); bonuses that depend on other cards (Michelangelo, Chaplin, Gaudí, Hollywood) go
  to the card with the text; only when the rating is clipped at 0 are the parts scaled (largest remainder, fixed card
  order) so they sum to the rating.
- `tableau(seat)`: one row per card in play at the end, plus leaders and wonders that left play: item = card key,
  kind = card kind, group = age, points = culture booked to it, tags = kind, age, set (base/rebalanced/new).
- `seat_extra(seat)`: `hand_left` = civil and military hand card ids at the end (a resigned player's at
  resignation), final science points, strength, culture and science ratings, rounds played.

## 8. What the agent observes (encoder; built in design-rl, for the deciding seat)

- **Global**: age, round, last-round flag, seat offset to the starting player, card row (per cost group 1/2/3 a
  card-count vector, plus the slots discarded at the next refill), deck sizes, current/future events **counts per age
  only**, past events, common tactics, selected leaders and wonders still to come and the Age A deck contents (public
  mix).
- **Decision context**: decision kind, the card / amount / target it concerns, the bid to beat, force still needed,
  budget left (International Agreement), and a 292-count **candidate vector** for choices among cards only the decider
  may see (Kidnap's candidates, Development of Planning's 3 cards).
- **Own private**: civil and military hand (counts per card id), events I prepared in either event deck, and `known`
  cards (Ian Fleming's peek, Joan of Arc's top event, Nostradamus' seen events in either deck).
- **Every player (public)**: technologies in play with workers and tokens, government, leader, wonders (completed,
  unfinished and stages paid), colonies, pacts, wars, tactic, banks, unused workers, action totals and spent, ratings,
  strength, happiness, discontent, science and culture points, hand sizes per age, and the civil hand of a player
  with Ashoka in play (T16.2).
- **Hidden**: other players' civil and military hands (P4), deck orders, the current events deck, others' prepared
  events (unless known). No legal-answer set depends on another player's hidden cards except Kidnap's (allowed, T16.2).
  Test: changing anything hidden from seat s leaves seat s's observation unchanged.

## 9. Recording and contract helpers

- `record_info(a)` before `step_id`: `decision` (kind), `decision_label` (verb of a two-step action), `action` (TAKE,
  DEVELOP, BUILD, UPGRADE, DESTROY, PLAY_LEADER, PLAY_ACTION, WONDER_STAGE, REVOLUTION, PREPARE, AGGRESSION, WAR, PACT,
  BID, SEND, DEFEND, DISCARD, …), `card`/`item` on the step that names the card (verb steps: None), `tags` {kind, age,
  set}, `extra` {cost paid, civil/military actions used, row slot}. Forced single-answer decisions and automatic
  events (revealed current events, war resolutions) go through `drain_forced()`.
- `catalog()`: one item per card key (292), `count` = copies in a 4-player game (stated in the catalog), proxies are not
  cards.
- `invariants(game)`: every physical card in exactly one zone; blue and yellow tokens conserved except moves to/from
  the box; urban limit; at most one leader and one unfinished wonder; spent ≤ total actions; military discard holds
  only current-age cards.
- `text_state()`: full deterministic dump (hidden hands included, for the clone check and logs); `describe(a)`: per
  segment, with card names.
- `SPEC.rounds = lambda g: g.s.round` (rounds completed; correct after resignations).

## 10. Game length

Variable: Age IV starts when the Age III civil deck runs out (T14.1); about 20 rounds expected (B-12.4), worst case for
random players about 40 rounds × 4 players × ~40 decisions ≈ 6,400 decisions. `max_steps` = 30,000.

## 11. Risks and how they are tested

| Risk | Test |
|---|---|
| Payment with change, token conservation, corruption before production (T12.2–T12.5) | rule tests with fixed token layouts; invariant |
| Bank tables and the leftmost-empty-section reading (T1.7, T1.8, T11.8) | table tests for every N 0–20 |
| Army forming with outdated armies, air forces, Genghis/Žižka/Dietrich/Hussars | exhaustive small cases against brute force over all groupings |
| Production bonuses order (T15.6) | rule tests with mines, bonuses and Acceptance of Supremacy B |
| Age changes inside a refill (T13), last round (T14.1), International Agreement ending Age III | scripted decks |
| Event deck flip and age order (T8.1), final Age III evaluation (T14.2, D8, D19) | scripted event decks |
| Colonization auction and force incl. Isabella, Cook, overpaying (T8.4–T8.6) | scripted auctions |
| Aggression strength rule, defense, Himeji, wars at start of turn, pacts ending on attack (T9, T10) | scripted fights |
| Revolution vs peaceful change, action totals rising/falling (T5.8, T5.9, T11.6) | rule tests |
| Hand limits, same-name technologies, one leader per age, wonder surcharge (T4.3–T4.6) | rule tests |
| Uprising, famine booked as actual loss (T11.8, T12.7, T12.4) | rule tests; `sum(breakdowns) == score` check |
| Ties (T8.3) and their card overrides | ranking-helper tests |
| Hidden information (T16.1, T16.2) | encoder hiding test |
| Resignation incl. the starting player resigning (T7.2, T7.3) | scripted games to the end |
| Military discards by age (T6.5, D7), Development of Planning's pile | invariant; scripted test |
| Public mix proxies and boards (T15.8, T15.9) | scripted proxy deal |
| Speed of statistics | timing at build step 3 (target: a 2-player random game well under 1 s) |
| Every non-END answer bounded; no empty legal lists | random-game checks (bgai.checks) and a unit test over random states |
| 200 effect types | one card test per card |

## 12. Design choices (confirmed by the maintainer, 2026-11-02)

- **C1 Automatic payment.** Food and resources are paid automatically: the exact amount, choosing among exact
  payments the one that returns the most blue tokens to the blue bank (lowers corruption), ties keeping higher-value
  tokens; with no exact payment, the smallest overpayment that empties the bank (T12.3). Trade Routes conversions are
  used automatically when needed to pay (Gutenberg's action is a choice after the review, rules D30); temporary
  resources first (T12.9). Losing
  blue tokens from cards with an empty bank stays a decision (`LOSE_BLUE`). The rules let a player choose each
  combination; a decision per token would add many steps for almost no strategic weight.
- **C2 Two-step actions.** Take a card = one answer; playing a hand card = one answer; build/upgrade/destroy and
  political actions = verb, then card/target. Keeps the numbering at 479 and each decision small.
- **C3 Per-card culture attribution** for the dashboard (section 7).
- **C4 Bids up to 128** (AMOUNT segment). Colonization force above 128 is not reachable in practice; an invariant fails
  if a player's possible force ever exceeds 128, so the cap can never silently change an auction.
- **C5 Resignation in checks.** `bgai.checks` always runs the game's default options. With resigning on, random
  players resign by round 2–3 (often the only political answers are END and RESIGN), so checks would barely reach Ages
  II–IV. Options: (a) default `allow_resign` off — resigning stays implemented and tested by rule tests and can be
  switched on for experiments; (b) add an options flag to `bgai.checks` (a platform change via the upgrade-platform
  skill) and run checks both ways. **Chosen: (a).** Resigned players score −1, −2, … (section 7).

## 13. Build order (build-engine, each step with its rule and card tests)

1. Data loading, state, setup (T1–T2), card row and taking cards (T4), round 1 (T3.2).
2. Economy: banks, payment, production, corruption, consumption, uprising, population, build/upgrade/destroy,
   develop, revolution, leaders, wonders, action totals (T5, T11, T12).
3. End of turn, ages and game end with no military (T3.6, T13, T14) — a complete peaceful game; first random-game
   checks and timing here.
4. Military: units, tactics, armies, strength (T6, T11.3–T11.4); military cards, discards by age.
5. Politics: events and colonization (T7, T8), aggressions and wars (T9), pacts (T10), resignation (T7.2).
6. Card effects family by family: action cards, events, territories, leaders, wonders, pacts (base), then expansion
   (T15) and the public mix.
7. Encoder hiding test, invariants, `bgai.checks` over 10,000 games per player count.
