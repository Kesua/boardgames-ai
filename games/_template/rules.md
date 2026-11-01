# Template toy game "Market" — rules as implemented

Own-words rules with IDs (`T<section>.<n>`); every rule has a test marked `@pytest.mark.rule("T…")`.
A real game's rules.md also names its two independent sources per rule and lists decisions where sources differ
(see games/wingspan/rules.md for a full example).

- **T1.1** 45 cards: numbers 1–15 in red, green and blue.
- **T2.1** Shuffle the deck; reveal 3 cards as the market.
- **T3.1** On your turn take one market card or the deck's top card.
- **T3.2** A taken market card is replaced at once from the deck (if any).
- **T4.1** The game ends when deck and market are empty.
- **T5.1** Score = sum of the numbers taken + 5 for every colour with at least 3 of your cards. Ties share the win.
