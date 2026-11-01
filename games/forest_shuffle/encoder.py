"""Compact fixed-size observation vector.

Layout (from the acting seat's view):
  global        : winter/3, deck/233, clearing/15, extra_turns/3, phase one-hot
  context       : species one-hot of the pending card (effect/bonus/target decision), remaining/3
  own hand      : count per card definition / 4
  clearing      : count per card definition / 4
  per player    : summary block (self first, then clockwise)
  own forest    : per-plant blocks for the first MAX_WOODY plants
Version 2 appends, per player (self first, then clockwise): score/300, free slots per side/20; for self the lead
over the best opponent (0.5 + lead/200); for opponents the cards they took from the clearing and still hold
(count per card definition / 4). Version 1 is kept for models trained before it.
"""
from __future__ import annotations

import numpy as np

from bgai.kit import add_counts

from .core.enums import ALL_DECISION_KINDS, ENCODER_PLANTS, HAND_LIMIT, MAX_WOODY, SLOTS
from .engine.scoring import score_player

N_PHASES = 1 + len(ALL_DECISION_KINDS)
DWELLER_TYPES = ("AMPHIBIAN", "BAT", "BIRD", "BUTTERFLY", "CLOVENHOOFED_ANIMAL", "DEER", "INSECT", "MUSHROOM",
                 "PAWED_ANIMAL", "PLANT")


class StateEncoder:
    def __init__(self, db, num_players: int, version: int = 2):
        self.db = db
        self.num_players = num_players
        self.version = version
        self.n_species = len(db.species)
        self.n_defs = db.num_play_defs
        self.n_symbols = len(db.meta["tree_symbols"])
        self.type_index = {t: i for i, t in enumerate(DWELLER_TYPES)}
        self.global_size = 4 + N_PHASES
        self.context_size = self.n_species + 1
        # summary: hand/10, cave/20, plants/20, saplings/10, fully occupied/10, species counts/4, symbol counts/8
        self.summary_size = 5 + self.n_species + self.n_symbols
        # plant block: species one-hot (+sapling), symbol one-hot (+none), 4 slots x (occupied, count/4, type flags)
        self.slot_size = 2 + len(DWELLER_TYPES)
        self.plant_size = (self.n_species + 1) + (self.n_symbols + 1) + 4 * self.slot_size
        self.v1_size = (self.global_size + self.context_size + 2 * self.n_defs
                        + num_players * self.summary_size + ENCODER_PLANTS * self.plant_size)
        # v2: per player score + 4 free sides, own lead, known hand cards of each opponent
        self.size = self.v1_size if version == 1 else             self.v1_size + num_players * (1 + len(SLOTS)) + 1 + (num_players - 1) * self.n_defs

    def _summary(self, v, i, p):
        v[i] = len(p.hand) / HAND_LIMIT
        v[i + 1] = min(len(p.cave), 20) / 20.0
        v[i + 2] = min(len(p.forest), MAX_WOODY) / MAX_WOODY
        v[i + 3] = min(sum(1 for w in p.forest if w.species is None), 10) / 10.0
        v[i + 4] = min(sum(1 for w in p.forest if w.is_fully_occupied()), 10) / 10.0
        sp = i + 5
        sy = sp + self.n_species
        for w in p.forest:
            if w.species:
                v[sp + self.db.species_index[w.species]] += 0.25
            if w.tree_symbol:
                v[sy + self.db.symbol_index[w.tree_symbol]] += 0.125
            for d in w.dwellers():
                v[sp + self.db.species_index[d.species]] += 0.25
                v[sy + self.db.symbol_index[d.tree_symbol]] += 0.125

    def _plant(self, v, j, w):
        v[j + (self.db.species_index[w.species] if w.species else self.n_species)] = 1.0
        j += self.n_species + 1
        v[j + (self.db.symbol_index[w.tree_symbol] if w.tree_symbol else self.n_symbols)] = 1.0
        j += self.n_symbols + 1
        for slot in SLOTS:
            occ = w.slots[slot]
            if occ:
                v[j] = 1.0
                v[j + 1] = min(len(occ), 4) / 4.0
                for d in occ:
                    for t in d.types:
                        if t in self.type_index:
                            v[j + 2 + self.type_index[t]] = 1.0
            j += self.slot_size

    def encode(self, game, seat: int) -> np.ndarray:
        s = game.state
        v = np.zeros(self.size, dtype=np.float32)
        i = 0
        v[0] = s.winter_revealed / 3.0
        v[1] = len(s.deck) / 233.0
        v[2] = min(len(s.clearing), 15) / 15.0
        v[3] = min(s.extra_turns, 3) / 3.0
        phase = 0 if not s.decisions else 1 + ALL_DECISION_KINDS.index(s.decisions[-1].kind)
        v[4 + phase] = 1.0
        i += self.global_size
        if s.decisions:
            d = s.decisions[-1]
            key = d.data.get("species") or (d.data.get("source") or {}).get("species")
            if key in self.db.species_index:
                v[i + self.db.species_index[key]] = 1.0
            rem = d.data.get("remaining")
            v[i + self.n_species] = (min(rem, 3) / 3.0) if isinstance(rem, int) else (1.0 if rem == "any" else 0.0)
        i += self.context_size
        add_counts(v, i, (c.def_id for c in s.players[seat].hand), 0.25, self.n_defs)
        i += self.n_defs
        add_counts(v, i, (c.def_id for c in s.clearing), 0.25, self.n_defs)
        i += self.n_defs
        for k in range(self.num_players):
            self._summary(v, i, s.players[(seat + k) % self.num_players])
            i += self.summary_size
        for w in s.players[seat].forest[:ENCODER_PLANTS]:
            self._plant(v, i, w)
            i += self.plant_size
        if self.version >= 2:
            self._v2(v, self.v1_size, s, seat)
        return np.clip(v, 0.0, 1.0, out=v)

    def _v2(self, v, i, s, seat):
        order = [(seat + k) % self.num_players for k in range(self.num_players)]
        scores = [score_player(self.db, s.players, j) for j in range(self.num_players)]
        for j in order:
            v[i] = scores[j] / 300.0
            for k, side in enumerate(SLOTS):
                v[i + 1 + k] = sum(1 for w in s.players[j].forest if not w.slots[side]) / 20.0
            i += 1 + len(SLOTS)
        v[i] = 0.5 + (scores[seat] - max(sc for j, sc in enumerate(scores) if j != seat)) / 200.0
        i += 1
        for j in order[1:]:
            p = s.players[j]
            for c in p.hand:
                if c.uid in p.known and c.def_id < self.n_defs:
                    v[i + c.def_id] += 0.25
            i += self.n_defs
