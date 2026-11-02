# Through the Ages: A New Story of Civilization (+ New Leaders and Wonders) — rules as implemented

Own-words summary of the rules this engine implements. It is not the rulebook: read the official CGE rulebook ("Code
of Laws", 2015) at https://d.cge.as/tta_manual/through-the-ages-new-story-rules-en.pdf and the New Leaders and Wonders
rulebook (CGE, October 2019). Every rule has an ID; tests cite it with `@pytest.mark.rule("T4.2")`.

**Sources.** Two researchers worked independently (raw notes kept outside git).
- **A (official):** the CGE base rulebook, read page by page from rendered images (numbers printed only as pictures
  were read from the pictures), and the CGE expansion rulebook, read from a copy hosted by the rulebook site 1jour-1jeu
  (`cdn.1j1ju.com`; no copy on a CGE server was found; the expansion's component list matches CGE's own product page).
  No official FAQ or errata page exists; the expansion rulebook's "rebalance" and clarification pages act as errata.
- **B (independent):** the Board Game Arena implementation of this edition (code by Romain Fromi, maintained by
  srussking, github.com/srussking/throughtheages @ `45b1c03`, read, never run): every table, cost and turn step; the
  fan-written Unofficial FAQ v15 (2017, compiled from BoardGameGeek rulings); the Misut Meeple rules walkthrough
  (2016); RulesPal FAQ answers that cite BoardGameGeek posts; the BGA help page. BGA has no expansion support, so B's
  expansion notes are thin; expansion rules rest on A, with B confirming the component list and the selection modes.

"(A/B)" after a rule means both confirm it; "(A)" or "(B)" means one source only (the other is silent; where they
disagree, a decision in T17 says which reading is used and why). Card-by-card effects are card data (`data/`, build-card-db step), not rules.

**Scope.** Second edition, full game (Ages A–III, ending with Age IV), 2–4 players, with the New Leaders and Wonders
expansion as described in T15. Choices between official options (P1–P5 in T17) were made by the maintainer.

## T1 Components

- **T1.1** Boards: military board (strength track, common tactics area, future events, current events, past events),
  culture board, science board, current-age board, card row with 13 spaces, one player board per player. (A/B)
- **T1.2** Card row cost to take a card, by space from the left: spaces 1–5 cost 1 civil action, 6–9 cost 2, 10–13
  cost 3; the same for every player count. (A from the board picture, B from BGA code)
- **T1.3** Eight decks: a civil and a military deck for each of Ages A, I, II, III. Age IV has no cards. (A/B)
- **T1.4** Civil card kinds: technologies (any civil card with a science cost: farm and mine; urban buildings — lab,
  temple, library, theater, arena; military units — infantry, cavalry, artillery, air force; special technologies —
  civil/law, military/warfare, colonization/exploration, construction; governments), leaders, wonders, action cards.
  Military card kinds: events, territories (events that become colonies), aggressions, wars, pacts, tactics, military
  bonus cards (a defense value and a colonization value). (A/B)
- **T1.5** Player board: blue bank of 16 spaces in sections of 5, 5, 6 (left to right); yellow bank of 18 spaces in
  sections of 4, 4, 4, 4, 2; a worker pool; six printed starting technologies: Warriors (infantry), Agriculture (farm),
  Bronze (mine), Philosophy (lab), Religion (temple), Despotism (government). (A/B)
- **T1.6** Despotism gives 4 civil actions, 2 military actions and an urban building limit of 2. (A/B)
- **T1.7** Corruption by blue tokens left in the blue bank: 11 or more → 0; 6–10 → 2; 1–5 → 4; 0 → 6. (B from BGA
  code and three play-based sources; A's pictures hide these values under tokens — decision D1)
- **T1.8** Yellow bank, by yellow tokens left in it (N): food cost of one population increase N 17–18 → 2, 13–16 → 3,
  9–12 → 4, 5–8 → 5, 1–4 → 7, 0 → not allowed; food consumption N 17–18 → 0, 13–16 → 1, 9–12 → 2, 5–8 → 3, 1–4 → 4,
  0 → 6; happy faces required N 17–18 → 0, 13–16 → 1, 11–12 → 2, 9–10 → 3, 7–8 → 4, 5–6 → 5, 3–4 → 6, 1–2 → 7,
  0 → 8. (A from the board pictures except the two leftmost consumption values; B from BGA code — decision D1)
- **T1.9** Banks fill from the left and give tokens from the right. Tokens gained beyond the printed spaces stay in the
  rightmost section without limit and count as that section (N above 18 behaves like 17–18; above 16 blue tokens like
  11+). Token supplies are unlimited. (A/B)

## T2 Setup

- **T2.1** Civil decks I, II, III: with 3 players remove the cards marked "4"; with 2 players remove the cards marked
  "3+" and "4"; with 4 players remove nothing. With the expansion's rebalanced cards (T15.2) this removes, per deck
  I / II / III, 10 / 11 / 12 cards with 2 players and 3 / 2 / 1 with 3 players. (A/B; counts A from the expansion's
  card-count table — decision D2; four of the six new "3+" action cards are not modelled — decision D18)
- **T2.2** With 2 players remove all pacts from the military decks (2 in Age I, 4 in Age II, 4 in Age III). (A/B)
- **T2.3** Each player: 16 blue tokens in the blue bank; 18 yellow tokens in the yellow bank, 1 in the worker pool and 6
  as workers — 1 on Warriors, 2 on Agriculture, 2 on Bronze, 1 on Philosophy, 0 on Religion; no food, resources,
  science or culture points. (A/B)
- **T2.4** Starting statistics follow from T2.3: science rating 1, culture rating 0, strength 1, happiness 0. Each
  player's tactic marker starts in the common area meaning "no tactic". (A/B)
- **T2.5** Current events deck: shuffle the Age A military deck and deal (players + 2) cards face down; the rest of the
  Age A military deck is set aside unseen (used only by the expansion event Development of Planning). The future
  events deck and the past events pile start empty. (A/B)
- **T2.6** Shuffle the Age A civil deck and deal 13 cards face up into the card row; the rest is the current civil deck.
  (A/B)
- **T2.7** The starting player is chosen at random and never changes; turns go clockwise. (A/B; random choice: engine)
- **T2.8** In round 1 the starting player has 1 civil action available, the next players 2, 3 and 4; nobody has
  military actions available. (A/B)

## T3 Turn structure

- **T3.1** A turn has four parts in this order: start of turn, politics phase, action phase, end of turn. (A/B)
- **T3.2** Round 1: start of turn and politics phase are skipped; in the action phase the only allowed actions are
  taking cards from the card row (T4); the end of turn happens normally, but nobody draws military cards (no military
  actions). The card row is not refilled during round 1. (A/B)
- **T3.3** Start of turn, in this order: (1) refill the card row (T4.1; may change the age, T13); (2) resolve your war
  declared on your previous turn, if any (T9.5); (3) move your exclusive tactic played on your previous turn to the
  common tactics area, keeping your marker on it; an identical card already there makes the two count as one common
  tactic. (A; B's BGA code shares the tactic before the war — decision D3)
- **T3.4** Politics phase: at most one political action (T7), optional. (A/B)
- **T3.5** Action phase: spend civil and military actions on actions (T5, T6) one at a time in any order; an action is
  allowed only if every step can be done and every cost paid; you may stop with actions left. (A/B)
- **T3.6** End of turn, in this order: (1) discard military cards down to your military action total (your choice,
  face down); (2) uprising check (T11.8); (3) production unless there is an uprising: score science points equal to
  your science rating and culture points equal to your culture rating, then corruption (T12.5), food production
  (T12.6), food consumption (T12.7), resource production (T12.8); (4) draw military cards (T3.7); (5) reset all civil
  and military actions to available. Only step (1) is a choice. (A/B)
- **T3.7** Draw one military card from the current military deck per military action still available, at most 3; none
  in Age IV. A temporary extra military action left unused counts. When the deck runs out, shuffle the current age's
  military discard pile into a new deck and keep drawing. (A/B)

## T4 Card row and taking cards

- **T4.1** Refill (start of every turn from round 2 on): discard the cards in the leftmost 3 spaces with 2 players, 2
  spaces with 3 players, 1 space with 4 players (whether or not those spaces hold cards); slide the remaining cards left
  without gaps; deal from the current civil deck into the empty spaces from the left. Discarded civil cards leave the
  game. (A/B)
- **T4.2** Take a non-wonder card: pay the space's civil actions (T1.2); the card goes to your hand. (A/B)
- **T4.3** Civil hand limit: you may not take a civil card into hand while the civil cards in your hand number your
  civil action total (spent or not) or more. Being above the limit never forces a discard. (A/B)
- **T4.4** You may not take a technology whose name matches a card in your hand or in play. (A/B)
- **T4.5** You may take only one leader of each age in the whole game, even if the first has left play. (A/B)
- **T4.6** Take a wonder: pay the space's civil actions plus 1 per wonder you have completed (ruined wonders count);
  the wonder goes straight into play as your unfinished wonder (never into hand; the hand limit does not apply). Not
  allowed while you have an unfinished wonder. An unfinished wonder has no effect. (A/B)

## T5 Civil actions

- **T5.1** Increase population: 1 civil action + the food cost of T1.8; move the rightmost yellow token of the yellow
  bank to the worker pool. Not allowed with an empty yellow bank. (A/B)
- **T5.2** Build a farm, mine or urban building: 1 civil action + the resource cost of a matching technology you have
  in play; move an unused worker onto it. (A/B)
- **T5.3** Urban building limit: you may not build an urban building of a type (lab, temple, library, theater, arena)
  if your workers on all technologies of that type, across all levels, already number your government's limit or
  more. Farms, mines and military units have no limit. (A/B)
- **T5.4** Upgrade a farm, mine or urban building: 1 civil action + (cost of the higher card − cost of the lower card),
  both after cost modifiers; move the worker to a higher-level technology of the same type in play. (A/B)
- **T5.5** Destroy a farm, mine or urban building: 1 civil action; the worker goes to the worker pool. (A/B)
- **T5.6** Play a leader: 1 civil action; it enters play at once. If it replaces your leader in play, the old leader is
  discarded and you get 1 civil action back. Never more than one leader in play. (A/B)
- **T5.7** Build a wonder stage: 1 civil action + the leftmost unpaid stage cost; cover that stage with a blue token
  from your blue bank (from your technology cards if the bank is empty). When every stage is covered the wonder is
  complete: its tokens return to the blue bank and its effects start. Several stages per action only where a card says
  so; their costs are added and paid at once. (A/B)
- **T5.8** Develop a technology: 1 civil action + the card's science cost; the card enters play. A special technology
  of a type you already have keeps only the higher-level card (playing a lower one removes it at once but still counts
  as developing). A government developed this way costs its higher science cost and replaces the old government. (A/B)
- **T5.9** Revolution: develop a government from hand paying civil actions equal to your civil action total (so all
  must still be available) and the lower science cost; civil actions added by the new government arrive spent;
  military actions added arrive available. Effects that trigger on developing a technology also trigger. (A/B)
- **T5.10** Play an action card: 1 civil action; reveal it, carry out what it says (actions it orders cost no further
  civil or military actions, other costs are paid unless it says free; cost reductions stop at 0), then discard it.
  Not allowed for a card taken during this same action phase, nor when its action cannot be carried out. A "develop"
  action card may be used for a revolution, paying the revolution cost instead of its own civil action. Bonuses "for
  this turn" exist only for this turn. (A/B)

## T6 Military actions

- **T6.1** Build a military unit: 1 military action + the resource cost of a unit technology in play; an unused worker
  goes onto it. No limit on units. (A/B)
- **T6.2** Upgrade a military unit: 1 military action + the cost difference (after modifiers) to a same-type higher
  unit technology in play. (A/B)
- **T6.3** Disband a military unit: 1 military action; the worker goes to the worker pool. (A/B)
- **T6.4** Play a tactic: 1 military action; the tactic enters your play area as your exclusive tactic and your marker
  moves onto it. Copy a tactic: 2 military actions; move your marker onto a tactic in the common area. At most one play
  or copy per turn. (A/B)
- **T6.5** Military hand limit = military action total; checked only at end of turn (T3.6 step 1). Military cards
  discarded or removed from play go face down onto their age's military discard pile. (A/B)

## T7 Politics

- **T7.1** Political actions: prepare an event (T8.1), play an aggression (T9.1), declare a war (T9.4; not in the last
  round), offer a pact (T10.1; 3–4 players), cancel a pact you are party to (T10.3; 3–4 players), or a political
  ability printed on a card in play. Aggressions and wars cost the military actions printed on them; the other
  political actions cost none. Resigning (T7.2) is a political action too, not allowed in Age IV. (A/B)
- **T7.2** Resign: the player leaves the game and has lost: their hands are discarded and all their cards leave play;
  pacts they are party to in other players' areas are removed; every player with a war declared against them removes
  that war and scores 7 culture points. If one player remains, the game ends and that player wins. Otherwise play goes
  on: the current decks stay as they are, but each later age's decks are set up for the new number of players (T2.1,
  T2.2), and card-row discards (T4.1) and 2-player event wording (T8.3) follow the players still in the game. (A/B)
- **T7.3** Ranking with resignations: every player still in the game ranks above every resigned player; resigned
  players rank by the order they resigned, the later one higher. (decision D16)

## T8 Events and colonization

- **T8.1** Prepare an event: put an event or territory from your hand face down on top of the future events deck;
  score culture points equal to its age (A 0, I 1, II 2, III 3); reveal the top card of the current events deck and
  resolve it. If the current events deck is now empty, shuffle the future events deck, order it with older ages above
  newer ages (order within an age random), and make it the new current events deck. A resolved card goes to the past
  events pile, never drawn again. (A/B)
- **T8.2** Resolving an event: follow the card. Players who must choose do so clockwise from the player who revealed
  it. Actions it grants cost no civil or military actions unless it says so. (A/B)
- **T8.3** Ties in "the strongest / weakest / most / least" comparisons: the current player counts as higher, then the
  players clockwise from the current player; at game end the starting player counts as current. Wording "all
  civilizations with the most / least" keeps ties (all tied players are affected). With 2 players "the two strongest
  (weakest)" means only the stronger (weaker). "Strongest / weakest" refers to military strength. (A/B)
- **T8.4** Territory revealed → colonization auction: starting with the revealing player and going clockwise, each
  player in the auction bids a whole number higher than the current bid (first bid ≥ 1) or passes and leaves; it ends
  when one bidder remains, who must colonize. If nobody bids the territory goes to the past events pile. A bid may not
  exceed the largest colonization force the player could send. (A/B)
- **T8.5** Colonization force = strength of the military units sent (at least one unit) + tactical strength of the
  armies those sent units form under the player's current tactic + the colonization modifier of cards in play + the
  colonization values of any military bonus cards played from hand. Strength modifiers of other cards (e.g. Napoleon,
  Alexander) do not count. The force must reach the bid; overpaying gives nothing back. (A/B)
- **T8.6** After colonizing: the workers of the sent units go to the yellow bank; used bonus cards are discarded; the
  territory enters the colonizer's play area as a colony; its permanent effect applies first (statistics updated, also
  for the lost units), then its one-time effect (gain resources, food, science, culture, population; draw military
  cards ignoring limits, none in Age IV). (A/B)
- **T8.7** A colony's one-time effect happens only when it is first colonized; a stolen colony moves with its permanent
  effect; a lost colony is removed from play. (A/B)

## T9 Aggressions and wars

- **T9.1** Aggression: reveal it, pay its military actions, name a rival. Not allowed against a player whose strength
  equals or exceeds yours (count bonuses that apply when you attack that player, not bonuses of pacts that end when
  you attack), nor against a player a pact forbids you to attack. A pact between you that ends on attack is removed.
  (A/B)
- **T9.2** Defense: the rival may raise their strength for this aggression by playing military bonus cards (each adds
  its defense value) and discarding other military cards face down (+1 each), at most as many cards in total as their
  military action total. The rival either reaches at least the aggressor's strength — the aggression fails — or plays
  nothing and the aggression succeeds and is resolved as printed (costs named on it ignore modifiers). The aggression
  card is discarded either way. (A/B — decision D4)
- **T9.3** Several players may attack the same player in one round; resolving a war and playing an aggression against
  the same player in one turn is allowed. A pact accepted later does not cancel a war already declared. (B; A silent —
  decision D5)
- **T9.4** Declare a war: reveal it, pay its military actions, name a rival (any rival a card does not protect;
  strength is not checked now); remove a pact between you that ends on attack; the war lies in your play area aimed at
  the rival. Not allowed in the last round. (A/B)
- **T9.5** Resolve a war at the start of the declarer's next turn (T3.3): compare current strengths (with attack
  bonuses against this rival); no bonus cards, discards or sacrifices; the higher is the victor and the difference is
  the strength advantage the card uses; a tie has no effect; the war is discarded. (A/B)
- **T9.6** A victor stealing a special technology may not take one identical to a card in their hand or play; if they
  have one of the same type, only the higher level stays. (A)

## T10 Pacts (3 and 4 players)

- **T10.1** Offer a pact: reveal it, name a player and, for a pact with A/B sides, the side each of you takes. The
  player accepts or refuses. Refused: the pact returns to your hand and your political action is used. (A/B)
- **T10.2** Accepted: any other pact in your own play area is removed; the new pact enters your play area with its
  sides facing the right players and applies at once. A player can be party to pacts in other players' areas too. (A/B)
- **T10.3** Cancel a pact: remove any pact in play you are party to. Pacts also end when they say so on an attack and
  when their age becomes antiquated (T13.3). (A/B)

## T11 Statistics, workers and actions

- **T11.1** A card that holds workers gives its bottom symbols once per worker; other cards in play give them once.
  Unfinished wonders give nothing. Written abilities modify statistics as stated. (A/B)
- **T11.2** Science rating and culture rating: sums of their symbols and modifiers, at least 0, no upper limit.
  One-off "score culture" effects do not change the rating. (A/B)
- **T11.3** Strength: unit strengths + tactical strength of armies + modifiers, at least 0. A unit always adds its own
  strength, in an army or not. (A/B)
- **T11.4** Armies: each complete set of units shown on your current tactic forms one army adding the tactic's tactical
  strength; a unit belongs to at most one army; each army may add one air force, doubling that army's tactical
  strength. For Age II and III tactics an army with a unit two or more levels below the tactic is outdated and adds the
  lower printed value (doubled with an air force). Armies always form in the way that gives the highest strength. (A/B)
- **T11.5** Happiness rating: happy faces minus unhappy faces, kept between 0 and 8. (A/B)
- **T11.6** Civil (military) action total = white (red) action symbols on the government and the bottoms of other
  cards in play. When a card entering play raises a total, the new actions arrive available (except T5.9); when a total
  falls, spent actions are removed first. A replacement is settled once, after both cards moved. Temporary actions are
  spent first and do not change totals. "Gain an action back" returns a spent action (nothing if none is spent). (A/B)
- **T11.7** Workers: yellow tokens outside the yellow bank; unused workers stand on no card. Gain population: yellow
  bank → worker pool, free. Increase population (as an effect): as T5.1, paying food unless free. Lose population:
  an unused worker → yellow bank; if none, a worker from a card of the owner's choice. (A/B)
- **T11.8** Discontent workers = happy faces required (T1.8) − happiness rating, if positive. If at your end of turn
  your discontent workers outnumber your unused workers, you have an uprising and skip the whole production step.
  The check happens only at your own end of turn. (A/B)
- **T11.9** Token symbols at a card's bottom change your banks when it enters play: a plain blue (yellow) token
  symbol adds that many tokens from the box to your blue (yellow) bank, a token symbol with a minus sign removes that
  many; when the card leaves play the change is reversed. Losing blue tokens: from the blue bank to the box, and if the bank
  runs short, from your farms and mines (your choice). Losing yellow tokens: from the yellow bank only; if it holds
  fewer, lose all it has. Taking yellow tokens from a player: from their yellow bank into yours, at most what it holds.
  (A; B's BGA code takes missing yellow tokens from cards — decision D6)
- **T11.10** Level of a card: A 0, I 1, II 2, III 3; a worker's level is its technology's level; "best X" = the highest
  level among your workers of that type. "Leaders, colonies, wonders, technologies" in a rule or effect mean cards in
  play unless stated. (A/B)

## T12 Food, resources, science and culture

- **T12.1** Food and resources are blue tokens on farm and mine technologies, each worth the value printed at the
  card's bottom; a card may hold tokens without workers; no limit per card. (A/B)
- **T12.2** Gain food (resources): move blue tokens from the blue bank onto your farms (mines) so the total gained is
  exactly the amount, using as few tokens as possible; if the bank cannot make the amount, gain the largest amount not
  above it that the tokens can make; an empty bank gives nothing. Food and resources gained together: in the written
  order. (A/B)
- **T12.3** Pay food (resources): return tokens from cards to the blue bank and/or move tokens to a lower-value card of
  the same kind (paying the difference), so that exactly the amount is paid; you may not pay if your total is too low.
  Paying more is allowed only when the exact amount is impossible and paying more empties your blue bank; change is
  then lost. Tokens never move to a higher-value card. Losing works like paying, but losing more than you have loses
  everything. Taking from a player: they lose, you gain what they actually lost. (A/B)
- **T12.4** Science and culture points: scoring moves forward, losing moves back, never below 0. You cannot pay more
  science than you have. Taking points from a player gives at most what they had. (A/B)
- **T12.5** Corruption (T1.7): lose that many resources; if you have fewer, lose all resources and the rest as food.
  It happens before this turn's food and resource production. (A/B)
- **T12.6** Food production: each worker on a farm moves one blue token from the blue bank onto that farm; if the bank
  runs out, farms are filled from the highest level down. (A; B confirms that production stops with an empty bank)
- **T12.7** Food consumption (T1.8): lose that much food; for each food you cannot pay, lose 4 culture points. (A/B)
- **T12.8** Resource production: as T12.6 for workers on mines, highest level first if the bank runs out; then the
  expansion's production bonuses (T15.6). (A/B)
- **T12.9** Food, resources or science given for a specific purpose or "for this turn" have no tokens, are spent first
  on what they apply to, and vanish at the end of your turn. (A; expansion clarification, also applies to base cards)

## T13 Ages

- **T13.1** Age A ends the first time the card row is refilled (the starting player's second turn): after the Age A
  cards are dealt, the rest of the Age A civil deck leaves the game, the Age I civil and military decks become current,
  and remaining empty spaces fill from Age I. No tokens are lost and nothing becomes antiquated. (A/B)
- **T13.2** Ages I, II and III end the moment the last card of the current civil deck is dealt into the card row; the
  next age begins at once and the refill continues from the new deck (Age IV: no deck, spaces stay empty, the leftmost
  spaces are still discarded each turn). (A/B)
- **T13.3** When Age II, III or IV begins, cards two ages older than the new age become antiquated (Age A cards at the
  start of Age II, Age I at Age III, Age II at Age IV): they are discarded from hands; antiquated leaders, unfinished
  wonders (their blue tokens return to the blue bank) and pacts leave play. Technologies, colonies, completed wonders,
  tactics and declared wars stay. Antiquated cards in the event decks stay. (A/B)
- **T13.4** When Age II, III or IV begins, every player loses 2 yellow tokens from the yellow bank (all it holds if
  fewer). (A/B)
- **T13.5** When an age begins, the previous age's military deck and military discard pile leave the game; the new
  age's military deck is shuffled and becomes current (Age IV: none). (A/B; discard pile — decision D7)

## T14 Game end and scoring

- **T14.1** If Age IV begins during the starting player's turn, that round is the last; otherwise the next round is
  the last. Every player has the same number of turns. (A/B)
- **T14.2** After the last round: evaluate every Age III card left in the current events deck and the future events
  deck (cards of other ages are ignored), the starting player counting as current player for ties; then score
  end-of-game bonuses printed on cards (e.g. Bill Gates). (A/B; evaluation order — decision D8)
- **T14.3** The player with the most culture points wins; tied players share the win. Score = culture points
  (higher is better). (A/B)

## T15 New Leaders and Wonders expansion

- **T15.1** The expansion has three parts used together here: rebalanced base cards (T15.2), new military decks
  (T15.3), new leaders and wonders (T15.4). (A/B — decisions P1–P3)
- **T15.2** Rebalanced base cards: the 7 leaders and 5 wonders with the rebalance mark, Communism, Fundamentalism,
  both Republic and both Professional Sports cards, and the "4"-marked Military Theory are replaced by their new
  versions (Republic, Professional Sports and that Military Theory are now marked "3+"); 6 new action cards marked
  "3+" are added (1 in Age I, 2 in Age II, 3 in Age III). (A; B confirms the rebalance and the 6 action cards)
- **T15.3** Military decks: the expansion's decks replace the base military decks: the base military cards (with
  Wealthy Territory I at its rebalanced value) plus 16 new cards and 3 extra military bonus cards (19 new: 1 in Age A,
  6 in each of Ages I–III). (A; B in conflict on whether the deck changed — decision D9)
- **T15.4** Leaders and wonders, selection ("public mix", decision P1): for each age A, I, II, III, draw at random
  from the base and expansion leaders of that age (12) and wonders (8): 6 leaders and 4 wonders with 2 players, 7
  leaders and 5 wonders with 3–4 players. The rest are not used. Every selected card is public from the start. (A; B
  confirms the mode and its board/proxy mechanics from community answers)
- **T15.5** Each new card's effect is card data; the expansion rulebook's clarifications for single cards are applied
  in the card database (data/SOURCES.md). (A)
- **T15.6** Production bonuses: whenever you produce resources (end of turn or an event), first normal mine
  production (and other per-worker production such as Bill Gates' labs), then add up all resource production bonuses
  (symbols and texts, including the base pacts International Trade Agreement and Acceptance of Supremacy) and gain the
  sum at once, or lose it if negative. Cards that count your resource production include these bonuses, except Impact
  of Industry, which counts only mine production. (A)
- **T15.7** An action card taken during the politics phase (e.g. by Aggression: Kidnap) may be played in the action
  phase of the same turn. (A)
- **T15.8** Public mix, Age A: the selected Age A leaders and wonders are shuffled into the Age A civil deck; the
  contents of the Age A civil deck are public, its order is not. (A/B)
- **T15.9** Public mix, Ages I–III: the civil decks hold numbered proxy cards instead of leaders and wonders — leader
  proxies 1–6 and wonder proxies 1–4 with 2 players, 1–7 and 1–5 with 3–4 players. The selected Age I leaders and
  wonders lie on the numbered spaces of the leader and wonder boards (assignment to numbers at random); the Age II and
  III selections wait face up. When a proxy is dealt into the card row it is at once replaced by the card on the board
  space with its number, and the proxy leaves the game. When Age I ends the Age II selections go onto the board spaces;
  when Age II ends, the Age III selections. (A; B from community answers)

- **T15.10** A military card that is not an event or territory (it can only be prepared as an event through
  Confucius) resolves, when revealed as the current event, as "each civilization gains 1 science", even after
  Confucius has left play. (A)

## T16 Information

- **T16.1** Secret: military cards in hand and civil cards in hand (for both, only the number of cards of each age is
  public — card backs show the age); the order of every deck; the contents of the current events deck; the future
  events deck, except that each player knows the cards they prepared. Public: all cards in play and in the card row,
  the selected leaders and wonders and the Age A deck contents (T15.4–T15.9), the past events pile, deck sizes, and how
  many cards of each age lie in the current and future events decks. (A/B — decision P4)
- **T16.2** With secret civil hands, cards that say to look at or reveal another player's civil hand (e.g. Ashoka,
  Aggression: Kidnap) show it only as far as the card says. (A)

## T17 Decisions where sources differed or were silent

| # | Question | Decision | Why |
|---|---|---|---|
| D1 | Corruption values and the two leftmost consumption values (hidden under tokens in every rulebook picture) | corruption 6/4/2 (0, 1–5, 6–10 tokens), consumption 6 (0 tokens) and 4 (1–4 tokens) | BGA code tables; Stately Play, Misut Meeple and the Unofficial FAQ agree; every value A could see matches the same code tables (A-1.11, B-1.3, B-1.4) |
| D2 | Cards removed for 2 and 3 players (base rulebook: 9 / 3 per deck) | rebalanced counts: 10/11/12 and 3/2/1 | the expansion's rebalanced set moves three technologies to "3+" and adds six "3+" action cards; its card-count table gives these numbers (A-14.4) |
| D3 | Start of turn: resolve the war or share the tactic first | refill → war → tactic | rulebook order (A-3.1); Misut Meeple and BoardGameGeek answers agree; BGA's order differs but cannot change a result (sharing does not change strength) (B-3.5) |
| D4 | May a defender discard cards without reaching the aggressor's strength | no: reach at least a tie or play nothing | rulebook says a rival who cannot or does not want to match plays nothing (A-8.2); BGA enforces the same (B-8.2) |
| D5 | Several attacks on one player per round; war + aggression on the same player in one turn | allowed | Unofficial FAQ rulings (B-8.5); the rulebook has no limit |
| D6 | Losing yellow tokens with too few in the yellow bank | lose only what the bank holds | rulebook (A-10.11) and Unofficial FAQ (B-10.7); BGA takes the rest from cards, which the rulebook does not say |
| D7 | Does the previous age's military discard pile stay | it leaves the game | only the current age's discards are ever reshuffled (A-3.16, B-3.7), so keeping it would change nothing |
| D8 | Order of evaluating Age III events at game end ("in any order") | current events deck top to bottom, then future events deck top to bottom | the rulebook allows any order; a fixed order keeps games reproducible (A-12.1) |
| D9 | Are the expansion's military decks the base cards or changed cards | base cards (Wealthy Territory I rebalanced) + 19 new | the expansion rulebook (A-14.5) beats a BoardGameGeek comment (B-14.7); 149 reprinted + rebalanced Wealthy Territory I = the 150 base military cards B counted in BGA |
| D10 | Wealthy Territory I gives 5 or 6 resources | 6 | the expansion rebalances it to the digital version's value (A-14.3, B-15.1a) |
| D11 | Production when the blue bank runs out | highest-level farms (mines) first | rulebook (A-3.13); BGA produces on the newest cards first, which is the same here (newer = higher level) (B-3.9) |
| D12 | Political action in round 2 | no special rule | nobody holds military cards then (none drawn in round 1), so only leader abilities could apply; BGA skips the phase, the rulebook does not (B-3.4) |
| D13 | Age III territories at game end | evaluated like any Age III event if any exist | rulebook says all Age III events are evaluated (A-12.4); the card database checks whether Age III territories exist |
| D14 | Peaceful variant (sources differ on whether it also removes pacts) | not modelled | the full game is modelled; the variant is not official base play (B-2.6) |
| D15 | Exact card counts per deck; International Negotiations thresholds (icons) | settled in the card database | neither rulebook lists deck sizes; BGA counts 20/53/53/53 civil and 10/45/50/45 military at 4 players (B-1.9); card values are card data (A-1.7, A-16.49) |
| D16 | How a resigned player ranks (rulebook: they have lost) | below everyone still playing; among resigned players the later one ranks higher | the rulebook says only that a resigned player lost (A-6.5); a later resignation means the civilization lasted longer |
| D17 | Sign of token symbols (rulebook pictures only the minus symbols: entering play loses tokens) | plain symbols add tokens, minus symbols remove them; both reverse on leaving play | the printed cards show plain symbols on Justice System, Civil Service, Taj Mahal and territories, and a minus on Vast Territory's blue token; BGA's data stores the same signs (A-10.11 read the minus picture as covering all symbols) |
| D18 | Four of the six new "3+" action cards (Age I ×1, Age II ×2, Age III ×1) are named in no reachable source | left out; the two identified (extra copies of Patriotism III and Revolutionary Idea III) are modelled | maintainer's decision 2026-11-02; 3–4 player civil decks are one or two cards short of the official count, 2-player games are unaffected (data/SOURCES.md) |
| P1 | How expansion leaders and wonders enter (maintainer, 2026-11-02) | public mix (T15.4, T15.8, T15.9) | maintainer's choice among the official modes; every one of the 48 leaders and 32 wonders can appear |
| P2 | Use the rebalanced base cards (maintainer) | yes | part of the chosen expansion; CGE asks players to use at least the new Republic and Professional Sports; the official app uses these values |
| P3 | Use the new military decks (maintainer) | yes | part of the chosen expansion |
| P4 | Civil cards in hand public or secret (maintainer) | secret | maintainer's choice; the rulebook leaves it to the group (A-13.1, B-13.2); the expansion rulebook gives the private-hand handling for Ashoka and Kidnap (A-16.20, A-16.51) |
| P5 | Resigning (maintainer) | modelled (T7.2) | maintainer's choice; it is an official political action |
