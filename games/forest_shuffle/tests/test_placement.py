import pytest
from games.forest_shuffle.core.cards import HalfDef
from games.forest_shuffle.core.state import make_dweller, make_sapling
from games.forest_shuffle.engine.placement import can_place


def dw(db, species, pos, sym="BEECH", uid=1):
    return make_dweller(db, uid, HalfDef(pos, species, sym))


@pytest.mark.rule("F4.4")
def test_empty_slot_ok(db):
    w = make_sapling(0)
    assert can_place(db, w, "TAWNY_OWL", "TOP")
    assert not can_place(db, w, "TAWNY_OWL", "BOTTOM")
    assert can_place(db, w, "WOLF", "LEFT") and can_place(db, w, "WOLF", "RIGHT")


@pytest.mark.rule("F4.4")
@pytest.mark.card("EUROPEAN_HARE")
def test_hares_stack_unlimited(db):
    w = make_sapling(0)
    for i in range(5):
        assert can_place(db, w, "EUROPEAN_HARE", "LEFT")
        w.slots["LEFT"].append(dw(db, "EUROPEAN_HARE", "LEFT", uid=i))
    assert not can_place(db, w, "MOUNTAIN_HARE", "LEFT")


@pytest.mark.rule("F4.4")
@pytest.mark.card("MOUNTAIN_HARE")
def test_mountain_hare_never_shares(db):
    w = make_sapling(0)
    w.slots["LEFT"].append(dw(db, "MOUNTAIN_HARE", "LEFT"))
    assert not can_place(db, w, "EUROPEAN_HARE", "LEFT")


@pytest.mark.rule("F4.4")
@pytest.mark.card("COMMON_TOAD")
def test_toads_max_two(db):
    w = make_sapling(0)
    w.slots["BOTTOM"].append(dw(db, "COMMON_TOAD", "BOTTOM", uid=1))
    assert can_place(db, w, "COMMON_TOAD", "BOTTOM")
    w.slots["BOTTOM"].append(dw(db, "COMMON_TOAD", "BOTTOM", uid=2))
    assert not can_place(db, w, "COMMON_TOAD", "BOTTOM")


@pytest.mark.rule("F4.4")
@pytest.mark.card("STINGING_NETTLE")
def test_nettle_lets_butterflies_share_top(db):
    w = make_sapling(0)
    w.slots["TOP"].append(dw(db, "PEACOCK_BUTTERFLY", "TOP"))
    assert not can_place(db, w, "MAP_BUTTERFLY", "TOP")
    w.slots["BOTTOM"].append(dw(db, "STINGING_NETTLE", "BOTTOM"))
    assert can_place(db, w, "MAP_BUTTERFLY", "TOP")
    assert not can_place(db, w, "TAWNY_OWL", "TOP")
