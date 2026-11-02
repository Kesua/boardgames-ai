import pytest
from games.forest_shuffle.core.actions import Action
from games.forest_shuffle.core.actions import ActionKind as K
from games.forest_shuffle.tests.conftest import attach, give, hand_only, plant, play_half


def use(game):
    game.step(Action(K.USE))


def skip(game):
    game.step(Action(K.SKIP))


def pay_all(game):
    while game.state.decisions and game.state.decisions[-1].kind == "PAY":
        game.step(next(a for a in game.legal_actions() if a.kind == K.PAY))


@pytest.mark.rule("F4.5")
@pytest.mark.rule("F7.1")
@pytest.mark.card("BIRCH")
def test_birch_effect_draws_one_and_is_optional(game):
    birch, = hand_only(game, 0, ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=birch.def_id))
    assert game.state.decisions[-1].kind == "USE_OR_SKIP"
    use(game)
    assert len(game.state.players[0].hand) == 1 and game.state.current == 1


def test_draw_respects_hand_limit(game):
    p = game.state.players[0]
    birch, = hand_only(game, 0, ("BIRCH", None))
    while len(p.hand) < 10:
        p.hand.append(game.state.deck.pop())
    game.step(Action(K.PLAY_WOODY, card=birch.def_id))
    use(game)
    assert len(p.hand) == 10


@pytest.mark.rule("F5.1")
@pytest.mark.rule("F4.5")
@pytest.mark.card("WOLF")
def test_wolf_draw_per_deer_and_extra_turn_bonus(game):
    t = plant(game, 0, "SILVER_FIR")
    attach(game, 0, t, "ROE_DEER")
    attach(game, 0, t, "FALLOW_DEER", "LINDEN")
    plant(game, 0, "BIRCH")
    wolf, *_ = hand_only(game, 0, ("WOLF", "SILVER_FIR"), ("EUROPEAN_HARE", "SILVER_FIR"),
                         ("RACCOON", "SILVER_FIR"), ("LYNX", "SILVER_FIR"))
    play_half(game, wolf, "WOLF")
    pay_all(game)
    use(game)                                    # effect: draw per deer (2)
    assert len(game.state.players[0].hand) == 2
    use(game)                                    # bonus: extra turn
    assert game.state.current == 0 and game.state.extra_turns == 0 and game.state.turn_index == 1


@pytest.mark.rule("F4.7")
@pytest.mark.rule("F4.5")
@pytest.mark.card("EUROPEAN_BADGER")
def test_place_free_skips_effect_and_bonus(game):
    t = plant(game, 0, "BIRCH")
    badger, jay, fox = hand_only(game, 0, ("EUROPEAN_BADGER", "HORSE_CHESTNUT"), ("EURASIAN_JAY", "HORSE_CHESTNUT"),
                                 ("RED_FOX", "OAK"))
    play_half(game, badger, "EUROPEAN_BADGER")
    game.step(Action(K.PAY, card=jay.def_id))
    use(game)                                    # bonus: place a pawed animal free
    assert game.state.decisions[-1].kind == "PLACE_FREE"
    opts = game.legal_actions()
    assert any(a.kind == K.DONE for a in opts)
    game.step(next(a for a in opts if a.kind == K.PLAY_HALF))
    assert len(game.state.players[0].forest[t].dwellers()) == 2
    assert game.state.decisions == [] and game.state.current == 1      # fox effect not offered


@pytest.mark.rule("F4.5")
@pytest.mark.card("RACCOON")
def test_raccoon_hand_to_cave(game):
    plant(game, 0, "BIRCH")
    rac, *_ = hand_only(game, 0, ("RACCOON", "BIRCH"), ("SQUEAKER", "OAK"), ("SQUEAKER", "OAK"), ("BIRCH", None))
    play_half(game, rac, "RACCOON")
    pay_all(game)
    use(game)
    assert game.state.decisions[-1].kind == "CHOOSE_HAND_CARD"
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))
    game.step(Action(K.DONE))
    p = game.state.players[0]
    assert len(p.cave) == 1 and len(p.hand) == 2      # 4 -1 played -1 paid -1 caved +1 drawn


@pytest.mark.rule("F4.5")
@pytest.mark.card("EURASIAN_MAGPIE")
def test_magpie_effect_and_bonus_from_clearing(game):
    plant(game, 0, "BIRCH")
    game.state.clearing = [game.state.deck.pop() for _ in range(3)]
    mag, beech = hand_only(game, 0, ("EURASIAN_MAGPIE", "BEECH"), ("BEECH", None))
    play_half(game, mag, "EURASIAN_MAGPIE")
    game.step(Action(K.PAY, card=beech.def_id))
    use(game)
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))    # effect: 1 to hand
    use(game)                                                                        # bonus: 2 to cave
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))
    game.step(next(a for a in game.legal_actions() if a.kind == K.CHOOSE_CARD))
    assert len(game.state.players[0].cave) == 2 and len(game.state.clearing) == 1


@pytest.mark.rule("F4.5")
@pytest.mark.card("FEMALE_WILD_BOAR")
def test_female_boar_removes_clearing(game):
    plant(game, 0, "BIRCH")
    game.state.clearing = [game.state.deck.pop() for _ in range(4)]
    boar, *_ = hand_only(game, 0, ("FEMALE_WILD_BOAR", "BIRCH"), ("BIRCH", None), ("BIRCH", None))
    play_half(game, boar, "FEMALE_WILD_BOAR")
    pay_all(game)
    use(game)
    assert game.state.clearing == []


@pytest.mark.rule("F4.5")
@pytest.mark.card("MOLE")
def test_mole_plays_more_cards(game):
    plant(game, 0, "BIRCH")
    mole, *_ = hand_only(game, 0, ("MOLE", "OAK"), ("BIRCH", None), ("BIRCH", None), ("BIRCH", None))
    play_half(game, mole, "MOLE")
    pay_all(game)
    use(game)
    assert game.state.decisions[-1].kind == "PLAY_MORE"
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_WOODY))
    skip(game)                                    # birch effect skipped
    assert game.state.decisions[-1].kind == "PLAY_MORE"
    game.step(Action(K.DONE))
    assert game.state.current == 1


@pytest.mark.rule("F4.5")
@pytest.mark.card("WATER_VOLE")
def test_water_vole_saplings(game):
    plant(game, 0, "BIRCH")
    vole, *_ = hand_only(game, 0, ("WATER_VOLE", "SYCAMORE"), ("BIRCH", None), ("BIRCH", None), ("BIRCH", None))
    play_half(game, vole, "WATER_VOLE")
    pay_all(game)
    use(game)
    n_clear = len(game.state.clearing)
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_SAPLING))
    game.step(Action(K.DONE))
    assert len(game.state.players[0].forest) == 2 and len(game.state.clearing) == n_clear + 1


@pytest.mark.rule("F4.6")
@pytest.mark.card("PARASOL_MUSHROOM")
def test_mushroom_triggers_from_next_turn(game):
    t = plant(game, 0, "BIRCH")
    attach(game, 0, t, "PARASOL_MUSHROOM")
    t2 = plant(game, 0, "BIRCH")
    toad, = hand_only(game, 0, ("COMMON_TOAD", "OAK"))
    play_half(game, toad, "COMMON_TOAD", target=t2)
    assert game.state.decisions == []                 # same turn as the mushroom → no trigger
    game.state.turn_index = 3
    game.state.current = 0
    toad, = hand_only(game, 0, ("COMMON_TOAD", "OAK"))
    play_half(game, toad, "COMMON_TOAD")
    d = game.state.decisions[-1]
    assert d.kind == "USE_OR_SKIP" and "Parasol" in d.data["label"]
    use(game)
    assert len(game.state.players[0].hand) == 1


@pytest.mark.rule("F4.6")
@pytest.mark.card("ELDERBERRY")
def test_shrub_bonus_applies_permanent_effect_now(game):
    plant(game, 0, "BIRCH")
    elder, p1, p2, moss = hand_only(game, 0, ("ELDERBERRY", "BIRCH"), ("BIRCH", None), ("BIRCH", None), ("MOSS", "LINDEN"))
    game.step(Action(K.PLAY_WOODY, card=elder.def_id))
    game.step(Action(K.PAY, card=p1.def_id))
    game.step(Action(K.PAY, card=p2.def_id))
    use(game)                                          # bonus: place a plant free
    play_half(game, moss, "MOSS", target=1)            # on the Elderberry
    d = game.state.decisions[-1]
    assert d.kind == "USE_OR_SKIP" and "Elderberry" in d.data["label"]
    use(game)
    assert len(game.state.players[0].hand) == 1


@pytest.mark.rule("F5.1")
@pytest.mark.card("BARN_OWL")
def test_barn_owl_conditional_extra_turn(game):
    plant(game, 0, "BIRCH")
    owl, *_ = hand_only(game, 0, ("BARN_OWL", "BIRCH"), ("BIRCH", None), ("BIRCH", None))
    play_half(game, owl, "BARN_OWL")
    pay_all(game)
    use(game)
    assert game.state.extra_turns == 0 and game.state.current == 1


@pytest.mark.rule("F4.5")
@pytest.mark.card("ALPINE_NEWT")
def test_alpine_newt_bonus_sequence(game):
    plant(game, 0, "BIRCH")
    newt, pay, marmot, gnat = hand_only(game, 0, ("ALPINE_NEWT", "SWISS_PINE"), ("CHAMOIS", "SWISS_PINE"),
                                        ("ALPINE_MARMOT", "BEECH"), ("GNAT", "BIRCH"))
    play_half(game, newt, "ALPINE_NEWT")
    game.step(Action(K.PAY, card=pay.def_id))
    use(game)                                          # bonus: sequence
    use(game)                                          # step 1: place an Alps card
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == marmot.def_id))
    use(game)                                          # step 2: place an insect
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == gnat.def_id))
    assert len(game.state.players[0].forest[0].dwellers()) == 3 and game.state.current == 1
