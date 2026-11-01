---
name: plan-engine
description: Write games/<slug>/PLAN.md — the engine design (state, turn flow as decisions, frozen action numbering, effect handling, scoring, what the agent observes) — before writing engine code. Use after ingest-rules and build-card-db.
---

# Plan the engine

## Goal
A good plan makes the engine short, correct and learnable. Three choices decide almost everything: how a turn is cut
into small decisions, how every possible answer gets a fixed number (the AI's output layer), and what the AI sees.
Getting these right first avoids rewrites after training has started (the action numbering is frozen once models exist).

## Read first
`bgai/game.py` (the contract), `bgai/kit/README.md` (reuse these parts), `games/_template/` (smallest example),
`games/wingspan/PLAN.md` (a full example).

## The plan must cover
1. **Kit parts used** (Deck, Rng, DecisionStack, CodecBuilder, TextLog, winners/ranks, encoding helpers) and why not
   the others.
2. **State**: plain data (dataclasses/lists/dicts) so `clone()` is a pickle. No generators, no closures.
3. **Turn flow as decisions.** Every choice a player makes is one Decision with a kind, the deciding seat and a list
   of legal action numbers. Big choices are split into steps (choose card → choose target → pay one resource at a
   time). Decisions can belong to a player outside their turn (reactions, pink powers). A task stack (see
   `games/wingspan/engine.py`) handles chains of effects cleanly.
4. **Action numbering** (`CodecBuilder` segments): small segments reused across decisions (`BIRD 180`, `SLOT 15`,
   `YES`, `NO`, …). Aim for a few hundred numbers; never one number per full move combination.
5. **Optional vs mandatory** for every decision (a NO/stop answer where the rules allow refusing or taking less).
6. **Effects**: one handler per effect type from the card database; pink/reactive timing explicitly ordered.
7. **Scoring**: categories (`breakdowns()`), tiebreak (`tiebreaks()`), and what `tableau()` reports per item.
8. **What the agent observes** (encoder): own private info, public info, decision context; what must stay hidden.
9. **Recording**: `record_info` fields (decision, action, card, item, tags) so the summaries can count plays, uses and
   discards per card; forced single-option decisions reported via `drain_forced()`.
10. **Game length**: fixed (set SPEC.rounds) or variable (rounds per player).
11. **Risks**: rules most likely to be implemented wrong (from ingest-rules), how each will be tested.

## Done when
`PLAN.md` covers all eleven points and a reviewer can predict the code's structure from it.
