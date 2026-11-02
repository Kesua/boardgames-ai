import pytest

from games.through_the_ages import SPEC
from games.through_the_ages.engine import CARDS, CODEC

rule = pytest.mark.rule


@rule("T1.1")
@rule("T2.1")
def test_setup():
    g = SPEC.new_game(2, 1)
    assert len(CARDS) == 45 and len(g.s.market) == 3 and len(g.s.deck) == 42


@rule("T3.1")
@rule("T3.2")
def test_take_market_refills():
    g = SPEC.new_game(2, 1)
    top = g.s.deck[0]
    g.step_id(CODEC.encode("MARKET", 0))
    assert len(g.s.market) == 3 and g.s.market[-1] == top and len(g.s.hands[0]) == 1


@rule("T4.1")
def test_game_ends_when_cards_run_out():
    g = SPEC.new_game(3, 2)
    while not g.game_over:
        g.step_id(g.legal_ids()[-1])
    assert not g.s.deck and not g.s.market and sum(len(h) for h in g.s.hands) == 45


@rule("T5.1")
def test_scoring():
    g = SPEC.new_game(2, 1)
    g.s.hands = [[0, 1, 2], [15]]            # red 1, 2, 3 -> 6 + set 5; green 1
    assert g.scores() == [11, 1]
