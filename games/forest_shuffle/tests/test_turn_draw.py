from bgai.kit import Deck
import pytest

from games.forest_shuffle.core.actions import Action
from games.forest_shuffle.core.actions import ActionKind as K
from games.forest_shuffle.engine.game import IllegalActionError


@pytest.mark.rule("F2.3")
def test_initial_state(game):
    s = game.state
    assert all(len(p.hand) == 6 for p in s.players) and s.clearing == [] and s.current == 0


@pytest.mark.rule("F3.1")
@pytest.mark.rule("F3.2")
def test_draw_action_draws_exactly_two(game):
    hand0 = len(game.state.players[0].hand)
    game.step(Action(K.DRAW_DECK))
    assert game.state.current == 0 and game.state.decisions[-1].kind == "DRAW"
    assert all(a.kind in (K.DRAW_DECK, K.DRAW_CLEARING) for a in game.legal_actions())
    game.step(Action(K.DRAW_DECK))
    assert len(game.state.players[0].hand) == hand0 + 2 and game.state.current == 1


@pytest.mark.rule("F3.2")
def test_hand_nine_draws_one(game):
    p = game.state.players[0]
    while len(p.hand) < 9:
        p.hand.append(game.state.deck.pop())
    game.step(Action(K.DRAW_DECK))
    assert len(p.hand) == 10 and game.state.current == 1


@pytest.mark.rule("F3.2")
def test_cannot_draw_with_full_hand(game):
    p = game.state.players[0]
    while len(p.hand) < 10:
        p.hand.append(game.state.deck.pop())
    assert not any(a.kind == K.DRAW_DECK for a in game.legal_actions())
    with pytest.raises(IllegalActionError):
        game.step(Action(K.DRAW_DECK))


@pytest.mark.rule("F3.2")
def test_draw_from_clearing_by_def(game):
    c = game.state.deck.pop()
    game.state.clearing.append(c)
    game.step(Action(K.DRAW_CLEARING, card=c.def_id))
    assert c in game.state.players[0].hand and game.state.clearing == []


@pytest.mark.rule("F3.3")
@pytest.mark.rule("F6.1")
def test_winter_replacement_and_game_end(game):
    w = game.db.winter_def_id
    winters = [c for c in game.state.deck if c.def_id == w]
    others = [c for c in game.state.deck if c.def_id != w]
    game.state.deck = Deck([winters[0], winters[1], others[0], winters[2]] + others[1:])
    info = game.step(Action(K.DRAW_DECK))
    assert game.state.winter_revealed == 2 and others[0] in game.state.players[0].hand
    assert info["winter_revealed"] == 2
    info = game.step(Action(K.DRAW_DECK))
    assert game.state.game_over and info["game_over"] and game.legal_actions() == []


@pytest.mark.rule("F5.1")
def test_clearing_emptied_at_turn_end(game):
    game.state.clearing = [game.state.deck.pop() for _ in range(10)]
    game.step(Action(K.DRAW_DECK))
    game.step(Action(K.DRAW_DECK))
    assert game.state.clearing == [] and len(game.state.removed) >= 10


def test_action_ids_roundtrip_through_step(game):
    ids = game.legal_ids()
    assert ids and game.codec.decode(ids[0]) in game.legal_actions()
    game.step_id(ids[0])
