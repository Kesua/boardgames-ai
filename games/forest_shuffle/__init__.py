"""Forest Shuffle (base game + Woodland Edge + Alpine), Lookout Games 2023. See README.md and rules.md here."""
from __future__ import annotations

from functools import lru_cache

from bgai.game import GameSpec

from .core.enums import ALL_EXPANSIONS, MAX_WOODY


@lru_cache(maxsize=1)
def card_db():
    from .data.database import CardDatabase
    return CardDatabase.load()


def new_game(num_players: int, seed: int, options: dict = None):
    from .engine.game import Game
    expansions = tuple((options or {}).get("expansions", ALL_EXPANSIONS))
    g = Game(card_db(), num_players, seed, expansions)
    g.reset()
    return g


def action_count(num_players: int) -> int:
    from .core.actions import ActionCodec
    return ActionCodec(card_db().num_play_defs, MAX_WOODY).size


def encoder(num_players: int, version: int = None):
    from .encoder import StateEncoder
    return StateEncoder(card_db(), num_players, version=version or 2)


def greedy(seed: int = None):
    from .agents import GreedyAgent
    return GreedyAgent(seed)


def summary(frames: dict, manifest: dict) -> dict:
    from .summary import game_sections
    return game_sections(frames, manifest)


def catalog() -> dict:
    """Item (species) attributes and the physical cards that carry each item (a split card carries two)."""
    db = card_db()
    items, cards = {}, {}
    for k, sp in db.species.items():
        items[k] = {"kind": sp.kind, "position": sp.position, "cost": sp.cost, "expansion": sp.expansion,
                    "types": [t for t in sp.types if t not in ("WOODLAND_EDGE", "ALPS")], "tags": {"symbol": []},
                    "cards": []}
    for d in db.defs:
        if d.layout == "WINTER":
            continue
        keys = [(d.species, d.tree_symbol)] if d.species else [(h.species, h.tree_symbol) for h in d.halves]
        cards[d.card_code] = {"label": db.card_label(d.def_id), "items": [k for k, _ in keys], "count": d.count}
        for k, sym in keys:
            items[k]["cards"].append(d.card_code)
            if sym and sym not in items[k]["tags"]["symbol"]:
                items[k]["tags"]["symbol"].append(sym)
    return {"items": items, "cards": cards}


def invariants(g) -> list:
    """Card conservation, unique cards and the hand limit (F3.2), checked by bgai.checks during random games."""
    s, out = g.state, []
    uids = [c.uid for c in s.deck] + [c.uid for c in s.clearing] + [c.uid for c in s.removed]
    for p in s.players:
        uids += [c.uid for c in p.hand] + [c.uid for c in p.cave]
        for w in p.forest:
            uids += ([w.uid] if w.uid is not None else []) + [d.uid for d in w.dwellers()]
        if len(p.hand) > 10:
            out.append(f"P{p.seat} has {len(p.hand)} cards in hand (limit 10)")
    if len(set(uids)) != len(uids):
        out.append("a card is in two places at once")
    total = getattr(g, "_card_total", None)
    if total is None:
        g._card_total = total = len(uids)
    if len(uids) != total:
        out.append(f"card count changed: {len(uids)} instead of {total}")
    return out


SPEC = GameSpec(slug="forest_shuffle", name="Forest Shuffle", players=(2, 3, 4, 5), new_game=new_game,
                action_count=action_count, encoder=encoder, greedy=greedy,
                default_options={"expansions": list(ALL_EXPANSIONS)}, summary=summary, catalog=catalog, invariants=invariants, max_steps=5000,
                encoder_versions=(2, 1))          # version 1 models (trained before observation v2) still play
