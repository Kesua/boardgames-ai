"""One proof per species: its scoring with hand-computed numbers, and its effect or bonus where it has one.

Expected values come from card_catalog.md (the card as written), never from the engine. Saplings are used as hosts
where possible because they score nothing themselves. Species already proven elsewhere carry their card marker there.
"""
import re
from pathlib import Path

import pytest

from bgai.game import load_spec
from games.forest_shuffle.core.actions import Action
from games.forest_shuffle.core.actions import ActionKind as K
from games.forest_shuffle.core.state import make_sapling
from games.forest_shuffle.engine.scoring import score_cards, score_player
from games.forest_shuffle.tests.conftest import attach, give, hand_only, plant, play_half

SYMBOL_TREE = {"ALPINE_LARCH": "EUROPEAN_LARCH", "SWISS_PINE": "STONE_PINE"}     # tree card showing each symbol


def sc(game, seat=0):
    return score_player(game.db, game.state.players, seat)


def pts(game, species, seat=0):
    """Points of all placed copies of one species."""
    return sum(p for _, _, s, p in score_cards(game.db, game.state.players, seat) if s == species)


def sapling(game, seat=0):
    forest = game.state.players[seat].forest
    forest.append(make_sapling(game.state.turn_index))
    return len(forest) - 1


def to_clearing(game, species, symbol=None):
    card = give(game, 0, species, symbol)
    game.state.players[0].hand.remove(card)
    game.state.clearing.append(card)
    return card


def use(game):
    game.step(Action(K.USE))


def skip(game):
    game.step(Action(K.SKIP))


def pay_all(game):
    while game.state.decisions and game.state.decisions[-1].kind == "PAY":
        game.step(next(a for a in game.legal_actions() if a.kind == K.PAY))


def play(game, card, species):
    """Play a woody card, or the half of a split card showing `species` (first legal plant)."""
    if game.db.defs[card.def_id].layout == "WOODY_PLANT":
        game.step(Action(K.PLAY_WOODY, card=card.def_id))
    else:
        play_half(game, card, species)


def play_with_bonus(game, species, symbol, *extra):
    """Hand = the card + `extra`; play it and pay its cost with trees of its own symbol (so the bonus applies)."""
    cost = game.db.species[species].cost
    tree = SYMBOL_TREE.get(symbol, symbol)
    card, *rest = hand_only(game, 0, (species, symbol), *[(tree, None)] * cost, *extra)
    play(game, card, species)
    for c in rest[:cost]:
        game.step(Action(K.PAY, card=c.def_id))
    return rest[cost:]


def resolve(game):
    """Use every offered effect and bonus; place every allowed hand card when a free placement is offered."""
    while game.state.decisions:
        d = game.state.decisions[-1]
        opts = game.legal_actions()
        if d.kind == "USE_OR_SKIP":
            use(game)
        elif d.kind == "PLACE_FREE":
            game.step(next((a for a in opts if a.kind == K.PLAY_HALF), Action(K.DONE)))
        elif d.kind in ("SAPLING_MORE", "PLAY_MORE", "CHOOSE_HAND_CARD"):
            game.step(Action(K.DONE))
        else:                                    # CHOOSE_TARGET, CHOOSE_CLEARING_CARD: first option
            game.step(opts[0])


def placed_uids(game, seat=0):
    return {d.uid for w in game.state.players[seat].forest for d in w.dwellers()}


# ---------------------------------------------------------------------- coverage
def test_every_species_has_a_card_test():
    ids = set(load_spec("forest_shuffle").catalog()["items"])
    src = "".join(f.read_text(encoding="utf-8") for f in Path(__file__).parent.glob("test_*.py"))
    marked = set(re.findall(r'card\("([A-Z_]+)"\)', src))
    assert sorted(ids - marked) == []


# ---------------------------------------------------------------------- fixed points
@pytest.mark.rule("F6.2")
@pytest.mark.parametrize("species, points", [
    pytest.param("BIRCH", 1, marks=pytest.mark.card("BIRCH")),
    pytest.param("DOUGLAS_FIR", 5, marks=pytest.mark.card("DOUGLAS_FIR")),
    pytest.param("EUROPEAN_LARCH", 3, marks=pytest.mark.card("EUROPEAN_LARCH")),
    pytest.param("ELDERBERRY", 0, marks=pytest.mark.card("ELDERBERRY")),
    pytest.param("COMMON_HAZEL", 0, marks=pytest.mark.card("COMMON_HAZEL")),
    pytest.param("BLACKTHORN", 0, marks=pytest.mark.card("BLACKTHORN")),
    pytest.param("EUROPEAN_BADGER", 2, marks=pytest.mark.card("EUROPEAN_BADGER")),
    pytest.param("SQUEAKER", 1, marks=pytest.mark.card("SQUEAKER")),
    pytest.param("TAWNY_OWL", 5, marks=pytest.mark.card("TAWNY_OWL")),
    pytest.param("EURASIAN_JAY", 3, marks=pytest.mark.card("EURASIAN_JAY")),
    pytest.param("POND_TURTLE", 5, marks=pytest.mark.card("POND_TURTLE")),
    pytest.param("EURASIAN_MAGPIE", 3, marks=pytest.mark.card("EURASIAN_MAGPIE")),
    pytest.param("COMMON_RAVEN", 5, marks=pytest.mark.card("COMMON_RAVEN")),
    pytest.param("EDELWEISS", 3, marks=pytest.mark.card("EDELWEISS")),
    pytest.param("STEINBOCK", 10, marks=pytest.mark.card("STEINBOCK")),
    pytest.param("PENNY_BUN", 0, marks=pytest.mark.card("PENNY_BUN")),
    pytest.param("PARASOL_MUSHROOM", 0, marks=pytest.mark.card("PARASOL_MUSHROOM")),
    pytest.param("CHANTERELLE", 0, marks=pytest.mark.card("CHANTERELLE")),
    pytest.param("FLY_AGARIC", 0, marks=pytest.mark.card("FLY_AGARIC")),
    pytest.param("BLACK_TRUMPET", 0, marks=pytest.mark.card("BLACK_TRUMPET")),
    pytest.param("MOLE", 0, marks=pytest.mark.card("MOLE")),
    pytest.param("RACCOON", 0, marks=pytest.mark.card("RACCOON")),
    pytest.param("BROWN_BEAR", 0, marks=pytest.mark.card("BROWN_BEAR")),
    pytest.param("WATER_VOLE", 0, marks=pytest.mark.card("WATER_VOLE")),
    pytest.param("VIOLET_CARPENTER_BEE", 0, marks=pytest.mark.card("VIOLET_CARPENTER_BEE")),
])
def test_fixed_points(game, species, points):
    if game.db.species[species].kind == "DWELLER":
        attach(game, 0, sapling(game), species)            # sapling host scores 0
    else:
        plant(game, 0, species)
    assert sc(game) == points


# ---------------------------------------------------------------------- trees
@pytest.mark.rule("F6.2")
@pytest.mark.card("LINDEN")
def test_linden_without_majority_scores_one(game):
    for _ in range(3):
        plant(game, 1, "LINDEN")
    plant(game, 0, "LINDEN")
    plant(game, 0, "LINDEN")
    assert sc(game, 0) == 2                    # 2 Linden x 1 (other forest has more)
    assert sc(game, 1) == 9                    # 3 Linden x 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("OAK")
@pytest.mark.card("WILD_STRAWBERRIES")
@pytest.mark.card("EUROPEAN_LARCH")
def test_oak_and_strawberries_count_alpine_larch_as_a_species(game):
    for k in ["OAK", "LINDEN", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE", "DOUGLAS_FIR"]:
        plant(game, 0, k)
    attach(game, 0, 3, "WILD_STRAWBERRIES")
    sapling(game)
    assert pts(game, "OAK") == 0 and pts(game, "WILD_STRAWBERRIES") == 0     # 7 species; a sapling is none
    plant(game, 0, "EUROPEAN_LARCH")
    assert pts(game, "OAK") == 10 and pts(game, "WILD_STRAWBERRIES") == 10   # 8 species (Alpine Larch is one)
    assert pts(game, "EUROPEAN_LARCH") == 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("BEECH")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_beech_needs_four_beeches_and_bee_counts(game):
    b = plant(game, 0, "BEECH")
    plant(game, 0, "BEECH")
    plant(game, 0, "BEECH")
    assert pts(game, "BEECH") == 0             # 3 Beech < 4
    attach(game, 0, b, "VIOLET_CARPENTER_BEE")
    assert pts(game, "BEECH") == 15            # 3 Beech + 1 from the bee = 4 → 3 x 5
    plant(game, 0, "BEECH")
    assert pts(game, "BEECH") == 20            # 4 Beech x 5


@pytest.mark.rule("F6.2")
@pytest.mark.card("SYCAMORE")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_sycamore_counts_trees_and_saplings_not_the_bee(game):
    plant(game, 0, "SYCAMORE")
    plant(game, 0, "SYCAMORE")
    b = plant(game, 0, "BIRCH")
    sapling(game)
    attach(game, 0, b, "VIOLET_CARPENTER_BEE")
    assert pts(game, "SYCAMORE") == 8          # 4 trees (2 sycamore, birch, sapling; bee not counted) x 1, twice


@pytest.mark.rule("F6.2")
@pytest.mark.card("STONE_PINE")
def test_stone_pine_counts_alps_cards(game):
    pine = plant(game, 0, "STONE_PINE")
    plant(game, 0, "EUROPEAN_LARCH")
    s = sapling(game)
    attach(game, 0, s, "CHAMOIS")
    attach(game, 0, s, "MOUNTAIN_HARE")
    attach(game, 0, pine, "EUROPEAN_HARE")     # not an Alps card
    assert pts(game, "STONE_PINE") == 4        # stone pine, larch, chamois, mountain hare = 4 Alps x 1


# ---------------------------------------------------------------------- counting dwellers
@pytest.mark.rule("F6.2")
@pytest.mark.card("GREATER_HORSESHOE_BAT")
@pytest.mark.card("BROWN_LONG_EARED_BAT")
@pytest.mark.card("BARBASTELLE_BAT")
@pytest.mark.card("BECHSTEINS_BAT")
@pytest.mark.card("COMMON_PIPISTRELLE")
@pytest.mark.card("SAVIS_PIPISTRELLE")
def test_bats_need_three_different_bats(game):
    s1, s2, s3, s4 = (sapling(game) for _ in range(4))
    attach(game, 0, s1, "GREATER_HORSESHOE_BAT")
    attach(game, 0, s1, "BROWN_LONG_EARED_BAT")
    assert sc(game) == 0                       # 2 different bats
    attach(game, 0, s2, "GREATER_HORSESHOE_BAT")
    assert sc(game) == 0                       # 3 bats, still 2 different
    attach(game, 0, s2, "BARBASTELLE_BAT")
    assert sc(game) == 20                      # 3 different → 4 bats x 5
    attach(game, 0, s3, "BECHSTEINS_BAT")
    attach(game, 0, s3, "COMMON_PIPISTRELLE")
    attach(game, 0, s4, "SAVIS_PIPISTRELLE")
    assert sc(game) == 35                      # 7 bats x 5


@pytest.mark.rule("F6.2")
@pytest.mark.card("GNAT")
@pytest.mark.card("CRANE_FLY")
@pytest.mark.card("BARN_OWL")
@pytest.mark.card("TREE_FROG")
def test_bat_and_gnat_counters(game):
    s1, s2 = sapling(game), sapling(game)
    attach(game, 0, s1, "GNAT")
    attach(game, 0, s1, "CRANE_FLY")
    attach(game, 0, s2, "BARBASTELLE_BAT")
    attach(game, 0, s2, "BECHSTEINS_BAT")
    attach(game, 0, s2, "BARN_OWL")
    attach(game, 0, s2, "TREE_FROG")
    assert pts(game, "GNAT") == 2              # 2 bats x 1
    assert pts(game, "CRANE_FLY") == 2         # 2 bats x 1
    assert pts(game, "BARN_OWL") == 6          # 2 bats x 3
    assert pts(game, "TREE_FROG") == 5         # 1 gnat x 5


@pytest.mark.rule("F6.2")
@pytest.mark.card("GOSHAWK")
@pytest.mark.card("BLUEBERRY")
@pytest.mark.card("EUROPEAN_WILDCAT")
def test_bird_counters(game):
    s1, s2, s3 = sapling(game), sapling(game), sapling(game)
    attach(game, 0, s1, "GOSHAWK")
    attach(game, 0, s1, "BLUEBERRY")
    attach(game, 0, s1, "EUROPEAN_WILDCAT")
    attach(game, 0, s1, "CAPERCAILLIE")
    attach(game, 0, s2, "CHAFFINCH")
    attach(game, 0, s3, "CHAFFINCH")
    assert pts(game, "GOSHAWK") == 12          # 4 birds (goshawk, capercaillie, 2 chaffinch) x 3
    assert pts(game, "EUROPEAN_WILDCAT") == 4  # 4 birds x 1
    assert pts(game, "BLUEBERRY") == 6         # 3 different birds x 2


@pytest.mark.rule("F6.2")
@pytest.mark.card("BLACKBERRIES")
@pytest.mark.card("BEE_SWARM")
@pytest.mark.card("CAPERCAILLIE")
@pytest.mark.card("DIGITALIS")
@pytest.mark.card("ALPINE_MARMOT")
def test_plant_counters(game):
    s1, s2, s3, s4 = (sapling(game) for _ in range(4))
    attach(game, 0, s1, "BLACKBERRIES")
    attach(game, 0, s1, "BEE_SWARM")
    attach(game, 0, s1, "CAPERCAILLIE")
    attach(game, 0, s2, "MOSS")
    attach(game, 0, s3, "MOSS")
    attach(game, 0, s3, "ALPINE_MARMOT")
    attach(game, 0, s4, "DIGITALIS")
    assert pts(game, "BLACKBERRIES") == 8      # 4 plants (blackberries, 2 moss, digitalis) x 2
    assert pts(game, "BEE_SWARM") == 4         # 4 plants x 1
    assert pts(game, "CAPERCAILLIE") == 4      # 4 plants x 1
    assert pts(game, "DIGITALIS") == 6         # 3 different plants → 6
    assert pts(game, "ALPINE_MARMOT") == 9     # 3 different plants x 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("DIGITALIS")
def test_digitalis_five_or_more_different_plants(game):
    for k in ["BLACKBERRIES", "WILD_STRAWBERRIES", "TREE_FERNS", "MOSS", "DIGITALIS", "STINGING_NETTLE"]:
        attach(game, 0, sapling(game), k)
    assert pts(game, "DIGITALIS") == 15        # 6 different plants: 5+ → 15


@pytest.mark.rule("F6.2")
@pytest.mark.rule("F6.3")
@pytest.mark.card("STINGING_NETTLE")
@pytest.mark.card("HEDGEHOG")
@pytest.mark.card("GENTIAN")
def test_butterfly_counters(game):
    for top, bottom in [("PEACOCK_BUTTERFLY", "STINGING_NETTLE"), ("MAP_BUTTERFLY", "HEDGEHOG"),
                        ("PHOEBUS_APOLLO", "GENTIAN")]:
        s = sapling(game)
        attach(game, 0, s, top)
        attach(game, 0, s, bottom)
    assert pts(game, "STINGING_NETTLE") == 6   # 3 butterflies x 2
    assert pts(game, "HEDGEHOG") == 6          # 3 butterflies x 2
    assert pts(game, "GENTIAN") == 9           # 3 butterflies x 3
    assert sc(game) == 6 + 6 + 9 + 6           # + one set of 3 different butterflies = 6


@pytest.mark.rule("F6.3")
@pytest.mark.card("LARGE_TORTOISESHELL")
@pytest.mark.card("CAMBERWELL_BEAUTY")
@pytest.mark.card("PURPLE_EMPEROR")
@pytest.mark.card("SILVER_WASHED_FRITILLARY")
@pytest.mark.card("PEACOCK_BUTTERFLY")
@pytest.mark.card("MAP_BUTTERFLY")
@pytest.mark.card("PHOEBUS_APOLLO")
def test_seven_different_butterflies_and_a_second_set(game):
    for k in ["LARGE_TORTOISESHELL", "CAMBERWELL_BEAUTY", "PURPLE_EMPEROR", "SILVER_WASHED_FRITILLARY",
              "PEACOCK_BUTTERFLY", "MAP_BUTTERFLY", "PHOEBUS_APOLLO"]:
        attach(game, 0, sapling(game), k)
    assert sc(game) == 55                      # one set of 7 different
    attach(game, 0, sapling(game), "PEACOCK_BUTTERFLY")
    assert sc(game) == 55 + 0                  # second set of 1
    attach(game, 0, sapling(game), "MAP_BUTTERFLY")
    assert sc(game) == 55 + 3                  # second set of 2 different


@pytest.mark.rule("F6.2")
@pytest.mark.card("BULLFINCH")
@pytest.mark.card("ALPINE_NEWT")
@pytest.mark.card("GREAT_GREEN_BUSH_CRICKET")
def test_insect_counters(game):
    s1, s2 = sapling(game), sapling(game)
    attach(game, 0, s1, "BULLFINCH")
    attach(game, 0, s1, "GREAT_GREEN_BUSH_CRICKET")
    attach(game, 0, s1, "GNAT")
    attach(game, 0, s2, "PEACOCK_BUTTERFLY")
    attach(game, 0, s2, "ALPINE_NEWT")
    assert pts(game, "BULLFINCH") == 6         # 3 insects (cricket, gnat, butterfly) x 2
    assert pts(game, "ALPINE_NEWT") == 6       # 3 insects x 2
    assert pts(game, "GREAT_GREEN_BUSH_CRICKET") == 3   # 3 insects x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("TREE_FERNS")
@pytest.mark.card("GOLDEN_EAGLE")
def test_amphibian_counters(game):
    s1, s2, s3 = sapling(game), sapling(game), sapling(game)
    attach(game, 0, s1, "TREE_FERNS")
    attach(game, 0, s1, "GOLDEN_EAGLE")
    attach(game, 0, s1, "EUROPEAN_HARE")
    attach(game, 0, s2, "POND_TURTLE")
    attach(game, 0, s3, "COMMON_TOAD")
    assert pts(game, "TREE_FERNS") == 12       # 2 amphibians (turtle, toad) x 6
    assert pts(game, "GOLDEN_EAGLE") == 3      # 1 pawed animal + 2 amphibians = 3 x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("STAG_BEETLE")
def test_stag_beetle_counts_pawed_animals(game):
    s = sapling(game)
    for k in ["STAG_BEETLE", "RED_SQUIRREL", "EUROPEAN_HARE", "EUROPEAN_BADGER"]:
        attach(game, 0, s, k)
    assert pts(game, "STAG_BEETLE") == 3       # 3 pawed animals (squirrel, hare, badger) x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("FALLOW_DEER")
@pytest.mark.card("WOLF")
@pytest.mark.card("RED_DEER")
def test_deer_and_cloven_hoofed_counters(game):
    s1, s2, s3 = sapling(game), sapling(game), sapling(game)
    attach(game, 0, s1, "FALLOW_DEER")
    attach(game, 0, s1, "ROE_DEER")
    attach(game, 0, s2, "RED_DEER")
    attach(game, 0, s2, "SQUEAKER")
    attach(game, 0, s3, "WOLF")
    assert pts(game, "FALLOW_DEER") == 12      # 4 cloven-hoofed (fallow, roe, red deer, squeaker) x 3
    assert pts(game, "WOLF") == 15             # 3 deer (fallow, roe, red) x 5
    assert pts(game, "RED_DEER") == 3          # 3 trees (saplings), 0 plants x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("RED_DEER")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_red_deer_counts_trees_and_plants_not_the_bee(game):
    s = sapling(game)
    b = plant(game, 0, "BIRCH")
    attach(game, 0, s, "RED_DEER")
    attach(game, 0, b, "MOSS")
    attach(game, 0, b, "VIOLET_CARPENTER_BEE")
    attach(game, 0, s, "BLACKBERRIES")
    assert pts(game, "RED_DEER") == 4          # 2 trees (sapling, birch) + 2 plants (moss, blackberries) x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("FEMALE_WILD_BOAR")
def test_female_wild_boar_per_squeaker(game):
    s1, s2 = sapling(game), sapling(game)
    attach(game, 0, s1, "FEMALE_WILD_BOAR")
    attach(game, 0, s1, "SQUEAKER")
    attach(game, 0, s2, "SQUEAKER")
    assert pts(game, "FEMALE_WILD_BOAR") == 20     # 2 squeakers x 10
    assert sc(game) == 20 + 2                      # + 2 squeakers x 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("WILD_BOAR")
@pytest.mark.card("SQUEAKER")
def test_wild_boar_needs_a_squeaker(game):
    s = sapling(game)
    attach(game, 0, s, "WILD_BOAR")
    assert sc(game) == 0
    attach(game, 0, s, "SQUEAKER")
    assert sc(game) == 10 + 1                  # boar 10 + squeaker 1


@pytest.mark.rule("F6.2")
@pytest.mark.card("LYNX")
@pytest.mark.card("ROE_DEER")
def test_lynx_needs_a_roe_deer(game):
    s = sapling(game)
    attach(game, 0, s, "LYNX")
    assert sc(game) == 0
    attach(game, 0, s, "ROE_DEER", "BEECH")
    assert sc(game) == 10 + 3                  # lynx 10 + roe deer (only Beech-symbol card: itself) 1 x 3


# ---------------------------------------------------------------------- symbols, hosts, positions
@pytest.mark.rule("F6.2")
@pytest.mark.card("ROE_DEER")
@pytest.mark.card("CHAMOIS")
def test_roe_deer_and_chamois_count_their_own_symbol(game):
    beech = plant(game, 0, "BEECH")
    attach(game, 0, beech, "ROE_DEER", "BEECH")
    attach(game, 0, beech, "CHAFFINCH", "BEECH")
    attach(game, 0, beech, "EUROPEAN_HARE", "LINDEN")
    pine = plant(game, 0, "STONE_PINE")
    attach(game, 0, pine, "CHAMOIS", "SWISS_PINE")
    attach(game, 0, pine, "EDELWEISS", "SWISS_PINE")
    attach(game, 0, pine, "MOUNTAIN_HARE", "ALPINE_LARCH")
    assert pts(game, "ROE_DEER") == 9          # 3 Beech-symbol cards (beech, roe deer, chaffinch) x 3
    assert pts(game, "CHAMOIS") == 9           # 3 Swiss-Pine-symbol cards (stone pine, chamois, edelweiss) x 3


@pytest.mark.rule("F6.2")
@pytest.mark.card("EUROPEAN_BISON")
def test_bison_counts_beech_and_oak_symbols(game):
    oak, beech = plant(game, 0, "OAK"), plant(game, 0, "BEECH")
    attach(game, 0, oak, "EUROPEAN_BISON", "OAK")
    attach(game, 0, beech, "CHAFFINCH", "BEECH")
    attach(game, 0, beech, "EUROPEAN_HARE", "LINDEN")
    assert pts(game, "EUROPEAN_BISON") == 8    # oak, beech, bison, chaffinch = 4 x 2


@pytest.mark.rule("F6.2")
@pytest.mark.card("GREAT_SPOTTED_WOODPECKER")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_woodpecker_tree_majority(game):
    for _ in range(3):
        plant(game, 1, "BIRCH")
    b = plant(game, 0, "BIRCH")
    sapling(game)
    attach(game, 0, b, "GREAT_SPOTTED_WOODPECKER")
    assert pts(game, "GREAT_SPOTTED_WOODPECKER") == 0      # 2 trees (birch, sapling) < 3
    attach(game, 0, b, "VIOLET_CARPENTER_BEE")
    assert pts(game, "GREAT_SPOTTED_WOODPECKER") == 10     # 2 + 1 from the bee = 3, tie counts as most


@pytest.mark.rule("F6.2")
@pytest.mark.card("MOSS")
@pytest.mark.card("VIOLET_CARPENTER_BEE")
def test_moss_needs_ten_trees(game):
    b = plant(game, 0, "BIRCH")
    for _ in range(8):
        sapling(game)
    attach(game, 0, 1, "MOSS")
    assert pts(game, "MOSS") == 0              # 9 trees (birch + 8 saplings)
    attach(game, 0, b, "VIOLET_CARPENTER_BEE")
    assert pts(game, "MOSS") == 10             # 9 + 1 from the bee = 10


@pytest.mark.rule("F6.2")
@pytest.mark.card("RED_SQUIRREL")
@pytest.mark.card("CHAFFINCH")
def test_squirrel_on_oak_chaffinch_on_beech(game):
    oak, birch, beech = plant(game, 0, "OAK"), plant(game, 0, "BIRCH"), plant(game, 0, "BEECH")
    attach(game, 0, oak, "RED_SQUIRREL")
    attach(game, 0, beech, "RED_SQUIRREL")
    attach(game, 0, birch, "CHAFFINCH")
    assert pts(game, "RED_SQUIRREL") == 5      # 5 on the oak, 0 on the beech
    assert pts(game, "CHAFFINCH") == 0         # not on a beech


@pytest.mark.rule("F6.2")
@pytest.mark.card("EUROPEAN_POLECAT")
def test_polecat_alone_on_its_plant(game):
    s1, s2 = sapling(game), sapling(game)
    attach(game, 0, s1, "EUROPEAN_POLECAT")
    attach(game, 0, s2, "EUROPEAN_POLECAT")
    attach(game, 0, s2, "EUROPEAN_HARE")
    assert pts(game, "EUROPEAN_POLECAT") == 10     # alone on s1: 10; with a hare on s2: 0


@pytest.mark.rule("F6.3")
@pytest.mark.card("FIRE_SALAMANDER")
@pytest.mark.card("FIREFLIES")
def test_salamander_and_fireflies_set_tables(game):
    for expected in [5, 15, 25]:               # 1/2/3 salamanders
        attach(game, 0, sapling(game), "FIRE_SALAMANDER")
        assert pts(game, "FIRE_SALAMANDER") == expected
    for expected in [0, 10, 15, 20]:           # 1/2/3/4 fireflies
        attach(game, 0, sapling(game), "FIREFLIES")
        assert pts(game, "FIREFLIES") == expected


# ---------------------------------------------------------------------- effects and bonuses
@pytest.mark.rule("F4.5")
@pytest.mark.parametrize("species, symbol, draws", [
    pytest.param("BEECH", "BEECH", 1, marks=pytest.mark.card("BEECH")),                       # effect 1
    pytest.param("STONE_PINE", "SWISS_PINE", 2, marks=pytest.mark.card("STONE_PINE")),        # effect 1 + bonus 1
    pytest.param("BEECH_MARTEN", "SYCAMORE", 1, marks=pytest.mark.card("BEECH_MARTEN")),      # effect 1
    pytest.param("GREAT_SPOTTED_WOODPECKER", "LINDEN", 1, marks=pytest.mark.card("GREAT_SPOTTED_WOODPECKER")),
    pytest.param("TAWNY_OWL", "SYCAMORE", 3, marks=pytest.mark.card("TAWNY_OWL")),           # effect 1 + bonus 2
    pytest.param("TREE_FERNS", "LINDEN", 1, marks=pytest.mark.card("TREE_FERNS")),           # effect 1
    pytest.param("POND_TURTLE", "BIRCH", 1, marks=pytest.mark.card("POND_TURTLE")),          # effect 1
    pytest.param("HEDGEHOG", "HORSE_CHESTNUT", 1, marks=pytest.mark.card("HEDGEHOG")),       # bonus 1
    pytest.param("ROE_DEER", "BEECH", 1, marks=pytest.mark.card("ROE_DEER")),                # bonus 1
    pytest.param("FALLOW_DEER", "LINDEN", 2, marks=pytest.mark.card("FALLOW_DEER")),         # bonus 2
    pytest.param("COMMON_RAVEN", "ALPINE_LARCH", 1, marks=pytest.mark.card("COMMON_RAVEN")), # effect 1
    pytest.param("EDELWEISS", "SWISS_PINE", 2, marks=pytest.mark.card("EDELWEISS")),         # effect 1 + bonus 1
])
def test_draw_effects_and_bonuses(game, species, symbol, draws):
    plant(game, 0, "BIRCH")
    play_with_bonus(game, species, symbol)
    assert game.state.players[0].hand == []    # card played, cost paid
    resolve(game)
    assert len(game.state.players[0].hand) == draws


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F5.1")
@pytest.mark.parametrize("species, symbol", [
    pytest.param("DOUGLAS_FIR", "DOUGLAS_FIR", marks=pytest.mark.card("DOUGLAS_FIR")),        # bonus
    pytest.param("EURASIAN_JAY", "HORSE_CHESTNUT", marks=pytest.mark.card("EURASIAN_JAY")),   # effect
    pytest.param("NIGHTINGALE", "BEECH", marks=pytest.mark.card("NIGHTINGALE")),              # bonus
    pytest.param("WATER_VOLE", "SYCAMORE", marks=pytest.mark.card("WATER_VOLE")),             # bonus
    pytest.param("EUROPEAN_BISON", "OAK", marks=pytest.mark.card("EUROPEAN_BISON")),          # effect
    pytest.param("EUROPEAN_POLECAT", "SILVER_FIR", marks=pytest.mark.card("EUROPEAN_POLECAT")),  # bonus
    pytest.param("STEINBOCK", "ALPINE_LARCH", marks=pytest.mark.card("STEINBOCK")),           # effect
])
def test_extra_turn_effects_and_bonuses(game, species, symbol):
    plant(game, 0, "BIRCH")
    play_with_bonus(game, species, symbol)
    resolve(game)
    assert game.state.current == 0 and game.state.turn_index == 1


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F4.7")
@pytest.mark.parametrize("species, symbol, free", [
    pytest.param("SILVER_FIR", "SILVER_FIR", [("EUROPEAN_HARE", "OAK")], marks=pytest.mark.card("SILVER_FIR")),
    pytest.param("EUROPEAN_LARCH", "ALPINE_LARCH", [("CHAMOIS", "SWISS_PINE")], marks=pytest.mark.card("EUROPEAN_LARCH")),
    pytest.param("FIRE_SALAMANDER", "LINDEN", [("EUROPEAN_HARE", "OAK")], marks=pytest.mark.card("FIRE_SALAMANDER")),
    pytest.param("STAG_BEETLE", "BIRCH", [("CHAFFINCH", "SYCAMORE")], marks=pytest.mark.card("STAG_BEETLE")),
    pytest.param("RED_DEER", "LINDEN", [("ROE_DEER", "BEECH")], marks=pytest.mark.card("RED_DEER")),
    pytest.param("FEMALE_WILD_BOAR", "BIRCH", [("SQUEAKER", "SYCAMORE")], marks=pytest.mark.card("FEMALE_WILD_BOAR")),
    pytest.param("GNAT", "BIRCH", [("BARBASTELLE_BAT", "HORSE_CHESTNUT"), ("BECHSTEINS_BAT", "BIRCH")],
                 marks=pytest.mark.card("GNAT")),                                            # any number of bats
    pytest.param("GREAT_GREEN_BUSH_CRICKET", "SILVER_FIR", [("TAWNY_OWL", "SYCAMORE")],
                 marks=pytest.mark.card("GREAT_GREEN_BUSH_CRICKET")),
    pytest.param("CAPERCAILLIE", "DOUGLAS_FIR", [("MOSS", "LINDEN")], marks=pytest.mark.card("CAPERCAILLIE")),
    pytest.param("BLUEBERRY", "BIRCH", [("TREE_FROG", "OAK")], marks=pytest.mark.card("BLUEBERRY")),
    pytest.param("GENTIAN", "BEECH", [("PEACOCK_BUTTERFLY", "LINDEN")], marks=pytest.mark.card("GENTIAN")),
])
def test_free_placement_effects_and_bonuses(game, species, symbol, free):
    plant(game, 0, "BIRCH")
    plant(game, 0, "BIRCH")
    cards = play_with_bonus(game, species, symbol, *free)
    resolve(game)
    assert game.state.players[0].hand == []
    assert all(c.uid in placed_uids(game) for c in cards)


@pytest.mark.rule("F4.6")
@pytest.mark.parametrize("mushroom, trigger, symbol", [
    pytest.param("PENNY_BUN", "RED_SQUIRREL", "OAK", marks=pytest.mark.card("PENNY_BUN")),       # top of a tree
    pytest.param("CHANTERELLE", "BIRCH", None, marks=pytest.mark.card("CHANTERELLE")),           # a tree
    pytest.param("FLY_AGARIC", "EUROPEAN_HARE", "OAK", marks=pytest.mark.card("FLY_AGARIC")),    # pawed animal
    pytest.param("BLACK_TRUMPET", "MOUNTAIN_HARE", None, marks=pytest.mark.card("BLACK_TRUMPET")),  # Alps card
])
def test_mushroom_draws_on_matching_play(game, mushroom, trigger, symbol):
    t = plant(game, 0, "BIRCH")
    attach(game, 0, t, mushroom)
    game.state.turn_index = 1                  # mushroom placed on an earlier turn
    card, = hand_only(game, 0, (trigger, symbol))
    play(game, card, trigger)
    label = game.db.species[mushroom].label
    fired = 0
    while game.state.decisions:
        if label in game.state.decisions[-1].data["label"]:
            fired += 1
            use(game)
        else:
            skip(game)                         # e.g. the Birch's own draw
    assert fired == 1 and len(game.state.players[0].hand) == 1


@pytest.mark.rule("F4.6")
@pytest.mark.parametrize("shrub, free, free_symbol", [
    pytest.param("COMMON_HAZEL", "BARBASTELLE_BAT", "HORSE_CHESTNUT", marks=pytest.mark.card("COMMON_HAZEL")),
    pytest.param("BLACKTHORN", "PEACOCK_BUTTERFLY", "LINDEN", marks=pytest.mark.card("BLACKTHORN")),
])
def test_shrub_bonus_places_free_and_triggers_its_draw(game, shrub, free, free_symbol):
    plant(game, 0, "BIRCH")
    card, p1, p2, f = hand_only(game, 0, (shrub, "BIRCH"), ("BIRCH", None), ("BIRCH", None), (free, free_symbol))
    game.step(Action(K.PLAY_WOODY, card=card.def_id))
    game.step(Action(K.PAY, card=p1.def_id))
    game.step(Action(K.PAY, card=p2.def_id))
    use(game)                                  # bonus: place a bat / butterfly free
    play_half(game, f, free, target=1)         # on the shrub
    d = game.state.decisions[-1]
    assert d.kind == "USE_OR_SKIP" and game.db.species[shrub].label in d.data["label"]
    use(game)                                  # permanent effect: draw 1
    assert len(game.state.players[0].hand) == 1


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F6.2")
@pytest.mark.card("RED_FOX")
def test_red_fox_draws_and_scores_per_hare(game):
    s1, s2 = sapling(game), sapling(game)
    attach(game, 0, s1, "EUROPEAN_HARE")
    attach(game, 0, s1, "EUROPEAN_HARE")
    attach(game, 0, s1, "MOUNTAIN_HARE")       # counts as a European Hare
    fox, *_ = hand_only(game, 0, ("RED_FOX", "OAK"), ("BIRCH", None), ("BIRCH", None))
    play_half(game, fox, "RED_FOX", target=s2)
    pay_all(game)
    use(game)
    assert len(game.state.players[0].hand) == 3    # 3 hares → draw 3
    assert pts(game, "RED_FOX") == 6               # 3 hares x 2


@pytest.mark.rule("F4.5")
@pytest.mark.card("BEE_SWARM")
def test_bee_swarm_caves_plants_shrubs_and_trees_from_clearing(game):
    plant(game, 0, "BIRCH")
    swarm, wolf = hand_only(game, 0, ("BEE_SWARM", "SYCAMORE"), ("WOLF", "SILVER_FIR"))
    game.state.clearing = []
    keep = [to_clearing(game, "EUROPEAN_HARE", "LINDEN")]                     # Hare | Badger: no plant
    caved = [to_clearing(game, "BIRCH"), to_clearing(game, "ELDERBERRY"), to_clearing(game, "MOSS")]
    play_half(game, swarm, "BEE_SWARM")
    game.step(Action(K.PAY, card=wolf.def_id))                               # Fox | Wolf: no plant
    use(game)
    assert sorted(c.uid for c in game.state.players[0].cave) == sorted(c.uid for c in caved)
    assert sorted(c.uid for c in game.state.clearing) == sorted(c.uid for c in keep + [wolf])


@pytest.mark.rule("F4.5")
@pytest.mark.card("EUROPEAN_WILDCAT")
def test_wildcat_takes_one_card_from_clearing(game):
    plant(game, 0, "BIRCH")
    cat, pay = hand_only(game, 0, ("EUROPEAN_WILDCAT", "HORSE_CHESTNUT"), ("BIRCH", None))
    game.state.clearing = []
    hare = to_clearing(game, "EUROPEAN_HARE", "LINDEN")
    play_half(game, cat, "EUROPEAN_WILDCAT")
    game.step(Action(K.PAY, card=pay.def_id))
    use(game)
    game.step(Action(K.CHOOSE_CARD, card=hare.def_id))
    assert game.state.players[0].hand == [hare] and game.state.clearing == [pay]


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F4.7")
@pytest.mark.card("CRANE_FLY")
def test_crane_fly_places_bats_and_takes_bats_from_clearing(game):
    plant(game, 0, "BIRCH")
    fly, beech, bat = hand_only(game, 0, ("CRANE_FLY", "BEECH"), ("BEECH", None), ("BARBASTELLE_BAT", "HORSE_CHESTNUT"))
    game.state.clearing = []
    other_bat = to_clearing(game, "BECHSTEINS_BAT", "BEECH")
    play_half(game, fly, "CRANE_FLY")
    game.step(Action(K.PAY, card=beech.def_id))                 # Beech symbol → bonus applies
    use(game)                                                   # effect: place bats free
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == bat.def_id))
    game.step(Action(K.DONE))
    use(game)                                                   # bonus: all bats from the clearing to hand
    assert bat.uid in placed_uids(game)
    assert game.state.players[0].hand == [other_bat] and game.state.clearing == [beech]


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F6.2")
@pytest.mark.card("BEARDED_VULTURE")
def test_bearded_vulture_caves_two_and_scores_per_cave_card(game):
    plant(game, 0, "BIRCH")
    vulture, pay = hand_only(game, 0, ("BEARDED_VULTURE", "SILVER_FIR"), ("BIRCH", None))
    game.state.clearing = [game.state.deck.pop() for _ in range(3)]
    play_half(game, vulture, "BEARDED_VULTURE")
    game.step(Action(K.PAY, card=pay.def_id))
    use(game)
    resolve(game)                                               # choose 2 clearing cards
    assert len(game.state.players[0].cave) == 2 and len(game.state.clearing) == 2     # 4 - 2
    assert pts(game, "BEARDED_VULTURE") == 2                    # 2 cave cards x 1


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F5.1")
@pytest.mark.card("BROWN_BEAR")
def test_brown_bear_caves_clearing_then_draws_and_goes_again(game):
    plant(game, 0, "BIRCH")
    bear, *_ = hand_only(game, 0, ("BROWN_BEAR", "LINDEN"), ("LINDEN", None), ("LINDEN", None), ("LINDEN", None))
    game.state.clearing = [game.state.deck.pop() for _ in range(2)]
    play_half(game, bear, "BROWN_BEAR")
    pay_all(game)
    use(game)                                                   # effect: whole clearing to cave
    p = game.state.players[0]
    assert len(p.cave) == 5 and game.state.clearing == []       # 2 + 3 paid
    use(game)                                                   # bonus: draw 1, then extra turn
    use(game)
    use(game)
    assert len(p.hand) == 1 and game.state.current == 0 and game.state.turn_index == 1


@pytest.mark.rule("F5.1")
@pytest.mark.card("BARN_OWL")
def test_barn_owl_extra_turn_with_a_bat(game):
    s = sapling(game)
    attach(game, 0, s, "BARBASTELLE_BAT")
    owl, *_ = hand_only(game, 0, ("BARN_OWL", "BIRCH"), ("LINDEN", None), ("LINDEN", None))
    play_half(game, owl, "BARN_OWL")
    pay_all(game)
    use(game)
    assert game.state.current == 0 and game.state.turn_index == 1
