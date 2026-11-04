# Independent review of the engine and data (verify-engine skill)

## Who and what

- **Reviewer:** an independent agent that did not write the engine, the card data or the tests; it read the code and
  the rules and ran its own scripts; it changed nothing in the repository. Reviewed state: the complete engine (base
  game + New Leaders and Wonders, Ages A–III, 2–4 players) after build-engine stage 3.
- **Standard:** the official rulebooks (base "Code of Laws" rulebook = CoL, New Leaders and Wonders rulebook = NLW),
  then the Unofficial FAQ v15 and the Board Game Arena code (source B). The maintainer chose the official rulebooks as
  the standard, so every finding they support was fixed the reviewer's way.
- **Fixes:** made by the engine author after the review; every fix has a test that failed before and passes after
  (`tests/test_review_fixes.py`, plus the extended hiding test in `tests/test_rules_military.py`). Readings that the
  sources left unclear are now rules.md T17 rows D20–D33.

## Checks that came out clean

| Check | Size | Result |
|---|---|---|
| Test suite at review time | 477 tests (TTA) | all passed |
| Encoder leak fuzz: other players' hands replaced by random same-age cards, deck orders shuffled, unknown event-deck entries replaced | 2,256 states, 2/3/4 players, random play | observation identical every time (one leak found by reading, F12, outside the fuzz: it kept known entries) |
| Stale statistics cache: cached statistics vs a fresh computation for every seat after every step | 85,062 steps | 0 differences |
| Army forming vs an exhaustive brute force (Genghis Khan, Jan Žižka's farms, Marlene Dietrich, Hussars, air forces, outdated armies) | 300 random cases | 0 mismatches |
| Score contract: breakdown sums = scores, culture book = culture, resigned players below active ones, take/play/develop/colonize steps carry a card, forced steps recorded | 120 games, ¼ with resigning | correct (except the colonization record of F13) |
| Age change inside a refill (II→III mid-deal) and the T14.1 last round in/out of the starting player's turn | targeted cases | correct |
| Rule-by-rule reading of T1–T16 against the code | all modules | matches except the findings below |
| Game logs read against the rules | 3 logs: 2p seed 7 (greedy), 3p seed 11 (greedy/random/greedy), 4p seed 13 | plausible throughout; nothing a human would object to beyond weak greedy play |

## Findings and how they were resolved

Severity: bug-high (inflates statistics in many games), bug-low (wrong in rare or narrow cases), doubtful (a reading
the official rulebooks contradict), info (no defect today).

| # | Severity | Rule / card | Finding | Resolution |
|---|---|---|---|---|
| F1 | bug-high | T5.7; Engineering Genius A/I/II/III | built several wonder stages with a construction technology (one discount) | fixed: exactly one stage (CoL p6/p9, NLW p9/p11; D20); test `test_f1_engineering_genius_builds_exactly_one_stage_even_with_a_construction_technology` |
| F2 | bug-low | T4.2; Charles Darwin | the fast row filter used the printed slot cost, so a technology made affordable by Darwin's −1 was not offered (also in International Agreement) | fixed: the filter uses the reduced cost; test `test_f2_darwin_take_discount_is_offered_with_one_civil_action_left_and_in_international_agreement` |
| F3 | bug-low | Darwin + St. Peter's Basilica | Darwin ran first, so an Age A temple ended with 0 faces | fixed: St. Peter's before Darwin in the happy-face chain (NLW p9; D21); test `test_f3_darwin_and_st_peters_cancel_on_temples` |
| F4 | bug-low | Hollywood, Internet | counted printed symbols only | fixed: everything the buildings add, effects of other cards included (CoL p12; D22); tests `test_f4_hollywood_counts_leader_culture_bonuses_of_theaters_and_libraries`, `test_f4_internet_counts_leader_science_bonuses_of_urban_buildings` |
| F5 | bug-low | T5.9; Development of Civilization | its development could never be a revolution | fixed: revolution allowed, 1 science cheaper, all civil actions spent (CoL p12; D23); test `test_f5_development_of_civilization_allows_a_revolution_one_science_cheaper` |
| F6 | bug-low | Maximilien Robespierre | a revolution deleted Patriotism's temporary military action; a revolution through Breakthrough still cost the card's civil action | fixed: temporary action kept, the card's civil action given back (CoL p12; D24); tests `test_f6_robespierre_revolution_keeps_patriotisms_military_action`, `test_f6_robespierre_revolution_through_breakthrough_costs_no_civil_action` |
| F7 | bug-low | Pierre de Coubertin | the Olympic Games could not be declared after the political action was given up to International Agreement | fixed: a politics decision offering only the Games or passing (NLW p10; D26); test `test_f7_olympics_can_be_declared_after_the_political_action_was_given_up` |
| F8 | bug-low | Silk Road with Endowment for the Arts / Wave of Nationalism / Military Build-Up | "+1 in total" only when the count was not 0 | fixed: always +1 (NLW p9; D27); tests `test_f8_silk_road_adds_one_to_a_per_civilization_total_of_zero`, `test_f8_silk_road_adds_one_to_military_resources_per_stronger_civilization_of_zero` |
| F9 | bug-low | Homer tucked under a wonder later ruined | the face was lost | fixed: the ruins keep it (CoL p12; D28); test `test_f9_homers_face_stays_on_a_ruined_wonder` |
| F10 | bug-low | International Tourism, United Nations | ruined wonders not counted | fixed: they count as completed wonders (CoL p12, Ravages of Time; D28); tests `test_f10_international_tourism_counts_a_ruined_wonder`, `test_f10_united_nations_counts_a_ruined_wonder` |
| F11 | bug-low | James Watt leaving play | "best farm or mine" ignored Machu Picchu's / Transcontinental Railroad's extra token | fixed: extra tokens counted (NLW p9; D29); test `test_f11_james_watt_best_mine_counts_machu_picchus_extra_token` |
| F12 | bug-low (information) | T16.1; Nostradamus | the encoder's "top card known" flag (meant for Joan of Arc's look) also fired for Nostradamus' cards after the future deck became the shuffled current deck: deck order leaked | fixed: Joan's look kept apart (`peeked_by`); tests `test_f12_nostradamus_does_not_learn_the_order_after_the_future_deck_is_shuffled`, hiding test `test_cards_that_reveal_information_reach_exactly_the_players_who_may_see_it` extended |
| F13 | bug-low (statistics) | Christopher Columbus, Suez Canal | colonizing from hand recorded Columbus / Suez as the card, never the territory | fixed: the territory is recorded (the colonizing card in `extra.by`); test `test_f13_columbus_colonization_records_the_territory` |
| F14 | doubtful | Johannes Gutenberg | his action was used automatically on the first lab/library action (losing his discount for a later one) and never for an action card | fixed: optional ACTION verb GUTENBERG (frozen number 26, a former spare; the numbering keeps 479 numbers and no number moved) for the next lab/library take, develop, build or upgrade or an action card used for one, discounts cumulative (NLW p8; D30); tests `test_f14_gutenberg_is_optional_and_can_wait_for_a_later_lab_action`, `test_f14_gutenberg_pays_for_an_action_card_used_on_a_lab_or_library_with_both_benefits`, `test_f14_gutenberg_alone_builds_a_lab_when_no_civil_action_is_left` |
| F15 | doubtful | T15.6; Bill Gates | lab output was a resource production bonus | fixed: Age I+ labs work as mines (tokens worth the lab's level, corruption, change, kept after he leaves; not in Impact of Industry) (CoL p12; D31); test `test_f15_bill_gates_labs_produce_blue_tokens_like_mines` |
| F16 | doubtful | T6.4; Sun Tzu | the +1 belonged to the owner and to the card id; others copying the tactic never got it | fixed: the marked card is its own tactic, never merged, +1 for whoever uses it, copyable (NLW p7; D32); test `test_f16_sun_tzus_tactic_gives_its_bonus_to_whoever_copies_it_and_is_never_merged` |
| F17 | doubtful | Trade Routes Agreement | usable on any player's turn, once per turn (the limit had no source) | fixed: only during the user's own turn, no limit; card data `uses_per_turn` removed (card text, source B; D33; data/SOURCES.md); test `test_f17_trade_routes_only_during_the_users_own_turn_and_without_a_per_turn_limit` |
| F18 | doubtful | T11.6; Hammurabi + revolution | a revolution deleted the temporary civil action | fixed: temporary civil actions stay (D25); test `test_f18_hammurabis_temporary_civil_action_survives_a_revolution` |
| F19 | info | Louvre Museum | the token exchange is an ACTION verb only, the card says "any time" | no change: documented simplification (STATUS Q31); using it outside the own action phase (e.g. to pay Isabella's purchase in another player's auction) is rare and small |
| F20 | info | encoder | the number of legal answers of the pending decision is encoded for any viewer | no change: the encoder is only ever called for the deciding seat (`bgai/agents.py`, `bgai/rl/selfplay.py`), so nothing leaks; revisit if a value head ever encodes other seats |

Counts: bug-high 1, bug-low 12, doubtful 5 (all fixed), info 2 (no change).

Data changes from the review: one — Trade Routes Agreement loses `uses_per_turn: 1` (`data/card_effects.py`,
`cards.json` rebuilt; only that entry changed). Everything else changed engine code only. The observation changed
(tokens on Bill Gates' labs, Sun Tzu's marked tactic, Joan of Arc's look); no model exists yet.

## Open questions STATUS.md Q1–Q40: verdicts

| Verdict | Questions |
|---|---|
| agree | Q1, Q2, Q4, Q5, Q6, Q7, Q8, Q9, Q11, Q12, Q13, Q14, Q15, Q16, Q18, Q19, Q20, Q21, Q27, Q28, Q32, Q33, Q35, Q36, Q37, Q40 |
| agree in principle, detail fixed | Q23 Robespierre (F6), Q29 Nostradamus (encoder leak, F12), Q39 Caesar / Coubertin (Olympics after a forfeit, F7) |
| partly reversed | Q17 (Development of Civilization may revolt, F5), Q24 (Hollywood / Internet, F4; Chaplin kept), Q30 (Silk Road +1 when 0, F8), Q38 (Watt counts extra tokens, F11; Mandela kept), Q34 (Darwin after St. Peter's, F3) |
| reversed | Q3 (Engineering Genius, F1), Q10 (Trade Routes, F17), Q22 (Gutenberg, F14), Q25 (Bill Gates, F15), Q26 (Sun Tzu, F16) |
| acceptable simplification, kept | Q31 (Louvre, F19) |

STATUS.md carries the corrected readings, each marked with its finding and decision row.

## Automated checks (report.json)

`checks/report.json` (10,000 random games per player count on the current engine) is still to be made; after the
fixes `python -m bgai.checks --game through_the_ages --games 1000 --no-write` reported 0 problems for 2, 3 and 4
players (greedy beat random 40/40). A random game takes about 19 / 35 / 57 ms for 2 / 3 / 4 players (237 / 411 / 668
decisions; before the fixes 19 / 32 / 55 ms).
