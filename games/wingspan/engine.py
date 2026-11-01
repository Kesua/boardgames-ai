"""Wingspan rules engine (base game). Rule IDs refer to rules.md.

Flow: all game logic runs as a stack of small tasks (dicts) in `State.tasks`. `_run()` keeps working on the top task
until one needs a choice from a player; that choice becomes the pending Decision (bgai.kit) with its legal action
numbers. `step_id(a)` hands the answer to the top task and runs on. State is plain data, so `clone()` is a pickle.
A decision with exactly one legal answer is applied automatically (it is not a choice).

Action numbers (frozen; bgai.kit.CodecBuilder segments in this order):
  ACTION 4 (play bird, gain food, lay eggs, draw cards), BIRD 180, HABITAT 3, FOOD 5, DIE 6 (5 foods + the
  invertebrate-or-seed face), SLOT 15 (habitat * 5 + column on the deciding player's mat), TRAY 3, DECK 1, BONUS 26,
  PLAYER 5 (seat offset from the decider), YES, NO (decline / stop / skip), REROLL.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from bgai.kit import CodecBuilder, Decision, DecisionStack, Deck, Rng, TextLog

from . import cards as C
from .cards import DUAL, FACES, FOODS, HABITATS, INV, SEED, RODENT

ACTIONS = ("PLAY_BIRD", "GAIN_FOOD", "LAY_EGGS", "DRAW_CARDS")
FOOD_BY_N = (1, 1, 2, 2, 3, 3)            # W4.2
EGGS_BY_N = (2, 2, 3, 3, 4, 4)
CARDS_BY_N = (1, 1, 2, 2, 3, 3)
TRADE_AT = (1, 3, 5)                       # W4.3: slots 2, 4, 6
EGG_COST = (0, 1, 1, 2, 2)                 # W4.4
TURNS = (8, 7, 6, 5)                       # W1.5

CODEC = CodecBuilder([("ACTION", 4), ("BIRD", 180), ("HABITAT", 3), ("FOOD", 5), ("DIE", 6), ("SLOT", 15), ("TRAY", 3),
                      ("DECK", 1), ("BONUS", 26), ("PLAYER", 5), ("YES", 1), ("NO", 1), ("REROLL", 1)])
A_ACTION, A_BIRD, A_HAB, A_FOOD, A_DIE, A_SLOT, A_TRAY = (CODEC.base[k][0] for k in
                                                         ("ACTION", "BIRD", "HABITAT", "FOOD", "DIE", "SLOT", "TRAY"))
A_DECK, A_BONUS, A_PLAYER = CODEC.base["DECK"][0], CODEC.base["BONUS"][0], CODEC.base["PLAYER"][0]
A_YES, A_NO, A_REROLL = CODEC.base["YES"][0], CODEC.base["NO"][0], CODEC.base["REROLL"][0]

DECISION_KINDS = ("SETUP_KEEP", "SETUP_FOOD", "SETUP_BONUS", "CHOOSE_ACTION", "PLAY_BIRD", "PLAY_HABITAT", "PAY_EGG",
                  "PAY_FOOD", "PAY_PAIR", "TAKE_DIE", "DUAL_FOOD", "LAY_EGG", "DRAW", "TRADE", "TRADE_DISCARD_CARD",
                  "TRADE_PAY_FOOD", "TRADE_DISCARD_EGG", "USE_POWER", "CACHE", "CHOOSE_FOOD", "TUCK", "DISCARD_EGG",
                  "MOVE", "REPEAT", "TRADE_GIVE", "TRADE_GET", "KEEP_BONUS", "START_PLAYER", "PICK_CARD",
                  "END_DISCARD", "PINK")


class IllegalActionError(Exception):
    pass


@dataclass
class Placed:
    bird: int
    eggs: int = 0
    cache: list = field(default_factory=lambda: [0] * 5)
    tucked: int = 0
    pink_used: bool = False


@dataclass
class Player:
    seat: int
    hand: list = field(default_factory=list)
    bonus: list = field(default_factory=list)
    food: list = field(default_factory=lambda: [0] * 5)
    rows: list = field(default_factory=lambda: [[], [], []])
    end_discards: int = 0
    offer: list = field(default_factory=list)          # setup: the 5 dealt birds
    offer_bonus: list = field(default_factory=list)    # setup: the 2 dealt bonus cards
    actions: list = field(default_factory=lambda: [0, 0, 0, 0])    # action choices this game

    def placed(self):
        for h, row in enumerate(self.rows):
            for c, p in enumerate(row):
                yield h, c, p

    def eggs(self) -> int:
        return sum(p.eggs for _, _, p in self.placed())


@dataclass
class State:
    players: list
    deck: Deck
    discard: list
    tray: list
    feeder: list                     # faces of the dice in the feeder
    outside: list                    # faces of dice taken out
    bonus_deck: Deck
    bonus_discard: list
    goals: list                      # 4 goal dicts (round 1..4)
    goal_side: str
    goal_points: list                # per round, per seat
    round: int = 0
    first: int = 0
    active: int = 0                  # player whose turn it is
    turns: int = 0                   # completed turns, all players
    round_turns: int = 0
    tasks: list = field(default_factory=list)
    decisions: DecisionStack = field(default_factory=DecisionStack)
    game_over: bool = False
    log: TextLog = field(default_factory=TextLog)
    reveal: list = field(default_factory=list)     # cards drawn by American Oystercatcher, before the pick
    forced: list = field(default_factory=list)     # record rows of forced moves since the last drain_forced()
    setup_done: bool = False                       # False while players still choose their starting hands


def egg_cost(row_len: int) -> int:
    return EGG_COST[row_len]


@lru_cache(maxsize=None)
def can_pay(counts: tuple, reqs: tuple) -> bool:
    """Can these food tokens pay these requirements, using two-for-one where needed (W5.3)?"""
    if not reqs:
        return True
    first, rest = reqs[0], reqs[1:]
    for f in first:
        if counts[f]:
            c = list(counts)
            c[f] -= 1
            if can_pay(tuple(c), rest):
                return True
    if sum(counts) >= 2:
        for f in range(5):
            if not counts[f]:
                continue
            for g in range(f, 5):
                if counts[g] - (f == g) <= 0:
                    continue
                c = list(counts)
                c[f] -= 1
                c[g] -= 1
                if can_pay(tuple(c), rest):
                    return True
    return False


class Game:
    def __init__(self, num_players: int = 2, seed: Optional[int] = None, options: dict = None):
        assert 2 <= num_players <= 5
        self.num_players = num_players
        self.options = dict(options or {})
        self.rng = Rng(seed)
        self.birds = C.birds()
        self.bonus = C.bonus_cards()
        self.s: Optional[State] = None

    # ------------------------------------------------------------------ setup (W2)
    def reset(self) -> "Game":
        rng = self.rng
        use_swift = self.options.get("swift_start_birds", True)
        deck = Deck(b.id for b in self.birds if use_swift or not b.swift_start)
        deck.shuffle(rng)
        bonus_deck = Deck(c.id for c in self.bonus)
        bonus_deck.shuffle(rng)
        tiles = list(range(8))
        rng.shuffle(tiles)
        goals = [C.goal_tiles()[t][rng.randrange(2)] for t in tiles[:4]]
        feeder = [rng.randrange(6) for _ in range(5)]
        players = [Player(i) for i in range(self.num_players)]
        self.s = State(players=players, deck=deck, discard=[], tray=[None, None, None], feeder=feeder, outside=[],
                       bonus_deck=bonus_deck, bonus_discard=[], goals=goals,
                       goal_side=self.options.get("goal_side", "green"),
                       goal_points=[[0] * self.num_players for _ in range(4)])
        for i in range(3):
            self.s.tray[i] = deck.draw()
        for p in players:
            p.offer = deck.draw_many(5)
            p.offer_bonus = bonus_deck.draw_many(2)
            p.food = [1, 1, 1, 1, 1]
        self.s.tasks = [{"op": "round", "r": 0, "pick_first": True}]
        for seat in reversed(range(self.num_players)):
            self.s.tasks.append({"op": "setup", "seat": seat, "i": 0, "kept": 0, "to_discard": None})
        self._run()
        return self

    def clone(self) -> "Game":
        g = Game.__new__(Game)
        g.num_players, g.options, g.birds, g.bonus = self.num_players, self.options, self.birds, self.bonus
        g.s = pickle.loads(pickle.dumps(self.s, protocol=pickle.HIGHEST_PROTOCOL))
        g.rng = Rng()
        g.rng.setstate(self.rng.getstate())
        return g

    # ------------------------------------------------------------------ interface
    @property
    def game_over(self) -> bool:
        return self.s.game_over

    @property
    def turns(self) -> int:
        return self.s.turns

    @property
    def decision(self) -> Optional[Decision]:
        return self.s.decisions.top

    @property
    def current_seat(self) -> int:
        d = self.s.decisions.top
        return d.seat if d is not None else self.s.active

    def drain_forced(self) -> list:
        """Record rows of moves applied automatically (one legal answer) since the last call."""
        out, self.s.forced = self.s.forced, []
        return out

    def legal_ids(self) -> list:
        d = self.s.decisions.top
        return list(d.data["legal"]) if d is not None else []

    def step_id(self, a: int) -> None:
        d = self.s.decisions.top
        if d is None or a not in d.data["legal"]:
            raise IllegalActionError(a)
        self.s.log.add(d.seat, self.describe(a))
        self.s.decisions.pop()
        task = self.s.tasks[-1]
        HANDLERS[task["op"]](self, task, a)
        self._run()

    def _run(self) -> None:
        s = self.s
        while not s.decisions and not s.game_over:
            task = s.tasks[-1]
            HANDLERS[task["op"]](self, task, None)

    def _ask(self, kind: str, seat: int, legal: list, **data) -> bool:
        """Make a decision pending. A single legal answer is applied at once. Returns True if a decision is pending."""
        if not legal:
            raise RuntimeError(f"{kind} for P{seat} has no legal answer")
        if len(legal) == 1:                      # forced: applied at once, but logged and recorded like any move
            d = Decision(kind, dict(data, legal=list(legal)), seat)
            self.s.decisions.push(d)
            self.s.forced.append(dict(self.record_info(legal[0]), seat=seat, forced=True))
            self.s.log.add(seat, self.describe(legal[0]) + " (only option)")
            self.s.decisions.pop()
            task = self.s.tasks[-1]
            HANDLERS[task["op"]](self, task, legal[0])
            return False
        self.s.decisions.push(Decision(kind, dict(data, legal=sorted(set(legal))), seat))
        return True

    # ------------------------------------------------------------------ helpers
    def p(self, seat: int) -> Player:
        return self.s.players[seat]

    def bird(self, i: int):
        return self.birds[i]

    def at(self, seat: int, h: int, c: int) -> Optional[Placed]:
        row = self.s.players[seat].rows[h]
        return row[c] if c < len(row) else None

    def order_from(self, seat: int) -> list:
        return [(seat + k) % self.num_players for k in range(self.num_players)]

    def draw_deck(self) -> Optional[int]:
        """Deck top; an empty deck is refilled from the shuffled discard pile (W8.3)."""
        s = self.s
        if not s.deck and s.discard:
            s.deck = Deck(s.discard)
            s.discard = []
            s.deck.shuffle(self.rng)
            s.log.add(None, "Discard pile shuffled into a new deck")
        return s.deck.draw()

    def can_draw(self) -> bool:
        s = self.s
        return any(t is not None for t in s.tray) or bool(s.deck) or bool(s.discard)

    def draw_options(self) -> list:
        s = self.s
        out = [A_TRAY + i for i in range(3) if s.tray[i] is not None]
        if s.deck or s.discard:
            out.append(A_DECK)
        return out

    def take_card(self, seat: int, a: int) -> Optional[int]:
        """Answer TRAY i / DECK: the card goes to the player's hand."""
        s = self.s
        if a == A_DECK:
            card = self.draw_deck()
        else:
            card = s.tray[a - A_TRAY]
            s.tray[a - A_TRAY] = None
        if card is not None:
            s.players[seat].hand.append(card)
        return card

    def refill_tray(self) -> None:
        s = self.s
        for i in range(3):
            if s.tray[i] is None:
                s.tray[i] = self.draw_deck()

    def reroll_allowed(self) -> bool:
        f = self.s.feeder
        return bool(f) and len(set(f)) == 1                         # W7.3

    def reroll(self) -> None:
        s = self.s
        s.feeder = [self.rng.randrange(6) for _ in range(5)]
        s.outside = []

    def die_options(self, foods=None) -> list:
        """DIE answers for the faces in the feeder that give one of `foods` (None = any)."""
        out = []
        for face in sorted(set(self.s.feeder)):
            gives = (INV, SEED) if face == DUAL else (face,)
            if foods is None or any(g in foods for g in gives):
                out.append(A_DIE + face)
        return out

    def take_die(self, face: int) -> None:
        s = self.s
        s.feeder.remove(face)
        s.outside.append(face)
        if not s.feeder:                                               # W7.2
            self.reroll()
            s.log.add(None, "Birdfeeder empty: all 5 dice rolled")

    def gain(self, seat: int, food: int, n: int = 1) -> None:
        self.s.players[seat].food[food] += n

    def lay_slots(self, seat: int, nest: str = None, exclude=None) -> list:
        out = []
        for h, c, p in self.s.players[seat].placed():
            b = self.birds[p.bird]
            if p.eggs < b.egg_limit and (nest is None or b.has_nest(nest)) and (h, c) != exclude:
                out.append(A_SLOT + h * 5 + c)
        return out

    def egg_slots(self, seat: int, exclude=None) -> list:
        return [A_SLOT + h * 5 + c for h, c, p in self.s.players[seat].placed() if p.eggs > 0 and (h, c) != exclude]

    def slot_of(self, a: int) -> tuple:
        return divmod(a - A_SLOT, 5)

    def playable(self, seat: int, bird_id: int, habitat: int = None) -> list:
        """Habitats where this bird can be played now (room, egg cost, food cost)."""
        pl = self.s.players[seat]
        b = self.birds[bird_id]
        eggs = pl.eggs()
        out = []
        for h in b.habitats:
            if habitat is not None and h != habitat:
                continue
            n = len(pl.rows[h])
            if n < 5 and egg_cost(n) <= eggs and can_pay(tuple(pl.food), b.requirements()):
                out.append(h)
        return out

    def playable_birds(self, seat: int, habitat: int = None) -> list:
        return [b for b in sorted(set(self.s.players[seat].hand)) if self.playable(seat, b, habitat)]

    # ------------------------------------------------------------------ pink triggers (W11)
    def trigger(self, active: int, kind: str, habitat: int = None) -> None:
        """Push the pink powers of other players that this event triggers, in turn order from the left of the active
        player (W11.3). The pushed tasks run before the active player's next step."""
        tasks = []
        for seat in self.order_from(active)[1:]:
            pl = self.s.players[seat]
            for h, c, p in pl.placed():
                pw = self.birds[p.bird].power
                if p.pink_used or not pw or self.birds[p.bird].color != "pink":
                    continue
                t = pw["type"]
                if (kind == "play" and t == "pink_play" and HABITATS.index(pw["habitat"]) == habitat) or \
                        (kind == "lay" and t == "pink_lay_eggs") or (kind == "rodent" and t == "pink_gain_food_rodent") or \
                        (kind == "predator" and t == "pink_predator"):
                    tasks.append({"op": "pink", "seat": seat, "h": h, "c": c, "stage": 0})
        self.s.tasks.extend(reversed(tasks))

    # ------------------------------------------------------------------ scoring
    def breakdowns(self) -> list:
        from .scoring import breakdown
        return [breakdown(self, seat) for seat in range(self.num_players)]

    def scores(self) -> list:
        return [sum(b.values()) for b in self.breakdowns()]

    def tiebreaks(self) -> list:
        return [sum(p.food) for p in self.s.players]                  # W14.2

    # ------------------------------------------------------------------ text
    def describe(self, a: int) -> str:
        from .describe import describe_action
        return describe_action(self, a)

    def text_state(self) -> str:
        from .describe import text_state
        return text_state(self)

    def record_info(self, a: int) -> dict:
        from .describe import record_info
        return record_info(self, a)

    def tableau(self, seat: int) -> list:
        pl = self.s.players[seat]
        out = []
        for h, c, p in pl.placed():
            b = self.birds[p.bird]
            out.append({"item": b.key, "kind": b.color, "group": HABITATS[h], "slot": c, "host": None,
                        "points": b.points + p.eggs + sum(p.cache) + p.tucked,
                        "tags": {"habitat": HABITATS[h], "nest": b.nest, "power": b.color,
                                 "printed": b.points, "eggs": p.eggs, "cache": sum(p.cache), "tucked": p.tucked}})
        return out

    def seat_extra(self, seat: int) -> dict:
        pl = self.s.players[seat]
        return {"birds": sum(len(r) for r in pl.rows), "forest": len(pl.rows[0]), "grassland": len(pl.rows[1]),
                "wetland": len(pl.rows[2]), "food_left": sum(pl.food), "bonus_cards": len(pl.bonus),
                "play_bird": pl.actions[0], "gain_food": pl.actions[1], "lay_eggs": pl.actions[2],
                "draw_cards": pl.actions[3], "eggs_total": pl.eggs(),
                "bonus_held": [self.bonus[b].name for b in pl.bonus],
                "goal_points": [self.s.goal_points[r][seat] for r in range(4)],
                "goal_ids": [x["id"] for x in self.s.goals],
                "hand_left": [self.birds[b].key for b in pl.hand]}


# ====================================================================== task handlers
# Each handler(game, task, answer): answer None = make progress (ask, push sub-tasks or finish by popping itself);
# answer given = apply the player's choice to the task.

def h_setup(g: Game, t: dict, a):
    """W2.4: keep birds (yes/no each), discard 1 food per kept bird, keep 1 of 2 bonus cards."""
    pl = g.p(t["seat"])
    if a is not None:
        if pl.offer:
            card = pl.offer.pop(0)                  # every card is always in exactly one place (checked)
            if a == A_YES:
                t["kept"] += 1
                pl.hand.append(card)
            else:
                g.s.discard.append(card)
        elif t["to_discard"]:
            pl.food[a - A_FOOD] -= 1
            t["to_discard"] -= 1
        else:
            keep = a - A_BONUS
            pl.bonus = [keep]
            g.s.bonus_discard += [b for b in pl.offer_bonus if b != keep]
            pl.offer_bonus = []
            g.s.tasks.pop()
        return
    if pl.offer:
        g._ask("SETUP_KEEP", t["seat"], [A_YES, A_NO], bird=pl.offer[0])
        return
    if t["to_discard"] is None:
        t["to_discard"] = t["kept"]
    if t["to_discard"]:
        g._ask("SETUP_FOOD", t["seat"], [A_FOOD + f for f in range(5) if pl.food[f]])
        return
    g._ask("SETUP_BONUS", t["seat"], [A_BONUS + b for b in pl.offer_bonus])


def h_round(g: Game, t: dict, a):
    s = g.s
    if t.pop("pick_first", False):
        s.setup_done = True
        s.first = g.rng.randrange(g.num_players)                       # W2.5
        s.log.add(None, f"Player {s.first} goes first")
    if "next" not in t:
        s.round = t["r"]
        s.round_turns = 0
        t["next"] = s.first
        s.log.add(None, f"Round {t['r'] + 1}")
    if s.round_turns >= TURNS[t["r"]] * g.num_players:
        s.tasks.pop()
        s.tasks.append({"op": "round_end", "r": t["r"]})
        return
    seat = t["next"]
    t["next"] = (seat + 1) % g.num_players
    s.tasks.append({"op": "turn", "seat": seat, "stage": 0})


def h_round_end(g: Game, t: dict, a):
    from .scoring import score_goal
    s = g.s
    s.tasks.pop()
    s.goal_points[t["r"]] = score_goal(g, t["r"])                       # W12
    s.log.add(None, f"Round {t['r'] + 1} goal {s.goals[t['r']]['id']}: {s.goal_points[t['r']]}")
    s.discard += [c for c in s.tray if c is not None]                    # W3.2
    s.tray = [None, None, None]
    g.refill_tray()
    s.first = (s.first + 1) % g.num_players
    if t["r"] == 3:
        s.game_over = True                                               # W3.3
        s.decisions.clear()
        return
    s.tasks.append({"op": "round", "r": t["r"] + 1})


def h_turn(g: Game, t: dict, a):
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    if t["stage"] == 0:
        t["stage"] = 1
        s.active = seat
        for _, _, p in pl.placed():                                     # W11.1: pink powers re-arm on own turn
            p.pink_used = False
        s.tasks.append({"op": "choose_action", "seat": seat})
        return
    if t["stage"] == 1:                                                 # end-of-turn discards (W10.9)
        if a is not None:
            pl.hand.remove(a - A_BIRD)
            s.discard.append(a - A_BIRD)
            pl.end_discards -= 1
            return
        if pl.end_discards > 0 and pl.hand:
            g._ask("END_DISCARD", seat, [A_BIRD + b for b in pl.hand])
            return
        pl.end_discards = 0
        g.refill_tray()                                                 # W8.2
        s.turns += 1
        s.round_turns += 1
        s.tasks.pop()


def h_choose_action(g: Game, t: dict, a):
    seat = t["seat"]
    if a is None:
        legal = [A_ACTION + 1, A_ACTION + 2, A_ACTION + 3]
        if g.playable_birds(seat):
            legal.insert(0, A_ACTION)
        g._ask("CHOOSE_ACTION", seat, legal)
        return
    g.s.tasks.pop()
    k = a - A_ACTION
    g.p(seat).actions[k] += 1
    if k == 0:
        g.s.tasks.append({"op": "play_bird", "seat": seat, "habitat": None, "optional": False, "stage": "bird"})
    else:
        h = k - 1
        n = len(g.p(seat).rows[h])
        amount = (FOOD_BY_N, EGGS_BY_N, CARDS_BY_N)[h][n]
        g.s.tasks.append({"op": ("gain_food", "lay_eggs", "draw_cards")[h], "seat": seat, "n": amount,
                          "trade": n in TRADE_AT, "stage": "base", "rodent": False})


# ---------------------------------------------------------------------- play a bird (W5)
def h_play_bird(g: Game, t: dict, a):
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    st = t["stage"]
    if a is not None:
        if st == "bird":
            if a == A_NO:
                s.tasks.pop()
                return
            t["bird"] = a - A_BIRD
            t["stage"] = "habitat"
        elif st == "habitat":
            t["h"] = a - A_HAB
            n = len(pl.rows[t["h"]])
            t["eggs"] = egg_cost(n)
            t["reqs"] = list(g.bird(t["bird"]).requirements())
            t["stage"] = "eggs"
        elif st == "eggs":
            h, c = g.slot_of(a)
            pl.rows[h][c].eggs -= 1
            t["eggs"] -= 1
        elif st == "food":
            f = a - A_FOOD if a != A_YES else None
            if f is None:
                t["pair"] = 2
                t["stage"] = "pair"
            else:
                pl.food[f] -= 1
                t["reqs"].pop(0)
        elif st == "pair":
            pl.food[a - A_FOOD] -= 1
            t["pair"] -= 1
            if t["pair"] == 0:
                t["reqs"].pop(0)
                t["stage"] = "food"
        return
    if st == "bird":
        legal = [A_BIRD + b for b in g.playable_birds(seat, t["habitat"])]
        if t["optional"]:
            legal.append(A_NO)
        if not legal:
            s.tasks.pop()
            return
        g._ask("PLAY_BIRD", seat, legal)
        return
    if st == "habitat":
        g._ask("PLAY_HABITAT", seat, [A_HAB + h for h in g.playable(seat, t["bird"], t["habitat"])], bird=t["bird"])
        return
    if st == "eggs":
        if t["eggs"] > 0:
            g._ask("PAY_EGG", seat, g.egg_slots(seat), bird=t["bird"])
            return
        t["stage"] = "food"
        return
    if st == "food":
        if t["reqs"]:
            reqs = tuple(t["reqs"])
            legal = []
            for f in reqs[0]:
                if pl.food[f]:
                    c = list(pl.food)
                    c[f] -= 1
                    if can_pay(tuple(c), reqs[1:]):
                        legal.append(A_FOOD + f)
            if sum(pl.food) >= 2 and _pair_ok(pl.food, reqs[1:]):
                legal.append(A_YES)                                      # two-for-one for this requirement (W5.3)
            g._ask("PAY_FOOD", seat, legal, bird=t["bird"], need=list(reqs[0]))
            return
        _place(g, t)
        return
    if st == "pair":
        reqs = tuple(t["reqs"][1:])
        legal = []
        for f in range(5):
            if pl.food[f]:
                c = list(pl.food)
                c[f] -= 1
                if (t["pair"] == 2 and _pair_ok_after_one(c, reqs)) or (t["pair"] == 1 and can_pay(tuple(c), reqs)):
                    legal.append(A_FOOD + f)
        g._ask("PAY_PAIR", seat, legal, bird=t["bird"])
        return


def _pair_ok(food, rest) -> bool:
    for f in range(5):
        for g_ in range(f, 5):
            c = list(food)
            c[f] -= 1
            c[g_] -= 1
            if min(c) >= 0 and can_pay(tuple(c), tuple(rest)):
                return True
    return False


def _pair_ok_after_one(c, rest) -> bool:
    for g_ in range(5):
        if c[g_]:
            d = list(c)
            d[g_] -= 1
            if can_pay(tuple(d), tuple(rest)):
                return True
    return False


def _place(g: Game, t: dict):
    """W5.1/W5.4: put the bird in the leftmost empty slot, then its white power, then pink 'plays a bird' triggers."""
    s = g.s
    seat, bid, h = t["seat"], t["bird"], t["h"]
    pl = g.p(seat)
    pl.hand.remove(bid)
    pl.rows[h].append(Placed(bid))
    c = len(pl.rows[h]) - 1
    s.tasks.pop()
    s.tasks.append({"op": "trigger", "kind": "play", "active": seat, "habitat": h})
    b = g.bird(bid)
    if b.color == "white" and b.power:
        s.tasks.append({"op": "power", "seat": seat, "h": h, "c": c, "stage": "ask", "chain": []})


def h_trigger(g: Game, t: dict, a):
    g.s.tasks.pop()
    g.trigger(t["active"], t["kind"], t.get("habitat"))


# ---------------------------------------------------------------------- habitat actions (W6)
def _take_die_task(seat, foods=None, then=None, optional=True, cache_pos=None, may_cache=False, mark=None):
    return {"op": "take_die", "seat": seat, "foods": foods, "optional": optional, "then": then,
            "cache_pos": cache_pos, "may_cache": may_cache, "stage": "die", "mark": mark}


def h_take_die(g: Game, t: dict, a):
    """Take one die from the feeder (W7.1): optional reroll first (W7.3); invertebrate-or-seed asks which food."""
    s = g.s
    seat = t["seat"]
    foods = t["foods"]
    if a is not None:
        if t["stage"] == "die":
            if a == A_NO:
                t["result"] = None
                t["stage"] = "done"
            elif a == A_REROLL:
                g.reroll()
                s.log.add(seat, "rerolls the birdfeeder")
                t["rerolled"] = True
            else:
                face = a - A_DIE
                g.take_die(face)
                if face == DUAL:
                    opts = [f for f in (INV, SEED) if foods is None or f in foods]
                    if len(opts) == 1:
                        t["result"] = opts[0]
                        t["stage"] = "cache"
                    else:
                        t["stage"] = "dual"
                else:
                    t["result"] = face
                    t["stage"] = "cache"
        elif t["stage"] == "dual":
            t["result"] = a - A_FOOD
            t["stage"] = "cache"
        elif t["stage"] == "cache_ask":
            t["cached"] = a == A_YES
            t["stage"] = "done"
        return
    if t["stage"] == "die":
        legal = g.die_options(foods)
        if g.reroll_allowed():
            legal.append(A_REROLL)
        if t["optional"] or not legal:
            legal.append(A_NO)
        g._ask("TAKE_DIE", seat, legal, foods=foods, purpose=t.get("then"))
        return
    if t["stage"] == "dual":
        g._ask("DUAL_FOOD", seat, [A_FOOD + INV, A_FOOD + SEED])
        return
    if t["stage"] == "cache":
        if t["cache_pos"] is not None and t["may_cache"]:
            t["stage"] = "cache_ask"
            g._ask("CACHE", seat, [A_YES, A_NO], food=t["result"])
            return
        t["cached"] = False
        t["stage"] = "done"
        return
    # done: deliver
    s.tasks.pop()
    r = t.get("result")
    if t.get("mark") is not None and (r is not None or t.get("rerolled")):
        h, c = t["mark"][1], t["mark"][2]
        p = g.at(t["mark"][0], h, c)
        if p is not None:
            p.pink_used = True                                      # W11.1: using the power (even a reroll) uses it
    if r is None:
        return
    if t.get("cached"):
        h, c = t["cache_pos"]
        g.at(seat, h, c).cache[r] += 1
    else:
        g.gain(seat, r)
    parent = s.tasks[-1] if s.tasks else None
    if parent is not None and t.get("then") == "action":
        parent["got"] = parent.get("got", 0) + 1
        if r == RODENT:
            parent["rodent"] = True


def h_gain_food(g: Game, t: dict, a):
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    if a is not None:                                                   # trade answers
        if t["stage"] == "trade_ask":
            t["stage"] = "trade_card" if a == A_YES else "after"
        elif t["stage"] == "trade_card":
            pl.hand.remove(a - A_BIRD)
            s.discard.append(a - A_BIRD)
            t["stage"] = "trade_die"
        return
    if t["stage"] == "base":
        if t.get("asked", 0) < t["n"] and not t.get("stop"):
            t["asked"] = t.get("asked", 0) + 1
            before = t.get("got", 0)
            t["expect"] = before
            s.tasks.append(_take_die_task(seat, then="action", optional=True))
            t["stage"] = "base_check"
            return
        t["stage"] = "trade"
        return
    if t["stage"] == "base_check":                                      # a declined die stops the gain (W6.2)
        if t.get("got", 0) == t["expect"]:
            t["stop"] = True
        t["stage"] = "base"
        return
    if t["stage"] == "trade":
        if t["trade"] and pl.hand:
            t["stage"] = "trade_ask"
            g._ask("TRADE", seat, [A_YES, A_NO], action="GAIN_FOOD")
            return
        t["stage"] = "after"
        return
    if t["stage"] == "trade_card":
        g._ask("TRADE_DISCARD_CARD", seat, [A_BIRD + b for b in sorted(set(pl.hand))])
        return
    if t["stage"] == "trade_die":
        t["stage"] = "after"
        s.tasks.append(_take_die_task(seat, then="action", optional=False))
        return
    if t["stage"] == "after":
        s.tasks.pop()
        s.tasks.append({"op": "brown_row", "seat": seat, "h": 0, "i": len(pl.rows[0]) - 1})
        if t.get("rodent"):
            s.tasks.append({"op": "trigger", "kind": "rodent", "active": seat})


def h_lay_eggs(g: Game, t: dict, a):
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    if a is not None:
        if t["stage"] == "base":
            if a == A_NO:
                t["laid"] = t["n"]
            else:
                h, c = g.slot_of(a)
                pl.rows[h][c].eggs += 1
                t["laid"] = t.get("laid", 0) + 1
        elif t["stage"] == "trade_ask":
            t["stage"] = "trade_food" if a == A_YES else "after"
        elif t["stage"] == "trade_food":
            pl.food[a - A_FOOD] -= 1
            t["stage"] = "trade_egg"
        elif t["stage"] == "trade_egg":
            h, c = g.slot_of(a)
            pl.rows[h][c].eggs += 1
            t["stage"] = "after"
        return
    if t["stage"] == "base":
        slots = g.lay_slots(seat)
        if t.get("laid", 0) < t["n"] and slots:
            g._ask("LAY_EGG", seat, slots + [A_NO], left=t["n"] - t.get("laid", 0))
            return
        t["stage"] = "trade"
        return
    if t["stage"] == "trade":
        if t["trade"] and sum(pl.food) and g.lay_slots(seat):
            t["stage"] = "trade_ask"
            g._ask("TRADE", seat, [A_YES, A_NO], action="LAY_EGGS")
            return
        t["stage"] = "after"
        return
    if t["stage"] == "trade_food":
        g._ask("TRADE_PAY_FOOD", seat, [A_FOOD + f for f in range(5) if pl.food[f]])
        return
    if t["stage"] == "trade_egg":
        g._ask("LAY_EGG", seat, g.lay_slots(seat), left=1)
        return
    if t["stage"] == "after":
        s.tasks.pop()
        s.tasks.append({"op": "brown_row", "seat": seat, "h": 1, "i": len(pl.rows[1]) - 1})
        s.tasks.append({"op": "trigger", "kind": "lay", "active": seat})


def h_draw_cards(g: Game, t: dict, a):
    s = g.s
    seat = t["seat"]
    pl = g.p(seat)
    if a is not None:
        if t["stage"] == "base":
            if a == A_NO:
                t["drawn"] = t["n"]
            else:
                g.take_card(seat, a)
                t["drawn"] = t.get("drawn", 0) + 1
        elif t["stage"] == "trade_ask":
            t["stage"] = "trade_egg" if a == A_YES else "after"
        elif t["stage"] == "trade_egg":
            h, c = g.slot_of(a)
            pl.rows[h][c].eggs -= 1
            t["stage"] = "trade_draw"
        elif t["stage"] == "trade_draw":
            g.take_card(seat, a)
            t["stage"] = "after"
        return
    if t["stage"] == "base":
        opts = g.draw_options()
        if t.get("drawn", 0) < t["n"] and opts:
            g._ask("DRAW", seat, opts + [A_NO], left=t["n"] - t.get("drawn", 0))
            return
        t["stage"] = "trade"
        return
    if t["stage"] == "trade":
        if t["trade"] and pl.eggs() and g.draw_options():
            t["stage"] = "trade_ask"
            g._ask("TRADE", seat, [A_YES, A_NO], action="DRAW_CARDS")
            return
        t["stage"] = "after"
        return
    if t["stage"] == "trade_egg":
        g._ask("TRADE_DISCARD_EGG", seat, g.egg_slots(seat))
        return
    if t["stage"] == "trade_draw":
        g._ask("DRAW", seat, g.draw_options(), left=1)
        return
    if t["stage"] == "after":
        s.tasks.pop()
        s.tasks.append({"op": "brown_row", "seat": seat, "h": 2, "i": len(pl.rows[2]) - 1})


def h_brown_row(g: Game, t: dict, a):
    """W6.1: brown powers of the row from right to left, each optional."""
    s = g.s
    while t["i"] >= 0:
        i = t["i"]
        t["i"] -= 1
        p = g.at(t["seat"], t["h"], i)
        if p is not None and g.bird(p.bird).color == "brown" and g.bird(p.bird).power:
            s.tasks.append({"op": "power", "seat": t["seat"], "h": t["h"], "c": i, "stage": "ask", "chain": []})
            return
    s.tasks.pop()


# ---------------------------------------------------------------------- powers (W10)
def h_power(g: Game, t: dict, a):
    """Ask whether to use the power (skipped when it could do nothing), then run its effect."""
    from .powers import can_use, start_effect
    s = g.s
    if a is not None:
        t["stage"] = "run" if a == A_YES else "skip"
        return
    if t["stage"] == "ask":
        if not can_use(g, t["seat"], t["h"], t["c"]):
            s.tasks.pop()
            return
        p = g.at(t["seat"], t["h"], t["c"])
        t["stage"] = "wait"
        g._ask("USE_POWER", t["seat"], [A_YES, A_NO], bird=p.bird)
        return
    if t["stage"] == "skip":
        s.tasks.pop()
        return
    if t["stage"] == "run":
        s.tasks.pop()
        start_effect(g, t["seat"], t["h"], t["c"], t.get("chain", []))


def h_pink(g: Game, t: dict, a):
    from .powers import pink_effect
    pink_effect(g, t, a)


from . import powers as _powers   # noqa: E402  (handlers of individual effects)

HANDLERS = {"setup": h_setup, "round": h_round, "round_end": h_round_end, "turn": h_turn,
            "choose_action": h_choose_action, "play_bird": h_play_bird, "trigger": h_trigger, "take_die": h_take_die,
            "gain_food": h_gain_food, "lay_eggs": h_lay_eggs, "draw_cards": h_draw_cards, "brown_row": h_brown_row,
            "power": h_power, "pink": h_pink, **_powers.HANDLERS}
