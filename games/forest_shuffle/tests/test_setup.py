import pytest
import random

from games.forest_shuffle.engine.setup import build_deck, removal_count

ALL = ("base", "woodland_edge", "alpine")


@pytest.mark.rule("F2.1")
def test_removal_counts():
    assert removal_count(2, ("base",)) == 30 and removal_count(5, ("base",)) == 0     # no extra 10 without expansions
    assert removal_count(2, ("base", "alpine")) == 55
    assert removal_count(3, ALL) == 60 and removal_count(5, ALL) == 30


@pytest.mark.rule("F2.1")
@pytest.mark.rule("F2.2")
def test_deck_size_and_winter_position(db):
    deck, removed = build_deck(db, random.Random(3), 2, ALL)
    assert len(deck) + len(removed) == 233
    assert len(removed) == 90
    winters = [i for i, c in enumerate(deck) if c.def_id == db.winter_def_id]
    assert len(winters) == 3
    third = (len(deck) - 3) // 3
    bottom_start = 2 * third
    assert winters[0] == bottom_start
    assert min(winters) >= bottom_start


@pytest.mark.rule("F2.1")
def test_only_selected_expansions(db):
    deck, removed = build_deck(db, random.Random(0), 4, ("base",))
    assert all(db.defs[c.def_id].expansion == "base" for c in deck + removed)
    assert len(deck) + len(removed) == 161


def test_deterministic(db):
    a, _ = build_deck(db, random.Random(7), 3, ALL)
    b, _ = build_deck(db, random.Random(7), 3, ALL)
    assert [c.uid for c in a] == [c.uid for c in b]
