import pytest
from games.forest_shuffle.core.actions import Action
from games.forest_shuffle.core.actions import ActionKind as K
from games.forest_shuffle.tests.conftest import give, hand_only, plant, play_half


def pay_all(game):
    while game.state.decisions and game.state.decisions[-1].kind == "PAY":
        game.step(next(a for a in game.legal_actions() if a.kind == K.PAY))


@pytest.mark.rule("F4.2")
def test_play_free_tree_reveals_clearing(game):
    birch, = hand_only(game, 0, ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=birch.def_id))
    f = game.state.players[0].forest
    assert len(f) == 1 and f[0].species == "BIRCH" and len(game.state.clearing) == 1
    assert game.state.decisions[-1].kind == "USE_OR_SKIP"      # Birch: draw 1


@pytest.mark.rule("F4.1")
@pytest.mark.rule("F4.5")
@pytest.mark.card("OAK")
def test_pay_cost_then_place_and_bonus(game):
    oak, pay1, pay2, other = hand_only(game, 0, ("OAK", None), ("EUROPEAN_HARE", "OAK"), ("SQUEAKER", "OAK"), ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=oak.def_id))
    assert game.state.decisions[-1].kind == "PAY"
    ids = {a.card for a in game.legal_actions()}
    assert oak.def_id not in ids and pay1.def_id in ids
    game.step(Action(K.PAY, card=pay1.def_id))
    game.step(Action(K.PAY, card=pay2.def_id))
    assert game.state.players[0].forest[0].species == "OAK"
    assert pay1 in game.state.clearing and pay2 in game.state.clearing
    top = game.state.decisions[-1]
    assert top.kind == "USE_OR_SKIP" and top.data["label"].startswith("bonus")
    game.step(Action(K.USE))
    assert game.state.current == 0 and game.state.turn_index == 1      # extra turn


@pytest.mark.rule("F4.5")
def test_bonus_not_offered_when_symbol_differs(game):
    oak, pay1, pay2 = hand_only(game, 0, ("OAK", None), ("EUROPEAN_HARE", "OAK"), ("BIRCH", None))
    game.step(Action(K.PLAY_WOODY, card=oak.def_id))
    game.step(Action(K.PAY, card=pay1.def_id))
    game.step(Action(K.PAY, card=pay2.def_id))
    assert game.state.decisions == [] and game.state.current == 1


@pytest.mark.rule("F4.3")
@pytest.mark.rule("F4.2")
def test_sapling_costs_nothing_and_reveals(game):
    card, = hand_only(game, 0, ("WOLF", None))
    game.step(Action(K.PLAY_SAPLING, card=card.def_id))
    f = game.state.players[0].forest
    assert f[0].species is None and f[0].kind == "TREE" and card in game.state.removed
    assert len(game.state.clearing) == 1 and game.state.current == 1


@pytest.mark.rule("F4.4")
@pytest.mark.card("TAWNY_OWL")
def test_split_card_needs_matching_empty_slot(game):
    hand_only(game, 0)
    t = plant(game, 0, "BIRCH")
    owl = give(game, 0, "TAWNY_OWL")
    give(game, 0, "EUROPEAN_HARE")
    give(game, 0, "BIRCH")
    give(game, 0, "BIRCH")
    halves = game.db.defs[owl.def_id].halves
    acts = [a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == owl.def_id
            and halves[a.half].species == "TAWNY_OWL"]
    assert len(acts) == 1 and acts[0].target is None
    play_half(game, owl, "TAWNY_OWL")                     # single legal plant: no target decision
    pay_all(game)
    assert game.state.players[0].forest[t].slots["TOP"][0].species == "TAWNY_OWL"
    acts = [a for a in game.legal_actions()]
    assert acts[0].kind in (K.USE, K.SKIP)                        # owl effect: draw 1


@pytest.mark.rule("F4.1")
def test_cannot_afford(game):
    wolf, = hand_only(game, 0, ("WOLF", None))
    plant(game, 0, "BIRCH")
    wolf = give(game, 0, "WOLF")
    assert not any(a.kind == K.PLAY_HALF for a in game.legal_actions())
    assert any(a.kind == K.PLAY_SAPLING for a in game.legal_actions())


def test_target_decision_when_several_plants(game):
    hand_only(game, 0)
    t1, t2 = plant(game, 0, "BIRCH"), plant(game, 0, "OAK")
    owl = give(game, 0, "TAWNY_OWL")
    give(game, 0, "BIRCH")
    give(game, 0, "BIRCH")
    game.step(next(a for a in game.legal_actions() if a.kind == K.PLAY_HALF and a.card == owl.def_id))
    assert game.state.decisions[-1].kind == "CHOOSE_TARGET"
    opts = game.legal_actions()
    assert {a.target for a in opts} == {t1, t2} and all(a.kind == K.CHOOSE_TARGET for a in opts)
    game.step(Action(K.CHOOSE_TARGET, target=t2))
    assert game.state.decisions[-1].kind == "PAY"
    pay_all(game)
    assert game.state.players[0].forest[t2].slots["TOP"][0].species == "TAWNY_OWL"
