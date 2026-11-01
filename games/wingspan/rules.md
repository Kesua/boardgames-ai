# Wingspan (base game) — rules as implemented

Own-words summary of the rules this engine implements. It is not the rulebook: read the official rules at
https://stonemaiergames.com/games/wingspan/rules/ (and the official reference https://wingspan.rulepop.com/).
Every rule has an ID; tests cite it with `@pytest.mark.rule("W4.2")`.

**Sources.** Two researchers worked independently: A from Rulepop (Stonemaier's official interactive reference,
including its component images) and the Stonemaier rules page with staff answers; B from a scan of the printed
rulebook and appendix, RulesPal (152 FAQ pages citing designer/publisher rulings), the official rulings bundled in the
Wingsearch card data, the Wingspan fan wiki and the Board Game Arena help. Their notes were compared line by line;
"A/B" after a rule means both confirm it. Where they differed, the decision is listed in section W15 with the reason.

Scope: base game, 2 to 5 players, green goal board by default, no expansions, no Automa.

## W1 Components

- **W1.1** Birds: 180 bird cards = 170 from the original box + the 10 Swift-Start birds that current boxes include and
  that are shuffled into the deck after the learning game (option `swift_start_birds`, default on). (A/B)
- **W1.2** 26 bonus cards; 8 double-sided goal tiles (16 goals), pairs: birds/eggs in forest; birds/eggs in
  grassland; birds/eggs in wetland; bowl birds with an egg/eggs in bowl nests; cavity likewise; ground likewise;
  platform likewise; total birds/sets of eggs. (A/B)
- **W1.3** 5 food dice, each with 6 faces: invertebrate, seed, fish, fruit, rodent, invertebrate-or-seed. (A/B; A from
  the die image, B from the rulebook scan)
- **W1.4** Food types: invertebrate, seed, fish, fruit, rodent. Food and eggs are unlimited. (A/B)
- **W1.5** 8 action cubes per player; turns per player in rounds 1–4: 8, 7, 6, 5 (26 in total). (A/B)

## W2 Setup

- **W2.1** Shuffle the bird deck; deal 3 face-up birds to the tray; roll all 5 dice into the feeder; shuffle the
  bonus deck. (A/B)
- **W2.2** Goals: shuffle the 8 tiles, place 4 with a random side up on rounds 1–4. Both faces of a tile can never
  appear in the same game. (A/B)
- **W2.3** Each player gets 5 random birds, 2 random bonus cards and 1 food of each of the 5 types. (A/B)
- **W2.4** Each player keeps any number of the 5 birds and must discard 1 food for each bird kept (kept birds + kept
  food = 5), and keeps 1 of the 2 bonus cards. Choices are made in secret; the engine asks seat by seat and no player
  sees another's choice (agents' observations hide other players' hand size, food and the discard pile until every
  player has chosen). Discarded birds go to the face-up discard pile. (A/B)
- **W2.5** After the choices the first player is chosen at random. (A/B)

## W3 Rounds and turns

- **W3.1** 4 rounds. Starting with the first player and going clockwise, each turn a player places 1 cube and takes
  exactly 1 of the 4 actions: play a bird, gain food (forest), lay eggs (grassland), draw cards (wetland). Any
  action may be repeated; there is no passing. (A/B)
- **W3.2** End of round, in order: score the round's goal (W12); remove the cubes; discard the 3 tray birds and deal
  3 new ones; pass the first-player token clockwise. The feeder is not rerolled. (A/B)
- **W3.3** The game ends after round 4's end-of-round steps. (A/B)

## W4 Player mat

- **W4.1** Each habitat row holds up to 5 birds, filled from the left. (A/B)
- **W4.2** A habitat action uses the leftmost exposed slot of its row: slot = birds in the row + 1 (with 5 birds, a
  sixth space at the far right). Base amounts by birds in row 0..5: gain food 1,1,2,2,3,3; lay eggs 2,2,3,3,4,4;
  draw cards 1,1,2,2,3,3. (A from the mat image, B from the rulebook examples and the fan wiki)
- **W4.3** Slots 2, 4 and 6 (1, 3 or 5 birds in the row) offer one optional trade after the base gain: forest —
  discard 1 bird card from hand for 1 more food from the feeder; grassland — pay 1 food for 1 more egg; wetland —
  discard 1 egg for 1 more card. At most once per action, decided after the base gain and before brown powers. (A/B)
- **W4.4** Egg cost to play a bird into column 1..5: 0, 1, 1, 2, 2. Only playing a bird costs eggs. (A/B)

## W5 Play a bird

- **W5.1** Choose a bird in hand and a habitat shown on it whose row has room; the bird goes into the leftmost empty
  slot. Pay that column's egg cost (eggs from any of your birds) and the food cost from your personal food. If you
  cannot pay in full you cannot play it. (A/B)
- **W5.2** Food cost: each icon is one food of that type; "wild" = 1 food of any type; "/" = exactly one of the
  listed foods; no icon = free. (A/B)
- **W5.3** Two for one: while paying a bird's food cost, any 2 food tokens may be spent as 1 food of any type,
  repeatedly. Never at any other time (not for power costs, not for the grassland trade). (A/B)
- **W5.4** Then the bird's white (when played) power may be used. Playing a bird activates no row and gives no slot
  benefit. (A/B)

## W6 Habitat actions

- **W6.1** Take the slot's base amount, then optionally the slot's trade (W4.3), then activate brown powers of that
  row from right to left, each optional. (A/B)
- **W6.2** A player may take less than offered: food, eggs and cards are taken one at a time and the player may stop
  early. A cost already paid is never refunded. (A/B)
- **W6.3** Lay eggs: each egg goes on any of your birds with room below its egg limit; eggs that fit nowhere are
  lost. The action may be taken with no room (only to run the powers). (A/B)
- **W6.4** Draw cards: each card from one of the face-up tray cards or the top of the deck, chosen one at a time. (A/B)

## W7 Birdfeeder

- **W7.1** Gaining food from the feeder: take 1 die out (it stays out until the feeder is refilled) and gain 1 food
  of its face; the invertebrate-or-seed face gives 1 of the two, the player chooses. (A/B)
- **W7.2** When the last die is taken, all 5 dice are rolled back in at once, before anything else happens. (A/B)
- **W7.3** Before taking a die (for an action, the forest trade or a power), if every die in the feeder shows the
  same face (one die always qualifies; the invertebrate-or-seed face is its own face), the player may reroll all 5
  dice; repeatable while the condition holds. (A/B)
- **W7.4** "Roll all dice not in the birdfeeder": roll only the dice outside (0–4 of them); they stay outside. If at
  least one shows the food, cache exactly 1 of it from the supply. No reroll option. (A/B)

## W8 Bird tray, deck and discards

- **W8.1** A plain "draw" takes from the tray or the deck top; "from the deck" means the deck top only. (A/B)
- **W8.2** Empty tray slots are refilled at the end of the active player's turn (after pink powers and end-of-turn
  discards), never mid-turn. (A/B)
- **W8.3** When the bird deck is empty, the discard pile is shuffled into a new deck. If deck and discard pile are
  both empty, no card can be drawn. Same for the bonus deck. (A/B)

## W9 Eggs, caching, tucking

- **W9.1** A bird never holds more eggs than its egg limit. Eggs never move; they leave only when discarded. (A/B)
- **W9.2** Cached food sits on a bird, cannot be spent and is worth 1 point. Tucked cards are worth 1 point each and
  are no longer birds. (A/B)
- **W9.3** Star nests count as every nest type for goals, bonus cards and powers. The two cowbirds have no nest and
  egg limit 0. (A/B)

## W10 Bird powers

- **W10.1** Colours: white = when played (once); brown = when the row is activated; pink = once between your turns,
  on other players' turns only. Birds without a power are skipped. All powers are optional. (A/B)
- **W10.2** "If you do" / "discard X to Y": the second part needs the first; a "may" part can be refused. (A/B)
- **W10.3** "All players / each player" powers: once the owner activates, every player resolves its own share in turn
  order from the owner (or from the player the owner chooses, where the card says so) and may decline its share. (A/B)
- **W10.4** Powers affect only the owner's own birds and supply unless they name other players. (B; A agrees in
  examples)
- **W10.5** Predators (base): "look at the deck top; if its wingspan is less than N cm, tuck it, otherwise discard it"
  (strictly less) and the dice hunters (W7.4). Success = a card tucked or food cached. (A/B)
- **W10.6** Repeat powers repeat the brown power of another bird in the same row (left or right, already used this
  turn or not): that bird's power runs again as that bird (eggs/tucks/caches land on it, costs as its text says).
  Hooded Merganser only repeats predator powers. A repeat cannot target itself or a bird already in the current
  repeat chain. (A/B)
- **W10.7** Movers: if the bird has no bird to its right in its row, it may move to the leftmost empty slot of
  another row (with room). No egg cost, no slot benefit, not a "play", eggs/cache/tucks stay; the cube stays in the
  original row and activation continues to the left. (A/B)
- **W10.8** "Play an additional bird in this habitat": the extra bird is played into the same row as the power bird
  with its full food and column egg cost (two-for-one allowed); its own white power resolves; chains are allowed.
  It counts as playing a bird for pink powers. (A/B; B reports the later ruling that counts it for pink triggers)
- **W10.9** "Draw N. If you do, discard 1 card from your hand at the end of your turn": one discard per activation,
  any card, nothing if the hand is empty then. (A/B)
- **W10.10** "Player(s) with the fewest birds in [habitat]": 0 counts; all tied players benefit, in turn order from
  the owner — except Hermit Thrush (dice), where the owner chooses which tied player goes first. (A/B)
- **W10.11** "All players lay 1 egg on any 1 [nest] bird; you may lay 1 on 1 additional [nest] bird": the owner's two
  eggs go on two different qualifying birds. (A/B)
- **W10.12** "Gain all [food] in the birdfeeder": take every matching die at once (the invertebrate-or-seed face
  counts for invertebrate or seed powers). (B; A silent)
- **W10.13** American Oystercatcher: draw players+1 cards (tray or deck), then starting with the owner and going
  clockwise each player keeps 1; the owner also keeps the last one. (A/B)
- **W10.14** Bonus-card powers: draw 2 bonus cards, keep 1, discard the other. (A/B)

## W11 Pink powers

- **W11.1** Each pink bird can fire at most once between two of its owner's turns; it re-arms when the owner takes a
  turn (not at round end). A newly played pink bird is armed at once. Declining keeps it armed. (A/B)
- **W11.2** Triggers: "takes the lay eggs action" / "takes the gain food action" = the basic habitat action only
  (including its trade); "plays a bird in their [habitat]" = any bird played into that row on that player's turn
  (also via a power), not a moved bird; "a predator succeeds". (A/B)
- **W11.3** Timing: the pink power resolves right after the step that triggered it (after the played bird's white
  power, after the predator power); several players' pink powers resolve in turn order starting left of the active
  player. (A/B)

## W12 End-of-round goals

- **W12.1** Green side (default): rank players by the goal count; 1st/2nd/3rd score 4/1/0, 5/2/1, 6/3/2, 7/4/3 in
  rounds 1–4; lower places score 0. A player with 0 items scores 0. (A/B)
- **W12.2** Ties: tied players share the places they cover: add those places' points, divide by the number tied,
  round down; the next player takes the place after them. (A/B)
- **W12.3** Blue side (option): 1 point per item, at most 5. (A/B)
- **W12.4** Counting: birds in a habitat = birds in that row; eggs in a habitat = all eggs there; [nest] birds with an
  egg = birds of that nest (star counts) with at least 1 egg; eggs in [nest] = eggs on birds of that nest (star
  counts); total birds = all birds on the mat; sets of eggs = the smallest egg total among the three habitats. Tucked
  cards and cached food never count. (A/B)

## W13 Bonus cards

- **W13.1** Every bonus card a player holds scores at game end; a tiered card scores only its highest tier reached.
  (A/B)
- **W13.2** Food cards count birds whose cost shows that exact food icon (also inside "/"); wild never counts. Food
  Web Expert counts birds whose cost is only invertebrates. Habitat cards (Forester, Prairie Manager, Wetland
  Scientist) count birds that can live only in that habitat. Nest cards count that nest and star nests. Word cards
  count listed words in the bird's common name (see data/bonus_cards.json). Large Bird Specialist: wingspan > 65 cm;
  Passerine Specialist: ≤ 30 cm; Backyard Birder: birds worth less than 4 points; Breeding Manager: birds with at
  least 4 eggs; Oologist: birds with at least 1 egg; Ecologist: birds in your habitat with the fewest birds; Visionary
  Leader: cards in hand at game end; Bird Counter: flocking birds; Falconer: predator birds. (A/B)

## W14 Scoring

- **W14.1** Score = printed bird points + bonus cards + end-of-round goals + eggs + cached food + tucked cards. (A/B)
- **W14.2** Tiebreak: most food in the personal supply; if still tied, the players share the win. (A/B)

## W15 Decisions where sources differed or were silent

| # | Question | Decision | Why |
|---|---|---|---|
| D1 | 170 or 180 birds | 180 (option to drop the 10 Swift-Start birds) | current box contains them and the rules say to shuffle them in (A-1.3, B-1.1) |
| D2 | Sets of eggs | smallest egg count among the 3 habitats | Rulepop text and example, later staff answers, RulesPal; one 2019 answer disagreed (A-11.7) |
| D3 | Photographer 6+ birds | 6 points | publisher ruling on RulesPal and the fan wiki; both card spreadsheets say 7 but derive from the same list |
| D4 | Backyard Birder top tier | 7+ birds: 6 (5–6: 3) | the spreadsheets' "6+" overlaps "5–6"; the fan wiki gives 7+ |
| D5 | Anatomist 4+ birds | 7 | base-game card; 6 is the Asia reprint |
| D6 | Canvasback for Anatomist | does not count | "back" is a European-expansion word (ruling 20201116) |
| D7 | Bird played by another bird's power triggers "plays a bird" pink powers | yes | later ruling 20200716a (B-13.17); A's sources silent |
| D8 | Forest trade die and Loggerhead Shrike | counts as part of the gain food action | the trade belongs to the action (B-5.3) |
| D9 | Movers' target row | any other row with room | ruling 20201206b; all base movers can live in all 3 habitats anyway |
| D10 | Repeat a repeater | allowed, but never a bird already in the current repeat chain | B-9.B2 (no loops) |
| D11 | Pink power on the tray when another player draws | the tray refills only at the end of the active player's turn | A-7.2, B-7.2 |
| D12 | Starting choices | made seat by seat in secret (observations hide the others' choices); first player drawn afterwards | B-2.14 unconfirmed; secrecy keeps it equivalent to simultaneous choices |
| D13 | Deck and discard both empty | nothing can be drawn | strict rule (B-7.4) |
| D14 | Card data source | Wingsearch (newest printing) checked field by field against the BoardGameGeek card list; the only real difference (American Redstart egg limit 2 vs 4) settled by the fan wiki: 2 | data/SOURCES.md |
