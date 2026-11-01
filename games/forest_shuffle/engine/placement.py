"""Slot placement legality (stacking, Mountain Hare, Stinging Nettle)."""
from __future__ import annotations


def _nettle_grant(db, woody, position, species_key) -> bool:
    sp_types = db.species[species_key].types
    for d in woody.dwellers():
        g = db.species[d.species].grants_host_slot_sharing
        if g and g["slot"] == position and any(t in sp_types for t in g["filter"]["types"]):
            return True
    return False


def can_place(db, woody, species_key: str, position: str) -> bool:
    sp = db.species[species_key]
    if sp.position == "LEFT_RIGHT":
        if position not in ("LEFT", "RIGHT"):
            return False
    elif sp.position != position:
        return False
    occupants = woody.slots[position]
    if not occupants:
        return True
    if _nettle_grant(db, woody, position, species_key):
        return True
    mine = sp.slot_sharing
    if not mine or species_key not in mine["with_names"]:
        return False
    for o in occupants:
        theirs = db.species[o.species].slot_sharing
        if not theirs or o.species not in mine["with_names"] or species_key not in theirs["with_names"]:
            return False
        if theirs["max"] is not None and len(occupants) >= theirs["max"]:
            return False
    return True


def legal_targets(db, forest, species_key: str, position: str) -> list:
    return [i for i, w in enumerate(forest) if can_place(db, w, species_key, position)]
