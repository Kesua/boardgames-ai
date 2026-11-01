"""Rule IDs the first test file did not cover, and the fixes from the independent engine audit."""
import random

import pytest

from bgai.records import GameRecorder, load
from bgai.agents import RandomAgent, play_game
from games.wingspan import SPEC, new_game
from games.wingspan import engine as E
from games.wingspan.cards import FISH, birds
from games.wingspan.tests.conftest import answer, bid, clear, food, give, kind, options, place, play, started

rule = pytest.mark.rule


@rule("W1.4")
def test_food_supply_unlimited():
    g = started(2, 3)
    me = g.current_seat
    g.gain(me, FISH, 500)
    assert g.p(me).food[FISH] >= 500


@rule("W2.1")
def test_setup_tray_and_feeder():
    g = new_game(3, 8)
    assert all(c is not None for c in g.s.tray) and len(g.s.feeder) == 5 and not g.s.outside
    assert len(g.s.bonus_deck) == 26 - 2 * 3


@rule("W2.2")
def test_goal_sides_random():
    seen = set()
    for seed in range(40):
        seen |= {x["id"] for x in new_game(2, seed).s.goals}
    assert len(seen) == 16


@rule("W4.1")
def test_row_full_at_five():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    for _ in range(5):
        place(g, me, "Hooded Warbler", "forest")
    give(g, me, "Hooded Warbler")
    food(g, me, invertebrate=5)
    assert "Play a bird" not in options(g)


@rule("W8.1")
def test_from_the_deck_means_deck_only():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    place(g, me, "Canvasback", "wetland")                      # all players draw 1 from the deck
    tray = list(g.s.tray)
    answer(g, "Draw cards")
    while kind(g) == "DRAW" and g.s.decisions.top.data.get("left") is not None and g.s.decisions.top.seat == me \
            and not getattr(g, "_used", False):
        answer(g, "Stop")
        break
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1])
    answer(g, "Use")
    assert g.s.tray == tray or None not in g.s.tray


@rule("W9.2")
def test_tucked_and_cached_are_points_not_birds():
    from games.wingspan.scoring import goal_count
    g = started(2, 3)
    clear(g)
    p = place(g, 0, "Wild Turkey", "grassland")
    p.tucked, p.cache[0] = 4, 2
    assert goal_count(g, 0, {"count": "total_birds"}) == 1
    b = g.breakdowns()[0]
    assert b["tucked"] == 4 and b["cache"] == 2


@rule("W10.3")
def test_each_player_gains_die_owner_chooses_start():
    g = started(3, 3)
    me = g.current_seat
    clear(g)
    place(g, me, "Anna's Hummingbird", "forest")
    answer(g, "Gain food")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1] if kind(g) == "TRADE" else g.s.decisions.top.data["legal"][0])
    answer(g, "Use")
    assert kind(g) == "START_PLAYER" and g.s.decisions.top.seat == me
    answer(g, "1 seats to the left")
    assert g.s.decisions.top.seat == (me + 1) % 3 and kind(g) == "TAKE_DIE"


@rule("W10.4")
def test_powers_affect_only_own_birds():
    g = started(2, 3)
    me = g.current_seat
    clear(g)
    other = 1 - me
    o = place(g, other, "Wild Turkey", "grassland")
    place(g, me, "Scaled Quail", "grassland")
    answer(g, "Lay eggs")
    legal_slots = [a for a in g.s.decisions.top.data["legal"] if E.A_SLOT <= a < E.A_SLOT + 15]
    assert all(g.at(me, *g.slot_of(a)) is not None for a in legal_slots)
    assert o.eggs == 0


@rule("W10.10")
def test_hermit_thrush_owner_chooses_first():
    g = started(3, 3)
    me = g.current_seat
    clear(g)
    for x in range(3):
        place(g, x, "Hermit Thrush" if x == me else "Wild Turkey", "forest" if x == me else "grassland")
    place(g, me, "Trumpeter Swan", "wetland")
    for x in range(3):
        if x != me:
            place(g, x, "Hooded Warbler", "forest")               # everyone has 1 forest bird: all tied
    answer(g, "Gain food")
    while kind(g) != "USE_POWER":
        g.step_id(g.s.decisions.top.data["legal"][-1] if kind(g) == "TRADE" else g.s.decisions.top.data["legal"][0])
    answer(g, "Use")
    assert kind(g) == "START_PLAYER"


@rule("W10.14")
def test_bonus_power_keeps_one_discards_other():
    g = started(2, 3)
    me = g.current_seat
    clear(g, me)
    give(g, me, "Wood Stork")
    food(g, me, fish=3, rodent=3, invertebrate=3)
    disc = len(g.s.bonus_discard)
    play(g, "Wood Stork")
    answer(g, "Use")
    g.step_id(g.s.decisions.top.data["legal"][0])
    assert len(g.s.bonus_discard) == disc + 1


@rule("W2.4")
def test_setup_choices_are_secret_in_observations():
    g = new_game(2, 5)
    first = g.current_seat
    for _ in range(5):
        answer(g, "Keep")
    while g.current_seat == first:
        g.step_id(g.s.decisions.top.data["legal"][0])
    other = g.current_seat
    v = SPEC.encoder(2).encode(g, other)
    i_others = 260 + 224 + 1145
    assert v[i_others:i_others + 6].sum() == 0 and v[258] == 0      # first player's food, hand and the discards


def test_opponent_bonus_points_hidden():
    g = started(2, 3)
    me = g.current_seat
    other = 1 - me
    g.p(other).bonus = [0]                                        # Anatomist
    clear(g, other)
    for name in ("Blue Grosbeak", "Red-Breasted Nuthatch", "Black-Chinned Hummingbird", "Ruby-Crowned Kinglet"):
        place(g, other, name, "forest")
    v = SPEC.encoder(2).encode(g, me)
    i = 260 + 224 + 1145
    assert v[i + 18 + 1] == 0                                     # their bonus category is 0 in my view


def test_forced_moves_are_recorded(tmp_path):
    path = tmp_path / "r.jsonl"
    rec = GameRecorder(str(path))
    g = new_game(2, 3)
    play_game(g, [RandomAgent(1), RandomAgent(2)], recorder=rec)
    rec.close()
    d = load(str(path))
    plays = d["action"][d["action"]["action"] == "PLAY"]
    on_mats = len(d["item"])
    assert len(plays) == on_mats                                  # every bird on a mat was recorded as played
