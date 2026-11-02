"""Through the Ages engine: the bgai.game.Game contract, the task stack and the turn flow (PLAN.md sections 3-5, 7, 9).

Rule IDs refer to rules.md. Stage 1 (PLAN section 13, steps 1-3): a complete peaceful game. Stage 2 (steps 4-5):
tactics and armies, the politics phase, events, colonization, aggressions, wars, pacts, resignation and every
military card (politics.py, military.py, effects.py). Stage 3 (steps 6-7): every civil card effect (civil.py; the
rule-level parts in this module: Gutenberg, take costs, discounts, Harvard, Silk Road, Louvre, Red Cross).

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
from .cards import (AGE, BUILDINGS, EFFECT, EFFECT_TYPE, IS_STARTING, IS_TECH, IS_UNIT, KEY, KIND,
                    LEADERS_BY_AGE, LEVEL, N_CARDS, NAME, NEXT_AGE, RESOURCE_COST, REVOLUTION_COST,
                    SCIENCE_COST, SET, SPECIALS, STAGE_COSTS, TOKEN_SYMBOLS, UNITS, URBAN,
                    WONDERS_BY_AGE, civil_deck_cards, military_deck_cards)
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
         "COPY_TACTIC", "PREPARE", "AGGRESSION", "WAR", "PACT", "CANCEL_PACT", "RESIGN",
         # 15..31: card abilities (frozen once a model exists; 27..31 spare)
         "ALEXANDER", "COLUMBUS", "CATHERINE", "OLYMPICS",                          # political (POLITICS)
         "HAMMURABI", "BARBAROSSA", "OCEAN_LINER", "BACH", "CHURCHILL", "LOUVRE", "RED_CROSS",   # ACTION
         "GUTENBERG")                                                               # ACTION (review F14, D30)
assert len(VERBS) <= 32
V = {name: i for i, name in enumerate(VERBS)}
VERB_TEXT = {"INCREASE_POP": "Increase population", "BUILD": "Build a farm, mine or urban building",
             "UPGRADE": "Upgrade a farm, mine or urban building", "DESTROY": "Destroy a farm, mine or urban building",
             "BUILD_UNIT": "Build a military unit", "UPGRADE_UNIT": "Upgrade a military unit",
             "DISBAND": "Disband a military unit", "WONDER_STAGE": "Build a wonder stage",
             "ALEXANDER": "Alexander the Great: remove him for 1 yellow token",
             "COLUMBUS": "Christopher Columbus: remove him to colonize a territory from hand",
             "CATHERINE": "Catherine the Great: weaker civilizations lose a yellow token",
             "OLYMPICS": "Pierre de Coubertin: declare the Olympic Games",
             "HAMMURABI": "Hammurabi: use a military action as a civil action",
             "BARBAROSSA": "Frederick Barbarossa: increase population and build a unit",
             "OCEAN_LINER": "Ocean Liner Service: free population increase",
             "BACH": "Bach: upgrade an urban building to a theater",
             "CHURCHILL": "Winston Churchill: choose his bonus",
             "LOUVRE": "Louvre Museum: return a token for 2 resources",
             "RED_CROSS": "International Red Cross: build a stage of another player's Red Cross",
             "GUTENBERG": "Johannes Gutenberg: use his extra civil action for the next lab or library action"}

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

    def card_name(self, c: int) -> str:
        return f"{NAME[c]} ({AGE[c]})"

    def remove_leader(self, seat: int) -> None:
        """The leader leaves play (Iconoclasm, Infiltrate, antiquated); kept in left_play for the tableau."""
        p = self.p(seat)
        before = E.totals(self, seat)
        old = p.leader
        p.leader = None
        self.leave_play(seat, old)
        p.left_play.append(old)
        E.settle_totals(self, seat, before)

    def ruin_wonder(self, seat: int, c: int) -> None:
        """Ravages of Time: the wonder is turned face down: no effects, 2 culture instead (economy.compute_stats)."""
        p = self.p(seat)
        before = E.totals(self, seat)
        p.wonders.remove(c)
        p.ruined.append(c)
        self.leave_play(seat, c)
        E.settle_totals(self, seat, before)
        for q in self.s.players:                                            # International Tourism counts wonders
            E.touch(q)

    def steal_special(self, seat: int, victim: int, c: int) -> None:
        """T9.6: a special technology moves from the loser to the victor; of two of the same type only the higher
        level stays (an equal or lower stolen card leaves the game)."""
        v, p = self.p(victim), self.p(seat)
        k = KIND[c]
        b0, b1 = E.totals(self, victim), E.totals(self, seat)
        del v.specials[k]
        self.leave_play(victim, c)
        E.settle_totals(self, victim, b0)
        old = p.specials.get(k)
        if old is not None and LEVEL[old] >= LEVEL[c]:
            self._remove_civil(c)
        else:
            if old is not None:
                self.leave_play(seat, old)
                self._remove_civil(old)
            p.specials[k] = c
            self.enter_play(seat, c)
        E.settle_totals(self, seat, b1)

    # ================================================================================= paying (T12.3, T12.9, pacts)
    def trade_conversion(self, seat: int, kind: str) -> int:
        """Trade Routes Agreement: side A may use food as resources, side B resources as food, 1 for 1, during its own
        turn, as often as it likes (D33); used automatically only when needed to pay (choice C1). Returns how much of
        the other kind could be used."""
        if self.s.turn_seat != seat:
            return 0
        p = self.p(seat)
        for owner, card, partner, side in military.pacts_in_play(self):
            if EFFECT_TYPE[card] != "pact_trade_routes":
                continue
            sd = military.side_of(owner, partner, side, seat)
            if (sd == "A" and kind == "mine") or (sd == "B" and kind == "farm"):
                return E.total(p, "farm" if kind == "mine" else "mine")
        return 0

    def afford(self, seat: int, kind: str, amount: int, purpose=None) -> bool:
        """Can pay `amount` food ('farm') or resources ('mine'): tokens + temporary ones for this purpose (T12.9) +
        a Trade Routes conversion."""
        if amount <= 0:
            return True
        p = self.p(seat)
        have = E.total(p, kind)
        if purpose and p.temp:
            have += p.temp.get(purpose, 0)
        return have >= amount or have + self.trade_conversion(seat, kind) >= amount

    def pay(self, seat: int, kind: str, amount: int, purpose=None) -> None:
        """T12.9: temporary food/resources for this purpose are spent first; then tokens (C1); Trade Routes only
        when the tokens are not enough. Purposes: 'unit' (build/upgrade military units: Patriotism, Homer, ...),
        'civic' (urban buildings and wonder stages: Cleopatra)."""
        p = self.p(seat)
        if purpose and p.temp.get(purpose):
            use = min(p.temp[purpose], amount)
            p.temp[purpose] -= use
            amount -= use
        if amount <= 0:
            return
        short = amount - E.total(p, kind)
        if short > 0 and self.trade_conversion(seat, kind):
            E.pay(p, "farm" if kind == "mine" else "mine", short)
            amount -= short
        E.pay(p, kind, amount)

    @staticmethod
    def purpose_of(card: int):
        """Which temporary resources may pay for building/upgrading this card (T12.9)."""
        return "unit" if IS_UNIT[card] else "civic" if KIND[card] in URBAN else None

    # ================================================================================= Gutenberg
    # Johannes Gutenberg's extra civil action (NLW p8, D30) is optional: the ACTION verb GUTENBERG ("arming") says
    # that the next action uses it; then only lab/library actions are legal (take, develop, build, upgrade, or an
    # action card used for one of these), which spend it instead of a civil action, with his discount and culture.
    def gutenberg_ready(self, seat: int) -> bool:
        """Johannes Gutenberg's extra civil action of this turn is still unused and not chosen yet."""
        p = self.p(seat)
        return effects.leader_type(p) == "gutenberg" and not p.flags.get("gutenberg_used") and \
            not p.flags.get("gutenberg_armed")

    def gutenberg_armed(self, seat: int) -> bool:
        return bool(self.p(seat).flags.get("gutenberg_armed"))

    def gutenberg_for(self, seat: int, kind: str, free: bool = False) -> bool:
        """Gutenberg's action pays for this action (chosen, a lab or library, not a free action)."""
        return not free and kind in EFFECT_GUTENBERG_KINDS and self.gutenberg_armed(seat)

    def use_gutenberg(self, seat: int) -> None:
        p = self.p(seat)
        p.flags["gutenberg_used"] = True
        p.flags["gutenberg_armed"] = False
        E.add_culture(p, EFFECT[p.leader]["culture_per_use"], "leaders", p.leader)

    def move_cost(self, seat: int, frm: int, to: int) -> int:
        """Freedom of Movement: the cost difference as for upgrading (both after modifiers), if positive."""
        return max(0, self.build_cost(seat, to) - self.build_cost(seat, frm))

    # ================================================================================= science (T5.8, pacts)
    def sci_coop_partner(self, seat: int):
        """(partner, discount, partner pays) of a Scientific Cooperation pact the player is party to, or None."""
        for q in self.s.players:
            if q.pact is not None and EFFECT_TYPE[q.pact[0]] == "pact_scientific_cooperation" and                     seat in (q.seat, q.pact[1]):
                eff = EFFECT[q.pact[0]]
                return (q.pact[1] if seat == q.seat else q.seat), eff["discount"], eff["partner_pays"]
        return None

    def card_sci_discount(self, seat: int, c: int, revolution: bool = False) -> int:
        """Science discounts of cards in play (Bach, Shakespeare, Watt, Colosseum, Gaudi, Acropolis)."""
        st = self.stats(seat)
        k = KIND[c]
        d = 0
        x = st.sci_disc.get(k)
        if x:
            d += x.get(AGE[c], 0)
        if st.gaudi is not None and k in URBAN:
            d += sum(1 for u in st.gaudi if u != k)
        if k == "government" and not revolution:
            d += st.gov_disc
        return d

    def science_cost(self, seat: int, c: int, revolution: bool = False, discount: int = 0) -> int:
        base = REVOLUTION_COST[c] if revolution else SCIENCE_COST[c]
        coop = self.sci_coop_partner(seat)
        return max(0, base - discount - (coop[1] if coop else 0) - self.card_sci_discount(seat, c, revolution))

    def temp_science(self, seat: int, c: int) -> int:
        """Winston Churchill: science usable only for military unit technologies this turn (T12.9)."""
        return self.p(seat).temp.get("unit_science", 0) if IS_UNIT[c] else 0

    def can_pay_science(self, seat: int, c: int, revolution: bool = False, discount: int = 0) -> bool:
        coop = self.sci_coop_partner(seat)
        if coop is not None and self.p(coop[0]).science < coop[2]:
            return False
        return self.p(seat).science + self.temp_science(seat, c) >= self.science_cost(seat, c, revolution, discount)

    def pay_science(self, seat: int, c: int, revolution: bool = False, discount: int = 0) -> None:
        coop = self.sci_coop_partner(seat)
        cost = self.science_cost(seat, c, revolution, discount)
        tmp = min(cost, self.temp_science(seat, c))
        if tmp:
            self.p(seat).temp["unit_science"] -= tmp
        E.add_science(self.p(seat), -(cost - tmp))
        if coop is not None:
            E.add_science(self.p(coop[0]), -coop[2])

    # ================================================================================= tactics (T6.4, T3.3)
    def sun_tzu_common(self):
        """The tactic marked by Sun Tzu (its own special tactic, +1 per army for whoever uses it, never merged: NLW p7,
        D32) once it lies in the common tactics area; None otherwise."""
        x = self.s.sun_tzu_tactic
        return x[0] if x is not None and x[1] is None else None

    def to_common(self, seat: int, c: int) -> None:
        """An exclusive tactic moves to the common tactics area (Sun Tzu's marked card stays its own entry)."""
        self.s.common_tactics.append(c)
        x = self.s.sun_tzu_tactic
        if x is not None and x[1] == seat and x[0] == c:
            x[1] = None

    def copy_options(self, seat: int) -> list:
        p = self.p(seat)
        boosted = self.sun_tzu_common()
        return sorted(c for c in set(self.s.common_tactics)
                      if c != p.tactic or (c == boosted and p.tactic_boost != c))

    def play_tactic(self, seat: int, c: int) -> None:
        """T6.4: 1 military action; the tactic becomes your exclusive tactic and your marker moves onto it."""
        p = self.p(seat)
        E.spend_military(p, 1)
        p.military_hand.remove(c)
        if p.exclusive_tactic is not None:
            if effects.leader_type(p) == "sun_tzu":                         # Sun Tzu: it stays, uncopyable
                p.kept_tactics.append(p.exclusive_tactic)
            else:
                self.to_common(seat, p.exclusive_tactic)
        p.exclusive_tactic = c
        p.tactic = c
        p.tactic_boost = None                                               # its own copy: never Sun Tzu's card
        p.flags["tactic_done"] = True
        E.touch(p)

    def copy_tactic(self, seat: int, c: int) -> None:
        """T6.4: 2 military actions; the marker moves onto a common tactic (onto Sun Tzu's marked card when it is
        that tactic: the same card with +1 per army, never worse, D32)."""
        p = self.p(seat)
        E.spend_military(p, 2)
        p.tactic = c
        p.tactic_boost = c if c == self.sun_tzu_common() else None
        p.flags["tactic_done"] = True
        E.touch(p)

    def share_tactic(self, seat: int) -> None:
        """T3.3 (3): the exclusive tactic of the previous turn moves to the common area; the marker stays on it.
        Sun Tzu: while he is in play nothing moves; on the first turn without him every tactic in the play area
        becomes common."""
        p = self.p(seat)
        if effects.leader_type(p) == "sun_tzu":
            return
        for c in p.kept_tactics:
            self.s.common_tactics.append(c)
            self.s.log.add(seat, f"{self.card_name(c)} becomes a common tactic")
        p.kept_tactics = []
        if p.exclusive_tactic is not None:
            self.to_common(seat, p.exclusive_tactic)
            self.s.log.add(seat, f"{self.card_name(p.exclusive_tactic)} becomes a common tactic")
            p.exclusive_tactic = None

    # ================================================================================= game end (T14, T7.2)
    def end_game(self, evaluate: bool = True) -> None:
        s = self.s
        if evaluate:
            effects.final_events(self)                                      # T14.2
            effects.fire(self, "game_end", s.start_seat)
        s.game_over = True
        s.phase = "over"
        s.decisions.clear()
        s.log.add(None, "Game over: " + ", ".join(f"P{i} {x}" for i, x in enumerate(self.scores())))

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
                    self.population_gained(seat, k2)
                else:                                                       # T11.7: LOSE_WORKER if no pool
                    self.s.tasks.append({"op": "lose_pop", "seat": seat, "n": -v, "card": card})
                E.touch(p)
            elif k == "military_cards":
                military.draw(self, seat, v)

    def population_gained(self, seat: int, k: int) -> None:
        """Maria Theresa: 1 science and 1 culture per population increased or gained (yellow bank -> pool)."""
        p = self.p(seat)
        if k > 0 and effects.leader_type(p) == "maria_theresa":
            per = EFFECT[p.leader]["per_population"]
            E.add_science(p, per["science"] * k)
            E.add_culture(p, per["culture"] * k, "leaders", p.leader)

    # ================================================================================= taking cards (T4)
    def take_cost(self, seat: int, slot: int) -> int:
        """T1.2 + T4.6 wonder surcharge (Michelangelo: none) - Darwin (technologies, minimum 1) + the card's own
        change (Taj Mahal after replacing a leader, Nelson Mandela without discontent workers)."""
        c = self.s.row[slot]
        cost = ROW_COST[slot]
        st = self.stats(seat)
        if KIND[c] == "wonder":
            p = self.p(seat)
            if not st.no_wonder_surcharge:
                cost += len(p.wonders) + len(p.ruined)                      # T4.6
        elif st.take_disc and IS_TECH[c]:
            cost = max(1, cost - st.take_disc)
        fn = effects.REGISTRY["take_cost"].get(EFFECT_TYPE[c])
        if fn is not None:
            cost = max(0, cost + fn(self, seat, c, EFFECT[c]))
        return cost

    def can_take(self, seat: int, slot: int, budget: int = None) -> bool:
        """T4.2-T4.6; with `budget` (International Agreement) the cost is checked against it, not civil actions."""
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
        have = E.civil_available(self, seat) if budget is None else budget
        if budget is None and self.gutenberg_for(seat, KIND[c]):
            have += 1
        return have >= self.take_cost(seat, slot)                           # T4.2

    def take_slots(self, seat: int, budget: int = None) -> list:
        """Row slots can_take() allows, computed in one pass (hot path of action_legal)."""
        p = self.p(seat)
        have = E.civil_available(self, seat) if budget is None else budget
        gut = budget is None and self.gutenberg_armed(seat)
        hand_ok = len(p.civil_hand) < E.civil_hand_limit(self, seat)
        disc = self.stats(seat).take_disc                                    # Darwin (technologies, minimum 1)
        names = None
        out = []
        for i, c in enumerate(self.s.row):
            if c is None:
                continue
            k = KIND[c]
            if k == "wonder":
                if p.unfinished is not None:
                    continue
            else:
                low = max(1, ROW_COST[i] - disc) if disc and IS_TECH[c] else ROW_COST[i]
                if not hand_ok or low > have + gut:
                    continue
                if IS_TECH[c]:
                    if names is None:
                        names = self.names_owned(seat)
                    if NAME[c] in names:
                        continue
                if k == "leader" and AGE[c] in p.leaders_taken:
                    continue
            if self.take_cost(seat, i) > have + (gut and k in EFFECT_GUTENBERG_KINDS):
                continue
            out.append(i)
        return out

    def take(self, seat: int, slot: int, pay: bool = True) -> None:
        s, p = self.s, self.p(seat)
        c = s.row[slot]
        if pay:
            cost = self.take_cost(seat, slot)
            if cost and self.gutenberg_for(seat, KIND[c]):
                self.use_gutenberg(seat)
                cost -= 1
            E.spend_civil(p, cost)
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
        return max(0, RESOURCE_COST[card] - effects.build_discount(st, card) - discount)

    def upgrade_cost(self, seat: int, frm: int, to: int, discount: int = 0) -> int:
        """T5.4: cost of the higher card minus cost of the lower card, both after modifiers."""
        st = self.stats(seat)
        hi = RESOURCE_COST[to] - effects.build_discount(st, to)
        lo = RESOURCE_COST[frm] - effects.build_discount(st, frm)
        return max(0, hi - lo - discount)

    def _action_ok(self, seat: int, unit: bool, free: bool) -> bool:
        if free:
            return True
        return (E.military_available if unit else E.civil_available)(self, seat) >= 1

    def _gut_discount(self, seat: int, kind: str, free: bool) -> int:
        return EFFECT[self.p(seat).leader]["discount"] if self.gutenberg_for(seat, kind, free) else 0

    def build_options(self, seat: int, kinds: tuple = BUILDINGS, discount: int = 0, free: bool = False) -> list:
        """Technologies in play a worker can be built on now (T5.2, T5.3, T6.1; Gutenberg for labs/libraries)."""
        p = self.p(seat)
        unit = kinds[0] in UNITS
        if p.pool < 1:
            return []
        gut = not unit and not free and self.gutenberg_armed(seat)          # only labs/libraries, his discount
        if not gut and not self._action_ok(seat, unit, free):
            return []
        gd = EFFECT[p.leader]["discount"] if gut else 0
        limit = self.stats(seat).urban_limit
        out = []
        for c in p.techs:
            k = KIND[c]
            if k not in kinds or (gut and k not in EFFECT_GUTENBERG_KINDS):
                continue
            d = discount + gd
            if not self.afford(seat, "mine", self.build_cost(seat, c, d), self.purpose_of(c)):
                continue
            if k in URBAN and E.urban_workers(p, k) >= limit:                  # T5.3
                continue
            out.append(c)
        return out

    def upgrade_to_options(self, seat: int, frm: int, discount: int = 0, free: bool = False) -> list:
        p = self.p(seat)
        d = discount + (self._gut_discount(seat, KIND[frm], free) if not IS_UNIT[frm] else 0)
        return [c for c in p.techs if KIND[c] == KIND[frm] and LEVEL[c] > LEVEL[frm]
                and self.afford(seat, "mine", self.upgrade_cost(seat, frm, c, d), self.purpose_of(frm))]

    def upgrade_from_options(self, seat: int, kinds: tuple = BUILDINGS, discount: int = 0, free: bool = False) -> list:
        p = self.p(seat)
        unit = kinds[0] in UNITS
        gut = not unit and not free and self.gutenberg_armed(seat)
        if not gut and not self._action_ok(seat, unit, free):
            return []
        return [c for c in p.techs if KIND[c] in kinds and p.workers.get(c, 0)
                and (not gut or KIND[c] in EFFECT_GUTENBERG_KINDS)
                and self.upgrade_to_options(seat, c, discount, free)]

    def destroy_options(self, seat: int, unit: bool = False) -> list:
        p = self.p(seat)
        if not self._action_ok(seat, unit, False):
            return []
        kinds = UNITS if unit else BUILDINGS
        return [c for c in p.techs if KIND[c] in kinds and p.workers.get(c, 0)]

    def wonder_max_stages(self, seat: int, discount: int = 0, free: bool = False, single: bool = False) -> int:
        """Stages buildable in one action now (T5.7): 1, or more with a construction technology; 0 if none. An action
        card that builds a stage (Engineering Genius) builds exactly one (`single`, D20)."""
        p = self.p(seat)
        if p.unfinished is None or not self._action_ok(seat, False, free):
            return 0
        card, paid, _ = p.unfinished
        costs = STAGE_COSTS[card][paid:]
        allowed = min(len(costs), 1 if single else self.stats(seat).wonder_stages)
        kind, purpose, discount = self.stage_payment(card, discount)
        k = 0
        for i in range(1, allowed + 1):
            if self.afford(seat, kind, max(0, sum(costs[:i]) - discount), purpose):
                k = i
        return k

    @staticmethod
    def stage_payment(card: int, discount: int) -> tuple:
        """(food/resources, temporary purpose, discount) of a wonder stage: International Red Cross is paid in food
        and resource discounts do not apply to it."""
        if EFFECT_TYPE[card] == "red_cross":
            return "farm", None, 0
        return "mine", "civic", discount

    def can_increase_population(self, seat: int, free_action: bool = False, discount: int = 0) -> bool:
        cost = E.pop_cost_for(self, seat, discount)                             # T5.1, T1.8, Moses
        return cost is not None and (free_action or E.civil_available(self, seat) >= 1) and \
            self.afford(seat, "farm", cost)

    def can_peaceful(self, seat: int, card: int, free: bool = False, sci_discount: int = 0) -> bool:
        return (free or E.civil_available(self, seat) >= 1) and self.can_pay_science(seat, card, False, sci_discount)

    def robespierre(self, seat: int) -> bool:
        p = self.p(seat)
        return effects.leader_type(p) == "robespierre" and EFFECT[p.leader]["revolution_spends_military_actions"]

    def can_revolution(self, seat: int, card: int, free: bool = False, revolution_ok: bool = False,
                       discount: int = 0) -> bool:
        """T5.9: all civil actions still available (a develop action card or Development of Civilization: they were
        before; the event's science discount applies, D23). Maximilien Robespierre: all military actions instead."""
        p = self.p(seat)
        if not self.can_pay_science(seat, card, True, discount):
            return False
        if self.robespierre(seat):
            return p.military_spent == 0 and self.stats(seat).military >= 1
        if free:
            return revolution_ok
        return p.civil_spent == 0 and self.stats(seat).civil >= 1

    def develop_options(self, seat: int, free: bool = False, exclude: int = None, revolution_ok: bool = None,
                        sci_discount: int = 0, only: tuple = None) -> list:
        """Technologies in hand that can be developed now (`only`: of these kinds). With a develop action card (free),
        a revolution needs all civil actions available before the card was played (revolution_ok; None = now, before
        playing it)."""
        p = self.p(seat)
        if free and revolution_ok is None:
            revolution_ok = p.civil_spent == 0 and self.stats(seat).civil >= 1
        out = []
        for c in sorted(set(p.civil_hand)):
            if c == exclude or not IS_TECH[c] or (only is not None and KIND[c] not in only):
                continue
            if KIND[c] == "government":
                ok = self.can_peaceful(seat, c, free, sci_discount) or \
                    self.can_revolution(seat, c, free, bool(revolution_ok), sci_discount)
            elif self.gutenberg_for(seat, KIND[c], free):
                ok = self.can_pay_science(seat, c, False, sci_discount + self._gut_discount(seat, KIND[c], free))
            else:
                ok = (free or E.civil_available(self, seat) >= 1) and self.can_pay_science(seat, c, False,
                                                                                          sci_discount)
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
        if k == "action":                                                       # T5.10, Harvard College
            return (c not in p.taken_this_phase or self.harvard_ready(seat)) and effects.can_play_action(self, seat, c)
        return False

    def harvard_ready(self, seat: int) -> bool:
        p = self.p(seat)
        return not p.flags.get("harvard_used") and any(EFFECT_TYPE[w] == "harvard" for w in p.wonders)

    def silk_road_active(self, seat: int) -> bool:
        """Silk Road works from its first built stage (unfinished) and when completed."""
        p = self.p(seat)
        if any(EFFECT_TYPE[w] == "silk_road" for w in p.wonders):
            return True
        return p.unfinished is not None and EFFECT_TYPE[p.unfinished[0]] == "silk_road" and p.unfinished[1] >= 1

    # ================================================================================= civil actions (T5, T6)
    def increase_population(self, seat: int, free_action: bool = False, discount: int = 0, free_food: bool = False):
        p = self.p(seat)
        cost = 0 if free_food else E.pop_cost_for(self, seat, discount)
        if not free_action:
            E.spend_civil(p, 1)
        self.pay(seat, "farm", cost)
        p.yellow_bank -= 1                                                      # rightmost yellow token -> pool
        p.pool += 1
        E.touch(p)
        self.population_gained(seat, 1)

    def _civil_or_gutenberg(self, seat: int, kind: str, free: bool) -> int:
        """Spend the civil action of a build/upgrade/develop (Gutenberg's when it applies); returns its discount."""
        if free:
            return 0
        if self.gutenberg_for(seat, kind):
            d = self._gut_discount(seat, kind, False)
            self.use_gutenberg(seat)
            return d
        E.spend_civil(self.p(seat), 1)
        return 0

    def build(self, seat: int, card: int, discount: int = 0, free: bool = False) -> None:
        p = self.p(seat)
        if IS_UNIT[card]:
            if not free:
                E.spend_military(p, 1)
        else:
            discount += self._civil_or_gutenberg(seat, KIND[card], free)
        cost = self.build_cost(seat, card, discount)
        self.pay(seat, "mine", cost, self.purpose_of(card))
        p.pool -= 1
        p.workers[card] = p.workers.get(card, 0) + 1
        E.touch(p)

    def upgrade(self, seat: int, frm: int, to: int, discount: int = 0, free: bool = False) -> None:
        p = self.p(seat)
        if IS_UNIT[frm]:
            if not free:
                E.spend_military(p, 1)
        else:
            discount += self._civil_or_gutenberg(seat, KIND[frm], free)
        cost = self.upgrade_cost(seat, frm, to, discount)
        self.pay(seat, "mine", cost, self.purpose_of(frm))
        p.workers[frm] -= 1
        p.workers[to] = p.workers.get(to, 0) + 1
        E.touch(p)

    def destroy(self, seat: int, card: int) -> None:
        p = self.p(seat)
        (E.spend_military if IS_UNIT[card] else E.spend_civil)(p, 1)
        p.workers[card] -= 1
        p.pool += 1
        E.touch(p)

    def develop(self, seat: int, c: int, free: bool = False, revolution: bool = False, sci_discount: int = 0,
                by_card: bool = False) -> None:
        """T5.8 develop a technology; T5.9 revolution (temporary actions are not part of the totals and stay, D24,
        D25). `by_card`: through a develop action card (Robespierre: that card's civil action is given back, D24)."""
        p = self.p(seat)
        p.civil_hand.remove(c)
        before = E.totals(self, seat)
        robes = revolution and self.robespierre(seat)
        if robes:                                                               # all military actions instead
            p.military_spent = before[1]
            if by_card:
                if p.civil_spent:
                    p.civil_spent -= 1
                else:
                    p.temp_civil += 1
            self.pay_science(seat, c, True, sci_discount)
        elif revolution:
            p.civil_spent = before[0]
            self.pay_science(seat, c, True, sci_discount)
        else:
            sci_discount += self._civil_or_gutenberg(seat, KIND[c], free)
            self.pay_science(seat, c, False, sci_discount)
        p.flags["developed"] = p.flags.get("developed", 0) + 1                  # Alfred Nobel's prize
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
        E.settle_totals(self, seat, before, revolution=revolution and not robes)
        if robes:
            p.military_spent = self.stats(seat).military
        self.used_kidnapped(seat, c)
        effects.fire(self, "on_develop", seat, card=c, developer=seat, revolution=revolution)

    def used_kidnapped(self, seat: int, c: int) -> None:
        """Aggression: Kidnap: culture when the taken card is used in the same turn."""
        p = self.p(seat)
        k = p.flags.get("kidnapped")
        if k and k[0] == c:
            E.add_culture(p, k[2], "military", k[1])
            p.flags["kidnapped"] = None

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
            p.flags["leader_replaced"] = True                                   # Taj Mahal
            back = effects.replace_refund(self, seat, old)                      # 1; Eleanor 3, Nobel 0
            refunded = min(back, p.civil_spent)
            p.civil_spent -= refunded                                           # civil actions back
            effects.leader_replaced(self, seat, old, refunded)                  # Homer's tuck, Nobel's prize
            effects.fire(self, "on_leader_replaced", seat, old=old, new=c, owner=seat)
        self.used_kidnapped(seat, c)

    def play_action_card(self, seat: int, c: int) -> None:
        """T5.10 (Harvard College: once per turn a card taken this turn; Silk Road: the first action card of the
        turn gives each benefit +1)."""
        p = self.p(seat)
        p.flags["all_civil_before_action"] = p.civil_spent == 0 and self.stats(seat).civil >= 1
        if c in p.taken_this_phase:
            p.flags["harvard_used"] = True
        eff = effects.action_effect(self, seat, c)
        if eff is not EFFECT[c]:
            p.flags["silk_road_used"] = True
        if self.gutenberg_armed(seat):                                          # his action pays (D30); the card's
            self.use_gutenberg(seat)                                            # task then serves labs/libraries
            p.flags["gutenberg_card"] = True                                    # only (effects.gutenberg_card)
        else:
            E.spend_civil(p, 1)
        p.civil_hand.remove(c)
        self.s.removed_civil.append(c)
        self.used_kidnapped(seat, c)
        effects.play_action(self, seat, c, eff)

    def complete_wonder(self, seat: int) -> None:
        """T5.7: tokens go back to the blue bank (Louvre: they stay on it) and the wonder's effects start."""
        p = self.p(seat)
        card, _, tok = p.unfinished
        if EFFECT_TYPE[card] == "louvre":
            p.louvre_tokens += tok
        else:
            p.blue_bank += tok
        p.unfinished = None
        before = E.totals(self, seat)
        p.wonders.append(card)
        self.enter_play(seat, card)
        E.settle_totals(self, seat, before)
        for q in self.s.players:                                            # International Tourism counts wonders
            E.touch(q)
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

    def slide_and_deal(self) -> None:
        """International Agreement: slide the row left and refill it without discards (may change the age)."""
        s = self.s
        rest = [c for c in s.row if c is not None]
        s.row = rest + [None] * (ROW_SIZE - len(rest))
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
                effects.hippocrates_age_end(self, seat)                         # a reminder into the yellow bank
        for p in s.players:                                                     # Roman Roads depends on the age
            E.touch(p)
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
            self.remove_leader(seat)
        if p.pact is not None and AGE[p.pact[0]] == age:                       # T13.3: antiquated pacts leave
            from .politics import remove_pact
            remove_pact(self, seat, "antiquated")
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
        E.produce_step(self, seat, "farm")                                      # T12.6
        missing = E.lose(p, "farm", E.consumption(p.yellow_bank))               # T12.7
        lost = E.add_culture(p, -4 * missing, "famine") if missing else 0
        E.produce_step(self, seat, "mine")                                      # T12.8, T15.6
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
                ([p.leader] if p.leader is not None else []) + p.wonders + p.ruined + p.colonies + p.left_play
        rows = []
        for i, c in enumerate(cards):
            rows.append({"item": KEY[c], "kind": KIND[c], "group": AGE[c], "slot": i, "host": None,
                         "points": int(pts.get(c, 0)), "tags": {"kind": KIND[c], "age": AGE[c], "set": SET[c]}})
        return rows

    def seat_extra(self, seat: int) -> dict:
        p = self.p(seat)
        st = self.stats(seat)
        hand = p.hand_at_resign if p.hand_at_resign is not None else p.civil_hand + p.military_hand
        return {"science": p.science, "strength": military.strength(self, seat), "culture_rating": st.culture,
                "science_rating": st.science, "rounds": self.s.round, "workers": self.workers_total(seat),
                "colonies": len(p.colonies), "hand_left": [KEY[c] for c in hand]}

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
        g.end_game(evaluate=len(active) > 1)
        return
    s.round += 1
    s.round_first = active[0]
    t["queue"] = list(active)
    s.log.add(None, f"Round {s.round}")


def h_turn(g: Game, t: dict, a):
    s, seat = g.s, t["seat"]
    st = t["stage"]
    if st == "start":                                                           # T3.3, D3
        s.turn_seat = seat
        s.phase = "start"
        if s.round > 1:
            g.refill()                                                          # (1)
        t["stage"] = "start2"
        if g.p(seat).wars:
            from .politics import resolve_wars
            resolve_wars(g, seat)                                               # (2) T9.5
    elif st == "start2":
        g.share_tactic(seat)                                                    # (3)
        effects.fire(g, "start_of_turn", seat, owner=seat)
        t["stage"] = "politics"
    elif st == "politics":                                                      # T3.4 (skipped in round 1, T3.2)
        t["stage"] = "actions"
        p = g.p(seat)
        if s.round > 1:
            s.phase = "politics"
            if s.olympics is not None and s.olympics[0] == seat:                # Coubertin: until before the
                s.olympics = None                                               # owner's next Politics Phase
            n = effects.political_actions(g, seat)                              # Julius Caesar: 2
            if p.forfeit_politics:                                              # International Agreement
                p.forfeit_politics -= 1
                n -= 1
                s.log.add(seat, "gives up this political action (International Agreement)")
            if n > 0:
                s.tasks.append({"op": "politics", "seat": seat, "left": n})
            elif "OLYMPICS" in [VERBS[x - A_VERB] for x in effects.ability_verbs(g, seat, "POLITICS")]:
                s.tasks.append({"op": "politics", "seat": seat, "left": 0, "only_olympics": True})   # D26
            effects.fire(g, "start_of_politics", seat, owner=seat)              # Joan of Arc, Ian Fleming first
    elif st == "actions":                                                       # T3.5
        s.phase = "actions"
        g.p(seat).taken_this_phase = []
        t["stage"] = "end"
        s.tasks.append({"op": "actions", "seat": seat})
        effects.fire(g, "start_of_action_phase", seat, owner=seat)          # Boudica's choice comes first
    elif st == "end":                                                           # T3.6
        s.phase = "end"
        s.tasks.append({"op": "end_turn", "seat": seat, "step": "discard"})
        t["stage"] = "done"
    else:
        s.turns += 1
        g._finish(t)


def action_legal(g: Game, seat: int) -> list:
    """ACTION answers that have a legal completion (PLAN 3, 5)."""
    s, p = g.s, g.p(seat)
    legal = [A_END]
    legal += [A_ROW + i for i in g.take_slots(seat)]
    if s.round == 1:                                                            # T3.2: only take cards
        return legal
    if g.gutenberg_armed(seat):                                                 # Gutenberg chosen (D30)
        return legal[:1] + gutenberg_legal(g, seat)
    civil = E.civil_available(g, seat)
    if civil >= 1:
        if civil and g.can_increase_population(seat):
            legal.append(A_VERB + V["INCREASE_POP"])
        if g.build_options(seat, BUILDINGS):
            legal.append(A_VERB + V["BUILD"])
        if g.upgrade_from_options(seat, BUILDINGS):
            legal.append(A_VERB + V["UPGRADE"])
        if civil and g.destroy_options(seat):
            legal.append(A_VERB + V["DESTROY"])
        if civil and g.wonder_max_stages(seat):
            legal.append(A_VERB + V["WONDER_STAGE"])
    legal += effects.ability_verbs(g, seat, "ACTION")
    if E.military_available(g, seat) >= 1:
        if not p.flags.get("tactic_done"):                                      # T6.4: one play or copy per turn
            legal += [A_CARD + c for c in sorted(set(p.military_hand)) if KIND[c] == "tactic"]
            if E.military_available(g, seat) >= 2 and g.copy_options(seat):
                legal.append(A_VERB + V["COPY_TACTIC"])
        if g.build_options(seat, UNITS):
            legal.append(A_VERB + V["BUILD_UNIT"])
        if g.upgrade_from_options(seat, UNITS):
            legal.append(A_VERB + V["UPGRADE_UNIT"])
        if g.destroy_options(seat, unit=True):
            legal.append(A_VERB + V["DISBAND"])
    dev = None
    for c in sorted(set(p.civil_hand)):
        if IS_TECH[c]:
            if dev is None:
                dev = g.develop_options(seat)
            if c in dev:
                legal.append(A_CARD + c)
        elif g.can_play_hand(seat, c):
            legal.append(A_CARD + c)
    return legal


def gutenberg_legal(g: Game, seat: int) -> list:
    """ACTION answers after choosing Gutenberg's action: lab/library takes, builds, upgrades, developments and action
    cards used for one of these (NLW p8, D30)."""
    p = g.p(seat)
    out = [A_ROW + i for i in g.take_slots(seat) if KIND[g.s.row[i]] in EFFECT_GUTENBERG_KINDS]
    if g.build_options(seat, BUILDINGS):
        out.append(A_VERB + V["BUILD"])
    if g.upgrade_from_options(seat, BUILDINGS):
        out.append(A_VERB + V["UPGRADE"])
    dev = None
    for c in sorted(set(p.civil_hand)):
        if IS_TECH[c] and KIND[c] in EFFECT_GUTENBERG_KINDS:
            if dev is None:
                dev = g.develop_options(seat)
            if c in dev:
                out.append(A_CARD + c)
        elif KIND[c] == "action" and gutenberg_card_ok(g, seat, c):
            out.append(A_CARD + c)
    return out


def gutenberg_card_ok(g: Game, seat: int, c: int) -> bool:
    """An action card Gutenberg's action can pay for: it develops, builds or upgrades a lab or library now, with his
    discount added to the card's."""
    p = g.p(seat)
    if c in p.taken_this_phase and not g.harvard_ready(seat):
        return False
    eff = effects.action_effect(g, seat, c)
    gd = EFFECT[p.leader]["discount"]
    t = EFFECT_TYPE[c]
    if t == "develop":
        return bool(g.develop_options(seat, free=True, exclude=c, sci_discount=gd, only=EFFECT_GUTENBERG_KINDS))
    if t in ("build_or_upgrade", "upgrade"):
        kinds = tuple(k for k in effects.action_targets(eff) if k in EFFECT_GUTENBERG_KINDS)
        if not kinds:
            return False
        d = eff["discount"] + gd
        return bool((t == "build_or_upgrade" and g.build_options(seat, kinds, d, True))
                    or g.upgrade_from_options(seat, kinds, d, True))
    return False


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
        elif verb == "COPY_TACTIC":
            s.tasks.append({"op": "copy_tactic", "seat": seat})
        else:
            effects.use_ability(g, seat, verb)                                  # card abilities (civil.py)
    else:                                                                       # CARD from a hand
        k = KIND[off]
        if k == "tactic":
            g.play_tactic(seat, off)
        elif IS_TECH[off]:
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


def h_copy_tactic(g: Game, t: dict, a):
    seat = t["seat"]
    if a is None:
        g._ask("CHOOSE_TACTIC", seat, [A_CARD + c for c in g.copy_options(seat)])
        return
    g._finish(t)
    g.copy_tactic(seat, a - A_CARD)


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
        g._ask("UPGRADE_TO", seat, [A_CARD + c for c in g.upgrade_to_options(seat, t["frm"], t["discount"],
                                                                              t["free"])],
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
            k = g.wonder_max_stages(seat, t["discount"], t["free"], t.get("single", False))
            g._ask("STAGES", seat, [A_AMOUNT + i for i in range(k)], card=p.unfinished[0])
            return
        t["stages"] = a - A_AMOUNT + 1
        a = None
    if "left" not in t:
        card, paid, _ = p.unfinished
        kind, purpose, discount = g.stage_payment(card, t["discount"])
        cost = max(0, sum(STAGE_COSTS[card][paid:paid + t["stages"]]) - discount)
        if not t["free"]:
            E.spend_civil(p, 1)
        g.pay(seat, kind, cost, purpose)
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
    effects.fire_card(g, "on_wonder_stage", t["seat"], p.unfinished[0], builder=t["seat"])


def h_develop(g: Game, t: dict, a):
    seat = t["seat"]
    if t["card"] is None:                                                       # develop action card: which card
        if a is None:
            opts = g.develop_options(seat, True, t["source"], t["revolution_ok"], t.get("sci_discount", 0),
                                     t.get("only"))
            g._ask("SUB_ACTION", seat, [A_CARD + c for c in opts], verb="DEVELOP", source=t["source"])
            return
        t["card"] = a - A_CARD
        a = None
    c = t["card"]
    if KIND[c] == "government" and "revolution" not in t:
        peace = g.can_peaceful(seat, c, t["free"], t.get("sci_discount", 0))
        rev = g.can_revolution(seat, c, t["free"], t["revolution_ok"], t.get("sci_discount", 0))
        if peace and rev:
            if a is None:
                g._ask("REVOLT", seat, [A_YES, A_NO], card=c)
                return
            t["revolution"] = a == A_YES
        else:
            t["revolution"] = rev
    g._finish(t)
    src = t["source"]
    g.develop(seat, c, t["free"], t.get("revolution", False), t.get("sci_discount", 0),
              by_card=src is not None and KIND[src] == "action")
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
            effects.excess_discarded(g, seat)                                   # Eleanor of Aquitaine
        if len(p.military_hand) > E.military_hand_limit(g, seat):
            g._ask("DISCARD_MILITARY", seat, [A_CARD + c for c in p.military_hand])
            return
        t["step"] = "effects"
        effects.nobel_prize(g, seat)
        effects.fire(g, "end_of_turn", seat, owner=seat)
        return
    g._finish(t)
    g.production(seat)                                                          # T3.6 (2)-(3)
    military.draw(g, seat, min(3, E.military_available(g, seat)) + effects.extra_draw(g, seat))   # T3.7, Sun Tzu
    p.civil_spent = p.military_spent = 0                                        # T3.6 (5)
    p.temp_civil = p.temp_military = 0
    p.temp = {}
    p.flags = {}
    p.peek = None                                                               # Ian Fleming's look is stale


HANDLERS = {"game": h_game, "turn": h_turn, "actions": h_actions, "build": h_build, "copy_tactic": h_copy_tactic,
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
        len(s.future_events) + len(s.past_events) + len(s.removed_military) + len(s.common_tactics) + len(s.resolving)
    for p in s.players:
        civil += len(p.civil_hand) + len(p.wonders) + len(p.ruined) + len(p.left_play)
        civil += sum(not IS_STARTING[c] for c in p.techs) + sum(1 for c in p.specials.values())
        civil += (not IS_STARTING[p.government]) + (p.leader is not None) + (p.unfinished is not None)
        mil += len(p.military_hand) + len(p.colonies) + len(p.wars) + (p.exclusive_tactic is not None) + \
            (p.pact is not None) + len(p.kept_tactics)
        tag = f"P{p.seat}"
        if p.tactic is not None and p.tactic != p.exclusive_tactic and p.tactic not in s.common_tactics and \
                p.tactic not in p.kept_tactics:
            out.append(f"{tag} tactic marker on a tactic that is not in play")
        if p.reminders < 0 or p.reminders > 3 or p.louvre_tokens < 0:
            out.append(f"{tag} Hippocrates reminders or Louvre tokens out of range")
        if p.resigned_order is None and military.max_colonization_force(g, p.seat) > 128:
            out.append(f"{tag} colonization force above the 128 bid cap (choice C4)")
        if p.pact is not None and (p.pact[1] == p.seat or s.players[p.pact[1]].resigned_order is not None):
            out.append(f"{tag} pact with itself or a resigned player")
        on_cards = sum(p.tokens.values()) + (p.unfinished[2] if p.unfinished else 0) + p.louvre_tokens
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
        if any(KIND[c] not in ("farm", "mine", "lab") or c not in p.techs for c, k in p.tokens.items() if k):
            out.append(f"{tag} blue tokens on a card that is not a farm, mine or (Bill Gates) lab in play")
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
        if any(E.VALUE[c] <= 0 for c in p.tokens):
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


EFFECT_GUTENBERG_KINDS = tuple(next(EFFECT[c]["extra_civil_action_for"] for c in range(N_CARDS)
                                    if EFFECT_TYPE[c] == "gutenberg"))

from . import politics  # noqa: E402,F401  (registers the politics task handlers)
from . import civil  # noqa: E402,F401  (registers the civil card effects and their task handlers)
