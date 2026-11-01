# Forest Shuffle (base + Woodland Edge + Alpine) — rules as implemented

Own-words summary of the rules this engine implements; not the rulebook (official rules: Lookout Games,
https://lookout-spiele.de). Every rule has an ID; tests cite it with `@pytest.mark.rule("F4.2")`. Card-by-card
numbers and effects are data (`data/cards.json`, overview in `card_catalog.md`).

**Sources.** The official rulebooks of the base game and both expansions (read in full), checked against the Board
Game Arena implementation's card sheets and the independent scoring tool github.com/soldag/forest-shuffle-scoring
(all 368 card halves agree in species, position and tree symbol; four card costs differ there and were settled from
the card images — see `card_catalog.md`). The original design and test history is in `PLAN.md`.

## F1 Components
- **F1.1** 233 deck cards: 80 trees, 12 shrubs, 72 top/bottom split cards, 66 left/right split cards, 3 winter cards;
  each split card shows two dwellers, each half with its own tree symbol.

## F2 Setup
- **F2.1** Set the 3 winter cards aside, shuffle, remove 10 cards unseen, then remove more by player count (base only
  / one expansion / both: 2p 30/45/80, 3p 20/30/50, 4p 10/15/35, 5p 0/0/20).
- **F2.2** Split the rest into three piles; shuffle two winter cards into the bottom pile, put the third winter card
  on top of it; stack the two other piles on top.
- **F2.3** Each player draws 6 cards. A hand without a tree may be replaced once (mulligan: discard the 6 to the box,
  draw 6). Simplification: the mulligan is taken automatically whenever allowed.

## F3 Turn
- **F3.1** On your turn either draw two cards or play one card.
- **F3.2** Drawing: take two cards one at a time, each from the deck top or the face-up clearing; at most 10 cards in
  hand (with 9, draw only one; with 10 you cannot draw).
- **F3.3** A drawn winter card is placed aside and replaced by the next card; when the third is revealed the game
  ends at once.

## F4 Playing a card
- **F4.1** Pay the card's cost by putting that many other hand cards face up into the clearing; for a split card
  choose one half and pay its cost.
- **F4.2** Trees and shrubs go into your forest; playing a tree (or sapling) also moves the deck's top card to the
  clearing.
- **F4.3** Any card may be played face down as a sapling (no cost): it gives four slots like a tree but is no tree
  species.
- **F4.4** A split card's half goes into an empty slot on the matching side (top, bottom, left, right) of one of your
  trees, saplings or shrubs; some species may share a slot (hares, toads, butterflies with a nettle).
- **F4.5** After playing: use the card's effect, then its bonus (both optional). The bonus requires that every paid
  card shows the played card's tree symbol.
- **F4.6** Mushrooms and shrubs have permanent effects that trigger when later cards are placed (from your next turn;
  a shrub's own bonus already applies it).
- **F4.7** Effects that place cards for free skip those cards' effects and bonuses.

## F5 End of turn
- **F5.1** If the clearing holds 10 or more cards at the end of your turn, remove them all from the game. Extra-turn
  effects let the same player go again.

## F6 End and scoring
- **F6.1** The game ends immediately when the third winter card is revealed.
- **F6.2** Score = points of all visible cards in your forest + cards in your cave; each species scores as printed
  (majorities, sets, per-card counts, conditions — data in cards.json). Ties share the win.
- **F6.3** Butterflies score as sets of different species; set-scored species score once for all copies.

## F7 Simplifications (documented, all players treated the same)
- **F7.1** Payment is one card per decision; every optional effect is offered as use/skip; forests are capped at 40
  plants (a player who cannot act passes); free-placement effects only place dwellers.
