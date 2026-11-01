from games.forest_shuffle.core.cards import HalfDef
from games.forest_shuffle.core.state import make_dweller, make_sapling, make_woody
from games.forest_shuffle.engine.filters import count_cards, shows_symbol, tree_species_set


def woody(db, key, uid=0):
    d = next(d for d in db.defs if d.species == key)
    return make_woody(db, uid, d, 0)


def test_kinds_tree_includes_saplings(db):
    forest = [woody(db, "BEECH"), make_sapling(0)]
    assert count_cards(db, forest, {"kinds": ["TREE"]}, False) == 2
    assert count_cards(db, forest, {"names": ["BEECH"]}, False) == 1


def test_counts_as(db):
    w = make_sapling(0)
    w.slots["LEFT"].append(make_dweller(db, 1, HalfDef("LEFT", "MOUNTAIN_HARE", "SWISS_PINE")))
    w.slots["RIGHT"].append(make_dweller(db, 2, HalfDef("RIGHT", "EUROPEAN_HARE", "BIRCH")))
    assert count_cards(db, [w], {"names": ["EUROPEAN_HARE"]}, False) == 2


def test_bee_modifier_only_with_modifiers(db):
    b = woody(db, "BEECH")
    b.slots["LEFT"].append(make_dweller(db, 1, HalfDef("LEFT", "VIOLET_CARPENTER_BEE", "DOUGLAS_FIR")))
    assert count_cards(db, [b], {"names": ["BEECH"]}, True) == 2
    assert count_cards(db, [b], {"names": ["BEECH"]}, False) == 1
    assert count_cards(db, [b], {"kinds": ["TREE"]}, True) == 2


def test_distinct_and_any(db):
    w, w2 = make_sapling(0), make_sapling(0)
    w.slots["BOTTOM"].append(make_dweller(db, 1, HalfDef("BOTTOM", "MOSS", "LINDEN")))
    w2.slots["BOTTOM"].append(make_dweller(db, 2, HalfDef("BOTTOM", "MOSS", "LINDEN")))
    forest = [w, w2]
    assert count_cards(db, forest, {"types": ["PLANT"], "distinct": True}, False) == 1
    assert count_cards(db, forest, {"kinds": ["TREE"], "types": ["PLANT"], "match": "any"}, False) == 4


def test_shows_symbol_any_half(db):
    d = db.defs[db.code_index["BH001"]]
    assert shows_symbol(db, d, "LINDEN") and shows_symbol(db, d, "DOUGLAS_FIR") and not shows_symbol(db, d, "OAK")


def test_tree_species_uses_alpine_names(db):
    forest = [woody(db, "EUROPEAN_LARCH"), make_sapling(0)]
    assert tree_species_set(db, forest) == {"ALPINE_LARCH"}
