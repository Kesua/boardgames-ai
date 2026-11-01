"""Data-driven scoring."""
from __future__ import annotations

from .filters import count_cards, forest_symbol_count, tree_species_set


def _table(table: dict, count: int) -> int:
    best = [int(k) for k in table if int(k) <= count]
    return table[str(max(best))] if best else 0


def _condition(db, players, seat, host, dweller, c) -> bool:
    forest = players[seat].forest
    t = c["type"]
    if t == "min_count":
        return count_cards(db, forest, c["filter"], True) >= c["count"]
    if t == "min_distinct":
        return count_cards(db, forest, dict(c["filter"], distinct=True), False) >= c["count"]
    if t == "host_species":
        return host.species == c["species"]
    if t == "host_kind":
        return host.kind == c["kind"]
    if t == "host_has":
        if host.kind not in c.get("host_kinds", ["TREE", "SHRUB"]):
            return False
        return any(d is not dweller and any(x in d.types for x in c["filter"]["types"]) for d in host.dwellers())
    if t == "alone_on_host":
        return len(host.dwellers()) == 1
    if t == "shares_slot_with":
        return any(d is not dweller and d.species in c["names"] for d in host.slots[dweller.position])
    if t == "all_tree_species":
        return len(tree_species_set(db, forest)) >= c["count"]
    if t == "min_trees":
        return count_cards(db, forest, {"kinds": ["TREE"]}, True) >= c["count"]
    raise ValueError(t)


def score_card(db, players, seat, host, dweller, species_key, rule, seen_sets) -> int:
    forest = players[seat].forest
    t = rule["type"]
    sp = db.species[species_key]
    if t == "flat":
        return rule["points"]
    if t == "per_card":
        return rule["points"] * count_cards(db, forest, rule["filter"], False)
    if t == "per_tree_symbol":
        if rule["symbols"] == "SELF":
            syms = [dweller.tree_symbol if dweller else host.tree_symbol]
        else:
            syms = rule["symbols"]
        return rule["points"] * forest_symbol_count(forest, syms)
    if t == "conditional":
        return rule["points"] if _condition(db, players, seat, host, dweller, rule["condition"]) else 0
    if t == "majority":
        mine = count_cards(db, forest, rule["filter"], True)
        others = [count_cards(db, p.forest, rule["filter"], True) for i, p in enumerate(players) if i != seat]
        return rule["points_if_most"] if all(mine >= o for o in others) else rule["points_otherwise"]
    if t == "set":
        canon = sp.counts_as or species_key
        if canon in seen_sets:
            return 0
        seen_sets.add(canon)
        return _table(rule["table"], count_cards(db, forest, {"names": [canon]}, True))
    if t == "table_by_count":
        return _table(rule["table"], count_cards(db, forest, rule["filter"], False))
    if t == "butterfly_set":
        if "BUTTERFLIES" in seen_sets:
            return 0
        seen_sets.add("BUTTERFLIES")
        names = [d.species for w in forest for d in w.dwellers() if "BUTTERFLY" in d.types]
        sets = []
        for n in names:
            for s in sets:
                if n not in s:
                    s.add(n)
                    break
            else:
                sets.append({n})
        return sum(_table(db.meta["butterfly_table"], len(s)) for s in sets)
    if t == "per_cave_card":
        return rule["points"] * len(players[seat].cave)
    if t == "per_attached_to_host":
        return rule["points"] * len(host.dwellers())
    if t == "per_fully_occupied":
        return rule["points"] * sum(1 for w in forest if w.kind in rule["host_kinds"] and w.is_fully_occupied())
    if t == "per_card_in_slot":
        return rule["points"] * sum(len(w.slots[rule["slot"]]) for w in forest if w.kind in rule["host_kinds"])
    raise ValueError(t)


def score_breakdown(db, players, seat) -> dict:
    seen, trees, dwellers = set(), 0, 0
    for w in players[seat].forest:
        if w.species:
            trees += score_card(db, players, seat, w, None, w.species, db.species[w.species].scoring, seen)
        for d in w.dwellers():
            dwellers += score_card(db, players, seat, w, d, d.species, db.species[d.species].scoring, seen)
    cave = len(players[seat].cave)
    return {"trees": trees, "dwellers": dwellers, "cave": cave, "total": trees + dwellers + cave}


def score_player(db, players, seat) -> int:
    return score_breakdown(db, players, seat)["total"]


def score_cards(db, players, seat) -> list:
    """Per placed card: (forest_idx, slot or None, species, points). Set-scored species attribute points to the first copy."""
    seen, out = set(), []
    for idx, w in enumerate(players[seat].forest):
        if w.species:
            out.append((idx, None, w.species, score_card(db, players, seat, w, None, w.species, db.species[w.species].scoring, seen)))
        for slot, occ in w.slots.items():
            for d in occ:
                out.append((idx, slot, d.species, score_card(db, players, seat, w, d, d.species, db.species[d.species].scoring, seen)))
    return out
