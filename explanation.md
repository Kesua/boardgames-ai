# How the computer learns to play Forest Shuffle

## Version for your wife (no technical terms)

Imagine a child who has never played Forest Shuffle. Nobody explains any strategy. The child knows only which moves are allowed and, at the end of each game, whether they won and by how many points.

1. **Play a lot.** The child plays tens of thousands of games, many of them against copies of themselves.
2. **Notice what worked.** After each game the child looks back: *"In positions like this I played that card, and then things went better than I expected."* Those moves become slightly more likely next time. Moves that went worse than expected become slightly less likely.
3. **Change a little at a time.** The child never changes their whole style after one game. They adjust a tiny bit after each batch of games, so one lucky or unlucky game cannot throw them off.
4. **Watch for a trap.** At first the child practised mostly against recent copies of themselves. They got very good at beating their own style and forgot how to play against anyone else, like a tennis player who only ever trains against a mirror. We noticed because the child started losing to an older, weaker player.
5. **The fix.** The child now also practises against old versions of themselves and against a simple player who always grabs the most points right away. The child also changes their style more slowly.
6. **Check fairly.** To see whether the child is really better, they play the same shuffled decks from both sides against an earlier version. That way, luck with the cards cancels out.

> **Result:** in about 3 hours of computer time, the new player beats the version we had before tonight in **97 games out of 100**.

---

## Version for you (data architect's view)

### 1. The pieces

| Piece | What it is | In data terms |
|---|---|---|
| **Environment** | The game engine: rules, deck, scoring | Deterministic system that takes an action and returns a new state |
| **Observation** | What one player can legally see, turned into about 3,850 numbers (0–1): own hand, the clearing, own forest, every player's forest summary, scores, free slots, and the cards opponents took from the clearing | A fixed-width feature vector, one row per decision |
| **Action** | One of the possible moves (play card X into slot Y, take a card, pay with card Z…) | A categorical output; a mask removes the moves that are illegal right now |
| **Policy** | A neural network: 3 layers (512, 512, 256 neurons) with about 3 million adjustable weights. It turns an observation into a probability for every move | A big parameterised function, `f(features) → probability per move` |
| **Value head** | A second output of the same network: "how well do I expect this game to end for me from here?" | A regression estimate of the final result |
| **Reward** | Given only at the end of the game: +1 for a win or −1 for a loss, plus (my score − best other score) / 100 | One label per game, not per move |

### 2. One training cycle

Repeated about 1,000 times per million steps.

**Collect.** 16 worker processes each run 4 games, so 64 games play at once. At every decision, the network picks a move by sampling from its probabilities. Sampling means it sometimes tries less likely moves; that is how it explores. Every seat at the table is the current network, and every seat's decisions are recorded. In 20 % of games one seat is a *frozen* opponent instead. That opponent plays but does not learn: an older version of the model, the old 7.2M model, or the greedy player.

**Score the moves after the game.** When a game ends, each seat gets its reward. For each of its decisions we then compute the **advantage**: did things turn out better or worse than the value head predicted at that moment? The method for this is **GAE** (generalized advantage estimation). It spreads the single end-of-game reward back over the roughly 150 decisions that seat made, giving less credit to moves that were further from the end.

**Update.** Once there are 16,384 recorded decisions, the GPU (graphics processor) adjusts the weights. The method is **PPO** (proximal policy optimization). It makes moves with a positive advantage more likely and moves with a negative advantage less likely. Its key safety rule is *clipping*: no move's probability may change by more than about 20 % in one update. In the same step the value head is trained to predict the final results better.

**Repeat** with the updated network.

> One "step" is one recorded decision. 1 million steps is about 3,500 games, and in this setup that takes about 8 minutes.

### 3. Measuring progress

- **Paired games:** the same 750 shuffled decks are played twice, with the new model in seat 1 and then in seat 2. That makes 1,500 games in which card luck largely cancels out. The margin of error is about ±1.3 percentage points.
- **Against a fixed older model:** we compare with the same opponent every time, so the numbers are comparable over the whole run.
- **Against an opponent the model never trained against:** this is the honest test. Beating an opponent you trained against is partly memorisation.
