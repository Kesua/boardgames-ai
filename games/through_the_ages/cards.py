"""Card data (data/cards.json, 292 cards, id 0-291), loaded once, with precomputed static lookups (PLAN.md section 2).

Everything here is read-only; the engine indexes these lists by card id on hot paths.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CARDS = json.loads((Path(__file__).resolve().parent / "data" / "cards.json").read_text(encoding="utf-8"))
N_CARDS = len(CARDS)
assert [c["id"] for c in CARDS] == list(range(N_CARDS))

AGES = ("A", "I", "II", "III", "IV")
LEVEL_OF = {"A": 0, "I": 1, "II": 2, "III": 3, "IV": 4}            # T11.10
NEXT_AGE = {"A": "I", "I": "II", "II": "III", "III": "IV"}

FARM_MINE = ("farm", "mine")
URBAN = ("lab", "temple", "library", "theater", "arena")
UNITS = ("infantry", "cavalry", "artillery", "air_force")
BUILDINGS = FARM_MINE + URBAN                                       # built/upgraded/destroyed with civil actions
SPECIALS = ("special_civil", "special_military", "special_colonization", "special_construction")
TECH_KINDS = BUILDINGS + UNITS + SPECIALS + ("government",)         # T1.4: civil cards with a science cost
MILITARY_KINDS = ("event", "territory", "aggression", "war", "pact", "tactic", "bonus")

# statistic indices of the per-player statistics vector (economy.Stats)
S_CIVIL, S_MIL, S_CULT, S_SCI, S_HAPPY, S_UNHAPPY, S_STR, S_COLON, S_RESB, S_FOODB = range(10)
N_STATS = 10
_STAT_OF = {"civil_actions": S_CIVIL, "military_actions": S_MIL, "culture": S_CULT, "science": S_SCI,
            "happy": S_HAPPY, "unhappy": S_UNHAPPY, "strength": S_STR, "colonization": S_COLON}


def _key(name: str, age: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_") + "_" + age.lower()


NAME = [c["name"] for c in CARDS]
AGE = [c["age"] for c in CARDS]
LEVEL = [LEVEL_OF[a] for a in AGE]
KIND = [c["kind"] for c in CARDS]
DECK_OF = [c["deck"] for c in CARDS]
SET = [c["set"] for c in CARDS]
KEY = [_key(c["name"], c["age"]) for c in CARDS]
assert len(set(KEY)) == N_CARDS
SCIENCE_COST = [c["science_cost"] for c in CARDS]
REVOLUTION_COST = [c["revolution_cost"] for c in CARDS]
RESOURCE_COST = [c["resource_cost"] for c in CARDS]
STAGE_COSTS = [tuple(c["stage_costs"]) if c["stage_costs"] else () for c in CARDS]
URBAN_LIMIT = [c["urban_limit"] for c in CARDS]
MILITARY_ACTION_COST = [c["military_action_cost"] for c in CARDS]
TACTIC = [c["tactic"] for c in CARDS]
BONUS = [c["bonus"] for c in CARDS]
EFFECT = [c["effect"] for c in CARDS]
EFFECT_TYPE = [c["effect"]["type"] if c["effect"] else None for c in CARDS]
STARTING = [c["id"] for c in CARDS if c["starting"]]
IS_STARTING = [bool(c["starting"]) for c in CARDS]
IS_TECH = [c["deck"] == "civil" and c["kind"] in TECH_KINDS for c in CARDS]
HOLDS_WORKERS = [c["kind"] in BUILDINGS + UNITS for c in CARDS]
IS_URBAN = [c["kind"] in URBAN for c in CARDS]
IS_UNIT = [c["kind"] in UNITS for c in CARDS]


def copies(card: int, players: int) -> int:
    cp = CARDS[card]["copies"]
    return cp[str(players)] if cp else 0


def _token_value(c) -> int:
    y = c["yields"] or {}
    if c["kind"] == "farm":
        return y.get("food", 0)
    if c["kind"] == "mine":
        return y.get("resources", 0)
    return 0


TOKEN_VALUE = [_token_value(c) for c in CARDS]                       # T12.1: food / resources per blue token


def _stat_yields(c) -> tuple:
    """(stat index, value) pairs from the card's bottom symbols; farm/mine token values and token symbols excluded."""
    out = []
    for k, v in (c["yields"] or {}).items():
        if k in _STAT_OF:
            out.append((_STAT_OF[k], v))
        elif k == "resources" and c["kind"] != "mine":
            out.append((S_RESB, v))                                  # production bonus (T15.6), e.g. Communism
        elif k == "food" and c["kind"] != "farm":
            out.append((S_FOODB, v))
    return tuple(out)


STAT_YIELDS = [_stat_yields(c) for c in CARDS]
TOKEN_SYMBOLS = [((c["yields"] or {}).get("blue_tokens", 0), (c["yields"] or {}).get("yellow_tokens", 0))
                 for c in CARDS]                                     # T11.9 (D17: plain = gain, minus = lose)

BY_NAME_AGE = {(c["name"], c["age"]): c["id"] for c in CARDS}
BY_KEY = {k: i for i, k in enumerate(KEY)}


def card_id(name: str, age: str = None) -> int:
    """Card id by name (and age when the name exists in several ages)."""
    if age is not None:
        return BY_NAME_AGE[(name, age)]
    hits = [i for i, n in enumerate(NAME) if n == name]
    if len(hits) != 1:
        raise KeyError(f"{name!r}: {len(hits)} cards, give the age")
    return hits[0]


DESPOTISM = card_id("Despotism")
AGRICULTURE = card_id("Agriculture")
BRONZE = card_id("Bronze")
PHILOSOPHY = card_id("Philosophy")
RELIGION = card_id("Religion")
WARRIORS = card_id("Warriors")

LEADERS_BY_AGE = {a: [c["id"] for c in CARDS if c["kind"] == "leader" and c["age"] == a] for a in AGES[:4]}
WONDERS_BY_AGE = {a: [c["id"] for c in CARDS if c["kind"] == "wonder" and c["age"] == a] for a in AGES[:4]}


def civil_deck_cards(age: str, players: int) -> list:
    """Civil cards of an age's deck except leaders and wonders (they come from the public mix, T15.4), with
    copies for the player count (T2.1)."""
    out = []
    for c in CARDS:
        if c["deck"] == "civil" and c["age"] == age and c["kind"] not in ("leader", "wonder") and c["copies"]:
            out += [c["id"]] * c["copies"][str(players)]
    return out


def military_deck_cards(age: str, players: int) -> list:
    """Military cards of an age with copies for the player count (pacts have no 2-player copies, T2.2)."""
    out = []
    for c in CARDS:
        if c["deck"] == "military" and c["age"] == age and c["copies"]:
            out += [c["id"]] * c["copies"][str(players)]
    return out
