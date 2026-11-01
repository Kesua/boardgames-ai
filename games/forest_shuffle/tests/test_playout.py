import random

import pytest

from games.forest_shuffle.engine.game import Game


def all_uids(state):
    uids = [c.uid for c in state.deck + state.clearing + state.removed]
    for p in state.players:
        uids += [c.uid for c in p.hand + p.cave]
        for w in p.forest:
            if w.uid is not None:
                uids.append(w.uid)
            uids += [d.uid for d in w.dwellers()]
    return sorted(uids)


@pytest.mark.rule("F6.1")
@pytest.mark.rule("F7.1")
@pytest.mark.parametrize("seed", range(25))
@pytest.mark.parametrize("players", [2, 3, 5])
def test_random_game_terminates_and_conserves_cards(db, seed, players):
    g = Game(db, players, seed=seed)
    g.reset()
    expected = all_uids(g.state)
    rng = random.Random(seed)
    steps = 0
    while not g.state.game_over:
        acts = g.legal_actions()
        assert acts, f"no legal actions at step {steps}: {g.state.decisions}"
        g.step(rng.choice(acts))
        steps += 1
        assert all(len(p.hand) <= 10 for p in g.state.players)
        assert steps < 5000
    assert all_uids(g.state) == expected
    assert g.state.winter_revealed == 3
    assert len(g.scores()) == players
