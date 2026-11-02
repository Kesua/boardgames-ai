"""Learning setup (design-rl): observation size, range and blocks; the greedy baseline's sanity."""
import random

import numpy as np

from games.through_the_ages import SPEC, new_game
from games.through_the_ages import engine as En
from games.through_the_ages.agents import GreedyAgent, rounds_left
from games.through_the_ages.encoder import C_INDEX, STATIC, StateEncoder
from games.through_the_ages.tests.conftest import cid, fresh

SIZES = {2: 3385, 3: 3705, 4: 4025}          # observation version 1; a change means a new version (and retraining)


def test_encoder_size_is_pinned_and_compact():
    for n, size in SIZES.items():
        enc = SPEC.encoder(n)
        assert enc.version == 1 and enc.size == size
        assert 2000 <= enc.size <= 5000


def test_observations_have_the_size_and_lie_in_0_1_through_random_games():
    for n in (2, 3, 4):
        enc = SPEC.encoder(n)
        g = new_game(n, 7)
        rng = random.Random(n)
        k = 0
        while not g.game_over:
            if k % 7 == 0:
                for viewer in range(n):
                    v = enc.encode(g, viewer)
                    assert v.shape == (enc.size,) and v.dtype == np.float32
                    assert np.isfinite(v).all() and v.min() >= 0.0 and v.max() <= 1.0
            g.step_id(rng.choice(g.legal_ids()))
            k += 1


def test_row_slots_carry_take_cost_and_card_features():
    g = fresh(2, 3)
    s = g.current_seat
    enc = StateEncoder(2)
    v = enc.encode(g, s)
    o = 5 + 4 + 4 + len(En.DECISION_KINDS)                                   # first row slot
    slot = 47
    for k, c in enumerate(g.s.row):
        if c is None:
            continue
        assert v[o + k * slot] == 1.0
        assert abs(v[o + k * slot + 1] - min(1.0, g.take_cost(s, k) / 4)) < 1e-6
        assert np.allclose(v[o + k * slot + 3:o + (k + 1) * slot], STATIC[c, :slot - 3])
        assert v[o + 13 * slot + C_INDEX[c]] > 0


def test_decision_context_shows_the_card_concerned():
    g = fresh(2, 1)
    s = g.current_seat
    g.p(s).civil_hand = []
    enc = StateEncoder(2)
    while g.s.decisions.top.kind != "CHOOSE_TECH":                         # Build -> which building
        legal = g.legal_ids()
        g.step_id(En.A_VERB + En.V["BUILD"] if En.A_VERB + En.V["BUILD"] in legal else En.A_END)
    v = enc.encode(g, s)
    ctx = enc.global_size
    assert v[ctx + 6] == 1.0                                                 # the decider is me
    kinds_at = 5 + 4 + 4
    assert v[kinds_at + En.DECISION_KINDS.index("CHOOSE_TECH")] == 1.0


def test_rounds_left_shrinks_with_the_decks():
    g = new_game(2, 1)
    r0 = rounds_left(g)
    assert 15 <= r0 <= 30
    rng = random.Random(1)
    while g.s.age in ("A", "I"):
        g.step_id(rng.choice(g.legal_ids()))
    assert rounds_left(g) < r0


def test_greedy_plays_complete_games_and_beats_random():
    from bgai.agents import RandomAgent
    wins = 0
    for seed in range(4):
        g = new_game(2, 40 + seed)
        agents = [GreedyAgent(seed), RandomAgent(seed)] if seed % 2 == 0 else [RandomAgent(seed), GreedyAgent(seed)]
        me = seed % 2
        while not g.game_over:
            seat = g.current_seat
            a = agents[seat].act(g, seat)
            assert a in g.legal_ids()
            g.step_id(a)
        sc = g.scores()
        wins += sc[me] >= sc[1 - me]
    assert wins >= 3


def test_greedy_judges_with_public_information_only():
    """Changing another player's hidden hand does not change the greedy's answer (same seed, same state)."""
    g = fresh(2, 5)
    s = g.current_seat
    o = 1 - s
    h = g.clone()
    h.p(o).civil_hand = [cid("Iron")]
    h.p(o).military_hand = [cid("Legion", "I")]
    g.p(o).civil_hand = [cid("Alchemy")]
    g.p(o).military_hand = [cid("Military Bonus", "I")]
    assert GreedyAgent(3).act(g, s) == GreedyAgent(3).act(h, s)
