---
name: build-engine
description: Implement a game engine for boardgames.ai test-first, rule by rule, following PLAN.md and the bgai.game contract, with a test for every rule ID and every card. Use after plan-engine.
---

# Build the engine

## Goal
An engine that implements `rules.md` exactly, plays fast (training runs hundreds of millions of decisions), never
gets stuck, and is proven by tests that name the rule they prove. The tests are the evidence a reviewer and the
public rely on.

## Steps
1. Implement the `bgai.game.Game` methods (see `games/_template/engine.py` for the smallest complete version):
   `current_seat`, `game_over`, `turns`, `legal_ids`, `step_id`, `clone`, `scores`, `tiebreaks`, `breakdowns`,
   `record_info`, `tableau`, `seat_extra` (with `hand_left`), `describe`, `text_state`; plus `drain_forced()` if the
   engine auto-applies single-option decisions.
2. Fill `SPEC` in `games/<slug>/__init__.py`: `new_game`, `action_count`, `encoder`, `greedy`, `default_options`,
   `rounds` (if fixed length), `summary`, `catalog`, `invariants`, `max_steps`.
3. **Test first, rule by rule.** For each rule ID write a test that builds the exact situation (helpers that place
   cards, set hands and resources), takes the action, and checks the result. Mark it `@pytest.mark.rule("X4.2")`.
   Example helpers: `games/wingspan/tests/conftest.py` (`started`, `place`, `give`, `answer("text")`, `play`).
4. **One test per card** (parametrised over the card list) that runs its effect through the real flow and checks the
   change by effect type: `games/wingspan/tests/test_cards.py`.
5. `invariants(game)` in the SPEC: conservation of cards/tokens/dice, limits never exceeded. `bgai.checks` calls it.
6. **A first encoder and greedy agent** (simple versions; design-rl improves them later): `bgai.checks` needs both —
   it checks the observation range and that greedy clearly beats random. Make the greedy agent actually score: in
   games where starting something costs points (an expedition, a loan), a greedy agent that never starts anything
   scores 0 and can still "beat" random players who lose points. Look at its average score in a few games.
7. **Every game must end.** If the rules allow endless play (both players can keep discarding and redrawing), add an
   end condition the rules or common practice support and record it as a decision in `rules.md`. A game that reaches
   `SPEC.max_steps` is an error in experiments and checks; training cuts it off and scores it as it stands.
6. Keep the engine fast: no logging of large strings on hot paths, no deep copies outside `clone`, precompute static
   card data. Measure: `python -m bgai.checks --game <slug> --games 400` should take seconds.

## Done when
`python -m pytest games/<slug> -q` passes, `python tools/check_repo.py` reports no untested rule ID, and random games
end for every player count.

## Pitfalls
- Hidden duplicates: a card can be in two places during multi-step flows (Wingspan setup counted kept cards twice
  until it moved them one by one). The conservation invariant catches this.
- A decision computed before a state change goes stale; recompute legal answers when you change state in tests.
- Forced moves applied automatically must still be recorded, or per-card play counts are wrong (an audit found 60 %
  of Wingspan plays missing before `drain_forced`).
