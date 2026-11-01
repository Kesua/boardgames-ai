"""Pins the card data: totals from data/SOURCES.md and rules.md W1, so an accidental change fails loudly."""
from collections import Counter

import pytest

from games.wingspan.cards import birds, bonus_cards, goal_tiles

rule = pytest.mark.rule


@rule("W1.1")
def test_bird_totals():
    b = birds()
    assert len(b) == 180 and sum(x.swift_start for x in b) == 10
    assert Counter(x.color for x in b) == {"brown": 125, "white": 37, "pink": 12, "none": 6}
    assert Counter(x.nest for x in b) == {"ground": 42, "cavity": 40, "bowl": 40, "platform": 39, "star": 17, "none": 2}
    assert sum(x.predator for x in b) == 23 and sum(x.flocking for x in b) == 27
    assert Counter(x.points for x in b) == {0: 7, 1: 13, 2: 22, 3: 35, 4: 37, 5: 34, 6: 12, 7: 7, 8: 8, 9: 5}
    assert sum(x.alternative for x in b) == 31 and sum(1 for x in b if x.wild) == 31
    assert sorted(x.name for x in b if x.food_total == 0) == ["Black Vulture", "California Condor", "Turkey Vulture"]


def test_known_corrections():
    by = {x.name: x for x in birds()}
    assert by["Spotted Sandpiper"].points == 5                       # first-printing error was 4
    assert by["American Redstart"].egg_limit == 2                    # SOURCES.md
    assert by["Northern Mockingbird"].food[0] == 1 and by["Northern Mockingbird"].food[3] == 1
    assert by["Mississippi Kite"].predator and by["Northern Harrier"].predator


@rule("W1.2")
def test_bonus_and_goal_totals():
    assert len(bonus_cards()) == 26
    assert len(goal_tiles()) == 8 and all(len(t) == 2 for t in goal_tiles())
    assert len({side["id"] for t in goal_tiles() for side in t}) == 16


def test_every_power_parsed():
    kinds = Counter(x.power["type"] if x.power else "none" for x in birds())
    assert kinds["none"] == 6 and kinds["draw_bonus"] == 15 and kinds["move"] == 8
    assert kinds["play_another"] == 10 and kinds["hunt_card"] == 10 and kinds["hunt_dice"] == 13
