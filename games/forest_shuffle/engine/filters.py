"""Card filters and counting used by effects, triggers and scoring."""
from __future__ import annotations


def _name_matches(db, species_key, names) -> bool:
    if species_key is None:
        return False
    return species_key in names or db.species[species_key].counts_as in names


def card_matches(db, card_types, species_key, kind, flt: dict) -> bool:
    checks = []
    if "types" in flt:
        checks.append(any(t in card_types for t in flt["types"]))
    if "names" in flt:
        checks.append(_name_matches(db, species_key, flt["names"]))
    if "kinds" in flt:
        checks.append(kind in flt["kinds"])
    if not checks:
        return True
    return any(checks) if flt.get("match") == "any" else all(checks)


def _entries(forest):
    for w in forest:
        yield (w.types, w.species, w.kind, w, None)
        for d in w.dwellers():
            yield (d.types, d.species, "DWELLER", w, d)


def count_cards(db, forest, flt: dict, with_modifiers: bool) -> int:
    seen, n = set(), 0
    for types, key, kind, host, dweller in _entries(forest):
        if not card_matches(db, types, key, kind, flt):
            continue
        if flt.get("distinct"):
            canon = (db.species[key].counts_as or key) if key else "SAPLING"
            if canon in seen:
                continue
            seen.add(canon)
        n += 1
    if with_modifiers:
        for w in forest:
            if card_matches(db, w.types, w.species, w.kind, flt):
                n += sum((db.species[d.species].modifiers or {}).get("host_tree_count_bonus", 0) for d in w.dwellers())
    return n


def shows_symbol(db, card_def, symbol: str) -> bool:
    if card_def.layout == "WOODY_PLANT":
        return card_def.tree_symbol == symbol
    return any(h.tree_symbol == symbol for h in card_def.halves)


def forest_symbol_count(forest, symbols) -> int:
    n = sum(1 for w in forest if w.tree_symbol in symbols)
    return n + sum(1 for w in forest for d in w.dwellers() if d.tree_symbol in symbols)


def tree_species_set(db, forest) -> set:
    out = set()
    for w in forest:
        if w.kind == "TREE" and w.species:
            out.add(db.species[w.species].tree_species or w.species)
    return out


def def_matches(db, card_def, flt: dict) -> bool:
    """A hand/clearing card matches if its woody species or any half matches."""
    if card_def.layout == "WINTER":
        return False
    if card_def.layout == "WOODY_PLANT":
        sp = db.species[card_def.species]
        return card_matches(db, tuple(sp.types), card_def.species, sp.kind, flt)
    return any(card_matches(db, db.half_types(h), h.species, "DWELLER", flt) for h in card_def.halves)
