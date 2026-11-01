"""Card data of Wingspan, loaded once from data/birds.json and data/bonus_cards.json."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

FOODS = ("invertebrate", "seed", "fish", "fruit", "rodent")
INV, SEED, FISH, FRUIT, RODENT = range(5)
HABITATS = ("forest", "grassland", "wetland")
NESTS = ("bowl", "cavity", "ground", "platform", "star", "none")
COLORS = ("brown", "white", "pink", "none")
DUAL = 5                                   # die face index of invertebrate-or-seed
FACES = FOODS + ("invertebrate_or_seed",)
DATA = Path(__file__).with_name("data")


def slug(name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


@dataclass(frozen=True)
class Bird:
    id: int
    key: str
    name: str
    points: int
    habitats: tuple            # habitat indices
    nest: str
    egg_limit: int
    wingspan: int
    food: tuple                # count per food type (5)
    wild: int
    alternative: bool          # "/" cost: pay exactly one of the listed foods
    food_total: int
    color: str
    predator: bool
    flocking: bool
    swift_start: bool
    power: dict
    words: dict

    def requirements(self) -> tuple:
        """Food cost as a tuple of requirements; each requirement = tuple of acceptable food indices."""
        if self.alternative:
            return (tuple(i for i in range(5) if self.food[i]),)
        req = []
        for i in range(5):
            req += [(i,)] * self.food[i]
        req += [tuple(range(5))] * self.wild
        return tuple(req)

    def has_nest(self, nest: str) -> bool:
        return self.nest == nest or self.nest == "star"


@dataclass(frozen=True)
class BonusCard:
    id: int
    name: str
    count: dict
    tiers: tuple
    per: int


@lru_cache(maxsize=1)
def birds() -> tuple:
    raw = json.loads((DATA / "birds.json").read_text(encoding="utf-8"))
    out = []
    for b in raw:
        out.append(Bird(id=b["id"], key=slug(b["name"]), name=b["name"], points=b["points"],
                        habitats=tuple(HABITATS.index(h) for h in b["habitats"]), nest=b["nest"],
                        egg_limit=b["egg_limit"], wingspan=b["wingspan"],
                        food=tuple(b["food"].get(f, 0) for f in FOODS), wild=b["wild"], alternative=b["alternative"],
                        food_total=b["food_total"], color=b["color"], predator=b["predator"],
                        flocking=b["flocking"], swift_start=b["swift_start"], power=b["power"], words=b["words"]))
    return tuple(out)


@lru_cache(maxsize=1)
def bonus_data() -> dict:
    return json.loads((DATA / "bonus_cards.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def bonus_cards() -> tuple:
    return tuple(BonusCard(id=c["id"], name=c["name"], count=c["count"], tiers=tuple(tuple(t) for t in c.get("tiers", ())),
                           per=c.get("per", 0)) for c in bonus_data()["cards"])


@lru_cache(maxsize=1)
def goal_tiles() -> tuple:
    return tuple(tuple(side for side in tile) for tile in bonus_data()["goals"]["tiles"])


@lru_cache(maxsize=1)
def goal_ids() -> tuple:
    return tuple(side["id"] for tile in goal_tiles() for side in tile)


def power_kinds() -> tuple:
    """All effect types (fixed order; part of the observation layout)."""
    return ("none", "gain_feeder", "gain_supply", "all_gain_supply", "lay_egg", "lay_each_nest", "all_lay_nest", "draw",
            "all_draw_deck", "fewest_draw", "fewest_die", "each_gain_die", "tuck_hand", "food_for_tucks", "egg_for_wild",
            "egg_for_cards", "hunt_card", "hunt_dice", "move", "repeat", "trade_food", "draw_bonus", "gain_all_feeder",
            "play_another", "oystercatcher", "take_tray", "pink_play", "pink_lay_eggs", "pink_gain_food_rodent",
            "pink_predator")
