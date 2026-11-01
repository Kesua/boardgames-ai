# Shared mechanics kit (`bgai/kit/`)

Small parts that mean the same thing in every game. It is a toolbox, not a framework: it never tries to model every
mechanic. Read this list before planning a new engine (`plan-engine` skill) and say in the game's `PLAN.md` which
parts it uses.

| Part | File | Behaviour | Used by |
|---|---|---|---|
| `Rng` | `deck.py` | the game's one random source (`random.Random`, seeded) | forest_shuffle, wingspan |
| `Deck` | `deck.py` | card pile, index 0 = top; `shuffle(rng)`, `draw()`, `draw_many(n)`, `put_bottom(cards)` | forest_shuffle, wingspan |
| `Decision`, `DecisionStack` | `decisions.py` | pending choices, top = answer now; `seat` = who decides (also outside its turn) | forest_shuffle, wingspan |
| `CodecBuilder` | `codec.py` | fixed action numbers from declared `(name, size)` segments; `encode`, `decode`, `mask` | forest_shuffle, wingspan |
| `winners`, `ranks` | `scores.py` | win = not beaten on (score, tiebreak), ties all win; ranks 1..n, remaining ties by seat | platform summaries, forest_shuffle, wingspan |
| `TextLog` | `textlog.py` | readable log lines `P<seat>: ...` for the log review | forest_shuffle, wingspan |
| `add_counts`, `one_hot` | `encoding.py` | write counts and one-hot values into the observation vector | forest_shuffle, wingspan |

What stays in each game: markets and trays, placement, card effects, scoring rules, end-of-game conditions, the game
state itself, dice.

## Rules

1. **Extract, don't design.** A part joins only when a second game needs the same behaviour, moved from working code
   with the `extract-to-kit` skill.
2. **No options for game-specific behaviour.** A game that needs different behaviour writes its own part.
3. **Optional.** The game interface (`bgai/game.py`) is the only contract.
4. **Frozen behaviour.** `tests/test_kit.py` pins each part's output for fixed seeds and inputs. A behaviour change is
   a new part (for example `Deck2`) or a regeneration of all experiments of every game that uses it
   (`upgrade-platform` skill). The fingerprint replay in CI catches unnoticed changes.
5. **Speed.** No callbacks or option checks on hot paths.
