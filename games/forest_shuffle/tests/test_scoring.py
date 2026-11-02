import pytest
from games.forest_shuffle.engine.scoring import score_player
from games.forest_shuffle.tests.conftest import attach, give, plant


def sc(game, seat=0):
    return score_player(game.db, game.state.players, seat)


@pytest.mark.rule("F6.2")
@pytest.mark.card("EUROPEAN_HARE")
@pytest.mark.card("BIRCH")
def test_five_hares_score_25(game):
    t = plant(game, 0, "BIRCH")
    for _ in range(5):
        attach(game, 0, t, "EUROPEAN_HARE")
    assert sc(game) == 1 + 25


@pytest.mark.rule("F6.2")
@pytest.mark.card("MOUNTAIN_HARE")
@pytest.mark.card("EUROPEAN_HARE")
def test_mountain_and_european_hares_36(game):
    t1, t2, t3 = plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH")
    for _ in range(4):
        attach(game, 0, t1, "EUROPEAN_HARE")
    attach(game, 0, t2, "MOUNTAIN_HARE")
    attach(game, 0, t3, "MOUNTAIN_HARE")
    assert sc(game) == 3 + 36


@pytest.mark.rule("F6.2")
@pytest.mark.card("LINDEN")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_linden_majority_with_bee(game):
    for _ in range(4):
        plant(game, 1, "LINDEN")
    a = plant(game, 0, "LINDEN")
    plant(game, 0, "LINDEN")
    plant(game, 0, "LINDEN")
    attach(game, 0, a, "VIOLET_CARPENTER_BEE")
    assert sc(game, 0) == 9
    assert sc(game, 1) == 12


@pytest.mark.rule("F6.3")
@pytest.mark.card("HORSE_CHESTNUT")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_horse_chestnut_set_with_bee(game):
    a = plant(game, 0, "HORSE_CHESTNUT")
    plant(game, 0, "HORSE_CHESTNUT")
    assert sc(game) == 4
    attach(game, 0, a, "VIOLET_CARPENTER_BEE")
    assert sc(game) == 9


@pytest.mark.rule("F6.2")
@pytest.mark.card("OAK")
@pytest.mark.card("SYCAMORE")
@pytest.mark.card("DOUGLAS_FIR")
@pytest.mark.card("LINDEN")
def test_oak_needs_eight_species(game):
    plant(game, 0, "OAK")
    assert sc(game) == 0
    for k in ["LINDEN", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE", "DOUGLAS_FIR", "HORSE_CHESTNUT"]:
        plant(game, 0, k)
    # oak 10, linden 3, silver fir 0, birch 1, beech 0, sycamore 8, douglas fir 5, horse chestnut 1
    assert sc(game) == 28


@pytest.mark.rule("F6.3")
@pytest.mark.card("PEACOCK_BUTTERFLY")
@pytest.mark.card("MAP_BUTTERFLY")
def test_butterfly_sets(game):
    t, t2, t3 = plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH")
    attach(game, 0, t, "PEACOCK_BUTTERFLY")
    attach(game, 0, t2, "PEACOCK_BUTTERFLY")
    attach(game, 0, t3, "MAP_BUTTERFLY")
    assert sc(game) == 3 + 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("COMMON_TOAD")
def test_common_toads(game):
    t = plant(game, 0, "BIRCH")
    attach(game, 0, t, "COMMON_TOAD")
    assert sc(game) == 1
    attach(game, 0, t, "COMMON_TOAD")
    assert sc(game) == 11


@pytest.mark.rule("F6.2")
@pytest.mark.card("SILVER_FIR")
@pytest.mark.card("WOOD_ANT")
@pytest.mark.card("BEECH_MARTEN")
@pytest.mark.card("TAWNY_OWL")
@pytest.mark.card("SQUEAKER")
def test_silver_fir_wood_ant_marten(game):
    f = plant(game, 0, "SILVER_FIR")
    game.debug_place_dweller(0, f, give(game, 0, "WOOD_ANT").def_id, "WOOD_ANT")
    attach(game, 0, f, "TAWNY_OWL")
    attach(game, 0, f, "BEECH_MARTEN", "SYCAMORE")
    assert not game.state.players[0].forest[f].is_fully_occupied()
    attach(game, 0, f, "SQUEAKER", "OAK")
    assert game.state.players[0].forest[f].is_fully_occupied()
    # silver fir 8, wood ant 2, owl 5, marten 5, squeaker 1
    assert sc(game) == 21


@pytest.mark.rule("F6.3")
@pytest.mark.card("FIREFLIES")
def test_fireflies_scored_once(game):
    t, t2 = plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH")
    attach(game, 0, t, "FIREFLIES")
    attach(game, 0, t2, "FIREFLIES")
    assert sc(game) == 2 + 10


@pytest.mark.rule("F6.2")
@pytest.mark.card("BEARDED_VULTURE")
def test_cave_and_vulture(game):
    game.state.players[0].cave.extend(game.state.deck[:3])
    del game.state.deck[:3]
    t = plant(game, 0, "BIRCH")
    attach(game, 0, t, "BEARDED_VULTURE")
    assert sc(game) == 1 + 3 + 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("DIGITALIS")
@pytest.mark.card("ALPINE_MARMOT")
def test_digitalis_and_marmot_distinct_plants(game):
    t, t2 = plant(game, 0, "BIRCH"), plant(game, 0, "BIRCH")
    attach(game, 0, t, "DIGITALIS")
    attach(game, 0, t2, "MOSS")
    attach(game, 0, t, "ALPINE_MARMOT")
    assert sc(game) == 2 + 3 + 0 + 6


@pytest.mark.rule("F6.2")
@pytest.mark.card("EUROPEAN_FAT_DORMOUSE")
@pytest.mark.card("CHAFFINCH")
@pytest.mark.card("NIGHTINGALE")
@pytest.mark.card("EUROPEAN_POLECAT")
def test_dormouse_polecat_chaffinch_nightingale(game):
    t = plant(game, 0, "BEECH")
    attach(game, 0, t, "EUROPEAN_FAT_DORMOUSE")
    assert sc(game) == 0
    attach(game, 0, t, "BARBASTELLE_BAT")
    assert sc(game) == 15
    attach(game, 0, t, "CHAFFINCH")
    assert sc(game) == 20
    s = plant(game, 0, "ELDERBERRY")
    attach(game, 0, s, "EUROPEAN_POLECAT")
    attach(game, 0, s, "NIGHTINGALE")
    assert sc(game) == 20 + 0 + 5          # polecat not alone
