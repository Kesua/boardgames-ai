import pytest
@pytest.mark.rule("F1.1")
def test_totals(db):
    assert len(db.species) == 92
    assert sum(d.count for d in db.defs) == 233
    assert db.defs[db.winter_def_id].layout == "WINTER"
    assert db.num_play_defs == len(db.defs) - 1


@pytest.mark.rule("F1.1")
def test_half_positions_match_species(db):
    for d in db.defs:
        for h in d.halves:
            sp = db.species[h.species]
            assert sp.position in (h.position, "LEFT_RIGHT")
            if sp.position == "LEFT_RIGHT":
                assert h.position in ("LEFT", "RIGHT")


def test_species_fields(db):
    hare = db.species["EUROPEAN_HARE"]
    assert hare.cost == 0 and hare.slot_sharing == {"with_names": ["EUROPEAN_HARE"], "max": None}
    assert db.species["MOUNTAIN_HARE"].counts_as == "EUROPEAN_HARE"
    assert db.species["EUROPEAN_LARCH"].tree_species == "ALPINE_LARCH"
    assert db.species["OAK"].bonus == {"type": "extra_turn"}


def test_woodland_squeaker_gets_marker_type(db):
    d = db.defs[db.code_index["WH004"]]
    half = next(h for h in d.halves if h.species == "SQUEAKER")
    assert "WOODLAND_EDGE" in half.extra_types
