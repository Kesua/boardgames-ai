# Forest Shuffle RL Engine, Agents and GUI — Implementation Plan (v3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A rule-complete Python implementation of Forest Shuffle (base + Woodland Edge + Alpine) that neural-network agents can play through a fixed action space, plus a small web GUI to start games, watch agents play, and play against them.

**Architecture:** A data-driven engine reads every species, effect and scoring rule from `forest_shuffle/data/cards.json`; the turn structure is a decision stack (each pending choice, including payment and effect resolution, is a `Decision` whose options are the legal actions). A turn-based multi-agent environment wraps the engine with a fixed-size action codec and observation encoder; a self-play wrapper exposes it to `MaskablePPO`. A FastAPI server plus a vanilla-JS page renders the game and lets human, scripted and trained agents occupy seats.

**Tech Stack:** Python 3.10 (existing `.venv`), numpy, pytest, gymnasium, sb3-contrib (MaskablePPO, torch), fastapi, uvicorn, httpx (tests). Frontend: plain HTML/CSS/JS, no build step.

**Spec:** `doc/game_rules.md` (rules), `doc/card_catalog.md` (human-readable card data), `forest_shuffle/data/cards.json` (authoritative card data). Section 2 of this document is the design spec the tasks implement.

## Global Constraints

- Python 3.10 syntax only (no `match`, no `Self`); type hints with `from __future__ import annotations`.
- Card data is never hard-coded in engine code. Every species, cost, effect, bonus and scoring rule comes from `cards.json`. Engine code may reference species keys only for rule text that names a species (`MOUNTAIN_HARE` counts-as is in the data; nothing else).
- Randomness only through a `random.Random` instance owned by the game (`game.rng`); never the module-level `random`.
- The engine never raises on a legal action and always raises `IllegalActionError` on an illegal one. `legal_actions()` is the single source of truth for legality.
- Every rule in `doc/game_rules.md` and every card in `doc/card_catalog.md` has a test.
- Hand limit is 10. Draw action draws exactly `min(2, 10 - hand)` cards. Effects that draw respect the limit.
- Commit after every task; tests must pass before each commit (`.venv/Scripts/python.exe -m pytest -q`).

---

## 1. What changed since v2 (review findings folded in)

| v2 problem | v3 decision |
|---|---|
| Single `tree_color` per card | Tree symbol lives on each half (`HalfDef.tree_symbol`); trees/shrubs carry their own symbol. Bonus matching checks any half of a payment card. |
| Trees had flat points and no effects | Trees have effects (Birch, Beech, Stone Pine draw), bonuses (Oak, Douglas Fir extra turn; Silver Fir, Larch place-free) and scoring rules (Linden majority, Sycamore per tree, Silver Fir per attached, Horse Chestnut set, Oak 8 species). All read from data. |
| Scoring had no host-tree context | `score_dweller(forest, woody, dweller, game)` gets the host and the whole game (Linden and Woodpecker compare against other players). |
| Effect vocabulary too small; mushroom bus was a stub | Twelve effect types (Section 2.6) cover all 92 species. Permanent effects are checked by `matching_triggers()` on every placement; no event bus. |
| Payment hidden from the agent; bonus forced | `PAY` decisions: the agent discards one card per action. Bonus eligibility is computed from the actual payment. |
| Oak always scored; `apply_shrub_effect` no-op | Conditions are evaluated from data; shrub bonus runs the shrub's permanent action once. |
| Stacking had no cap; Mountain Hare/Toad wrong | `slot_sharing.max`, `counts_as`, Stinging Nettle host grant, all data-driven (Section 2.3). |
| Action index had no stable meaning | `ActionCodec`: fixed id space (~7.2k) built from card-definition ids, half and target slot. Same id means the same thing in every state. |
| Reward went to the wrong player | Environment returns a reward vector per seat and reports `current_player` before and after the step. |
| Observation lost visible half, stack counts, pending effect | Encoder uses species-level multi-hot per slot with stack counts and a decision-context block. |
| Global `random.seed` | `random.Random(seed)` per game. |
| Card removal table hard-coded | Removal count depends on the expansions in play. |
| No GUI, no orchestration | Tasks 16–18: FastAPI server, static page, agent seats, tournament CLI. |

---

## 2. Design

### 2.1 Card data (already produced)

`forest_shuffle/data/cards.json`:

- `meta`: tree symbols, dweller types, marker types, butterfly table, setup removal tables.
- `species[key]`: `name, kind (TREE|SHRUB|DWELLER), position (TOP|BOTTOM|LEFT_RIGHT|null), expansion, types[], cost, effect, bonus, scoring` plus optional `slot_sharing {with_names[], max|null}`, `counts_as`, `grants_host_slot_sharing {slot, filter, max}`, `modifiers {host_tree_count_bonus}`, `tree_species`, `display_name`.
- `cards[]`: `id, layout (WOODY_PLANT|TOP_BOTTOM|LEFT_RIGHT|WINTER), expansion, count` and either `species + tree_symbol` (woody) or `halves[{position, species, tree_symbol, extra_types?}]`.

Filters (used by effects, scoring and triggers): `{"types": [...], "names": [...], "kinds": [...], "match": "all"|"any", "distinct": bool, "slot": ..., "host_kinds": [...]}`. `kinds: ["TREE"]` means tree cards **and saplings**; `names` match through `counts_as`.

### 2.2 Core objects

```python
# forest_shuffle/core/cards.py
@dataclass(frozen=True)
class Species:
    key: str; name: str; kind: str; position: Optional[str]; expansion: str
    types: tuple[str, ...]; cost: int
    effect: Optional[dict]; bonus: Optional[dict]; scoring: dict
    slot_sharing: Optional[dict] = None; counts_as: Optional[str] = None
    grants_host_slot_sharing: Optional[dict] = None; modifiers: Optional[dict] = None
    tree_species: Optional[str] = None            # e.g. ALPINE_LARCH for "European Larch"

@dataclass(frozen=True)
class HalfDef:
    position: str                                  # TOP|BOTTOM|LEFT|RIGHT
    species: str; tree_symbol: str
    extra_types: tuple[str, ...] = ()

@dataclass(frozen=True)
class CardDef:
    def_id: int; card_code: str; layout: str; expansion: str; count: int
    species: Optional[str] = None; tree_symbol: Optional[str] = None   # woody
    halves: tuple[HalfDef, ...] = ()                                    # split

@dataclass(frozen=True)
class CardInstance:
    uid: int; def_id: int
```

```python
# forest_shuffle/core/state.py
@dataclass
class PlacedDweller:
    uid: int; species: str; tree_symbol: str; types: tuple[str, ...]; position: str

@dataclass
class PlacedWoody:
    uid: Optional[int]                 # None for a sapling (the face-down card goes to removed)
    species: Optional[str]             # None for a sapling
    kind: str                          # TREE | SHRUB (sapling is TREE)
    tree_symbol: Optional[str]
    types: tuple[str, ...]
    placed_turn: int
    slots: dict[str, list[PlacedDweller]] = field(default_factory=lambda: {s: [] for s in ("TOP", "BOTTOM", "LEFT", "RIGHT")})

@dataclass
class PlayerState:
    seat: int
    hand: list[CardInstance] = field(default_factory=list)
    forest: list[PlacedWoody] = field(default_factory=list)
    cave: list[CardInstance] = field(default_factory=list)
    mulligan_used: bool = False

@dataclass
class Decision:
    kind: str                          # DecisionKind value
    data: dict = field(default_factory=dict)

@dataclass
class GameState:
    players: list[PlayerState]; deck: list[CardInstance]; clearing: list[CardInstance]
    removed: list[CardInstance]; winter_revealed: int = 0
    current: int = 0; turn_index: int = 0; extra_turns: int = 0
    decisions: list[Decision] = field(default_factory=list)   # stack, top = last
    game_over: bool = False
    log: list[str] = field(default_factory=list)
```

### 2.3 Placement rules

`can_place(forest_woody, half_species, half_position) -> bool`:

1. Position must equal the slot (`LEFT_RIGHT` species may go LEFT or RIGHT according to the half's `position`).
2. Empty slot: allowed.
3. Occupied slot: allowed only if **every** occupant shares with the newcomer: occupant species `slot_sharing.with_names` contains the newcomer's key **and** newcomer's `slot_sharing.with_names` contains the occupant key, and `len(slot) < max` when `max` is set. Mountain Hare has `slot_sharing = null`, so it never shares even with European Hare.
4. Stinging Nettle: if any dweller on this woody has `grants_host_slot_sharing` with `slot == TOP`, then any number of dwellers whose types include `BUTTERFLY` may share the TOP slot (regardless of their own `slot_sharing`).

### 2.4 Turn structure as a decision stack

`legal_actions()`:
- stack empty → `CHOOSE_ACTION` options: `DRAW_DECK` (if deck non-empty and hand < 10), `DRAW_CLEARING(def)` for each distinct def in the clearing (hand < 10), `PLAY_WOODY(def)` for affordable woody cards in hand, `PLAY_SAPLING(def)` for every hand card, `PLAY_HALF(def, half, target)` for affordable halves with a legal target.
- otherwise the top decision's options (table below).

| DecisionKind | data | options | on action |
|---|---|---|---|
| `DRAW` | `remaining` | `DRAW_DECK`, `DRAW_CLEARING(def)` | draw; `remaining -= 1`; pop when 0 or no source |
| `PAY` | `play` (uid, half_idx, target), `cost`, `paid: [uid]` | `PAY(def)` for hand cards ≠ played card | move card to clearing; when `len(paid)==cost` → pop and `_place_pending(play, paid)` |
| `USE_OR_SKIP` | `effect`, `source` (uid, species, woody index), `label` | `USE`, `SKIP` | pop; `USE` → `apply_effect` |
| `CHOOSE_CLEARING_CARD` | `remaining`, `filter`, `dest` (HAND\|CAVE) | `CHOOSE_CARD(def)` for matching clearing cards, `DONE` if `optional` | move card; pop when remaining 0 or clearing empty |
| `CHOOSE_HAND_CARD` | `dest` (CAVE), `chosen` | `CHOOSE_CARD(def)`, `DONE` | Raccoon: move to cave; on `DONE` draw `len(chosen)` and pop |
| `PLACE_FREE` | `filter`, `remaining` (int or "any") | `PLAY_HALF(def, half, target)` for matching halves with legal target, `DONE` | place without cost/effect/bonus; triggers still fire; pop when remaining hits 0 |
| `PLAY_MORE` | — | all `PLAY_*` options as in CHOOSE_ACTION, `DONE` | Mole: chosen play runs the normal pipeline on top of this decision |
| `SAPLING_MORE` | — | `PLAY_SAPLING(def)`, `DONE` | Water Vole |

Turn end happens when the stack is empty after an action that was not the first `CHOOSE_ACTION` selection. `_end_turn()`: if `len(clearing) >= 10` move clearing to `removed`; `turn_index += 1`; if `extra_turns > 0` decrement and keep `current`, else advance `current`.

Pipeline for playing a card (`_start_play`):
1. If cost > 0 push `PAY`; else `_place_pending` immediately.
2. `_place_pending`: remove card from hand; create `PlacedWoody` or `PlacedDweller`; saplings send the card to `removed`; trees and saplings call `_reveal_to_clearing()` (winter handling inside).
3. Compute `bonus_ok = cost > 0 and all(payment card shows played symbol)`; a card shows a symbol if its woody symbol or any half's symbol equals it.
4. Push in reverse order so they resolve as: effect (if any), bonus (if `bonus_ok` and species has a bonus), then one `USE_OR_SKIP` per matching active permanent trigger. Shrubs: the bonus decision's `effect` is the shrub's permanent `action`.
5. Cards placed via `PLACE_FREE` skip steps 3–4 except triggers.

Winter: `_draw_from_deck()` pops the top card; if it is WINTER, `winter_revealed += 1`, the card goes to `removed`, and if the count reaches 3 the game ends immediately (`game_over = True`, stack cleared); otherwise it draws again.

### 2.5 Action codec

```python
# forest_shuffle/core/actions.py
class ActionKind(str, Enum):
    DRAW_DECK = "DRAW_DECK"; DRAW_CLEARING = "DRAW_CLEARING"
    PLAY_WOODY = "PLAY_WOODY"; PLAY_SAPLING = "PLAY_SAPLING"; PLAY_HALF = "PLAY_HALF"
    PAY = "PAY"; CHOOSE_CARD = "CHOOSE_CARD"; CHOOSE_TARGET = "CHOOSE_TARGET"
    USE = "USE"; SKIP = "SKIP"; DONE = "DONE"

@dataclass(frozen=True)
class Action:
    kind: ActionKind
    card: Optional[int] = None    # def_id (identical copies are interchangeable)
    half: Optional[int] = None    # 0 or 1
    target: Optional[int] = None  # index into current player's forest
```

Id layout with `N = number of non-winter defs (160)` and `W = MAX_WOODY = 40`:

| range | meaning |
|---|---|
| 0 | DRAW_DECK |
| 1 .. N | DRAW_CLEARING(card) |
| +N | PLAY_WOODY(card) |
| +N | PLAY_SAPLING(card) |
| +2·N·W | PLAY_HALF(card, half, target) = base + (card·2 + half)·W + target |
| +N | PAY(card) |
| +N | CHOOSE_CARD(card) |
| +W | CHOOSE_TARGET(target) |
| +3 | USE, SKIP, DONE |

Total = 1 + 5N + 2NW + W + 3 = 13 644 for N=160, W=40. `ActionCodec.size`, `encode(Action) -> int`, `decode(int) -> Action`, `mask(actions) -> np.ndarray[bool]`. When the forest already holds `W` woody plants, `PLAY_WOODY`/`PLAY_SAPLING` are not offered.

### 2.6 Effect vocabulary (engine semantics)

| `effect.type` | fields | semantics |
|---|---|---|
| `draw` | `count` | draw `count` from deck, stop at hand 10 |
| `draw_per` | `filter` | draw `count_cards(own forest, filter)` cards, hand limit |
| `place_free` | `filter`, `count` (1 or `"any"`) | push `PLACE_FREE`; halves whose species matches `filter` (types include marker types; `names` for Squeaker) |
| `extra_turn` | optional `condition {type: min_count, count, filter}` | `extra_turns += 1` if condition holds |
| `take_from_clearing` | `count` (1 or `"all"`), optional `filter` | 1 → push `CHOOSE_CLEARING_CARD(dest=HAND)`; `"all"` → move all matching to hand up to limit, no choice |
| `clearing_to_cave` | `count` (2 or `"all"`), optional `filter` | 2 → push `CHOOSE_CLEARING_CARD(dest=CAVE, remaining=min(2, available))`; `"all"` → move all matching |
| `hand_to_cave_draw_equal` | — | push `CHOOSE_HAND_CARD(dest=CAVE)`; on DONE draw as many as moved |
| `remove_clearing` | — | move clearing to `removed` |
| `play_cards` | — | push `PLAY_MORE` |
| `play_saplings` | — | push `SAPLING_MORE` |
| `sequence` | `steps[]` | push steps so they resolve in order (each step may push its own decision) |
| `permanent` | `trigger {event, filter}`, `action` | registered by presence in the forest; `matching_triggers(player, placed)` returns woody/dweller sources whose `placed_turn < turn_index` and whose filter matches the placed card (types/kinds/`slot` + `host_kinds`) |

Draw effects and `_reveal_to_clearing` use `_draw_from_deck`, so winter cards end the game mid-effect.

### 2.7 Scoring vocabulary

`count_cards(forest, filter, with_modifiers)`: counts woody plants (kind TREE incl. saplings, SHRUB) and visible dwellers matching the filter; `distinct` counts distinct species keys (after `counts_as`); with `with_modifiers`, each Violet Carpenter Bee adds 1 for its host woody if the host matches the filter. Name-based, `set`, `majority`, `min_count` and `min_trees` counts use modifiers; type-based `per_card` counts do not (mirrors the reference card).

| `scoring.type` | result |
|---|---|
| `flat` | `points` |
| `per_card` | `points × count_cards(filter, with_modifiers=False)` |
| `per_tree_symbol` | `points × number of forest cards (woody + visible dwellers) showing the symbol(s)`; `"SELF"` = the scoring dweller's own symbol |
| `conditional` | `points` if condition: `min_count`, `min_distinct`, `host_species`, `host_kind`, `host_has` (another dweller on the same woody matches filter; host must be a TREE for the Dormouse), `alone_on_host` (only dweller on its woody), `shares_slot_with` (another occupant of the same slot with that name), `all_tree_species` (≥8 distinct tree species, saplings excluded, `tree_species` used for Alpine trees), `min_trees` (trees incl. saplings, with modifiers) |
| `majority` | `points_if_most` if own count ≥ every other player's count, else `points_otherwise` (with modifiers) |
| `set` | scored **once per species**: table value for the species count (with modifiers, highest key ≤ count) |
| `table_by_count` | table value for `count_cards(filter)` clamped to the highest key |
| `butterfly_set` | scored once per forest: greedily pack butterflies into sets of distinct species, sum `meta.butterfly_table[len]` |
| `per_cave_card` | `len(cave)` |
| `per_attached_to_host` | `points × dwellers on this woody` |
| `per_fully_occupied` | `points × woody of `host_kinds` with all four slots non-empty` |
| `per_card_in_slot` | `points × dwellers in `slot` of woody of `host_kinds`` |

Total score = Σ woody scores + Σ dweller scores + `len(cave)`.

### 2.8 Observation

Fixed-size float vector, from the acting seat's view:

| block | size |
|---|---|
| global: winter/3, deck/233, clearing size/15, turn phase one-hot (CHOOSE, DRAW, PAY, USE_OR_SKIP, CHOOSE_CLEARING, CHOOSE_HAND, PLACE_FREE, PLAY_MORE, SAPLING_MORE), extra_turns/3 | 13 |
| decision context: species one-hot (92) of the card whose effect/bonus is pending, `remaining`/3 | 93 |
| own hand: count per def_id / 4 | 160 |
| clearing: count per def_id / 4 | 160 |
| per player (self first, then clockwise), each: hand size/10, cave/20, forest block | P × (2 + 24 × F) |
| forest block per woody: species one-hot (95 = 92 species + SAPLING + empty + unused), symbol one-hot (11), 4 slots × (species multi-hot 92 + stack count/4) | F = 95 + 11 + 4 × 93 = 478 |

For 2 players: 13 + 93 + 320 + 2 × (2 + 24 × 478) = 23 374 floats. `StateEncoder.size(num_players)`.

### 2.9 Environment, agents, training

- `ForestShuffleEnv(num_players, seed, expansions)`: `reset() -> (obs, info)`, `step(action_id) -> (obs, rewards: np.ndarray[num_players], terminated, truncated, info)`; `info` carries `current_player`, `action_mask`, `acting_player` (who took the step), `scores` at the end. Rewards are zero until the end; final reward per seat is `+1` for the winner(s), `-1` otherwise (tie = shared win). `truncated` after 2 000 steps.
- `Agent` protocol: `act(env_view: GameView) -> int`. `RandomAgent`, `GreedyAgent` (deep-copies the game, applies each legal action, picks the one maximising own score − best opponent score; ties random), `PolicyAgent` (MaskablePPO model, deterministic flag).
- `SelfPlayEnv(gym.Env)`: learner is seat 0; other seats are played inside `step()` by an opponent agent (random at first, then frozen snapshots of the learner). Exposes `action_masks()` for `MaskablePPO`.
- `train.py`: MaskablePPO with an MLP policy, opponent snapshot every `snapshot_every` updates, evaluation vs random and greedy, checkpoints to `runs/`.

### 2.10 GUI

FastAPI app (`forest_shuffle/gui/server.py`) with a single in-memory game session:

| endpoint | purpose |
|---|---|
| `GET /` | serves `static/index.html` |
| `POST /api/new` `{num_players, seats: [{type: "human"|"random"|"greedy"|"model", path?}], seed?, expansions?}` | new game |
| `GET /api/state?viewer=<seat>` | JSON view: clearing, deck/winter counts, every forest, the viewer's hand, current seat, phase, pending decision label, legal actions with labels (if the viewer is current), scores, log tail |
| `POST /api/action {id}` | apply an action for a human seat |
| `POST /api/step` | let the current AI seat take one action |
| `POST /api/autoplay {max_steps}` | step AI seats until a human seat must act, game over, or `max_steps` |

Frontend (`static/index.html`, `app.js`, `style.css`): top bar (new game form, step, auto-play toggle + speed, scores), clearing row, one forest panel per player (woody cards as boxes with four slot lists), the human's hand, an action panel grouped by kind with readable labels, and a log. Polls `/api/state` every 400 ms while auto-play runs.

---

## 3. File structure

```
forest_shuffle/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── enums.py          # Slot, Kind, Layout, DecisionKind, constants
│   ├── cards.py          # Species, HalfDef, CardDef, CardInstance
│   ├── state.py          # PlacedDweller, PlacedWoody, PlayerState, Decision, GameState
│   └── actions.py        # ActionKind, Action, ActionCodec
├── data/
│   ├── __init__.py
│   ├── cards.json        # (exists)
│   └── database.py       # CardDatabase
├── engine/
│   ├── __init__.py
│   ├── filters.py        # matches(), count_cards(), shows_symbol()
│   ├── placement.py      # can_place(), legal_targets()
│   ├── scoring.py        # score_player(), score_woody(), score_dweller()
│   ├── setup.py          # build_deck(), removal_count(), deal()
│   ├── effects.py        # apply_effect(), matching_triggers(), decision option builders
│   └── game.py           # Game: legal_actions(), step(), scores(), IllegalActionError
├── rl/
│   ├── __init__.py
│   ├── encoder.py        # StateEncoder
│   ├── env.py            # ForestShuffleEnv (multi-agent, reward vector)
│   ├── agents.py         # Agent, RandomAgent, GreedyAgent, PolicyAgent
│   ├── selfplay_env.py   # SelfPlayEnv (gymnasium, action_masks)
│   └── train.py          # MaskablePPO training loop
├── gui/
│   ├── __init__.py
│   ├── view.py           # state_to_view(), describe_action()
│   ├── server.py         # FastAPI app
│   └── static/index.html, app.js, style.css
examples/
├── play_random.py
└── tournament.py
tests/
├── conftest.py           # db fixture, game factory helpers
├── test_database.py, test_placement.py, test_filters.py, test_scoring.py, test_setup.py,
├── test_actions.py, test_turn_draw.py, test_turn_play.py, test_effects.py, test_playout.py,
├── test_encoder.py, test_env.py, test_agents.py, test_selfplay.py, test_gui.py
requirements.txt
pyproject.toml
```

Test helper used throughout (`tests/conftest.py`):

```python
import pytest
from forest_shuffle.data.database import CardDatabase
from forest_shuffle.engine.game import Game

@pytest.fixture(scope="session")
def db():
    return CardDatabase.load()

@pytest.fixture
def game(db):
    g = Game(db, num_players=2, seed=1)
    g.reset()
    return g

def give(game, seat, species_key, tree_symbol=None):
    """Put a fresh instance of a card containing `species_key` (with the given symbol if any) in a hand."""
    for d in game.db.defs:
        if d.layout == "WOODY_PLANT" and d.species == species_key and (tree_symbol in (None, d.tree_symbol)):
            return game.spawn_into_hand(seat, d.def_id)
        for h in d.halves:
            if h.species == species_key and (tree_symbol in (None, h.tree_symbol)):
                return game.spawn_into_hand(seat, d.def_id)
    raise KeyError(species_key)

def plant(game, seat, species_key, tree_symbol=None):
    """Place a woody plant directly (test shortcut). Returns forest index."""
    return game.debug_place_woody(seat, give(game, seat, species_key, tree_symbol).def_id)

def attach(game, seat, forest_idx, species_key, tree_symbol=None):
    """Place a dweller directly (test shortcut)."""
    card = give(game, seat, species_key, tree_symbol)
    return game.debug_place_dweller(seat, forest_idx, card.def_id, species_key)
```

`Game.spawn_into_hand`, `debug_place_woody`, `debug_place_dweller` are test-only helpers defined in Task 8 (they bypass costs but respect placement legality).

---

## 4. Tasks

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `forest_shuffle/__init__.py`, `forest_shuffle/{core,data,engine,rl,gui}/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`
- Modify: `.gitignore`, `README.md`

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_smoke.py
def test_package_imports():
    import forest_shuffle
    assert forest_shuffle.__version__ == "0.1.0"
```

- [ ] **Step 2: Run it, expect ImportError**

Run: `.venv/Scripts/python.exe -m pytest tests/test_smoke.py -q`

- [ ] **Step 3: Create the package and config**

`forest_shuffle/__init__.py`: `__version__ = "0.1.0"`. Empty `__init__.py` in the five sub-packages and `tests/`.

```toml
# pyproject.toml
[project]
name = "forest-shuffle"
version = "0.1.0"
requires-python = ">=3.10"
[tool.pytest.ini_options]
testpaths = ["tests"]
```

```
# requirements.txt
numpy>=1.26
pytest>=8
gymnasium>=0.29
sb3-contrib>=2.3
torch>=2.2
fastapi>=0.110
uvicorn>=0.29
httpx>=0.27
```

Append to `.gitignore`: `__pycache__/`, `runs/`, `*.zip`. Replace `README.md` with a short description and the three commands: install (`.venv/Scripts/python.exe -m pip install -r requirements.txt`), test, run GUI (`.venv/Scripts/python.exe -m uvicorn forest_shuffle.gui.server:app --reload`).

- [ ] **Step 4: Install and run**

Run: `.venv/Scripts/python.exe -m pip install -r requirements.txt` then `.venv/Scripts/python.exe -m pytest -q` → 1 passed.

- [ ] **Step 5: Commit** `git add -A && git commit -m "chore: project scaffolding"`

---

### Task 2: Card database loader

**Files:**
- Create: `forest_shuffle/core/enums.py`, `forest_shuffle/core/cards.py`, `forest_shuffle/data/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `CardDatabase.load(path: Optional[str] = None) -> CardDatabase` with `species: dict[str, Species]`, `defs: list[CardDef]` (index == `def_id`, winter def last), `winter_def_id: int`, `num_play_defs: int` (defs excluding winter), `meta: dict`, `species_index: dict[str, int]` (0..91 stable order = JSON order), `symbol_index: dict[str, int]`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_database.py
from forest_shuffle.data.database import CardDatabase

def test_totals(db):
    assert len(db.species) == 92
    assert sum(d.count for d in db.defs) == 233
    assert db.defs[db.winter_def_id].layout == "WINTER"
    assert db.num_play_defs == len(db.defs) - 1

def test_half_positions_match_species(db):
    for d in db.defs:
        for h in d.halves:
            sp = db.species[h.species]
            assert sp.position in (h.position, "LEFT_RIGHT")
            if sp.position == "LEFT_RIGHT":
                assert h.position in ("LEFT", "RIGHT")

def test_species_fields(db):
    hare = db.species["EUROPEAN_HARE"]
    assert hare.cost == 0 and hare.slot_sharing == {"with_names": ["EUROPEAN_HARE"], "max": None}
    assert db.species["MOUNTAIN_HARE"].counts_as == "EUROPEAN_HARE"
    assert db.species["EUROPEAN_LARCH"].tree_species == "ALPINE_LARCH"
    assert db.species["OAK"].bonus == {"type": "extra_turn"}

def test_woodland_squeaker_gets_marker_type(db):
    d = next(d for d in db.defs if d.card_code == "WH004")
    half = next(h for h in d.halves if h.species == "SQUEAKER")
    assert "WOODLAND_EDGE" in half.extra_types
```

- [ ] **Step 2: Run, expect failures (module missing)**

- [ ] **Step 3: Implement**

```python
# forest_shuffle/core/enums.py
SLOTS = ("TOP", "BOTTOM", "LEFT", "RIGHT")
TREE_SYMBOLS = ("LINDEN", "OAK", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE", "DOUGLAS_FIR", "HORSE_CHESTNUT", "ALPINE_LARCH", "SWISS_PINE")
HAND_LIMIT = 10
CLEARING_LIMIT = 10
MAX_WOODY = 24
class DecisionKind:
    DRAW = "DRAW"; PAY = "PAY"; USE_OR_SKIP = "USE_OR_SKIP"
    CHOOSE_CLEARING_CARD = "CHOOSE_CLEARING_CARD"; CHOOSE_HAND_CARD = "CHOOSE_HAND_CARD"
    PLACE_FREE = "PLACE_FREE"; PLAY_MORE = "PLAY_MORE"; SAPLING_MORE = "SAPLING_MORE"
ALL_DECISION_KINDS = ("DRAW", "PAY", "USE_OR_SKIP", "CHOOSE_CLEARING_CARD", "CHOOSE_HAND_CARD", "PLACE_FREE", "PLAY_MORE", "SAPLING_MORE")
```

`cards.py`: the dataclasses from Section 2.2.

```python
# forest_shuffle/data/database.py
import json
from pathlib import Path
from ..core.cards import Species, HalfDef, CardDef

class CardDatabase:
    def __init__(self, raw: dict):
        self.meta = raw["meta"]
        self.species = {k: Species(key=k, name=v["name"], kind=v["kind"], position=v["position"], expansion=v["expansion"],
                                   types=tuple(v["types"]), cost=v["cost"], effect=v["effect"], bonus=v["bonus"], scoring=v["scoring"],
                                   slot_sharing=v.get("slot_sharing"), counts_as=v.get("counts_as"),
                                   grants_host_slot_sharing=v.get("grants_host_slot_sharing"), modifiers=v.get("modifiers"),
                                   tree_species=v.get("tree_species")) for k, v in raw["species"].items()}
        self.species_index = {k: i for i, k in enumerate(self.species)}
        self.symbol_index = {s: i for i, s in enumerate(self.meta["tree_symbols"])}
        play = [c for c in raw["cards"] if c["layout"] != "WINTER"]
        winter = [c for c in raw["cards"] if c["layout"] == "WINTER"]
        self.defs = []
        for i, c in enumerate(play + winter):
            halves = tuple(HalfDef(h["position"], h["species"], h["tree_symbol"], tuple(h.get("extra_types", []))) for h in c.get("halves", []))
            self.defs.append(CardDef(def_id=i, card_code=c["id"], layout=c["layout"], expansion=c["expansion"], count=c["count"],
                                     species=c.get("species"), tree_symbol=c.get("tree_symbol"), halves=halves))
        self.winter_def_id = len(self.defs) - 1
        self.num_play_defs = len(play)

    @classmethod
    def load(cls, path=None):
        p = Path(path) if path else Path(__file__).with_name("cards.json")
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def half_types(self, half: HalfDef) -> tuple:
        return tuple(self.species[half.species].types) + half.extra_types
```

- [ ] **Step 4: Run tests → pass.** `.venv/Scripts/python.exe -m pytest tests/test_database.py -q`
- [ ] **Step 5: Commit** `git commit -am "feat: card database loader"` (add new files first)

---

### Task 3: State objects and placement rules

**Files:**
- Create: `forest_shuffle/core/state.py`, `forest_shuffle/engine/placement.py`
- Test: `tests/test_placement.py`

**Interfaces:**
- Produces: `can_place(db, woody: PlacedWoody, species_key: str, position: str) -> bool`; `legal_targets(db, forest: list[PlacedWoody], species_key, position) -> list[int]`; `PlacedWoody.is_fully_occupied() -> bool`; `PlacedWoody.dwellers() -> list[PlacedDweller]`; `make_dweller(db, uid, half: HalfDef) -> PlacedDweller`; `make_woody(db, uid, def: CardDef, turn) -> PlacedWoody`; `make_sapling(turn) -> PlacedWoody`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_placement.py
from forest_shuffle.core.state import make_sapling, make_dweller
from forest_shuffle.engine.placement import can_place
from forest_shuffle.core.cards import HalfDef

def dw(db, species, pos, sym="BEECH", uid=1):
    return make_dweller(db, uid, HalfDef(pos, species, sym))

def test_empty_slot_ok(db):
    w = make_sapling(0)
    assert can_place(db, w, "TAWNY_OWL", "TOP")
    assert not can_place(db, w, "TAWNY_OWL", "BOTTOM")

def test_hares_stack_unlimited(db):
    w = make_sapling(0)
    for i in range(5):
        assert can_place(db, w, "EUROPEAN_HARE", "LEFT")
        w.slots["LEFT"].append(dw(db, "EUROPEAN_HARE", "LEFT", uid=i))
    assert not can_place(db, w, "MOUNTAIN_HARE", "LEFT")

def test_mountain_hare_never_shares(db):
    w = make_sapling(0)
    w.slots["LEFT"].append(dw(db, "MOUNTAIN_HARE", "LEFT"))
    assert not can_place(db, w, "EUROPEAN_HARE", "LEFT")

def test_toads_max_two(db):
    w = make_sapling(0)
    w.slots["BOTTOM"].append(dw(db, "COMMON_TOAD", "BOTTOM", uid=1))
    assert can_place(db, w, "COMMON_TOAD", "BOTTOM")
    w.slots["BOTTOM"].append(dw(db, "COMMON_TOAD", "BOTTOM", uid=2))
    assert not can_place(db, w, "COMMON_TOAD", "BOTTOM")

def test_nettle_lets_butterflies_share_top(db):
    w = make_sapling(0)
    w.slots["TOP"].append(dw(db, "PEACOCK_BUTTERFLY", "TOP"))
    assert not can_place(db, w, "MAP_BUTTERFLY", "TOP")
    w.slots["BOTTOM"].append(dw(db, "STINGING_NETTLE", "BOTTOM"))
    assert can_place(db, w, "MAP_BUTTERFLY", "TOP")
    assert not can_place(db, w, "TAWNY_OWL", "TOP")
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**

`state.py`: dataclasses from Section 2.2 plus:

```python
def make_dweller(db, uid, half):
    sp = db.species[half.species]
    return PlacedDweller(uid=uid, species=half.species, tree_symbol=half.tree_symbol, types=tuple(sp.types) + half.extra_types, position=half.position)

def make_woody(db, uid, card_def, turn):
    sp = db.species[card_def.species]
    return PlacedWoody(uid=uid, species=card_def.species, kind=sp.kind, tree_symbol=card_def.tree_symbol, types=tuple(sp.types), placed_turn=turn)

def make_sapling(turn):
    return PlacedWoody(uid=None, species=None, kind="TREE", tree_symbol=None, types=("TREE",), placed_turn=turn)
```

`PlacedWoody.dwellers()` flattens the four slot lists; `is_fully_occupied()` is `all(self.slots[s] for s in SLOTS)`.

```python
# forest_shuffle/engine/placement.py
def _nettle_grant(db, woody, position, species_key):
    for d in woody.dwellers():
        g = db.species[d.species].grants_host_slot_sharing
        if g and g["slot"] == position and any(t in db.species[species_key].types for t in g["filter"]["types"]):
            return True
    return False

def can_place(db, woody, species_key, position):
    sp = db.species[species_key]
    if sp.position not in (position, "LEFT_RIGHT") or (sp.position == "LEFT_RIGHT" and position not in ("LEFT", "RIGHT")):
        return False
    occupants = woody.slots[position]
    if not occupants:
        return True
    if _nettle_grant(db, woody, position, species_key):
        return True
    mine = sp.slot_sharing
    if not mine or species_key not in mine["with_names"]:
        return False
    for o in occupants:
        theirs = db.species[o.species].slot_sharing
        if not theirs or o.species not in mine["with_names"] or species_key not in theirs["with_names"]:
            return False
        if theirs["max"] is not None and len(occupants) >= theirs["max"]:
            return False
    return True

def legal_targets(db, forest, species_key, position):
    return [i for i, w in enumerate(forest) if can_place(db, w, species_key, position)]
```

- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: state objects and placement rules"`

---

### Task 4: Filters and counting

**Files:**
- Create: `forest_shuffle/engine/filters.py`
- Test: `tests/test_filters.py`

**Interfaces:**
- Produces: `card_matches(db, card_types: tuple, species_key: Optional[str], kind: str, flt: dict) -> bool`; `count_cards(db, forest: list[PlacedWoody], flt: dict, with_modifiers: bool) -> int`; `shows_symbol(db, card_def: CardDef, symbol: str) -> bool`; `forest_symbol_count(forest, symbols: list[str]) -> int`; `tree_species_set(db, forest) -> set[str]`; `hand_card_types(db, card_def) -> list[tuple[HalfDef|None, tuple]]`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_filters.py
from forest_shuffle.core.state import make_sapling, make_dweller, make_woody
from forest_shuffle.core.cards import HalfDef
from forest_shuffle.engine.filters import count_cards, shows_symbol, tree_species_set

def woody(db, key, sym, uid=0):
    d = next(d for d in db.defs if d.species == key)
    return make_woody(db, uid, d, 0)

def test_kinds_tree_includes_saplings(db):
    forest = [woody(db, "BEECH", "BEECH"), make_sapling(0)]
    assert count_cards(db, forest, {"kinds": ["TREE"]}, False) == 2
    assert count_cards(db, forest, {"names": ["BEECH"]}, False) == 1

def test_counts_as(db):
    w = make_sapling(0)
    w.slots["LEFT"].append(make_dweller(db, 1, HalfDef("LEFT", "MOUNTAIN_HARE", "SWISS_PINE")))
    w.slots["RIGHT"].append(make_dweller(db, 2, HalfDef("RIGHT", "EUROPEAN_HARE", "BIRCH")))
    assert count_cards(db, [w], {"names": ["EUROPEAN_HARE"]}, False) == 2

def test_bee_modifier_only_with_modifiers(db):
    b = woody(db, "BEECH", "BEECH")
    b.slots["LEFT"].append(make_dweller(db, 1, HalfDef("LEFT", "VIOLET_CARPENTER_BEE", "DOUGLAS_FIR")))
    assert count_cards(db, [b], {"names": ["BEECH"]}, True) == 2
    assert count_cards(db, [b], {"names": ["BEECH"]}, False) == 1
    assert count_cards(db, [b], {"kinds": ["TREE"]}, True) == 2

def test_distinct_and_any(db):
    w = make_sapling(0)
    w.slots["BOTTOM"].append(make_dweller(db, 1, HalfDef("BOTTOM", "MOSS", "LINDEN")))
    w2 = make_sapling(0)
    w2.slots["BOTTOM"].append(make_dweller(db, 2, HalfDef("BOTTOM", "MOSS", "LINDEN")))
    forest = [w, w2]
    assert count_cards(db, forest, {"types": ["PLANT"], "distinct": True}, False) == 1
    assert count_cards(db, forest, {"kinds": ["TREE"], "types": ["PLANT"], "match": "any"}, False) == 4

def test_shows_symbol_any_half(db):
    d = next(d for d in db.defs if d.card_code == "BH001")   # European Hare[Li] | European Badger[DF]
    assert shows_symbol(db, d, "LINDEN") and shows_symbol(db, d, "DOUGLAS_FIR") and not shows_symbol(db, d, "OAK")

def test_tree_species_uses_alpine_names(db):
    forest = [woody(db, "EUROPEAN_LARCH", "ALPINE_LARCH"), make_sapling(0)]
    assert tree_species_set(db, forest) == {"ALPINE_LARCH"}
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**

```python
# forest_shuffle/engine/filters.py
def _name_matches(db, species_key, names):
    if species_key is None: return False
    sp = db.species[species_key]
    return species_key in names or (sp.counts_as in names)

def card_matches(db, card_types, species_key, kind, flt):
    checks = []
    if "types" in flt:  checks.append(any(t in card_types for t in flt["types"]))
    if "names" in flt:  checks.append(_name_matches(db, species_key, flt["names"]))
    if "kinds" in flt:  checks.append(kind in flt["kinds"])
    if not checks: return True
    return any(checks) if flt.get("match") == "any" else all(checks)

def _entries(db, forest):
    """(types, species_key, kind, host_woody, dweller_or_None) for every woody and visible dweller."""
    for w in forest:
        yield (w.types, w.species, w.kind, w, None)
        for d in w.dwellers():
            yield (d.types, d.species, "DWELLER", w, d)

def count_cards(db, forest, flt, with_modifiers):
    seen, n = set(), 0
    for types, key, kind, host, dweller in _entries(db, forest):
        if not card_matches(db, types, key, kind, flt): continue
        if flt.get("distinct"):
            canon = db.species[key].counts_as or key if key else "SAPLING"
            if canon in seen: continue
            seen.add(canon)
        n += 1
    if with_modifiers:
        for w in forest:
            if card_matches(db, w.types, w.species, w.kind, flt):
                n += sum((db.species[d.species].modifiers or {}).get("host_tree_count_bonus", 0) for d in w.dwellers())
    return n

def shows_symbol(db, card_def, symbol):
    if card_def.layout == "WOODY_PLANT": return card_def.tree_symbol == symbol
    return any(h.tree_symbol == symbol for h in card_def.halves)

def forest_symbol_count(forest, symbols):
    n = sum(1 for w in forest if w.tree_symbol in symbols)
    return n + sum(1 for w in forest for d in w.dwellers() if d.tree_symbol in symbols)

def tree_species_set(db, forest):
    out = set()
    for w in forest:
        if w.kind == "TREE" and w.species:
            out.add(db.species[w.species].tree_species or w.species)
    return out
```

- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: card filters and counting"`

---

### Task 5: Scoring engine

**Files:**
- Create: `forest_shuffle/engine/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: `count_cards`, `forest_symbol_count`, `tree_species_set`.
- Produces: `score_player(db, players: list[PlayerState], seat: int) -> int`; `score_breakdown(db, players, seat) -> dict[str, int]` (keys: `trees`, `dwellers`, `cave`, `total`).

- [ ] **Step 1: Failing tests** (examples taken from the reference cards and rulebook)

```python
# tests/test_scoring.py
from tests.conftest import plant, attach
from forest_shuffle.engine.scoring import score_player

def test_five_hares_score_25(game):
    t = plant(game, 0, "BIRCH")
    for _ in range(5): attach(game, 0, t, "EUROPEAN_HARE")
    assert score_player(game.db, game.state.players, 0) == 1 + 25

def test_mountain_and_european_hares_36(game):
    t1, t2, t3 = plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH")
    for _ in range(4): attach(game, 0, t1, "EUROPEAN_HARE")
    attach(game, 0, t2, "MOUNTAIN_HARE"); attach(game, 0, t3, "MOUNTAIN_HARE")
    assert score_player(game.db, game.state.players, 0) == 3 + 36

def test_linden_majority_with_bee(game):
    for _ in range(4): plant(game, 1, "LINDEN")
    a = plant(game, 0, "LINDEN"); plant(game, 0, "LINDEN"); plant(game, 0, "LINDEN")
    attach(game, 0, a, "VIOLET_CARPENTER_BEE")
    assert score_player(game.db, game.state.players, 0) == 9          # 3 Lindens × 3, bee 0
    assert score_player(game.db, game.state.players, 1) == 12

def test_horse_chestnut_set_with_bee(game):
    a = plant(game, 0, "HORSE_CHESTNUT"); plant(game, 0, "HORSE_CHESTNUT")
    assert score_player(game.db, game.state.players, 0) == 4
    attach(game, 0, a, "VIOLET_CARPENTER_BEE")
    assert score_player(game.db, game.state.players, 0) == 9

def test_oak_needs_eight_species(game):
    plant(game, 0, "OAK")
    assert score_player(game.db, game.state.players, 0) == 0
    for k in ["LINDEN", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE", "DOUGLAS_FIR", "HORSE_CHESTNUT"]: plant(game, 0, k)
    # oak 10, linden 3 (own 1 ≥ opponent 0), silver fir 0 (nothing attached), birch 1, beech 0 (1 of 4),
    # sycamore 8 (1 per tree), douglas fir 5, horse chestnut 1 (set of 1)
    assert score_player(game.db, game.state.players, 0) == 28
def test_butterfly_sets(game):
    t = plant(game, 0, "BIRCH"); t2 = plant(game, 0, "BIRCH"); t3 = plant(game, 0, "BIRCH")
    attach(game, 0, t, "PEACOCK_BUTTERFLY"); attach(game, 0, t2, "PEACOCK_BUTTERFLY"); attach(game, 0, t3, "MAP_BUTTERFLY")
    assert score_player(game.db, game.state.players, 0) == 3 + 3 + 0       # set {Peacock, Map}=3, set {Peacock}=0

def test_common_toads(game):
    t = plant(game, 0, "BIRCH")
    attach(game, 0, t, "COMMON_TOAD"); assert score_player(game.db, game.state.players, 0) == 1
    attach(game, 0, t, "COMMON_TOAD"); assert score_player(game.db, game.state.players, 0) == 11

def test_silver_fir_wood_ant_marten(game):
    f = plant(game, 0, "SILVER_FIR")
    game.debug_place_dweller(0, f, give(game, 0, "WOOD_ANT").def_id, "WOOD_ANT")      # BOTTOM
    attach(game, 0, f, "TAWNY_OWL")                                                     # TOP
    attach(game, 0, f, "BEECH_MARTEN", "SYCAMORE")                                      # LEFT (first free side)
    assert not game.state.players[0].forest[f].is_fully_occupied()
    attach(game, 0, f, "SQUEAKER", "OAK")                                               # RIGHT (LEFT is taken)
    assert game.state.players[0].forest[f].is_fully_occupied()
    # silver fir 2×4 attached = 8, wood ant 2×1 bottom card = 2, tawny owl 5, beech marten 5×1 fully occupied = 5, squeaker 1
    assert score_player(game.db, game.state.players, 0) == 21

def test_fireflies_scored_once(game):
    t = plant(game, 0, "BIRCH"); t2 = plant(game, 0, "BIRCH")
    attach(game, 0, t, "FIREFLIES"); attach(game, 0, t2, "FIREFLIES")
    assert score_player(game.db, game.state.players, 0) == 2 + 10

def test_cave_and_vulture(game):
    game.state.players[0].cave.extend(game.state.deck[:3]); del game.state.deck[:3]
    t = plant(game, 0, "BIRCH"); attach(game, 0, t, "BEARDED_VULTURE")
    assert score_player(game.db, game.state.players, 0) == 1 + 3 + 3

def test_digitalis_and_marmot_distinct_plants(game):
    t = plant(game, 0, "BIRCH"); t2 = plant(game, 0, "BIRCH")
    attach(game, 0, t, "DIGITALIS"); attach(game, 0, t2, "MOSS"); attach(game, 0, t, "ALPINE_MARMOT")
    assert score_player(game.db, game.state.players, 0) == 2 + 3 + 0 + 6   # digitalis 2 distinct → 3; moss 0; marmot 3×2
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**

```python
# forest_shuffle/engine/scoring.py
from .filters import count_cards, forest_symbol_count, tree_species_set
from ..core.enums import SLOTS

def _table(table, count):
    keys = sorted(int(k) for k in table)
    best = [k for k in keys if k <= count]
    return table[str(best[-1])] if best else 0

def _condition(db, players, seat, host, dweller, c):
    forest = players[seat].forest; t = c["type"]
    if t == "min_count":     return count_cards(db, forest, c["filter"], True) >= c["count"]
    if t == "min_distinct":  return count_cards(db, forest, dict(c["filter"], distinct=True), False) >= c["count"]
    if t == "host_species":  return host.species == c["species"]
    if t == "host_kind":     return host.kind == c["kind"]
    if t == "host_has":      return host.kind in c.get("host_kinds", ["TREE", "SHRUB"]) and any(d is not dweller and any(x in d.types for x in c["filter"]["types"]) for d in host.dwellers())
    if t == "alone_on_host": return len(host.dwellers()) == 1
    if t == "shares_slot_with": return any(d is not dweller and d.species in c["names"] for d in host.slots[dweller.position])
    if t == "all_tree_species": return len(tree_species_set(db, forest)) >= c["count"]
    if t == "min_trees":     return count_cards(db, forest, {"kinds": ["TREE"]}, True) >= c["count"]
    raise ValueError(t)

def score_card(db, players, seat, host, dweller, species_key, rule, seen_sets):
    forest = players[seat].forest; t = rule["type"]; sp = db.species[species_key]
    if t == "flat": return rule["points"]
    if t == "per_card": return rule["points"] * count_cards(db, forest, rule["filter"], False)
    if t == "per_tree_symbol":
        syms = [ (dweller.tree_symbol if dweller else host.tree_symbol) ] if rule["symbols"] == "SELF" else rule["symbols"]
        return rule["points"] * forest_symbol_count(forest, syms)
    if t == "conditional": return rule["points"] if _condition(db, players, seat, host, dweller, rule["condition"]) else 0
    if t == "majority":
        mine = count_cards(db, forest, rule["filter"], True)
        others = [count_cards(db, p.forest, rule["filter"], True) for i, p in enumerate(players) if i != seat]
        return rule["points_if_most"] if all(mine >= o for o in others) else rule["points_otherwise"]
    if t == "set":
        canon = sp.counts_as or species_key
        if canon in seen_sets: return 0
        seen_sets.add(canon)
        return _table(rule["table"], count_cards(db, forest, {"names": [canon]}, True))
    if t == "table_by_count": return _table(rule["table"], count_cards(db, forest, rule["filter"], False))
    if t == "butterfly_set":
        if "BUTTERFLIES" in seen_sets: return 0
        seen_sets.add("BUTTERFLIES")
        names = [d.species for w in forest for d in w.dwellers() if "BUTTERFLY" in d.types]
        sets = []
        for n in names:
            for s in sets:
                if n not in s: s.add(n); break
            else: sets.append({n})
        return sum(_table(db.meta["butterfly_table"], len(s)) for s in sets)
    if t == "per_cave_card": return rule["points"] * len(players[seat].cave)
    if t == "per_attached_to_host": return rule["points"] * len(host.dwellers())
    if t == "per_fully_occupied": return rule["points"] * sum(1 for w in forest if w.kind in rule["host_kinds"] and w.is_fully_occupied())
    if t == "per_card_in_slot": return rule["points"] * sum(len(w.slots[rule["slot"]]) for w in forest if w.kind in rule["host_kinds"])
    raise ValueError(t)

def score_breakdown(db, players, seat):
    seen, trees, dwellers = set(), 0, 0
    for w in players[seat].forest:
        if w.species: trees += score_card(db, players, seat, w, None, w.species, db.species[w.species].scoring, seen)
        for d in w.dwellers(): dwellers += score_card(db, players, seat, w, d, d.species, db.species[d.species].scoring, seen)
    cave = len(players[seat].cave)
    return {"trees": trees, "dwellers": dwellers, "cave": cave, "total": trees + dwellers + cave}

def score_player(db, players, seat): return score_breakdown(db, players, seat)["total"]
```

`attach` relies on `debug_place_dweller` (Task 8) trying LEFT before RIGHT for LEFT_RIGHT species, which is why the Beech Marten lands on the left and the Squeaker on the right in `test_silver_fir_wood_ant_marten`.

- [ ] **Step 4: Run tests → pass** (tests depend on the Task 8 debug helpers; until then run with `-k "not game"` or implement Task 8 helpers early as stubs on a minimal `Game` — preferred: implement Tasks 6–8 then return to run this file)
- [ ] **Step 5: Commit** `git commit -m "feat: data-driven scoring engine"`

---

### Task 6: Setup and deck construction

**Files:**
- Create: `forest_shuffle/engine/setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: `removal_count(num_players: int, expansions: tuple[str, ...]) -> int` (10 + table), `build_deck(db, rng, num_players, expansions) -> tuple[list[CardInstance], list[CardInstance]]` (deck, removed), `deal_hands(state, num_players)`, `can_mulligan(db, hand) -> bool`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_setup.py
import random
from forest_shuffle.engine.setup import build_deck, removal_count

ALL = ("base", "woodland_edge", "alpine")

def test_removal_counts():
    assert removal_count(2, ("base",)) == 40 and removal_count(5, ("base",)) == 10
    assert removal_count(2, ("base", "alpine")) == 55
    assert removal_count(3, ALL) == 60 and removal_count(5, ALL) == 30

def test_deck_size_and_winter_position(db):
    deck, removed = build_deck(db, random.Random(3), 2, ALL)
    assert len(deck) + len(removed) == 233
    assert len(removed) == 90
    winters = [i for i, c in enumerate(deck) if c.def_id == db.winter_def_id]
    assert len(winters) == 3
    third = (len(deck) - 3) // 3                      # 140 non-winter cards → piles of 46, 46, 48
    bottom_start = 2 * third
    assert winters[0] == bottom_start                 # the third winter card sits on top of the bottom pile
    assert min(winters) >= bottom_start               # all three in the bottom pile

def test_only_selected_expansions(db):
    deck, removed = build_deck(db, random.Random(0), 4, ("base",))
    assert all(db.defs[c.def_id].expansion == "base" for c in deck + removed)
    assert len(deck) + len(removed) == 161

def test_deterministic(db):
    a, _ = build_deck(db, random.Random(7), 3, ALL); b, _ = build_deck(db, random.Random(7), 3, ALL)
    assert [c.uid for c in a] == [c.uid for c in b]
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**

```python
# forest_shuffle/engine/setup.py
from ..core.cards import CardInstance
from ..core.enums import HAND_LIMIT

def removal_count(num_players, expansions):
    n_exp = len([e for e in expansions if e != "base"])
    table = {0: {2: 30, 3: 20, 4: 10, 5: 0}, 1: {2: 45, 3: 30, 4: 15, 5: 0}, 2: {2: 80, 3: 50, 4: 35, 5: 20}}[n_exp]
    return 10 + table[num_players]

def build_deck(db, rng, num_players, expansions):
    uid = 0; cards = []; winters = []
    for d in db.defs:
        if d.expansion not in expansions: continue
        for _ in range(d.count):
            inst = CardInstance(uid, d.def_id); uid += 1
            (winters if d.layout == "WINTER" else cards).append(inst)
    rng.shuffle(cards)
    k = removal_count(num_players, expansions)
    removed, cards = cards[:k], cards[k:]
    third = len(cards) // 3
    top, middle, bottom = cards[:third], cards[third:2 * third], cards[2 * third:]
    bottom = bottom + winters[:2]; rng.shuffle(bottom)
    bottom = [winters[2]] + bottom
    return top + middle + bottom, removed

def can_mulligan(db, hand):
    return not any(db.defs[c.def_id].layout == "WOODY_PLANT" and db.species[db.defs[c.def_id].species].kind == "TREE" for c in hand)
```

`deal_hands(state, num_players)`: pop 6 cards from the top of `state.deck` into each hand (winter cards cannot be there because they are in the bottom third).

- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: deck setup with expansion-aware removal"`

---

### Task 7: Action codec

**Files:**
- Create: `forest_shuffle/core/actions.py`
- Test: `tests/test_actions.py`

**Interfaces:**
- Produces: `ActionKind`, `Action`, `ActionCodec(num_play_defs: int, max_woody: int = MAX_WOODY)` with `size`, `encode(Action) -> int`, `decode(int) -> Action`, `mask(actions: Iterable[Action]) -> np.ndarray`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_actions.py
import numpy as np
from forest_shuffle.core.actions import Action, ActionKind, ActionCodec

def test_roundtrip_all_ids():
    c = ActionCodec(160, 24)
    assert c.size == 1 + 6 * 160 + 2 * 160 * 24 + 24 + 3
    for i in range(c.size):
        assert c.encode(c.decode(i)) == i

def test_specific_ids():
    c = ActionCodec(160, 24)
    assert c.encode(Action(ActionKind.DRAW_DECK)) == 0
    assert c.encode(Action(ActionKind.DRAW_CLEARING, card=0)) == 1
    assert c.decode(c.size - 1) == Action(ActionKind.DONE)
    m = c.mask([Action(ActionKind.USE), Action(ActionKind.SKIP)])
    assert m.dtype == bool and m.sum() == 2
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement** the layout from Section 2.5 (`_bases` dict computed in `__init__`; `decode` walks the ranges; `PLAY_HALF` index `= base + (card*2 + half)*W + target`).
- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: fixed action codec"`

---

### Task 8: Game engine — turn flow, drawing, winter, clearing

**Files:**
- Create: `forest_shuffle/engine/game.py`
- Test: `tests/test_turn_draw.py`

**Interfaces:**
- Produces: `class IllegalActionError(Exception)`; `Game(db, num_players, seed, expansions=ALL)` with `state: GameState`, `rng`, `codec: ActionCodec`, `reset()`, `legal_actions() -> list[Action]`, `legal_ids() -> list[int]`, `step(action: Action) -> dict` (info: `turn_ended`, `winter_revealed`, `game_over`), `step_id(i)`, `scores() -> list[int]`, `current_seat`, `pending_label() -> str`, `clone() -> Game` (deepcopy of state, rng state copied). Test helpers: `spawn_into_hand(seat, def_id) -> CardInstance` (new uid ≥ 10_000), `debug_place_woody(seat, def_id) -> int`, `debug_place_dweller(seat, forest_idx, def_id, species_key) -> PlacedDweller`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_turn_draw.py
import pytest
from forest_shuffle.core.actions import Action, ActionKind as K
from forest_shuffle.engine.game import IllegalActionError

def test_initial_state(game):
    s = game.state
    assert all(len(p.hand) == 6 for p in s.players) and s.clearing == [] and s.current == 0

def test_draw_action_draws_exactly_two(game):
    hand0 = len(game.state.players[0].hand)
    game.step(Action(K.DRAW_DECK))
    assert game.state.current == 0 and game.state.decisions[-1].kind == "DRAW"
    assert all(a.kind in (K.DRAW_DECK, K.DRAW_CLEARING) for a in game.legal_actions())
    game.step(Action(K.DRAW_DECK))
    assert len(game.state.players[0].hand) == hand0 + 2 and game.state.current == 1

def test_hand_nine_draws_one(game):
    p = game.state.players[0]
    while len(p.hand) < 9: p.hand.append(game.state.deck.pop())
    game.step(Action(K.DRAW_DECK))
    assert len(p.hand) == 10 and game.state.current == 1

def test_cannot_draw_with_full_hand(game):
    p = game.state.players[0]
    while len(p.hand) < 10: p.hand.append(game.state.deck.pop())
    assert not any(a.kind == K.DRAW_DECK for a in game.legal_actions())
    with pytest.raises(IllegalActionError): game.step(Action(K.DRAW_DECK))

def test_draw_from_clearing_by_def(game):
    c = game.state.deck.pop(); game.state.clearing.append(c)
    game.step(Action(K.DRAW_CLEARING, card=c.def_id))
    assert c in game.state.players[0].hand and game.state.clearing == []

def test_winter_replacement_and_game_end(game):
    w = game.db.winter_def_id
    winters = [c for c in game.state.deck if c.def_id == w]
    others = [c for c in game.state.deck if c.def_id != w]
    game.state.deck = [winters[0], winters[1], others[0], winters[2]] + others[1:]
    info = game.step(Action(K.DRAW_DECK))            # reveals 2 winters, draws others[0]
    assert game.state.winter_revealed == 2 and others[0] in game.state.players[0].hand and info["winter_revealed"] == 2
    info = game.step(Action(K.DRAW_DECK))            # third winter → immediate end
    assert game.state.game_over and info["game_over"] and game.legal_actions() == []

def test_clearing_emptied_at_turn_end(game):
    game.state.clearing = [game.state.deck.pop() for _ in range(10)]
    game.step(Action(K.DRAW_DECK)); game.step(Action(K.DRAW_DECK))
    assert game.state.clearing == [] and len(game.state.removed) >= 10
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement the skeleton** (play actions come in Task 9; here `legal_actions` in CHOOSE_ACTION returns only draw actions plus a `_play_actions()` hook that returns `[]`).

```python
# forest_shuffle/engine/game.py (core parts)
class IllegalActionError(Exception): pass

class Game:
    def __init__(self, db, num_players=2, seed=None, expansions=("base", "woodland_edge", "alpine")):
        self.db, self.num_players, self.expansions = db, num_players, tuple(expansions)
        self.rng = random.Random(seed)
        self.codec = ActionCodec(db.num_play_defs, MAX_WOODY)
        self.state = None; self._next_uid = 10_000

    def reset(self):
        deck, removed = build_deck(self.db, self.rng, self.num_players, self.expansions)
        self.state = GameState(players=[PlayerState(i) for i in range(self.num_players)], deck=deck, clearing=[], removed=removed)
        deal_hands(self.state, self.num_players)
        for p in self.state.players:               # forced mulligan (documented simplification)
            if can_mulligan(self.db, p.hand):
                self.state.removed.extend(p.hand); p.hand.clear(); p.mulligan_used = True
                for _ in range(6): p.hand.append(self.state.deck.pop(0))
        return self.state

    # ---- legality
    def legal_actions(self):
        s = self.state
        if s.game_over: return []
        if not s.decisions:
            return self._draw_actions(first=True) + self._play_actions()
        return self._decision_options(s.decisions[-1])

    def _draw_actions(self, first):
        p = self.state.players[self.state.current]
        if len(p.hand) >= HAND_LIMIT: return []
        out = [Action(ActionKind.DRAW_DECK)] if self.state.deck else []
        out += [Action(ActionKind.DRAW_CLEARING, card=d) for d in sorted({c.def_id for c in self.state.clearing})]
        return out

    # ---- stepping
    def step(self, action):
        if action not in self.legal_actions(): raise IllegalActionError(action)
        s = self.state; info = {"turn_ended": False, "winter_revealed": 0, "game_over": False}
        before = s.winter_revealed
        if not s.decisions:
            if action.kind in (ActionKind.DRAW_DECK, ActionKind.DRAW_CLEARING):
                p = s.players[s.current]
                s.decisions.append(Decision("DRAW", {"remaining": min(2, HAND_LIMIT - len(p.hand))}))
                self._handle_draw(action, info)
            else:
                self._start_play(action)
        else:
            self._handle_decision(s.decisions[-1], action, info)
        info["winter_revealed"] = s.winter_revealed - before
        if s.game_over: info["game_over"] = True; return info
        if not s.decisions:
            self._end_turn(); info["turn_ended"] = True
        return info

    def _handle_draw(self, action, info):
        s = self.state; d = s.decisions[-1]; p = s.players[s.current]
        if action.kind == ActionKind.DRAW_DECK:
            card = self._draw_from_deck()
            if card: p.hand.append(card)
        else:
            card = self._take_from_clearing(action.card); p.hand.append(card)
        d.data["remaining"] -= 1
        if s.game_over: return
        if d.data["remaining"] == 0 or len(p.hand) >= HAND_LIMIT or not (s.deck or s.clearing):
            s.decisions.pop()

    def _draw_from_deck(self):
        s = self.state
        while s.deck:
            c = s.deck.pop(0)
            if c.def_id != self.db.winter_def_id: return c
            s.winter_revealed += 1; s.removed.append(c); s.log.append("Winter card revealed")
            if s.winter_revealed >= 3:
                s.game_over = True; s.decisions.clear(); return None
        return None

    def _take_from_clearing(self, def_id):
        for i, c in enumerate(self.state.clearing):
            if c.def_id == def_id: return self.state.clearing.pop(i)
        raise IllegalActionError(def_id)

    def _end_turn(self):
        s = self.state
        if len(s.clearing) >= CLEARING_LIMIT:
            s.removed.extend(s.clearing); s.clearing.clear()
        s.turn_index += 1
        if s.extra_turns > 0: s.extra_turns -= 1
        else: s.current = (s.current + 1) % self.num_players
```

`_decision_options` for `DRAW` returns `_draw_actions(first=False)`; `_handle_decision` dispatches on `kind`. `_play_actions`, `_start_play` return `[]` / raise until Task 9. Add `scores()`, `clone()` (`copy.deepcopy(self)`), `legal_ids`, `step_id`, `current_seat`, and the three debug helpers (`spawn_into_hand` appends `CardInstance(self._next_uid, def_id)`; `debug_place_woody` uses `make_woody`/`_place_woody`; `debug_place_dweller` picks the half with that species, tries its position, for LEFT_RIGHT tries LEFT then RIGHT with `can_place`, and appends via `make_dweller`; all move the card out of the hand).

- [ ] **Step 4: Run tests → pass** (`tests/test_turn_draw.py`, then `tests/test_scoring.py` which now has its helpers)
- [ ] **Step 5: Commit** `git commit -m "feat: game engine turn flow, drawing, winter, clearing"`

---

### Task 9: Game engine — playing cards, payment, bonus eligibility

**Files:**
- Modify: `forest_shuffle/engine/game.py`
- Test: `tests/test_turn_play.py`

**Interfaces:**
- Produces: `_play_actions()`, `_start_play(action)`, `_place_pending(play, paid)`, `_reveal_to_clearing()`, `_after_placement(seat, woody_idx, dweller_or_None, species_key, bonus_ok, free)` (pushes effect/bonus/trigger decisions; effect handlers arrive in Task 10, so for now it pushes nothing when `species.effect is None and species.bonus is None`).

- [ ] **Step 1: Failing tests**

```python
# tests/test_turn_play.py
from tests.conftest import give
from forest_shuffle.core.actions import Action, ActionKind as K

def hand_only(game, seat, *keys_syms):
    p = game.state.players[seat]; game.state.removed.extend(p.hand); p.hand.clear()
    return [give(game, seat, k, s) for k, s in keys_syms]

def test_play_free_tree_reveals_clearing(game):
    birch, = hand_only(game, 0, ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=birch.def_id))
    f = game.state.players[0].forest
    assert len(f) == 1 and f[0].species == "BIRCH" and len(game.state.clearing) == 1

def test_pay_cost_then_place_and_bonus(game):
    oak, pay1, pay2, other = hand_only(game, 0, ("OAK", None), ("EUROPEAN_HARE", "OAK"), ("SQUEAKER", "OAK"), ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=oak.def_id))
    assert game.state.decisions[-1].kind == "PAY"
    ids = {a.card for a in game.legal_actions()}
    assert oak.def_id not in ids and pay1.def_id in ids
    game.step(Action(K.PAY, card=pay1.def_id)); game.step(Action(K.PAY, card=pay2.def_id))
    assert game.state.players[0].forest[0].species == "OAK"
    assert pay1 in game.state.clearing and pay2 in game.state.clearing
    top = game.state.decisions[-1]
    assert top.kind == "USE_OR_SKIP" and top.data["label"].startswith("bonus")   # extra turn offered, paid with 2 Oak-symbol cards

def test_bonus_not_offered_when_symbol_differs(game):
    oak, pay1, pay2 = hand_only(game, 0, ("OAK", None), ("EUROPEAN_HARE", "OAK"), ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=oak.def_id))
    game.step(Action(K.PAY, card=pay1.def_id)); game.step(Action(K.PAY, card=pay2.def_id))
    assert game.state.decisions == [] and game.state.current == 1

def test_sapling_costs_nothing_and_reveals(game):
    card, = hand_only(game, 0, ("WOLF", None))
    game.step(Action(K.PLAY_SAPLING, card=card.def_id))
    f = game.state.players[0].forest
    assert f[0].species is None and f[0].kind == "TREE" and card in game.state.removed and len(game.state.clearing) == 1

def test_split_card_needs_matching_empty_slot(game):
    from tests.conftest import plant
    hand_only(game, 0)
    t = plant(game, 0, "BIRCH")
    owl = give(game, 0, "TAWNY_OWL"); hare = give(game, 0, "EUROPEAN_HARE"); give(game, 0, "BIRCH"); give(game, 0, "BIRCH")
    acts = [a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == owl.def_id]
    assert all(a.target == t for a in acts) and len(acts) >= 1
    game.step(acts[0])
    for a in list(game.legal_actions()):            # pay 2 for the owl with anything
        if a.kind == K.PAY: game.step(a)
        if game.state.decisions and game.state.decisions[-1].kind != "PAY": break
    assert game.state.players[0].forest[t].slots["TOP"][0].species == "TAWNY_OWL"

def test_cannot_afford(game):
    wolf, = hand_only(game, 0, ("WOLF", None))
    assert not any(a.kind == K.PLAY_HALF for a in game.legal_actions())
    assert any(a.kind == K.PLAY_SAPLING for a in game.legal_actions())
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**

```python
    def _play_actions(self):
        s = self.state; p = s.players[s.current]; out = []
        room = len(p.forest) < MAX_WOODY
        for def_id in sorted({c.def_id for c in p.hand}):
            d = self.db.defs[def_id]; others = len(p.hand) - 1
            if room: out.append(Action(ActionKind.PLAY_SAPLING, card=def_id))
            if d.layout == "WOODY_PLANT":
                if room and self.db.species[d.species].cost <= others: out.append(Action(ActionKind.PLAY_WOODY, card=def_id))
            else:
                for hi, h in enumerate(d.halves):
                    if self.db.species[h.species].cost > others: continue
                    for t in legal_targets(self.db, p.forest, h.species, h.position):
                        out.append(Action(ActionKind.PLAY_HALF, card=def_id, half=hi, target=t))
        return out

    def _start_play(self, action, free=False):
        s = self.state; p = s.players[s.current]
        card = next(c for c in p.hand if c.def_id == action.card); d = self.db.defs[card.def_id]
        play = {"uid": card.uid, "kind": action.kind.value, "half": action.half, "target": action.target}
        cost = 0 if action.kind == ActionKind.PLAY_SAPLING or free else self.db.species[d.species if action.kind == ActionKind.PLAY_WOODY else d.halves[action.half].species].cost
        if cost > 0: s.decisions.append(Decision("PAY", {"play": play, "cost": cost, "paid": []}))
        else: self._place_pending(play, [], free)

    def _place_pending(self, play, paid, free=False):
        s = self.state; seat = s.current; p = s.players[seat]
        card = next(c for c in p.hand if c.uid == play["uid"]); p.hand.remove(card); d = self.db.defs[card.def_id]
        if play["kind"] == "PLAY_SAPLING":
            p.forest.append(make_sapling(s.turn_index)); s.removed.append(card); self._reveal_to_clearing(); return
        if play["kind"] == "PLAY_WOODY":
            w = make_woody(self.db, card.uid, d, s.turn_index); p.forest.append(w); idx = len(p.forest) - 1
            if w.kind == "TREE": self._reveal_to_clearing()
            symbol, key, dweller = d.tree_symbol, d.species, None
        else:
            h = d.halves[play["half"]]; dweller = make_dweller(self.db, card.uid, h)
            p.forest[play["target"]].slots[h.position].append(dweller); idx = play["target"]; symbol, key = h.tree_symbol, h.species
        if s.game_over: return
        paid_defs = [self.db.defs[c.def_id] for c in s.clearing if c.uid in paid]
        bonus_ok = bool(paid) and all(shows_symbol(self.db, pd, symbol) for pd in paid_defs)
        self._after_placement(seat, idx, dweller, key, bonus_ok, free)

    def _reveal_to_clearing(self):
        c = self._draw_from_deck()
        if c: self.state.clearing.append(c)
```

`PAY` handling: `_decision_options` returns `PAY(def)` for distinct defs in hand excluding the played uid; `_handle_decision` moves the chosen card (first instance with that def, not the played uid) to the clearing, appends its uid to `paid`, and when `len(paid) == cost` pops the decision and calls `_place_pending(play, paid)`. `_after_placement` in this task: if `bonus_ok and species.bonus`, push `Decision("USE_OR_SKIP", {"effect": bonus, "label": f"bonus: {name}", "source": {...}})`; if `species.effect and effect["type"] != "permanent"`, push the effect decision **after** the bonus so it sits on top and resolves first. `USE_OR_SKIP` options: `[USE, SKIP]`; handling pops the decision and, for `USE`, calls `apply_effect` (Task 10; stub here for `extra_turn` so the Oak test passes: `s.extra_turns += 1`).

- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: play cards with payment and bonus eligibility"`

---

### Task 10: Effects, bonuses and permanent triggers

**Files:**
- Create: `forest_shuffle/engine/effects.py`
- Modify: `forest_shuffle/engine/game.py` (delegate `USE`, decision options for the remaining kinds, trigger pushing in `_after_placement`)
- Test: `tests/test_effects.py`

**Interfaces:**
- Produces: `apply_effect(game, seat, effect: dict, source: dict)`; `decision_options(game, decision) -> list[Action]`; `handle_choice(game, decision, action)`; `matching_triggers(game, seat, placed_species_key, placed_types, position: Optional[str], host: PlacedWoody, is_tree_play: bool) -> list[tuple[dict, str]]` (action, label).

- [ ] **Step 1: Failing tests** (one per effect type; use `hand_only`/`give`/`plant` from the previous tests)

```python
# tests/test_effects.py
from tests.conftest import give, plant, attach
from tests.test_turn_play import hand_only
from forest_shuffle.core.actions import Action, ActionKind as K

def use(game):   game.step(Action(K.USE))
def skip(game):  game.step(Action(K.SKIP))

def test_birch_effect_draws_one_and_is_optional(game):
    birch, = hand_only(game, 0, ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=birch.def_id))
    assert game.state.decisions[-1].kind == "USE_OR_SKIP"
    use(game)
    assert len(game.state.players[0].hand) == 1 and game.state.current == 1

def test_draw_respects_hand_limit(game):
    p = game.state.players[0]; hand_only(game, 0, ("BIRCH", None))
    while len(p.hand) < 10: p.hand.append(game.state.deck.pop())
    birch = next(c for c in p.hand if game.db.defs[c.def_id].species == "BIRCH")
    game.step(Action(K.PLAY_WOODY, card=birch.def_id)); use(game)
    assert len(p.hand) == 10

def test_wolf_draw_per_deer_and_extra_turn_bonus(game):
    t = plant(game, 0, "SILVER_FIR"); attach(game, 0, t, "ROE_DEER"); attach(game, 0, t, "FALLOW_DEER", "LINDEN")
    hand_only(game, 0, ("WOLF", "SILVER_FIR"), ("EUROPEAN_HARE", "SILVER_FIR"), ("RACCOON", "SILVER_FIR"), ("LYNX", "SILVER_FIR"))
    t2 = plant(game, 0, "BIRCH")
    wolf = next(c for c in game.state.players[0].hand if any(h.species == "WOLF" for h in game.db.defs[c.def_id].halves))
    act = next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == wolf.def_id)
    game.step(act)
    for a in [a for a in game.legal_actions() if a.kind == K.PAY][:3]: game.step(a)
    use(game)                                        # effect: draw per deer (2)
    assert len(game.state.players[0].hand) == 2
    use(game)                                        # bonus: extra turn
    assert game.state.current == 0 and game.state.extra_turns == 0 and game.state.turn_index == 1

def test_place_free_skips_effect_and_bonus(game):
    t = plant(game, 0, "BIRCH")
    hand_only(game, 0, ("EUROPEAN_BADGER", "HORSE_CHESTNUT"), ("TAWNY_OWL", "HORSE_CHESTNUT"), ("WOLF", "HORSE_CHESTNUT"))
    badger = give(game, 0, "EUROPEAN_BADGER", "HORSE_CHESTNUT")
    act = next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == badger.def_id)
    game.step(act); game.step(next(a for a in game.legal_actions() if a.kind == K.PAY and a.card != badger.def_id))
    use(game)                                        # bonus: place a pawed animal free
    assert game.state.decisions[-1].kind == "PLACE_FREE"
    opts = game.legal_actions(); assert any(a.kind == K.DONE for a in opts)
    wolf_act = next(a for a in opts if a.kind == K.PLAY_HALF)
    game.step(wolf_act)
    assert len(game.state.players[0].forest[t].dwellers()) == 2 and game.state.decisions == []

def test_raccoon_hand_to_cave(game):
    t = plant(game, 0, "BIRCH")
    hand_only(game, 0, ("RACCOON", "BIRCH"), ("SQUEAKER", "OAK"), ("SQUEAKER", "OAK"), ("BIRCH", None))
    rac = give(game, 0, "RACCOON", "BIRCH")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == rac.def_id))
    game.step(next(a for a in game.legal_actions() if a.kind == K.PAY))
    use(game)
    assert game.state.decisions[-1].kind == "CHOOSE_HAND_CARD"
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD)); game.step(Action(K.DONE))
    p = game.state.players[0]
    assert len(p.cave) == 1 and len(p.hand) == 3          # 3 left after playing+paying, minus 1 to cave, plus 1 drawn

def test_magpie_effect_and_bonus_from_clearing(game):
    t = plant(game, 0, "BIRCH")
    game.state.clearing = [game.state.deck.pop() for _ in range(3)]
    hand_only(game, 0, ("EURASIAN_MAGPIE", "BEECH"), ("BEECH", None))
    mag = give(game, 0, "EURASIAN_MAGPIE", "BEECH")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == mag.def_id))
    game.step(next(a for a in game.legal_actions() if a.kind == K.PAY))
    use(game); game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))   # effect: 1 to hand
    use(game)                                                                                  # bonus: 2 to cave
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD)); game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))
    assert len(game.state.players[0].cave) == 2 and len(game.state.clearing) == 1

def test_female_boar_removes_clearing_and_bee_swarm_caves_plants(game):
    plant(game, 0, "BIRCH")
    game.state.clearing = [game.state.deck.pop() for _ in range(4)]
    hand_only(game, 0, ("FEMALE_WILD_BOAR", "BIRCH"), ("BIRCH", None), ("BIRCH", None))
    boar = give(game, 0, "FEMALE_WILD_BOAR", "BIRCH")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == boar.def_id))
    for a in [a for a in game.legal_actions() if a.kind == K.PAY][:2]: game.step(a)
    use(game)
    assert game.state.clearing == []

def test_mole_plays_more_cards(game):
    plant(game, 0, "BIRCH")
    hand_only(game, 0, ("MOLE", "OAK"), ("BIRCH", None), ("BIRCH", None), ("BIRCH", None))
    mole = give(game, 0, "MOLE", "OAK")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == mole.def_id))
    for a in [a for a in game.legal_actions() if a.kind == K.PAY][:2]: game.step(a)
    use(game)
    assert game.state.decisions[-1].kind == "PLAY_MORE"
    birch = next(a for a in game.legal_actions() if a.kind == K.PLAY_WOODY)
    game.step(birch); skip(game)                                  # birch effect skipped
    assert game.state.decisions[-1].kind == "PLAY_MORE"
    game.step(Action(K.DONE)); assert game.state.current == 1

def test_water_vole_saplings(game):
    plant(game, 0, "BIRCH")
    hand_only(game, 0, ("WATER_VOLE", "SYCAMORE"), ("BIRCH", None), ("BIRCH", None), ("BIRCH", None))
    vole = give(game, 0, "WATER_VOLE", "SYCAMORE")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == vole.def_id))
    for a in [a for a in game.legal_actions() if a.kind == K.PAY][:2]: game.step(a)
    use(game)
    n_clear = len(game.state.clearing)
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_SAPLING)); game.step(Action(K.DONE))
    assert len(game.state.players[0].forest) == 2 and len(game.state.clearing) == n_clear + 1

def test_mushroom_triggers_from_next_turn(game):
    t = plant(game, 0, "BIRCH"); attach(game, 0, t, "PARASOL_MUSHROOM")          # placed_turn 0
    game.state.players[0].forest[t].slots["BOTTOM"][0]; game.state.players[0].forest[t].placed_turn = 0
    t2 = plant(game, 0, "BIRCH")
    hand_only(game, 0, ("COMMON_TOAD", "OAK"))
    toad = give(game, 0, "COMMON_TOAD", "OAK")
    act = next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == toad.def_id and a.target == t2)
    game.step(act)                                                              # same turn as mushroom → no trigger
    assert game.state.decisions == []
    game.state.turn_index = 3; game.state.current = 0
    hand_only(game, 0, ("COMMON_TOAD", "OAK")); toad = give(game, 0, "COMMON_TOAD", "OAK")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == toad.def_id))
    assert game.state.decisions[-1].kind == "USE_OR_SKIP" and "Parasol" in game.state.decisions[-1].data["label"]
    use(game); assert len(game.state.players[0].hand) == 1

def test_barn_owl_conditional_extra_turn(game):
    t = plant(game, 0, "BIRCH")
    hand_only(game, 0, ("BARN_OWL", "BIRCH"), ("BIRCH", None), ("BIRCH", None))
    owl = give(game, 0, "BARN_OWL", "BIRCH")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == owl.def_id))
    for a in [a for a in game.legal_actions() if a.kind == K.PAY][:2]: game.step(a)
    use(game)                                                                   # no bat → nothing happens
    assert game.state.extra_turns == 0 and game.state.current == 1
```

For the mushroom test the `attach` helper must set the mushroom dweller's host `placed_turn`; simpler: `matching_triggers` compares the **dweller's** placement turn, so add `placed_turn: int` to `PlacedDweller` (set in `make_dweller(db, uid, half, turn=0)`) and to the state. Update Task 3's dataclass accordingly (`placed_turn: int = 0`).

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement `effects.py`** following Section 2.6 exactly:

```python
def apply_effect(game, seat, effect, source):
    s = game.state; p = s.players[seat]; t = effect["type"]
    if t == "draw":
        for _ in range(effect["count"]):
            if len(p.hand) >= HAND_LIMIT: break
            c = game._draw_from_deck()
            if c is None: break
            p.hand.append(c)
    elif t == "draw_per":
        n = count_cards(game.db, p.forest, effect["filter"], False)
        apply_effect(game, seat, {"type": "draw", "count": n}, source)
    elif t == "place_free":
        s.decisions.append(Decision("PLACE_FREE", {"filter": effect["filter"], "remaining": effect["count"]}))
    elif t == "extra_turn":
        c = effect.get("condition")
        if c is None or count_cards(game.db, p.forest, c["filter"], True) >= c["count"]: s.extra_turns += 1
    elif t == "take_from_clearing":
        flt = effect.get("filter", {})
        if effect["count"] == "all":
            for c in [c for c in s.clearing if game.hand_card_matches(c, flt)]:
                if len(p.hand) >= HAND_LIMIT: break
                s.clearing.remove(c); p.hand.append(c)
        elif s.clearing and len(p.hand) < HAND_LIMIT:
            s.decisions.append(Decision("CHOOSE_CLEARING_CARD", {"remaining": 1, "filter": flt, "dest": "HAND", "optional": False}))
    elif t == "clearing_to_cave":
        flt = effect.get("filter", {})
        if effect["count"] == "all":
            for c in [c for c in s.clearing if game.hand_card_matches(c, flt)]: s.clearing.remove(c); p.cave.append(c)
        else:
            n = min(effect["count"], len(s.clearing))
            if n: s.decisions.append(Decision("CHOOSE_CLEARING_CARD", {"remaining": n, "filter": flt, "dest": "CAVE", "optional": False}))
    elif t == "hand_to_cave_draw_equal":
        s.decisions.append(Decision("CHOOSE_HAND_CARD", {"dest": "CAVE", "chosen": 0}))
    elif t == "remove_clearing":
        s.removed.extend(s.clearing); s.clearing.clear()
    elif t == "play_cards":   s.decisions.append(Decision("PLAY_MORE", {}))
    elif t == "play_saplings": s.decisions.append(Decision("SAPLING_MORE", {}))
    elif t == "sequence":
        for step in reversed(effect["steps"]):
            s.decisions.append(Decision("USE_OR_SKIP", {"effect": step, "label": source.get("label", "") + " step", "source": source, "auto": True}))
    else: raise ValueError(t)
```

`game.hand_card_matches(card, flt)`: a card matches if its woody species or any half matches `card_matches(...)` with `kind` derived from the layout (`TREE`/`SHRUB` for woody, `DWELLER` for halves).

`decision_options` / `handle_choice`:
- `PLACE_FREE`: options = `PLAY_HALF` for hand halves whose species matches `filter` (types via `db.half_types`, names via `counts_as`) with legal targets, plus `DONE`. On `PLAY_HALF`: `_start_play(action, free=True)` then `remaining -= 1` (if int) and pop at 0. `DONE` pops.
- `CHOOSE_CLEARING_CARD`: options = `CHOOSE_CARD(def)` for matching clearing defs (`DONE` only if `optional`). On choice move to hand or cave, `remaining -= 1`, pop at 0 or when no matching card remains.
- `CHOOSE_HAND_CARD`: options = `CHOOSE_CARD(def)` for hand defs + `DONE`; on choice move to cave, `chosen += 1`; on `DONE` pop then draw `chosen` cards with the hand limit.
- `PLAY_MORE`: options = `game._play_actions()` + `DONE`; a play action runs `_start_play` (normal pipeline, decisions stack on top); `DONE` pops.
- `SAPLING_MORE`: options = `PLAY_SAPLING(def)` for hand defs (if forest has room) + `DONE`.
- `USE_OR_SKIP` with `auto: True` (sequence steps) still offers both `USE` and `SKIP` (each step is optional).

`matching_triggers` (in `effects.py`): for each woody `w` in `p.forest` with `placed_turn < turn_index` whose species effect is `permanent`, and each dweller `d` with `placed_turn < turn_index` whose species effect is `permanent`, test the trigger filter against the placed card: `types` → any in placed types; `kinds` → `is_tree_play`; `slot` → `position == slot and host.kind in host_kinds`. Return `(action, f"{Species.name} trigger")`. `_after_placement` pushes one `USE_OR_SKIP` per trigger **before** (below) the effect and bonus decisions so they resolve last. For shrub bonuses, the pushed effect is `species.effect["action"]`.

- [ ] **Step 4: Run tests → pass** (`tests/test_effects.py` and the whole suite)
- [ ] **Step 5: Commit** `git commit -m "feat: effects, bonuses and permanent triggers"`

---

### Task 11: Random playout invariants

**Files:**
- Test: `tests/test_playout.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_playout.py
import random, pytest
from forest_shuffle.engine.game import Game

def all_uids(state):
    uids = [c.uid for c in state.deck + state.clearing + state.removed]
    for p in state.players:
        uids += [c.uid for c in p.hand + p.cave]
        for w in p.forest:
            if w.uid is not None: uids.append(w.uid)
            uids += [d.uid for d in w.dwellers()]
    return sorted(uids)

@pytest.mark.parametrize("seed", range(40))
@pytest.mark.parametrize("players", [2, 3, 5])
def test_random_game_terminates_and_conserves_cards(db, seed, players):
    g = Game(db, players, seed=seed); g.reset()
    expected = all_uids(g.state); rng = random.Random(seed); steps = 0
    while not g.state.game_over:
        acts = g.legal_actions()
        assert acts, f"no legal actions at step {steps}: {g.state.decisions}"
        g.step(rng.choice(acts)); steps += 1
        assert all(len(p.hand) <= 10 for p in g.state.players)
        assert steps < 5000
    assert all_uids(g.state) == expected
    assert g.state.winter_revealed == 3
    assert len(g.scores()) == players
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/test_playout.py -q -x`. Fix every engine bug it surfaces (typical: a decision with zero options — every decision kind must offer `DONE` or auto-pop when it has no options; add `assert options` guard in `legal_actions` that pops empty decisions except `PAY`).
- [ ] **Step 3: Commit** `git commit -m "test: random playout invariants"`

---

### Task 12: Observation encoder

**Files:**
- Create: `forest_shuffle/rl/encoder.py`
- Test: `tests/test_encoder.py`

**Interfaces:**
- Produces: `StateEncoder(db, num_players)` with `size: int`, `encode(game: Game, seat: int) -> np.ndarray[float32]`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_encoder.py
import numpy as np
from forest_shuffle.rl.encoder import StateEncoder

def test_size_matches_formula(db, game):
    enc = StateEncoder(db, 2)
    F = 95 + 11 + 4 * 93
    assert enc.size == 13 + 93 + 160 + 160 + 2 * (2 + 24 * F)
    v = enc.encode(game, 0); assert v.shape == (enc.size,) and v.dtype == np.float32 and 0 <= v.min() and v.max() <= 1

def test_hand_is_order_invariant(db, game):
    enc = StateEncoder(db, 2); p = game.state.players[0]
    a = enc.encode(game, 0); p.hand.reverse(); b = enc.encode(game, 0)
    assert np.array_equal(a, b)

def test_opponent_hand_hidden(db, game):
    enc = StateEncoder(db, 2)
    v = enc.encode(game, 1)
    hand_block = v[13 + 93: 13 + 93 + 160]
    assert hand_block.sum() * 4 == len(game.state.players[1].hand)
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement** per Section 2.8. Phase one-hot index: 0 = CHOOSE_ACTION, 1..8 = `ALL_DECISION_KINDS`. Decision context species = `decisions[-1].data["source"]["species"]` when present. Forest block ordering: seat, then `(seat+1) % P`, ….
- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: fixed-size state encoder"`

---

### Task 13: Multi-agent environment

**Files:**
- Create: `forest_shuffle/rl/env.py`
- Test: `tests/test_env.py`

**Interfaces:**
- Produces: `ForestShuffleEnv(num_players=2, seed=None, expansions=ALL, max_steps=2000)` with `reset(seed=None) -> (obs, info)`, `step(action_id) -> (obs, rewards, terminated, truncated, info)`, `action_mask() -> np.ndarray[bool]`, `current_player: int`, `game: Game`, `codec`, `encoder`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_env.py
import numpy as np, pytest
from forest_shuffle.rl.env import ForestShuffleEnv
from forest_shuffle.engine.game import IllegalActionError

def test_reset_and_mask():
    env = ForestShuffleEnv(2, seed=0); obs, info = env.reset()
    assert obs.shape == (env.encoder.size,) and info["action_mask"].sum() == len(env.game.legal_actions()) and info["current_player"] == 0

def test_rewards_assigned_to_winner():
    env = ForestShuffleEnv(2, seed=0); env.reset(); rng = np.random.default_rng(0)
    terminated = False
    while not terminated:
        mask = env.action_mask(); a = rng.choice(np.flatnonzero(mask))
        obs, rewards, terminated, truncated, info = env.step(int(a))
        if not terminated: assert np.all(rewards == 0)
    scores = info["scores"]; best = max(scores)
    assert all((r == 1.0) == (s == best) for r, s in zip(rewards, scores))

def test_illegal_action_raises():
    env = ForestShuffleEnv(2, seed=0); env.reset()
    bad = int(np.flatnonzero(~env.action_mask())[0])
    with pytest.raises(IllegalActionError): env.step(bad)
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**: `step` records `acting = game.current_seat`, calls `game.step_id`, computes rewards (zeros, or `+1/-1` per seat at the end with ties sharing `+1`), `truncated = steps >= max_steps`, `info = {"acting_player", "current_player", "action_mask", "turn_ended", "scores" (at end)}`, obs encoded for the **new** current player.
- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: multi-agent environment with per-seat rewards"`

---

### Task 14: Agents

**Files:**
- Create: `forest_shuffle/rl/agents.py`
- Test: `tests/test_agents.py`

**Interfaces:**
- Produces: `class Agent: name: str; def act(self, game: Game, seat: int) -> Action`; `RandomAgent(seed)`, `GreedyAgent(seed)`, `PolicyAgent(model_path, encoder, codec, deterministic=True)` (imports sb3-contrib lazily); `play_game(game, agents: list[Agent]) -> list[int]` (scores).

- [ ] **Step 1: Failing tests**

```python
# tests/test_agents.py
from forest_shuffle.engine.game import Game
from forest_shuffle.rl.agents import RandomAgent, GreedyAgent, play_game

def test_play_game_returns_scores(db):
    g = Game(db, 2, seed=1); g.reset()
    scores = play_game(g, [RandomAgent(1), RandomAgent(2)])
    assert len(scores) == 2 and g.state.game_over

def test_greedy_beats_random(db):
    wins = 0
    for seed in range(20):
        g = Game(db, 2, seed=seed); g.reset()
        s = play_game(g, [GreedyAgent(seed), RandomAgent(seed)])
        wins += s[0] > s[1]
    assert wins >= 14
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**: `GreedyAgent.act` clones the game per legal action, steps it, and scores `own − max(others)` from `score_player`; for `PAY`/`CHOOSE_CARD` choices it prefers discarding the lowest-value card (value = species base points of the halves, cheapest first); ties broken by `rng`. `play_game` loops `agents[game.current_seat].act(game, seat)` until `game_over` and returns `game.scores()`.
- [ ] **Step 4: Run tests → pass** (the greedy test takes a few seconds; keep `MAX` clone cost low by cloning `state` only)
- [ ] **Step 5: Commit** `git commit -m "feat: random and greedy agents"`

---

### Task 15: Self-play wrapper and PPO training

**Files:**
- Create: `forest_shuffle/rl/selfplay_env.py`, `forest_shuffle/rl/train.py`
- Test: `tests/test_selfplay.py`

**Interfaces:**
- Produces: `SelfPlayEnv(gym.Env)(num_players=2, opponent: Agent, seed=None)` with `observation_space = Box(0,1,(size,))`, `action_space = Discrete(codec.size)`, `action_masks()`; `train(total_timesteps, out_dir="runs", snapshot_every=5)` in `train.py` with `python -m forest_shuffle.rl.train --timesteps 200000`.

- [ ] **Step 1: Failing test**

```python
# tests/test_selfplay.py
import numpy as np
from forest_shuffle.rl.selfplay_env import SelfPlayEnv
from forest_shuffle.rl.agents import RandomAgent

def test_selfplay_episode_with_random_policy():
    env = SelfPlayEnv(2, RandomAgent(0), seed=0); obs, info = env.reset(seed=0); rng = np.random.default_rng(0)
    done = False; total = 0.0
    while not done:
        a = int(rng.choice(np.flatnonzero(env.action_masks())))
        obs, r, term, trunc, info = env.step(a); total += r; done = term or trunc
    assert total in (-1.0, 1.0)
    assert env.game.current_seat == 0 or env.game.state.game_over

def test_maskable_ppo_smoke():
    from sb3_contrib import MaskablePPO
    env = SelfPlayEnv(2, RandomAgent(0), seed=0)
    model = MaskablePPO("MlpPolicy", env, n_steps=64, batch_size=32, verbose=0, seed=0)
    model.learn(128)
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement**: `SelfPlayEnv.step` applies the learner's action, then loops `while not game_over and current_seat != 0: opponent.act(...)`; reward is the learner's terminal reward. `train.py`: builds the env, `MaskablePPO("MlpPolicy", env, policy_kwargs=dict(net_arch=[512, 512]))`, every `snapshot_every` calls to `learn(chunk)` saves `runs/ppo_<step>.zip` and swaps the opponent for `PolicyAgent(latest)`, then evaluates 20 games vs `RandomAgent` and `GreedyAgent` and prints win rates.
- [ ] **Step 4: Run tests → pass**; run a 5-minute training locally and confirm the win rate vs random exceeds 0.5.
- [ ] **Step 5: Commit** `git commit -m "feat: self-play wrapper and MaskablePPO training"`

---

### Task 16: GUI backend — view model and API

**Files:**
- Create: `forest_shuffle/gui/view.py`, `forest_shuffle/gui/server.py`
- Test: `tests/test_gui.py`

**Interfaces:**
- Produces: `state_to_view(game, viewer_seat) -> dict`; `describe_action(game, action) -> str` (e.g. `"Play Tawny Owl [Sycamore] on tree 2 (top)"`, `"Pay with European Hare | Badger"`, `"Use effect: draw 1"`); FastAPI `app` with the endpoints in Section 2.10 and a `Session` holding `game`, `seats: list[Agent|None]`.

- [ ] **Step 1: Failing tests**

```python
# tests/test_gui.py
from fastapi.testclient import TestClient
from forest_shuffle.gui.server import app

def test_new_game_state_and_step():
    c = TestClient(app)
    r = c.post("/api/new", json={"num_players": 2, "seats": [{"type": "human"}, {"type": "random"}], "seed": 3})
    assert r.status_code == 200
    s = c.get("/api/state", params={"viewer": 0}).json()
    assert s["current"] == 0 and len(s["hand"]) == 6 and len(s["legal_actions"]) > 0 and s["phase"] == "CHOOSE_ACTION"
    a = s["legal_actions"][0]
    assert set(a) >= {"id", "label", "kind"}
    r = c.post("/api/action", json={"id": a["id"]}); assert r.status_code == 200
    r = c.post("/api/autoplay", json={"max_steps": 50}); assert r.status_code == 200
    s = c.get("/api/state", params={"viewer": 0}).json()
    assert s["current"] == 0 or s["game_over"]

def test_action_rejected_for_ai_seat():
    c = TestClient(app)
    c.post("/api/new", json={"num_players": 2, "seats": [{"type": "random"}, {"type": "human"}], "seed": 1})
    r = c.post("/api/action", json={"id": 0}); assert r.status_code == 409
```

- [ ] **Step 2: Run, expect failure**
- [ ] **Step 3: Implement** `view.py` (view dict keys: `current, phase, pending_label, game_over, deck_count, winter_revealed, clearing: [card views], players: [{seat, hand_count, cave_count, forest: [{species, name, symbol, is_sapling, slots: {TOP: [dweller views], ...}}]}], hand: [card views] (viewer only), legal_actions: [{id, kind, label, card?, half?, target?}] (empty unless viewer is current), scores: [breakdowns], log: last 30`; card view = `{uid, def_id, code, layout, halves: [{position, species, name, symbol, cost}]}`) and `server.py` (`StaticFiles` mount for `/static`, `409` when the current seat is not human, `400` for illegal ids).
- [ ] **Step 4: Run tests → pass**
- [ ] **Step 5: Commit** `git commit -m "feat: GUI API and view model"`

---

### Task 17: GUI frontend

**Files:**
- Create: `forest_shuffle/gui/static/index.html`, `forest_shuffle/gui/static/app.js`, `forest_shuffle/gui/static/style.css`

- [ ] **Step 1: Build the page**

`index.html`: header with a form (players 2–5, per-seat `<select>` human/random/greedy/model + model path input, seed, expansions checkboxes, "New game"), controls (`Step AI`, `Auto-play` toggle, speed slider 100–2000 ms), a status line (current seat, phase, pending decision label, deck and winter counts), `#clearing`, `#forests`, `#hand`, `#actions`, `#scores`, `#log`.

`app.js` (vanilla, ~250 lines): `fetchState()` → renders; `render()` draws each forest as a CSS grid per woody plant (name + symbol badge, four slot columns listing dweller names with `×n` for stacks, sapling shown as grey box); hand cards as two-half tiles; legal actions grouped by kind into buttons whose click posts `/api/action`; `Step AI` posts `/api/step`; auto-play uses `setInterval` posting `/api/autoplay {max_steps: 1}` until a human must act or the game ends; scores table from `scores` breakdown.

`style.css`: tree-symbol colour classes (`.sym-LINDEN` yellow, `.sym-BIRCH` light green, `.sym-BEECH` dark green, `.sym-SYCAMORE` red, `.sym-OAK` brown, `.sym-HORSE_CHESTNUT` orange, `.sym-DOUGLAS_FIR` light blue, `.sym-SILVER_FIR` teal, `.sym-ALPINE_LARCH` purple, `.sym-SWISS_PINE` pink) matching the physical cards.

- [ ] **Step 2: Manual verification**

Run: `.venv/Scripts/python.exe -m uvicorn forest_shuffle.gui.server:app --reload`, open `http://127.0.0.1:8000/`. Check: new 2-player game human vs greedy renders six hand cards; clicking a play action shows the PAY step with per-card buttons; auto-play against two random seats runs to the end and shows final scores; a 5-player random game finishes without console errors.

- [ ] **Step 3: Commit** `git commit -m "feat: GUI frontend"`

---

### Task 18: Orchestration scripts and docs

**Files:**
- Create: `examples/play_random.py`, `examples/tournament.py`
- Modify: `README.md`

- [ ] **Step 1: Scripts**

`play_random.py`: `python examples/play_random.py --players 3 --seed 5` plays one game with `RandomAgent`s and prints each turn's action label and final breakdowns.

`tournament.py`: `python examples/tournament.py --games 100 --seats greedy random --seed 0 [--model runs/ppo_latest.zip]`; rotates seat order every game, prints win rate, mean score and mean margin per agent.

- [ ] **Step 2: README**: purpose, install, tests, GUI, training and tournament commands, pointer to `doc/card_catalog.md` and this plan.
- [ ] **Step 3: Run both scripts once; commit** `git commit -m "docs: examples and README"`

---

## 5. Documented simplifications

- Mulligan is applied automatically whenever a starting hand has no tree.
- Payment ordering: the agent discards one card per action; the bonus is granted if all discards show the played symbol. There is no separate "decline bonus" before payment; the agent declines via `SKIP` afterwards.
- Every optional effect (including mushroom and shrub triggers) is offered as `USE`/`SKIP`.
- `MAX_WOODY = 40` woody plants per forest; beyond that no new trees or saplings can be played. Random playouts never approach this.
- The environment truncates at 2 000 steps as a safety net.
- Effects that pick "any number" of cards (Raccoon, Gnat, Crane Fly, Mole, Water Vole) are resolved one choice per action followed by `DONE`.

## 6. Self-review checklist (done while writing)

- Every rule in `doc/game_rules.md` maps to Tasks 3, 6, 8, 9, 10 tests; every effect and scoring type in `cards.json` maps to Sections 2.6/2.7 and Tasks 5 and 10.
- Names used across tasks: `Game`, `GameState`, `Decision`, `Action`, `ActionKind`, `ActionCodec`, `CardDatabase`, `count_cards`, `shows_symbol`, `can_place`, `legal_targets`, `score_player`, `apply_effect`, `matching_triggers`, `StateEncoder`, `ForestShuffleEnv`, `SelfPlayEnv`, `RandomAgent`, `GreedyAgent`, `PolicyAgent`, `play_game`, `state_to_view`, `describe_action`.
- Known coupling: `tests/test_scoring.py` uses debug helpers from Task 8; run Tasks 6–8 before expecting Task 5's tests to pass (noted in Task 5 Step 4).


---

## 7. Addendum (v3.1): training and analysis readiness

Implemented after the first full build, replacing parts of Sections 2.5, 2.8 and 2.9:

- **Two-step placement.** `PLAY_HALF(card, half)` no longer carries a target. When several plants are legal the engine
  pushes a `CHOOSE_TARGET` decision whose options are `CHOOSE_TARGET(target)`. Codec size is `1 + 7N + W + 3 = 1 164`.
- **Compact observation.** Global + decision context + own hand counts + clearing counts + one summary block per
  player (species and symbol counts) + detailed blocks for the first 20 own plants. 3 681 floats for 2 players,
  3 895 for 4. `MAX_WOODY` stays 40 for the engine; `ENCODER_PLANTS = 20`.
- **Self-play.** `SelfPlayEnv(num_players, opponents, reward)`: learner seat rotates each episode, opponents are
  sampled per seat from a pool (`set_opponent_pool(paths)`), reward modes `win`, `margin`, `mixed`.
- **Training.** `python -m forest_shuffle.rl.train --players N --timesteps T --envs 8 [--resume]` uses
  `SubprocVecEnv`, saves to `runs/pN/`, adds snapshots to the pool every 2 chunks (pool size 4), logs win rates
  vs random and greedy to `train_log.csv`.
- **Greedy agent** evaluates one sapling option and resolves payment/target choices inside the lookahead (2p game
  in about 2 s instead of 7 s).
- **Recorder and analysis.** `GameRecorder` writes JSON lines (game, action, seat, card rows with per-card points);
  `analysis.stats.run` produces species, card-usage, symbol and agent tables. Scripts: `examples/simulate.py`,
  `examples/analyze.py`.
