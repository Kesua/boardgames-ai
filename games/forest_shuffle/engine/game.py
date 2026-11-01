"""Game engine: legal actions, stepping, turn flow."""
from __future__ import annotations

import copy
import pickle
import random
from typing import Optional

from dataclasses import replace

from ..core.actions import Action, ActionCodec, ActionKind
from ..core.cards import CardInstance, HalfDef
from ..core.enums import ALL_EXPANSIONS, CLEARING_LIMIT, HAND_LIMIT, MAX_WOODY
from ..core.state import Decision, GameState, PlayerState, make_dweller, make_sapling, make_woody
from . import effects
from .filters import def_matches, shows_symbol
from .placement import can_place, legal_targets
from .scoring import score_breakdown, score_cards, score_player
from .setup import build_deck, can_mulligan, deal_hands


class IllegalActionError(Exception):
    pass


class Game:
    def __init__(self, db, num_players: int = 2, seed: Optional[int] = None, expansions=ALL_EXPANSIONS):
        assert 2 <= num_players <= 5
        self.db = db
        self.num_players = num_players
        self.expansions = tuple(expansions)
        self.rng = random.Random(seed)
        self.codec = ActionCodec(db.num_play_defs, MAX_WOODY)
        self.state: Optional[GameState] = None
        self._next_uid = 10_000

    # ------------------------------------------------------------------ setup
    def reset(self) -> GameState:
        deck, removed = build_deck(self.db, self.rng, self.num_players, self.expansions)
        self.state = GameState(players=[PlayerState(i) for i in range(self.num_players)],
                               deck=deck, clearing=[], removed=removed)
        deal_hands(self.state, self.num_players)
        for p in self.state.players:                     # automatic mulligan (documented simplification)
            if can_mulligan(self.db, p.hand):
                self.state.removed.extend(p.hand)
                p.hand.clear()
                p.mulligan_used = True
                for _ in range(6):
                    p.hand.append(self.state.deck.draw())
        return self.state

    def clone(self) -> "Game":
        g = copy.copy(self)
        g.state = pickle.loads(pickle.dumps(self.state, protocol=pickle.HIGHEST_PROTOCOL))
        g.rng = random.Random()
        g.rng.setstate(self.rng.getstate())
        return g

    # ------------------------------------------------------------------ queries
    @property
    def current_seat(self) -> int:
        return self.state.current

    def scores(self) -> list:
        return [score_player(self.db, self.state.players, i) for i in range(self.num_players)]

    def breakdowns(self) -> list:
        """Per seat {trees, dwellers, cave} (the score categories in manifest.json)."""
        out = []
        for i in range(self.num_players):
            b = score_breakdown(self.db, self.state.players, i)
            out.append({"trees": b["trees"], "dwellers": b["dwellers"], "cave": b["cave"]})
        return out

    def legal_actions(self) -> list:
        s = self.state
        if s.game_over:
            return []
        if not s.decisions:
            acts = self._draw_actions() + self._play_actions()
            return acts or [Action(ActionKind.DONE)]        # stuck (full hand, full forest): pass
        return effects.decision_options(self, s.decisions[-1])

    def legal_ids(self) -> list:
        return [self.codec.encode(a) for a in self.legal_actions()]

    def pending_label(self) -> str:
        s = self.state
        if s.game_over:
            return "Game over"
        if not s.decisions:
            return "Choose: draw two cards or play a card"
        d = s.decisions[-1]
        return {
            "DRAW": lambda: f"Draw {d.data['remaining']} more card(s)",
            "PAY": lambda: f"Pay {d.data['cost'] - len(d.data['paid'])} more card(s) for {d.data['label']}",
            "USE_OR_SKIP": lambda: f"Use or skip {d.data['label']}",
            "CHOOSE_CLEARING_CARD": lambda: f"Choose {d.data['remaining']} card(s) from the clearing → {d.data['dest'].lower()}",
            "CHOOSE_HAND_CARD": lambda: "Choose hand cards for your cave, then Done",
            "PLACE_FREE": lambda: "Place a card for free (or Done)",
            "PLAY_MORE": lambda: "Mole: play more cards (or Done)",
            "SAPLING_MORE": lambda: "Water Vole: play saplings (or Done)",
            "CHOOSE_TARGET": lambda: f"Choose the plant for {d.data['label']}",
        }[d.kind]()

    def describe_action(self, a: Action) -> str:
        db = self.db
        if a.kind == ActionKind.DRAW_DECK:
            return "Draw from deck"
        if a.kind == ActionKind.DRAW_CLEARING:
            return f"Take {db.card_label(a.card)} from clearing"
        if a.kind == ActionKind.PLAY_WOODY:
            return f"Play {db.card_label(a.card)}"
        if a.kind == ActionKind.PLAY_SAPLING:
            return f"Play {db.card_label(a.card)} face down as sapling"
        if a.kind == ActionKind.PLAY_HALF:
            h = db.defs[a.card].halves[a.half]
            where = f" on plant {a.target + 1}" if a.target is not None else ""
            return f"Play {db.species[h.species].label} [{h.tree_symbol}]{where} ({h.position.lower()})"
        if a.kind == ActionKind.CHOOSE_TARGET:
            w = self.state.players[self.state.current].forest[a.target]
            name = db.species[w.species].label if w.species else "Sapling"
            return f"Plant {a.target + 1}: {name}" + (f" [{w.tree_symbol}]" if w.tree_symbol else "")
        if a.kind == ActionKind.PAY:
            return f"Pay with {db.card_label(a.card)}"
        if a.kind == ActionKind.CHOOSE_CARD:
            return f"Choose {db.card_label(a.card)}"
        if a.kind == ActionKind.DONE and not self.state.decisions:
            return "Pass (no legal move)"
        return {"USE": "Use", "SKIP": "Skip", "DONE": "Done", "CHOOSE_TARGET": "Target"}[a.kind.value]

    # ------------------------------------------------------------------ option builders
    def _draw_actions(self) -> list:
        s = self.state
        p = s.players[s.current]
        if len(p.hand) >= HAND_LIMIT:
            return []
        out = [Action(ActionKind.DRAW_DECK)] if s.deck else []
        out += [Action(ActionKind.DRAW_CLEARING, card=d) for d in sorted({c.def_id for c in s.clearing})]
        return out

    def _play_actions(self) -> list:
        s = self.state
        p = s.players[s.current]
        out = []
        room = len(p.forest) < MAX_WOODY
        others = len(p.hand) - 1
        for def_id in sorted({c.def_id for c in p.hand}):
            d = self.db.defs[def_id]
            if room:
                out.append(Action(ActionKind.PLAY_SAPLING, card=def_id))
            if d.layout == "WOODY_PLANT":
                if room and self.db.species[d.species].cost <= others:
                    out.append(Action(ActionKind.PLAY_WOODY, card=def_id))
            else:
                for hi, h in enumerate(d.halves):
                    if self.db.species[h.species].cost > others:
                        continue
                    if legal_targets(self.db, p.forest, h.species, h.position):
                        out.append(Action(ActionKind.PLAY_HALF, card=def_id, half=hi))
        return out

    def sapling_actions(self) -> list:
        s = self.state
        p = s.players[s.current]
        if len(p.forest) >= MAX_WOODY:
            return []
        return [Action(ActionKind.PLAY_SAPLING, card=d) for d in sorted({c.def_id for c in p.hand})]

    def free_place_actions(self, flt: dict) -> list:
        s = self.state
        p = s.players[s.current]
        out = []
        for def_id in sorted({c.def_id for c in p.hand}):
            d = self.db.defs[def_id]
            for hi, h in enumerate(d.halves):
                if not effects.half_matches(self, h, flt):
                    continue
                if legal_targets(self.db, p.forest, h.species, h.position):
                    out.append(Action(ActionKind.PLAY_HALF, card=def_id, half=hi))
        return out

    # ------------------------------------------------------------------ stepping
    def step(self, action: Action) -> dict:
        if action not in self.legal_actions():
            raise IllegalActionError(action)
        s = self.state
        info = {"turn_ended": False, "winter_revealed": 0, "game_over": False}
        before = s.winter_revealed
        s.log.add(s.current, self.describe_action(action))
        if not s.decisions:
            if action.kind == ActionKind.DONE:
                pass                                           # forced pass
            elif action.kind in (ActionKind.DRAW_DECK, ActionKind.DRAW_CLEARING):
                p = s.players[s.current]
                s.decisions.append(Decision("DRAW", {"remaining": min(2, HAND_LIMIT - len(p.hand))}))
                self._handle_draw(action)
            else:
                self._start_play(action)
        else:
            d = s.decisions[-1]
            if d.kind == "DRAW":
                self._handle_draw(action)
            elif d.kind == "PAY":
                self._handle_pay(d, action)
            else:
                effects.handle_decision(self, d, action)
        info["winter_revealed"] = s.winter_revealed - before
        if s.game_over:
            info["game_over"] = True
            return info
        self._settle()
        if s.game_over:
            info["game_over"] = True
            return info
        if not s.decisions:
            self._end_turn()
            info["turn_ended"] = True
        return info

    def step_id(self, action_id: int) -> dict:
        return self.step(self.codec.decode(action_id))

    def _settle(self) -> None:
        """Pop decisions that have no options left (e.g. nothing matching in the clearing)."""
        s = self.state
        while s.decisions and not s.game_over:
            d = s.decisions[-1]
            if d.kind == "PAY" or effects.decision_options(self, d):
                return
            s.decisions.pop()
            if d.kind == "CHOOSE_HAND_CARD":
                effects.finish_hand_to_cave(self, d)

    # ------------------------------------------------------------------ drawing
    def _handle_draw(self, action: Action) -> None:
        s = self.state
        d = s.decisions[-1]
        p = s.players[s.current]
        if action.kind == ActionKind.DRAW_DECK:
            card = self._draw_from_deck()
            if card:
                p.hand.append(card)
        else:
            card = self._take_from_clearing(action.card)
            p.hand.append(card)
            p.known.add(card.uid)
        d.data["remaining"] -= 1
        if s.game_over:
            return
        if d.data["remaining"] <= 0 or len(p.hand) >= HAND_LIMIT or not (s.deck or s.clearing):
            s.decisions.pop()

    def _draw_from_deck(self) -> Optional[CardInstance]:
        s = self.state
        while s.deck:
            c = s.deck.draw()
            if c.def_id != self.db.winter_def_id:
                return c
            s.winter_revealed += 1
            s.removed.append(c)
            s.log.add(None, f"Winter card {s.winter_revealed} revealed")
            if s.winter_revealed >= 3:
                s.game_over = True
                s.decisions.clear()
                return None
        return None

    def draw_to_hand(self, seat: int, count: int) -> int:
        """Draw up to `count` cards respecting the hand limit; returns number drawn."""
        p = self.state.players[seat]
        n = 0
        for _ in range(count):
            if len(p.hand) >= HAND_LIMIT or self.state.game_over:
                break
            c = self._draw_from_deck()
            if c is None:
                break
            p.hand.append(c)
            n += 1
        return n

    def _take_from_clearing(self, def_id: int) -> CardInstance:
        for i, c in enumerate(self.state.clearing):
            if c.def_id == def_id:
                return self.state.clearing.pop(i)
        raise IllegalActionError(def_id)

    def take_from_clearing(self, def_id: int) -> CardInstance:
        return self._take_from_clearing(def_id)

    def _reveal_to_clearing(self) -> None:
        c = self._draw_from_deck()
        if c:
            self.state.clearing.append(c)

    def hand_card_matches(self, card: CardInstance, flt: dict) -> bool:
        return def_matches(self.db, self.db.defs[card.def_id], flt)

    # ------------------------------------------------------------------ playing
    def _start_play(self, action: Action, free: bool = False, source_idx: Optional[int] = None) -> None:
        s = self.state
        p = s.players[s.current]
        card = next(c for c in p.hand if c.def_id == action.card)
        d = self.db.defs[card.def_id]
        if action.kind == ActionKind.PLAY_HALF and action.target is None:
            h = d.halves[action.half]
            targets = legal_targets(self.db, p.forest, h.species, h.position)
            if len(targets) == 1:
                action = replace(action, target=targets[0])
            else:
                s.decisions.append(Decision("CHOOSE_TARGET", {
                    "card": action.card, "half": action.half, "targets": targets, "free": free,
                    "source_idx": source_idx, "species": h.species, "label": self.db.species[h.species].label}))
                return
        play = {"uid": card.uid, "kind": action.kind.value, "half": action.half, "target": action.target,
                "source_idx": source_idx}
        if action.kind == ActionKind.PLAY_SAPLING or free:
            cost = 0
        elif action.kind == ActionKind.PLAY_WOODY:
            cost = self.db.species[d.species].cost
        else:
            cost = self.db.species[d.halves[action.half].species].cost
        if cost > 0:
            label = self.db.card_label(card.def_id) if action.kind == ActionKind.PLAY_WOODY else \
                self.db.species[d.halves[action.half].species].label
            s.decisions.append(Decision("PAY", {"play": play, "cost": cost, "paid": [], "label": label}))
        else:
            self._place_pending(play, [], free)

    def pay_options(self, d: Decision) -> list:
        p = self.state.players[self.state.current]
        played = d.data["play"]["uid"]
        return [Action(ActionKind.PAY, card=x) for x in sorted({c.def_id for c in p.hand if c.uid != played})]

    def _handle_pay(self, d: Decision, action: Action) -> None:
        s = self.state
        p = s.players[s.current]
        played = d.data["play"]["uid"]
        card = next(c for c in p.hand if c.def_id == action.card and c.uid != played)
        p.hand.remove(card)
        s.clearing.append(card)
        d.data["paid"].append(card.uid)
        if len(d.data["paid"]) >= d.data["cost"]:
            s.decisions.pop()
            self._place_pending(d.data["play"], d.data["paid"], False)

    def _place_pending(self, play: dict, paid: list, free: bool) -> None:
        s = self.state
        seat = s.current
        p = s.players[seat]
        card = next(c for c in p.hand if c.uid == play["uid"])
        p.hand.remove(card)
        d = self.db.defs[card.def_id]
        if play["kind"] == "PLAY_SAPLING":
            p.forest.append(make_sapling(s.turn_index))
            s.removed.append(card)
            self._reveal_to_clearing()
            return
        if play["kind"] == "PLAY_WOODY":
            w = make_woody(self.db, card.uid, d, s.turn_index)
            p.forest.append(w)
            idx = len(p.forest) - 1
            if w.kind == "TREE":
                self._reveal_to_clearing()
            symbol, key, dweller, types = d.tree_symbol, d.species, None, w.types
            is_tree_play = w.kind == "TREE"
            position = None
        else:
            h = d.halves[play["half"]]
            dweller = make_dweller(self.db, card.uid, h, s.turn_index)
            idx = play["target"]
            p.forest[idx].slots[h.position].append(dweller)
            symbol, key, types = h.tree_symbol, h.species, dweller.types
            is_tree_play = False
            position = h.position
        if s.game_over:
            return
        paid_defs = [self.db.defs[c.def_id] for c in s.clearing if c.uid in paid]
        bonus_ok = bool(paid) and len(paid_defs) == len(paid) and all(shows_symbol(self.db, pd, symbol) for pd in paid_defs)
        self._after_placement(seat, idx, dweller, key, types, position, is_tree_play, bonus_ok, free,
                              play.get("source_idx"))

    def _after_placement(self, seat, idx, dweller, key, types, position, is_tree_play, bonus_ok, free, source_idx):
        s = self.state
        sp = self.db.species[key]
        host = s.players[seat].forest[idx]
        # permanent triggers resolve last → push first
        for action, label in effects.matching_triggers(self, seat, types, position, host, is_tree_play, source_idx):
            s.decisions.append(Decision("USE_OR_SKIP", {"effect": action, "label": label,
                                                        "source": {"species": key, "idx": idx}}))
        if free:
            return
        source = {"species": key, "idx": idx, "label": sp.label}
        if bonus_ok and sp.bonus:
            s.decisions.append(Decision("USE_OR_SKIP", {"effect": sp.bonus, "label": f"bonus of {sp.label}",
                                                        "source": source}))
        if sp.effect and sp.effect["type"] != "permanent":
            s.decisions.append(Decision("USE_OR_SKIP", {"effect": sp.effect, "label": f"effect of {sp.label}",
                                                        "source": source}))

    def _end_turn(self) -> None:
        s = self.state
        if len(s.clearing) >= CLEARING_LIMIT:
            s.removed.extend(s.clearing)
            s.clearing.clear()
            s.log.add(None, "Clearing emptied")
        s.turn_index += 1
        if s.extra_turns > 0:
            s.extra_turns -= 1
        else:
            s.current = (s.current + 1) % self.num_players

    # ------------------------------------------------------------------ platform interface (bgai.game.Game)
    @property
    def game_over(self) -> bool:
        return self.state.game_over

    @property
    def turns(self) -> int:
        return self.state.turn_index

    def tiebreaks(self):
        return None                                    # Forest Shuffle has no tiebreak: tied players share the win

    def describe(self, action_id: int) -> str:
        return self.describe_action(self.codec.decode(action_id))

    def record_info(self, action_id: int) -> dict:
        """Recorded before the action is applied (same fields as the original forest_shuffle recorder)."""
        s = self.state
        action = self.codec.decode(action_id)
        d = s.decisions[-1] if s.decisions else None
        code = species = symbol = None
        if action.card is not None:
            cd = self.db.defs[action.card]
            if action.kind == ActionKind.PLAY_HALF and action.half is not None:
                h = cd.halves[action.half]
                code, species, symbol = cd.card_code, h.species, h.tree_symbol
            elif cd.layout == "WOODY_PLANT":
                code, species, symbol = cd.card_code, cd.species, cd.tree_symbol
            else:
                code = cd.card_code
        if action.kind == ActionKind.CHOOSE_TARGET and d is not None:
            species = d.data.get("species")
        return {"decision": d.kind if d else "CHOOSE_ACTION", "decision_label": d.data.get("label") if d else None,
                "action": action.kind.value, "card": code, "item": species, "tags": {"symbol": symbol},
                "extra": {"half": action.half, "target": action.target, "hand": len(s.players[s.current].hand),
                          "clearing": len(s.clearing), "deck": len(s.deck)}}

    def tableau(self, seat: int) -> list:
        p = self.state.players[seat]
        out = []
        for idx, slot, species, pts in score_cards(self.db, self.state.players, seat):
            host = p.forest[idx]
            symbol = (next(d.tree_symbol for d in host.slots[slot] if d.species == species) if slot else host.tree_symbol)
            out.append({"item": species, "kind": "DWELLER" if slot else host.kind, "group": idx, "slot": slot,
                        "host": host.species or "SAPLING", "points": pts, "tags": {"symbol": symbol}})
        return out

    def seat_extra(self, seat: int) -> dict:
        p = self.state.players[seat]
        return {"plants": len(p.forest), "saplings": sum(1 for w in p.forest if w.species is None),
                "hand_left": [self.db.defs[c.def_id].card_code for c in p.hand]}

    def text_state(self) -> str:
        s = self.state
        db = self.db
        lines = [f"turn {s.turn_index}, player {s.current} to act, winter cards {s.winter_revealed}/3, deck {len(s.deck)}",
                 "clearing: " + ", ".join(db.card_label(c.def_id) for c in s.clearing),
                 "pending: " + self.pending_label()]
        for i, p in enumerate(s.players):
            lines.append(f"P{i}: hand {len(p.hand)}, cave {len(p.cave)}, score {score_player(db, s.players, i)}")
            for idx, w in enumerate(p.forest):
                name = db.species[w.species].label if w.species else "Sapling"
                slots = "; ".join(f"{k.lower()}: " + ", ".join(db.species[d.species].label for d in v)
                                  for k, v in w.slots.items() if v)
                lines.append(f"  plant {idx + 1}: {name} [{w.tree_symbol}] {slots}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ test helpers
    def spawn_into_hand(self, seat: int, def_id: int) -> CardInstance:
        c = CardInstance(self._next_uid, def_id)
        self._next_uid += 1
        self.state.players[seat].hand.append(c)
        return c

    def debug_place_woody(self, seat: int, def_id: int) -> int:
        p = self.state.players[seat]
        card = next(c for c in p.hand if c.def_id == def_id)
        p.hand.remove(card)
        p.forest.append(make_woody(self.db, card.uid, self.db.defs[def_id], self.state.turn_index))
        return len(p.forest) - 1

    def debug_place_dweller(self, seat: int, forest_idx: int, def_id: int, species_key: str):
        p = self.state.players[seat]
        card = next(c for c in p.hand if c.def_id == def_id)
        half = next(h for h in self.db.defs[def_id].halves if h.species == species_key)
        sp = self.db.species[species_key]
        positions = ("LEFT", "RIGHT") if sp.position == "LEFT_RIGHT" else (sp.position,)
        woody = p.forest[forest_idx]
        for pos in positions:
            if can_place(self.db, woody, species_key, pos):
                p.hand.remove(card)
                dw = make_dweller(self.db, card.uid, HalfDef(pos, species_key, half.tree_symbol, half.extra_types),
                                  self.state.turn_index)
                woody.slots[pos].append(dw)
                return dw
        raise ValueError(f"cannot place {species_key} on plant {forest_idx}")
