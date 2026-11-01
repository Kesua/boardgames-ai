"""Loads cards.json into Species / CardDef objects."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..core.cards import CardDef, HalfDef, Species


class CardDatabase:
    def __init__(self, raw: dict):
        self.meta = raw["meta"]
        self.species: dict[str, Species] = {}
        for k, v in raw["species"].items():
            self.species[k] = Species(
                key=k, name=v["name"], kind=v["kind"], position=v["position"], expansion=v["expansion"],
                types=tuple(v["types"]), cost=v["cost"], effect=v["effect"], bonus=v["bonus"], scoring=v["scoring"],
                slot_sharing=v.get("slot_sharing"), counts_as=v.get("counts_as"),
                grants_host_slot_sharing=v.get("grants_host_slot_sharing"), modifiers=v.get("modifiers"),
                tree_species=v.get("tree_species"), display_name=v.get("display_name"))
        self.species_index = {k: i for i, k in enumerate(self.species)}
        self.symbol_index = {s: i for i, s in enumerate(self.meta["tree_symbols"])}
        play = [c for c in raw["cards"] if c["layout"] != "WINTER"]
        winter = [c for c in raw["cards"] if c["layout"] == "WINTER"]
        self.defs: list[CardDef] = []
        for i, c in enumerate(play + winter):
            halves = tuple(HalfDef(h["position"], h["species"], h["tree_symbol"], tuple(h.get("extra_types", [])))
                           for h in c.get("halves", []))
            self.defs.append(CardDef(def_id=i, card_code=c["id"], layout=c["layout"], expansion=c["expansion"],
                                     count=c["count"], species=c.get("species"), tree_symbol=c.get("tree_symbol"),
                                     halves=halves))
        self.winter_def_id = len(self.defs) - 1
        self.num_play_defs = len(play)
        self.code_index = {d.card_code: d.def_id for d in self.defs}

    @classmethod
    def load(cls, path: Optional[str] = None) -> "CardDatabase":
        p = Path(path) if path else Path(__file__).with_name("cards.json")
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def half_types(self, half: HalfDef) -> tuple:
        return tuple(self.species[half.species].types) + tuple(half.extra_types)

    def card_label(self, def_id: int) -> str:
        d = self.defs[def_id]
        if d.layout == "WINTER":
            return "Winter"
        if d.layout == "WOODY_PLANT":
            return f"{self.species[d.species].label} [{d.tree_symbol}]"
        return " | ".join(f"{self.species[h.species].label} [{h.tree_symbol}]" for h in d.halves)
