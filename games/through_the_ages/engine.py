"""Through the Ages engine: the bgai.game.Game contract, the task stack and the turn flow (PLAN.md sections 3-5, 7, 9).

Rule IDs refer to rules.md. Stage 1 (PLAN section 13, steps 1-3): a complete peaceful game. Politics offers only END,
military cards are drawn and discarded but not played (stage 2), card effects beyond printed symbols are partly
implemented (effects.UNIMPLEMENTED_EFFECT_TYPES).

All logic runs as tasks (dicts with "op") on `State.tasks`; `_run()` works on the top task until one needs a choice
(`_ask` makes a Decision pending); `step_id` hands the answer to the top task. A decision with one legal answer is
applied at once and reported through `drain_forced()`.
"""
from __future__ import annotations

import pickle
from typing import Optional

from bgai.kit import CodecBuilder, Decision, Deck, Rng

from . import economy as E
from . import effects, military
from .cards import (AGE, BUILDINGS, IS_STARTING, IS_TECH, IS_UNIT, KEY, KIND, LEADERS_BY_AGE, LEVEL,
                    N_CARDS, NAME, NEXT_AGE, RESOURCE_COST, REVOLUTION_COST, SCIENCE_COST, SET, SPECIALS,
                    STAGE_COSTS, TOKEN_SYMBOLS, TOKEN_VALUE, UNITS, URBAN, WONDERS_BY_AGE, civil_deck_cards,
                    military_deck_cards)
from .state import LEADER_PROXY, ROW_SIZE, WONDER_PROXY, Player, State

# ---------------------------------------------------------------------------------------------- action numbers
CODEC = CodecBuilder([("END", 1), ("NO", 1), ("YES", 1), ("ROW", 13), ("VERB", 32), ("CARD", N_CARDS), ("SEAT", 3),
                      ("AMOUNT", 128), ("OPTION", 8)])                      # frozen once a model exists (PLAN 4)
A_END = CODEC.encode("END")
A_NO = CODEC.encode("NO")
A_YES = CODEC.encode("YES")
A_ROW = CODEC.encode("ROW", 0)
A_VERB = CODEC.encode("VERB", 0)
A_CARD = CODEC.encode("CARD", 0)
A_SEAT = CODEC.encode("SEAT", 0)
A_AMOUNT = CODEC.encode("AMOUNT", 0)       # AMOUNT offset k = the number k + 1
A_OPTION = CODEC.encode("OPTION", 0)

VERBS = ("INCREASE_POP", "BUILD", "UPGRADE", "DESTROY", "BUILD_UNIT", "UPGRADE_UNIT", "DISBAND", "WONDER_STAGE",
         "COPY_TACTIC", "PREPARE", "AGGRESSION", "WAR", "PACT", "CANCEL_PACT", "RESIGN")   # 15..31: card abilities
V = {name: i for i, name in enumerate(VERBS)}
VERB_TEXT = {"INCREASE_POP": "Increase population", "BUILD": "Build a farm, mine or urban building",
             "UPGRADE": "Upgrade a farm, mine or urban building", "DESTROY": "Destroy a farm, mine or urban building",
             "BUILD_UNIT": "Build a military unit", "UPGRADE_UNIT": "Upgrade a military unit",
             "DISBAND": "Disband a military unit", "WONDER_STAGE": "Build a wonder stage"}

DECISION_KINDS = ("POLITICS", "POLITICS_CARD", "TARGET", "PACT_SIDE", "PACT_ANSWER", "CANCEL_WHICH", "DEFEND",
                  "ACTION", "CHOOSE_TECH", "UPGRADE_TO", "STAGES", "REVOLT", "SUB_ACTION", "CHOOSE_TACTIC",
                  "DISCARD_MILITARY", "BID", "SEND", "MIX", "EVENT_CHOICE", "TAKE_LOOP", "LOSE_WORKER", "TERRORISM",
                  "LOSE_BLUE", "STEAL_TECH", "KIDNAP", "INFILTRATE", "ANNEX", "ABILITY")
ROW_COST = (1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3)                         # T1.2
ROW_DISCARD = {2: 3, 3: 2, 4: 1}                                           # T4.1
CATEGORIES = ("production", "leaders", "wonders", "events", "military", "colonies", "actions", "famine", "resigned")
BUILD_VERB = {True: "BUILD_UNIT", False: "BUILD"}
UPGRADE_VERB = {True: "UPGRADE_UNIT", False: "UPGRADE"}
DESTROY_VERB = {True: "DISBAND", False: "DESTROY"}


class IllegalActionError(Exception):
    pass


class Game:
    def __init__(self, num_players: int = 2, seed: Optional[int] = None, options: dict = None):
        assert 2 <= num_players <= 4
        self.num_players = num_players
        self.options = dict(options or {})
        self.rng = Rng(seed)
        self.s: Optional[State] = None
        self._stats = {}                   # seat -> (Player.ver, Stats); not part of the state

    # ================================================================================= setup (T2, T15.4, T15.8)
    def reset(self) -> "Game":
        rng, n = self.rng, self.num_players
        start = rng.randrange(n)                                            # T2.7
        s = State(players=[Player.new(i) for i in range(n)], start_seat=start, turn_seat=start, round_first=start)
        self.s = s
        nl, nw = (6, 4) if n == 2 else (7, 5)                               # T15.4 public mix
        for age in ("A", "I", "II", "III"):
            s.selection[age] = {"leaders": rng.sample(LEADERS_BY_AGE[age], nl),
                                "wonders": rng.sample(WONDERS_BY_AGE[age], nw)}
        mil = Deck(military_deck_cards("A", n))                             # T2.5
        mil.shuffle(rng)
        s.military_created += len(mil)
        s.current_events = [[c, None] for c in mil.draw_many(n + 2)]
        s.age_a_unused = list(mil)
        deck = Deck(civil_deck_cards("A", n) + s.selection["A"]["leaders"] + s.selection["A"]["wonders"])   # T15.8
        deck.shuffle(rng)                                                   # T2.6
        s.civil_created += len(deck)
        s.row = deck.draw_many(ROW_SIZE)
        s.civil_deck = deck
        for k in range(n):                                                  # T2.8
            p = s.players[(start + k) % n]
            p.civil_spent = 4 - (k + 1)
            p.military_spent = 2
        s.log.add(None, f"P{start} is the starting player")
        s.tasks = [{"op": "game", "queue": []}]
        self._run()
        return self

    def clone(self) -> "Game":
        g = Game.__new__(Game)
        g.num_players, g.options = self.num_players, self.options
        g.s = pickle.loads(pickle.dumps(self.s, protocol=pickle.HIGHEST_PROTOCOL))
        g.rng = Rng()
        g.rng.setstate(self.rng.getstate())
        g._stats = {}
        return g

    # ================================================================================= contract
    @property
    def current_seat(self) -> int:
        d = self.s.decisions.top
        return d.seat if d is not None else self.s.turn_seat

    @property
    def game_over(self) -> bool:
        return self.s.game_over

    @property
    def turns(self) -> int:
        return self.s.turns

    @property
    def decision(self) -> Optional[Decision]:
        return self.s.decisions.top

    def legal_ids(self) -> list:
        d = self.s.decisions.top
        return list(d.data["legal"]) if d is not None else []

    def drain_forced(self) -> list:
        out, self.s.forced = self.s.forced, []
        return out

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

    def _ask(self, kind: str, seat: int, legal: list, **data) -> None:
        """Make a decision pending; with one legal answer apply it at once (recorded as forced). Handlers return
        right after calling this."""
        if not legal:
            raise RuntimeError(f"{kind} for P{seat} has no legal answer")
        legal = sorted(set(legal))
        d = Decision(kind, dict(data, legal=legal), seat)
        self.s.decisions.push(d)
        if len(legal) == 1:
            self.s.forced.append(dict(self.record_info(legal[0]), seat=seat, forced=True))
            self.s.log.add(seat, self.describe(legal[0]) + " (only option)")
            self.s.decisions.pop()
            task = self.s.tasks[-1]
            HANDLERS[task["op"]](self, task, legal[0])

    def _finish(self, t: dict) -> None:
        """Remove task t from the stack (by identity: sub-tasks it pushed stay)."""
        tasks = self.s.tasks
        for i in range(len(tasks) - 1, -1, -1):
            if tasks[i] is t:
                del tasks[i]
                return
        raise RuntimeError(f"task {t} not on the stack")

    # ================================================================================= small helpers
    def p(self, seat: int) -> Player:
        return self.s.players[seat]

    def stats(self, seat: int) -> E.Stats:
        return E.stats(self, seat)

    def touch(self, seat: int) -> None:
        E.touch(self.s.players[seat])

    def active_seats(self, first: int = None) -> list:
        n = self.num_players
        first = self.s.start_seat if first is None else first
        return [(first + k) % n for k in range(n) if self.s.players[(first + k) % n].resigned_order is None]

    def names_owned(self, seat: int) -> set:
        """Names of technologies in hand or in play (T4.4)."""
        p = self.p(seat)
        out = {NAME[c] for c in p.techs}
        out.add(NAME[p.government])
        out.update(NAME[c] for c in p.specials.values())
        out.update(NAME[c] for c in p.civil_hand if IS_TECH[c])
        return out

    def _remove_civil(self, card: int) -> None:
        if not IS_STARTING[card]:
            self.s.removed_civil.append(card)

    # ================================================================================= cards in play (T11.6, T11.9)
    def enter_play(self, seat: int, card: int) -> None:
        p = self.p(seat)
        p.play_order.append(card)
        E.touch(p)
        b, y = TOKEN_SYMBOLS[card]
        self.change_tokens(seat, b, y)
        effects.fire_card(self, "on_enter_play", seat, card)

    def leave_play(self, seat: int, card: int) -> None:
        p = self.p(seat)
        p.play_order.remove(card)
        E.touch(p)
        b, y = TOKEN_SYMBOLS[card]
        self.change_tokens(seat, -b, -y)
        effects.fire_card(self, "on_leave_play", seat, card)

    def change_tokens(self, seat: int, blue: int, yellow: int) -> None:
        """T11.9: tokens from/to the box. Losing blue tokens beyond the bank takes them from farms and mines (owner's
        choice, LOSE_BLUE); losing yellow tokens takes only what the yellow bank holds (D6)."""
        p = self.p(seat)
        if blue > 0:
            p.blue_bank += blue
            p.blue_owned += blue
        elif blue < 0:
            take = min(p.blue_bank, -blue)
            p.blue_bank -= take
            p.blue_owned -= take
            rest = -blue - take
            if rest and any(p.tokens.values()):
                self.s.tasks.append({"op": "lose_blue", "seat": seat, "n": rest, "to_box": True})
        if yellow > 0:
            p.yellow_bank += yellow
            p.yellow_owned += yellow
        elif yellow < 0:
            take = min(p.yellow_bank, -yellow)
            p.yellow_bank -= take
            p.yellow_owned -= take

    def apply_gain(self, seat: int, gain: dict, category: str, card=None) -> None:
        """Gains (or losses) in the written order: food, resources, science, culture, population, military cards."""
        p = self.p(seat)
        for k, v in gain.items():
            if k == "food":
                E.gain(p, "farm", v) if v > 0 else E.lose(p, "farm", -v)
            elif k == "resources":
                E.gain(p, "mine", v) if v > 0 else E.lose(p, "mine", -v)
            elif k == "science":
                E.add_science(p, v)
            elif k == "culture":
                E.add_culture(p, v, category, card)
            elif k == "population":
                if v > 0:                                                   # T11.7 gain population: free
                    k2 = min(v, p.yellow_bank)
                    p.yellow_bank -= k2
                    p.pool += k2
                else:                                                       # TODO stage 2: LOSE_WORKER choice
                    k2 = min(-v, p.pool)
                    p.pool -= k2
                    p.yellow_bank += k2
                E.touch(p)
            elif k == "military_cards":
                military.draw(self, seat, v)

    # ================================================================================= taking cards (T4)
    def take_cost(self, seat: int, slot: int) -> int:
        c = self.s.row[slot]
        cost = ROW_COST[slot]
        if KIND[c] == "wonder":
            p = self.p(seat)
            cost += len(p.wonders) + len(p.ruined)                          # T4.6
        return cost

    def can_take(self, seat: int, slot: int) -> bool:
        c = self.s.row[slot]
        if c is None:
            return False
        p = self.p(seat)
        if KIND[c] == "wonder":
            if p.unfinished is not None:                                    # T4.6
                return False
        else:
            if len(p.civil_hand) >= E.civil_hand_limit(self, seat):         # T4.3
                return False
            if IS_TECH[c] and NAME[c] in self.names_owned(seat):            # T4.4
                return False
            if KIND[c] == "leader" and AGE[c] in p.leaders_taken:           # T4.5
                return False
        return E.civil_available(self, seat) >= self.take_cost(seat, slot)  # T4.2

    def take(self, seat: int, slot: int) -> None:
        s, p = self.s, self.p(seat)
        c = s.row[slot]
        E.spend_civil(p, self.take_cost(seat, slot))
        s.row[slot] = None
        if KIND[c] == "wonder":
            p.unfinished = [c, 0, 0]                                        # T4.6: straight into play, unfinished
        else:
            p.civil_hand.append(c)
            p.taken_this_phase.append(c)
            if KIND[c] == "leader":
                p.leaders_taken.append(AGE[c])
        effects.fire(self, "on_take_card", seat, card=c, taker=seat)

    # ================================================================================= costs and options (T5, T6)
    def build_cost(self, seat: int, card: int, discount: int = 0) -> int:
        st = self.stats(seat)
        return max(0, RESOURCE_COST[card] - effects.urban_discount(st, card) - discount)

    def upgrade_cost(self, seat: int, frm: int, to: int, discount: int = 0) -> int:
        """T5.4: cost of the higher card minus cost of the lower card, both after modifiers."""
        st = self.stats(seat)
        hi = RESOURCE_COST[to] - effects.urban_discount(st, to)
        lo = RESOURCE_COST[frm] - effects.urban_discount(st, frm)
        return max(0, hi - lo - discount)

    def _action_ok(self, seat: int, unit: bool, free: bool) -> bool:
        if free:
            return True
        return (E.military_available if unit else E.civil_available)(self, seat) >= 1

    def build_options(self, seat: int, kinds: tuple = BUILDINGS, discount: int = 0, free: bool = False) -> list:
        """Technologies in play a worker can be built on now (T5.2, T5.3, T6.1)."""
        p = self.p(seat)
        unit = kinds[0] in UNITS
        if p.pool < 1 or not self._action_ok(seat, unit, free):
            return []
        res = E.resources(p)
        limit = self.stats(seat).urban_limit
        out = []
        for c in p.techs:
            k = KIND[c]
            if k not in kinds or self.build_cost(seat, c, discount) > res:
                continue
            if k in URBAN and E.urban_workers(p, k) >= limit:                  # T5.3
                continue
            out.append(c)
        return out

    def upgrade_to_options(self, seat: int, frm: int, discount: int = 0) -> list:
        p = self.p(seat)
        res = E.resources(p)
        return [c for c in p.techs if KIND[c] == KIND[frm] and LEVEL[c] > LEVEL[frm]
                and self.upgrade_cost(seat, frm, c, discount) <= res]

    def upgrade_from_options(self, seat: int, kinds: tuple = BUILDINGS, discount: int = 0, free: bool = False) -> list:
        p = self.p(seat)
        unit = kinds[0] in UNITS
        if not self._action_ok(seat, unit, free):
            return []
        return [c for c in p.techs if KIND[c] in kinds and p.workers.get(c, 0)
                and self.upgrade_to_options(seat, c, discount)]

    def destroy_options(self, seat: int, unit: bool = False) -> list:
        p = self.p(seat)
        if not self._action_ok(seat, unit, False):
            return []
        kinds = UNITS if unit else BUILDINGS
        return [c for c in p.techs if KIND[c] in kinds and p.workers.get(c, 0)]

    def wonder_max_stages(self, seat: int, discount: int = 0, free: bool = False) -> int:
        """Stages buildable in one action now (T5.7): 1, or more with a construction technology; 0 if none."""
        p = self.p(seat)
        if p.unfinished is None or not self._action_ok(seat, False, free):
            return 0
        card, paid, _ = p.unfinished
        costs = STAGE_COSTS[card][paid:]
        allowed = min(len(costs), self.stats(seat).wonder_stages)
        res = E.resources(p)
        k = 0
        for i in range(1, allowed + 1):
            if max(0, sum(costs[:i]) - discount) <= res:
                k = i
        return k

    def can_increase_population(self, seat: int, free_action: bool = False) -> bool:
        p = self.p(seat)
        cost = E.pop_cost(p.yellow_bank)                                       # T5.1, T1.8
        return cost is not None and (free_action or E.civil_available(self, seat) >= 1) and E.food(p) >= cost

    def can_peaceful(self, seat: int, card: int, free: bool = False) -> bool:
        return (free or E.civil_available(self, seat) >= 1) and self.p(seat).science >= SCIENCE_COST[card]

    def can_revolution(self, seat: int, card: int, free: bool = False, revolution_ok: bool = False) -> bool:
        """T5.9: all civil actions still available (a develop action card: they were before it was played)."""
        p = self.p(seat)
        if p.science < REVOLUTION_COST[card]:
            return False
        if free:
            return revolution_ok
        return p.civil_spent == 0 and self.stats(seat).civil >= 1

    def develop_options(self, seat: int, free: bool = False, exclude: int = None, revolution_ok: bool = None) -> list:
        """Technologies in hand that can be developed now. With a develop action card (free), a revolution needs all
        civil actions available before the card was played (revolution_ok; None = now, before playing it)."""
        p = self.p(seat)
        if free and revolution_ok is None:
            revolution_ok = p.civil_spent == 0 and self.stats(seat).civil >= 1
        out = []
        for c in sorted(set(p.civil_hand)):
            if c == exclude or not IS_TECH[c]:
                continue
            if KIND[c] == "government":
                ok = self.can_peaceful(seat, c, free) or self.can_revolution(seat, c, free, bool(revolution_ok))
            else:
                ok = (free or E.civil_available(self, seat) >= 1) and p.science >= SCIENCE_COST[c]
            if ok:
                out.append(c)
        return out

    def can_play_hand(self, seat: int, c: int) -> bool:
        p = self.p(seat)
        k = KIND[c]
        if IS_TECH[c]:
            return c in self.develop_options(seat)
        if E.civil_available(self, seat) < 1:
            return False
        if k == "leader":
            return True                                                         # T5.6
        if k == "action":                                                       # T5.10
            return c not in p.taken_this_phase and effects.can_play_action(self, seat, c)
        return False

    # ================================================================================= civil actions (T5, T6)
    def increase_population(self, seat: int, free_action: bool = False) -> None:
        p = self.p(seat)
        cost = E.pop_cost(p.yellow_bank)
        if not free_action:
            E.spend_civil(p, 1)
        E.pay(p, "farm", cost)
        p.yellow_bank -= 1                                                      # rightmost yellow token -> pool
        p.pool += 1
        E.touch(p)

    def build(self, seat: int, card: int, discount: int = 0, free: bool = False) -> None:
        p = self.p(seat)
        cost = self.build_cost(seat, card, discount)
        if not free:
            (E.spend_military if IS_UNIT[card] else E.spend_civil)(p, 1)
        E.pay(p, "mine", cost)
        p.pool -= 1
        p.workers[card] = p.workers.get(card, 0) + 1
        E.touch(p)

    def upgrade(self, seat: int, frm: int, to: int, discount: int = 0, free: bool = False) -> None:
        p = self.p(seat)
        cost = self.upgrade_cost(seat, frm, to, discount)
        if not free:
            (E.spend_military if IS_UNIT[frm] else E.spend_civil)(p, 1)
        E.pay(p, "mine", cost)
        p.workers[frm] -= 1
        p.workers[to] = p.workers.get(to, 0) + 1
        E.touch(p)

    def destroy(self, seat: int, card: int) -> None:
        p = self.p(seat)
        (E.spend_military if IS_UNIT[card] else E.spend_civil)(p, 1)
        p.workers[card] -= 1
        p.pool += 1
        E.touch(p)

    def develop(self, seat: int, c: int, free: bool = False, revolution: bool = False) -> None:
        """T5.8 develop a technology; T5.9 revolution."""
        p = self.p(seat)
        p.civil_hand.remove(c)
        before = E.totals(self, seat)
        if revolution:
            p.civil_spent = before[0]
            p.temp_civil = 0
            E.add_science(p, -REVOLUTION_COST[c])
        else:
            if not free:
                E.spend_civil(p, 1)
            E.add_science(p, -SCIENCE_COST[c])
        k = KIND[c]
        if k == "government":
            old = p.government
            self.leave_play(seat, old)
            self._remove_civil(old)
            p.government = c
            self.enter_play(seat, c)
        elif k in SPECIALS:
            old = p.specials.get(k)
            if old is not None and LEVEL[old] >= LEVEL[c]:
                self._remove_civil(c)                                           # lower one leaves at once
            else:
                if old is not None:
                    self.leave_play(seat, old)
                    self._remove_civil(old)
                p.specials[k] = c
                self.enter_play(seat, c)
        else:
            p.techs.append(c)
            self.enter_play(seat, c)
        E.settle_totals(self, seat, before, revolution=revolution)
        effects.fire(self, "on_develop", seat, card=c, developer=seat, revolution=revolution)

    def play_leader(self, seat: int, c: int) -> None:
        """T5.6."""
        p = self.p(seat)
        E.spend_civil(p, 1)
        p.civil_hand.remove(c)
        before = E.totals(self, seat)
        old = p.leader
        if old is not None:
            self.leave_play(seat, old)
            p.left_play.append(old)
        p.leader = c
        self.enter_play(seat, c)
        E.settle_totals(self, seat, before)
        if old is not None:
            p.civil_spent = max(0, p.civil_spent - 1)                           # one civil action back
            effects.fire(self, "on_leader_replaced", seat, old=old, new=c, owner=seat)

    def play_action_card(self, seat: int, c: int) -> None:
        """T5.10."""
        p = self.p(seat)
        p.flags["all_civil_before_action"] = p.civil_spent == 0 and self.stats(seat).civil >= 1
        E.spend_civil(p, 1)
        p.civil_hand.remove(c)
        self.s.removed_civil.append(c)
        effects.play_action(self, seat, c)

    def complete_wonder(self, seat: int) -> None:
        """T5.7: tokens go back to the blue bank and the wonder's effects start."""
        p = self.p(seat)
        card, _, tok = p.unfinished
        p.blue_bank += tok
        p.unfinished = None
        before = E.totals(self, seat)
        p.wonders.append(card)
        self.enter_play(seat, card)
        E.settle_totals(self, seat, before)
        effects.fire_card(self, "on_wonder_complete", seat, card)

    # ================================================================================= card row and ages (T4.1, T13)
    def refill(self) -> None:
        s = self.s
        k = ROW_DISCARD[max(2, len(self.active_seats()))]
        for c in s.row[:k]:
            if c is not None:
                s.removed_civil.append(c)                                       # discarded civil cards leave
        rest = [c for c in s.row[k:] if c is not None]
        s.row = rest + [None] * (ROW_SIZE - len(rest))
        if s.age == "A":                                                        # T13.1
            self._deal()
            self.begin_age("I")
        self._deal()

    def _deal(self) -> None:
        s = self.s
        for i in range(ROW_SIZE):
            if s.row[i] is not None:
                continue
            if not s.civil_deck:
                break
            c = s.civil_deck.draw()
            if c >= LEADER_PROXY:                                               # T15.9: proxy -> board card
                sel = s.selection[s.age]
                c = sel["leaders"][c - LEADER_PROXY] if c < WONDER_PROXY else sel["wonders"][c - WONDER_PROXY]
                s.proxies_used += 1
                s.civil_created += 1
            s.row[i] = c
            if not s.civil_deck and s.age in ("I", "II", "III"):               # T13.2
                self.begin_age(NEXT_AGE[s.age])

    def build_civil_deck(self, age: str) -> Deck:
        s = self.s
        n = max(2, len(self.active_seats()))
        sel = s.selection[age]
        cards = civil_deck_cards(age, n)
        proxies = [LEADER_PROXY + k for k in range(len(sel["leaders"]))] + \
                  [WONDER_PROXY + k for k in range(len(sel["wonders"]))]
        deck = Deck(cards + proxies)
        deck.shuffle(self.rng)
        s.civil_created += len(cards)
        s.proxies_created += len(proxies)
        return deck

    def begin_age(self, new: str) -> None:
        s = self.s
        old = s.age
        s.age = new
        s.log.add(None, f"Age {new} begins")
        if old == "A":
            s.removed_civil += list(s.civil_deck)                               # T13.1: rest of Age A leaves
        s.civil_deck = self.build_civil_deck(new) if new != "IV" else Deck()
        s.removed_military += list(s.military_deck) + s.military_discard        # T13.5, D7
        s.military_discard = []
        if new != "IV":
            mil = Deck(military_deck_cards(new, max(2, len(self.active_seats()))))
            mil.shuffle(self.rng)
            s.military_created += len(mil)
            s.military_deck = mil
        else:
            s.military_deck = Deck()
        if new in ("II", "III", "IV"):
            antiquated = {"II": "A", "III": "I", "IV": "II"}[new]
            for seat in self.active_seats():
                self.antiquate(seat, antiquated)                                # T13.3
                self.change_tokens(seat, 0, -2)                                 # T13.4
        effects.fire(self, "age_start", s.turn_seat, age=new)
        if new == "IV":                                                         # T14.1
            s.last_round = s.round if s.turn_seat == s.round_first else s.round + 1
            s.log.add(None, f"Round {s.last_round} is the last round")

    def antiquate(self, seat: int, age: str) -> None:
        s, p = self.s, self.p(seat)
        keep = []
        for c in p.civil_hand:
            (s.removed_civil.append(c) if AGE[c] == age else keep.append(c))
        p.civil_hand = keep
        keep = []
        for c in p.military_hand:
            (s.removed_military.append(c) if AGE[c] == age else keep.append(c))
        p.military_hand = keep
        if p.leader is not None and AGE[p.leader] == age:
            before = E.totals(self, seat)
            old = p.leader
            p.leader = None
            self.leave_play(seat, old)
            p.left_play.append(old)
            E.settle_totals(self, seat, before)
        if p.unfinished is not None and AGE[p.unfinished[0]] == age:
            card, _, tok = p.unfinished
            p.blue_bank += tok
            p.unfinished = None
            s.removed_civil.append(card)

    # ================================================================================= end of turn (T3.6, T12)
    def production(self, seat: int) -> None:
        s, p = self.s, self.p(seat)
        if E.discontent(self, seat) > p.pool:                                   # T11.8
            s.log.add(seat, "Uprising: no production")
            return
        st = self.stats(seat)
        E.add_science(p, st.science)                                            # T3.6 (3)
        cult = E.book_culture_rating(self, seat)
        missing = E.lose(p, "mine", E.corruption(p.blue_bank))                  # T12.5
        if missing:
            E.lose(p, "farm", missing)
        E.produce(p, "farm")                                                    # T12.6
        if st.food_bonus:
            E.gain(p, "farm", st.food_bonus) if st.food_bonus > 0 else E.lose(p, "farm", -st.food_bonus)
        missing = E.lose(p, "farm", E.consumption(p.yellow_bank))               # T12.7
        lost = E.add_culture(p, -4 * missing, "famine") if missing else 0
        E.produce(p, "mine")                                                    # T12.8
        if st.resource_bonus:                                                   # T15.6
            E.gain(p, "mine", st.resource_bonus) if st.resource_bonus > 0 else E.lose(p, "mine", -st.resource_bonus)
        s.log.add(seat, f"Production: +{st.science} science, +{cult} culture"
                        + (f", famine {lost} culture" if missing else ""))

    # ================================================================================= results (T14.3, PLAN 7)
    def breakdowns(self) -> list:
        out = []
        for p in self.s.players:
            b = {k: 0 for k in CATEGORIES}
            for (cat, _), v in p.culture_book.items():
                b[cat] += v
            if p.resigned_order is not None:
                b["resigned"] = self._score(p) - sum(v for k, v in b.items() if k != "resigned")
            out.append(b)
        return out

    def _score(self, p) -> int:
        if p.resigned_order is None:
            return p.culture
        return -1 - (self.s.resigned - 1 - p.resigned_order)                   # C5: later resignation ranks higher

    def scores(self) -> list:
        return [self._score(p) for p in self.s.players]

    def tiebreaks(self):
        return None

    def card_points(self, seat: int) -> dict:
        out = {}
        for (_, c), v in self.p(seat).culture_book.items():
            if c is not None:
                out[c] = out.get(c, 0) + v
        return out

    def tableau(self, seat: int) -> list:
        p = self.p(seat)
        pts = self.card_points(seat)
        cards = [p.government] + list(p.techs) + list(p.specials.values()) + \
                ([p.leader] if p.leader is not None else []) + p.wonders + p.colonies + p.left_play
        rows = []
        for i, c in enumerate(cards):
            rows.append({"item": KEY[c], "kind": KIND[c], "group": AGE[c], "slot": i, "host": None,
                         "points": int(pts.get(c, 0)), "tags": {"kind": KIND[c], "age": AGE[c], "set": SET[c]}})
        return rows

    def seat_extra(self, seat: int) -> dict:
        p = self.p(seat)
        st = self.stats(seat)
        return {"science": p.science, "strength": military.strength(self, seat), "culture_rating": st.culture,
                "science_rating": st.science, "rounds": self.s.round, "workers": self.workers_total(seat),
                "hand_left": [KEY[c] for c in p.civil_hand + p.military_hand]}

    def workers_total(self, seat: int) -> int:
        p = self.p(seat)
        return p.pool + sum(p.workers.values())

    # ================================================================================= text
    def describe(self, a: int) -> str:
        from .describe import describe
        return describe(self, a)

    def record_info(self, a: int) -> dict:
        from .describe import record_info
        return record_info(self, a)

    def text_state(self) -> str:
        from .describe import text_state
        return text_state(self)


# ===================================================================================================== task handlers
# handler(game, task, answer): answer None = make progress (ask, push sub-tasks, or finish); else apply the answer.

def h_game(g: Game, t: dict, a):
    """Rounds: each starts with the first seat still in the game from the starting player (T2.7, T7.2)."""
    s = g.s
    while t["queue"]:
        seat = t["queue"].pop(0)
        if s.players[seat].resigned_order is None:
            s.tasks.append({"op": "turn", "seat": seat, "stage": "start"})
            return
    active = g.active_seats()
    if s.round and (s.last_round == s.round or len(active) <= 1):               # T14.1, T7.2
        effects.final_events(g)                                                 # T14.2
        effects.fire(g, "game_end", s.start_seat)
        s.game_over = True
        s.phase = "over"
        s.decisions.clear()
        s.log.add(None, "Game over: " + ", ".join(f"P{i} {x}" for i, x in enumerate(g.scores())))
        return
    s.round += 1
    s.round_first = active[0]
    t["queue"] = list(active)
    s.log.add(None, f"Round {s.round}")


def h_turn(g: Game, t: dict, a):
    s, seat = g.s, t["seat"]
    st = t["stage"]
    if st == "start":                                                           # T3.3
        s.turn_seat = seat
        s.phase = "start"
        if s.round > 1:
            g.refill()
        # TODO stage 2: resolve this player's war (T9.5), move the exclusive tactic to the common area
        effects.fire(g, "start_of_turn", seat, owner=seat)
        t["stage"] = "politics"
    elif st == "politics":                                                      # T3.4 (skipped in round 1, T3.2)
        t["stage"] = "actions"
        if s.round > 1:
            s.phase = "politics"
            s.tasks.append({"op": "politics", "seat": seat})
    elif st == "actions":                                                       # T3.5
        s.phase = "actions"
        g.p(seat).taken_this_phase = []
        effects.fire(g, "start_of_action_phase", seat, owner=seat)
        s.tasks.append({"op": "actions", "seat": seat})
        t["stage"] = "end"
    elif st == "end":                                                           # T3.6
        s.phase = "end"
        s.tasks.append({"op": "end_turn", "seat": seat, "step": "discard"})
        t["stage"] = "done"
    else:
        s.turns += 1
        g._finish(t)


def h_politics(g: Game, t: dict, a):
    """T3.4 / T7: stage 1 offers only END (political actions come in stage 2)."""
    if a is None:
        g._ask("POLITICS", t["seat"], [A_END])
        return
    g._finish(t)


def action_legal(g: Game, seat: int) -> list:
    """ACTION answers that have a legal completion (PLAN 3, 5)."""
    s, p = g.s, g.p(seat)
    legal = [A_END]
    legal += [A_ROW + i for i in range(ROW_SIZE) if g.can_take(seat, i)]
    if s.round == 1:                                                            # T3.2: only take cards
        return legal
    if E.civil_available(g, seat) >= 1:
        if g.can_increase_population(seat):
            legal.append(A_VERB + V["INCREASE_POP"])
        if g.build_options(seat, BUILDINGS):
            legal.append(A_VERB + V["BUILD"])
        if g.upgrade_from_options(seat, BUILDINGS):
            legal.append(A_VERB + V["UPGRADE"])
        if g.destroy_options(seat):
            legal.append(A_VERB + V["DESTROY"])
        if g.wonder_max_stages(seat):
            legal.append(A_VERB + V["WONDER_STAGE"])
    if E.military_available(g, seat) >= 1:
        if g.build_options(seat, UNITS):
            legal.append(A_VERB + V["BUILD_UNIT"])
        if g.upgrade_from_options(seat, UNITS):
            legal.append(A_VERB + V["UPGRADE_UNIT"])
        if g.destroy_options(seat, unit=True):
            legal.append(A_VERB + V["DISBAND"])
    for c in sorted(set(p.civil_hand)):
        if g.can_play_hand(seat, c):
            legal.append(A_CARD + c)
    return legal


def h_actions(g: Game, t: dict, a):
    seat = t["seat"]
    if a is None:
        g._ask("ACTION", seat, action_legal(g, seat))
        return
    s = g.s
    seg, off = CODEC.decode(a)
    if seg == "END":
        g._finish(t)
    elif seg == "ROW":
        g.take(seat, off)
    elif seg == "VERB":
        verb = VERBS[off]
        if verb == "INCREASE_POP":
            g.increase_population(seat)
        elif verb in ("BUILD", "BUILD_UNIT"):
            s.tasks.append({"op": "build", "seat": seat, "kinds": UNITS if verb == "BUILD_UNIT" else BUILDINGS,
                            "discount": 0, "free": False, "card": None})
        elif verb in ("UPGRADE", "UPGRADE_UNIT"):
            s.tasks.append(g_upgrade_task(seat, UNITS if verb == "UPGRADE_UNIT" else BUILDINGS, 0, False, None))
        elif verb in ("DESTROY", "DISBAND"):
            s.tasks.append({"op": "destroy", "seat": seat, "unit": verb == "DISBAND"})
        elif verb == "WONDER_STAGE":
            s.tasks.append({"op": "wonder", "seat": seat, "discount": 0, "free": False, "card": None})
    else:                                                                       # CARD from the civil hand
        k = KIND[off]
        if IS_TECH[off]:
            s.tasks.append({"op": "develop", "seat": seat, "card": off, "free": False, "then_gain": None,
                            "source": None, "revolution_ok": False})
        elif k == "leader":
            g.play_leader(seat, off)
        elif k == "action":
            g.play_action_card(seat, off)


def g_upgrade_task(seat, kinds, discount, free, source) -> dict:
    return {"op": "upgrade", "seat": seat, "kinds": kinds, "discount": discount, "free": free, "frm": None,
            "card": source}


Game.upgrade_task = staticmethod(g_upgrade_task)


def h_build(g: Game, t: dict, a):
    seat = t["seat"]
    unit = t["kinds"][0] in UNITS
    if a is None:
        g._ask("CHOOSE_TECH", seat, [A_CARD + c for c in g.build_options(seat, t["kinds"], t["discount"], t["free"])],
               verb=BUILD_VERB[unit])
        return
    g._finish(t)
    g.build(seat, a - A_CARD, t["discount"], t["free"])


def h_upgrade(g: Game, t: dict, a):
    seat = t["seat"]
    unit = t["kinds"][0] in UNITS
    if t["frm"] is None:
        if a is None:
            g._ask("CHOOSE_TECH", seat, [A_CARD + c for c in g.upgrade_from_options(seat, t["kinds"], t["discount"],
                                                                                     t["free"])],
                   verb=UPGRADE_VERB[unit])
            return
        t["frm"] = a - A_CARD
        a = None
    if a is None:
        g._ask("UPGRADE_TO", seat, [A_CARD + c for c in g.upgrade_to_options(seat, t["frm"], t["discount"])],
               verb=UPGRADE_VERB[unit], frm=t["frm"])
        return
    g._finish(t)
    g.upgrade(seat, t["frm"], a - A_CARD, t["discount"], t["free"])


def h_destroy(g: Game, t: dict, a):
    seat = t["seat"]
    if a is None:
        g._ask("CHOOSE_TECH", seat, [A_CARD + c for c in g.destroy_options(seat, t["unit"])],
               verb=DESTROY_VERB[t["unit"]])
        return
    g._finish(t)
    g.destroy(seat, a - A_CARD)


def h_wonder(g: Game, t: dict, a):
    """T5.7: choose how many stages (STAGES, with a construction technology), pay, cover each stage with a blue
    token from the bank (from farms/mines if the bank is empty: LOSE_BLUE), complete."""
    seat = t["seat"]
    p = g.p(seat)
    if "stages" not in t:
        if a is None:
            k = g.wonder_max_stages(seat, t["discount"], t["free"])
            g._ask("STAGES", seat, [A_AMOUNT + i for i in range(k)], card=p.unfinished[0])
            return
        t["stages"] = a - A_AMOUNT + 1
        a = None
    if "left" not in t:
        card, paid, _ = p.unfinished
        cost = max(0, sum(STAGE_COSTS[card][paid:paid + t["stages"]]) - t["discount"])
        if not t["free"]:
            E.spend_civil(p, 1)
        E.pay(p, "mine", cost)
        t["left"] = t["stages"]
    if a is not None:                                                           # LOSE_BLUE answer
        p.tokens[a - A_CARD] -= 1
        if not p.tokens[a - A_CARD]:
            del p.tokens[a - A_CARD]
        p.unfinished[2] += 1
        _stage_done(g, t, p)
    while t["left"]:
        if p.blue_bank > 0:
            p.blue_bank -= 1
            p.unfinished[2] += 1
        elif any(p.tokens.values()):
            g._ask("LOSE_BLUE", seat, [A_CARD + c for c, k in p.tokens.items() if k], purpose="wonder")
            return
        _stage_done(g, t, p)
    g._finish(t)
    if p.unfinished[1] >= len(STAGE_COSTS[p.unfinished[0]]):
        g.complete_wonder(seat)


def _stage_done(g: Game, t: dict, p) -> None:
    p.unfinished[1] += 1
    t["left"] -= 1
    effects.fire_card(g, "on_wonder_stage", t["seat"], p.unfinished[0])


def h_develop(g: Game, t: dict, a):
    seat = t["seat"]
    if t["card"] is None:                                                       # develop action card: which card
        if a is None:
            g._ask("SUB_ACTION", seat, [A_CARD + c for c in g.develop_options(seat, True, t["source"], t["revolution_ok"])],
                   verb="DEVELOP", source=t["source"])
            return
        t["card"] = a - A_CARD
        a = None
    c = t["card"]
    if KIND[c] == "government" and "revolution" not in t:
        peace = g.can_peaceful(seat, c, t["free"])
        rev = g.can_revolution(seat, c, t["free"], t["revolution_ok"])
        if peace and rev:
            if a is None:
                g._ask("REVOLT", seat, [A_YES, A_NO], card=c)
                return
            t["revolution"] = a == A_YES
        else:
            t["revolution"] = rev
    g._finish(t)
    g.develop(seat, c, t["free"], t.get("revolution", False))
    if t["then_gain"]:
        g.apply_gain(seat, t["then_gain"], "actions", t["source"])


def h_sub_action(g: Game, t: dict, a):
    """Action cards with a choice of build or upgrade (Rich Land, Urban Growth)."""
    seat = t["seat"]
    if a is None:
        legal = []
        if g.build_options(seat, t["kinds"], t["discount"], True):
            legal.append(A_VERB + V["BUILD"])
        if g.upgrade_from_options(seat, t["kinds"], t["discount"], True):
            legal.append(A_VERB + V["UPGRADE"])
        g._ask("SUB_ACTION", seat, legal, verb="BUILD_OR_UPGRADE", source=t["card"])
        return
    g._finish(t)
    if a == A_VERB + V["BUILD"]:
        g.s.tasks.append({"op": "build", "seat": seat, "kinds": t["kinds"], "discount": t["discount"], "free": True,
                          "card": t["card"]})
    else:
        g.s.tasks.append(g_upgrade_task(seat, t["kinds"], t["discount"], True, t["card"]))


def h_choose_gain(g: Game, t: dict, a):
    if a is None:
        g._ask("SUB_ACTION", t["seat"], [A_OPTION + i for i in range(len(t["options"]))], verb="GAIN",
               options=t["options"], source=t["card"])
        return
    g._finish(t)
    g.apply_gain(t["seat"], t["options"][a - A_OPTION], "actions", t["card"])


def h_lose_blue(g: Game, t: dict, a):
    """T11.9: lose blue tokens the bank could not give, from farms and mines of the owner's choice."""
    p = g.p(t["seat"])
    if a is not None:
        c = a - A_CARD
        p.tokens[c] -= 1
        if not p.tokens[c]:
            del p.tokens[c]
        p.blue_owned -= 1
        t["n"] -= 1
    if t["n"] <= 0 or not any(p.tokens.values()):
        g._finish(t)
        return
    g._ask("LOSE_BLUE", t["seat"], [A_CARD + c for c, k in p.tokens.items() if k], purpose="box")


def h_end_turn(g: Game, t: dict, a):
    """T3.6: discard military cards to the limit, end-of-turn effects, uprising check, production, draw, reset."""
    s, seat = g.s, t["seat"]
    p = g.p(seat)
    if t["step"] == "discard":
        if a is not None:
            c = a - A_CARD
            p.military_hand.remove(c)
            military.discard(g, c)
        if len(p.military_hand) > E.military_hand_limit(g, seat):
            g._ask("DISCARD_MILITARY", seat, [A_CARD + c for c in p.military_hand])
            return
        t["step"] = "effects"
        effects.fire(g, "end_of_turn", seat, owner=seat)
        return
    g._finish(t)
    g.production(seat)                                                          # T3.6 (2)-(3)
    military.draw(g, seat, min(3, E.military_available(g, seat)))               # T3.7
    p.civil_spent = p.military_spent = 0                                        # T3.6 (5)
    p.temp_civil = p.temp_military = 0
    p.temp = {}
    p.flags = {}


HANDLERS = {"game": h_game, "turn": h_turn, "politics": h_politics, "actions": h_actions, "build": h_build,
            "upgrade": h_upgrade, "destroy": h_destroy, "wonder": h_wonder, "develop": h_develop,
            "sub_action": h_sub_action, "choose_gain": h_choose_gain, "lose_blue": h_lose_blue,
            "end_turn": h_end_turn}


# ===================================================================================================== invariants
def invariants(g) -> list:
    """Card and token conservation and limits (PLAN 9), checked by bgai.checks during random games."""
    s = g.s
    out = []
    civil = len(s.row) - s.row.count(None) + len(s.removed_civil)
    proxies = 0
    for c in s.civil_deck:
        if c >= LEADER_PROXY:
            proxies += 1
        else:
            civil += 1
    mil = len(s.military_deck) + len(s.military_discard) + len(s.age_a_unused) + len(s.current_events) + \
        len(s.future_events) + len(s.past_events) + len(s.removed_military) + len(s.common_tactics)
    for p in s.players:
        civil += len(p.civil_hand) + len(p.wonders) + len(p.ruined) + len(p.left_play)
        civil += sum(not IS_STARTING[c] for c in p.techs) + sum(1 for c in p.specials.values())
        civil += (not IS_STARTING[p.government]) + (p.leader is not None) + (p.unfinished is not None)
        mil += len(p.military_hand) + len(p.colonies)
        tag = f"P{p.seat}"
        on_cards = sum(p.tokens.values()) + (p.unfinished[2] if p.unfinished else 0)
        if p.blue_bank < 0 or any(k < 0 for k in p.tokens.values()):
            out.append(f"{tag} negative blue tokens")
        if p.blue_bank + on_cards != p.blue_owned:
            out.append(f"{tag} blue tokens {p.blue_bank}+{on_cards} != {p.blue_owned}")
        workers = sum(p.workers.values())
        if min([p.yellow_bank, p.pool] + list(p.workers.values())) < 0:
            out.append(f"{tag} negative yellow tokens")
        if p.yellow_bank + p.pool + workers != p.yellow_owned:
            out.append(f"{tag} yellow tokens {p.yellow_bank}+{p.pool}+{workers} != {p.yellow_owned}")
        if any(c not in p.techs for c, k in p.workers.items() if k):
            out.append(f"{tag} workers on a card not in play")
        if any(KIND[c] not in ("farm", "mine") or c not in p.techs for c, k in p.tokens.items() if k):
            out.append(f"{tag} blue tokens on a card that is not a farm or mine in play")
        if p.culture < 0 or p.science < 0:
            out.append(f"{tag} negative points")
        st = E.compute_stats(g, p)
        if p.civil_spent > st.civil or p.military_spent > st.military:
            out.append(f"{tag} spent actions above total ({p.civil_spent}/{st.civil}, {p.military_spent}/{st.military})")
        if p.unfinished is not None and p.unfinished[1] >= len(STAGE_COSTS[p.unfinished[0]]):
            out.append(f"{tag} finished wonder still unfinished")
        expected_play = [p.government] + p.techs + list(p.specials.values()) + \
            ([p.leader] if p.leader is not None else []) + p.wonders + p.colonies
        if sorted(expected_play) != sorted(p.play_order):
            out.append(f"{tag} play order {p.play_order} does not match the cards in play")
        if any(TOKEN_VALUE[c] <= 0 for c in p.tokens):
            out.append(f"{tag} token on a card without a value")
    if civil != s.civil_created:
        out.append(f"civil cards {civil} != {s.civil_created}")
    if proxies + s.proxies_used != s.proxies_created:
        out.append(f"proxies {proxies}+{s.proxies_used} != {s.proxies_created}")
    if mil != s.military_created:
        out.append(f"military cards {mil} != {s.military_created}")
    if any(AGE[c] != s.age for c in s.military_discard):
        out.append("military discard holds a card of another age")
    return out
