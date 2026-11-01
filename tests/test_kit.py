"""Golden tests: the kit's behaviour is frozen (bgai/kit/README.md rule 4). If one of these fails, a kit change has
altered behaviour that existing games and their experiments depend on — make a new part instead, or regenerate."""
import numpy as np
import pytest

from bgai.kit import CodecBuilder, Decision, DecisionStack, Deck, Rng, TextLog, add_counts, one_hot, ranks, winners


def test_deck_order_is_frozen():
    d = Deck(range(10))
    d.shuffle(Rng(42))
    assert list(d) == [7, 3, 2, 8, 5, 6, 9, 4, 0, 1]
    assert d.draw() == 7 and d.draw_many(3) == [3, 2, 8] and len(d) == 6
    d.put_bottom([99])
    assert d[-1] == 99
    assert Deck().draw() is None and Deck([1]).draw_many(5) == [1]


def test_rng_sequence_is_frozen():
    r = Rng(7)
    assert [r.randrange(6) for _ in range(8)] == [2, 1, 3, 5, 0, 0, 4, 0]


def test_decision_stack():
    s = DecisionStack()
    assert s.top is None and s.decider(3) == 3
    s.push(Decision("PAY", {"n": 1}))
    s.push(Decision("PINK", {}, seat=1))
    assert s.top.kind == "PINK" and s.decider(0) == 1
    s.pop()
    assert s.decider(0) == 0


def test_codec_numbering_is_frozen():
    c = CodecBuilder([("A", 1), ("B", 3), ("C", 2)])
    assert c.size == 6 and c.encode("B", 2) == 3 and c.decode(4) == ("C", 0)
    assert list(np.flatnonzero(c.mask([0, 5]))) == [0, 5]
    with pytest.raises(IndexError):
        c.encode("B", 3)
    with pytest.raises(ValueError):
        CodecBuilder([("A", 1), ("A", 2)])


def test_winners_and_ranks():
    assert winners([10, 12, 12]) == [1, 2]                      # ties share the win
    assert winners([10, 12, 12], [0, 3, 5]) == [2]              # tiebreak decides
    assert ranks([10, 12, 12]) == [3, 1, 2]                     # still tied: seat order
    assert ranks([5, 9]) == [2, 1]


def test_textlog_and_encoding():
    log = TextLog()
    log.add(1, "draws")
    log.add(None, "round 2")
    assert log.render() == "P1: draws\nround 2"
    v = np.zeros(6, dtype=np.float32)
    add_counts(v, 1, [0, 0, 3, 9], 0.5, limit=4)
    one_hot(v, 0, 0)
    assert list(v) == [1.0, 1.0, 0.0, 0.0, 0.5, 0.0]
