from games.forest_shuffle.core.actions import Action, ActionCodec, ActionKind


def test_roundtrip_all_ids():
    c = ActionCodec(160, 40)
    assert c.size == 1 + 7 * 160 + 40 + 3
    for i in range(c.size):
        assert c.encode(c.decode(i)) == i


def test_specific_ids():
    c = ActionCodec(160, 40)
    assert c.encode(Action(ActionKind.DRAW_DECK)) == 0
    assert c.encode(Action(ActionKind.DRAW_CLEARING, card=0)) == 1
    assert c.decode(c.size - 1) == Action(ActionKind.DONE)
    m = c.mask([Action(ActionKind.USE), Action(ActionKind.SKIP)])
    assert m.dtype == bool and m.sum() == 2
