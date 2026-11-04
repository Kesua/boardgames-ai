"""Pins the card data (data/cards.json, built by data/build_cards.py): totals from rules.md T1, T2, T15 and
data/SOURCES.md, so an accidental data change fails loudly."""
import json
from collections import Counter
from pathlib import Path

import pytest

rule = pytest.mark.rule
CARDS = json.loads((Path(__file__).resolve().parents[1] / "data" / "cards.json").read_text(encoding="utf-8"))
TEXT_KINDS = {"leader", "action", "event", "territory", "aggression", "war", "pact"}


def deck(age, kind_of_deck, players):
    return sum(c["copies"][str(players)] for c in CARDS
               if c["age"] == age and c["deck"] == kind_of_deck and c["copies"])


def test_ids_and_names_unique():
    assert [c["id"] for c in CARDS] == list(range(len(CARDS)))
    assert len({(c["name"], c["age"]) for c in CARDS}) == len(CARDS)


@rule("T1.4")
def test_card_kinds():
    assert len(CARDS) == 292
    assert Counter(c["set"] for c in CARDS) == {"base": 218, "new": 56, "rebalanced": 18}
    kinds = Counter(c["kind"] for c in CARDS)
    assert kinds["leader"] == 48 and kinds["wonder"] == 32 and kinds["government"] == 8
    assert kinds["tactic"] == 17 and kinds["pact"] == 11 and kinds["bonus"] == 3
    assert all(c["effect"] for c in CARDS if c["kind"] in TEXT_KINDS)


@rule("T1.5")
def test_starting_technologies():
    start = sorted(c["name"] for c in CARDS if c["starting"])
    assert start == ["Agriculture", "Bronze", "Despotism", "Philosophy", "Religion", "Warriors"]


@rule("T1.3")
@rule("T15.3")
def test_military_deck_sizes():
    # base 10/45/50/45 at 4 players (BGA, = CGE's 149 + rebalanced Wealthy Territory I) + 1/6/6/6 new
    assert [deck(a, "military", 4) for a in ("A", "I", "II", "III")] == [11, 51, 56, 51]
    # pacts (2 + Naval Trade Agreement, 4, 4) are the only cards missing with 2 players
    assert [deck(a, "military", 4) - deck(a, "military", 2) for a in ("I", "II", "III")] == [3, 4, 4]


@rule("T2.1")
@rule("T15.2")
def test_player_count_markings():
    # 3+ / 4 marked civil cards per deck I/II/III; the expansion table says 7/9/11 and 3/2/1, minus the 4 unknown
    # 3+ action cards left out by the maintainer's decision (1 in Age I, 2 in Age II, 1 in Age III; SOURCES.md)
    def marks(age, lo, hi):
        return sum(c["copies"][hi] - c["copies"][lo] for c in CARDS
                   if c["age"] == age and c["deck"] == "civil" and c["copies"])
    assert [marks(a, "2", "3") for a in ("I", "II", "III")] == [6, 7, 10]
    assert [marks(a, "3", "4") for a in ("I", "II", "III")] == [3, 2, 1]


@rule("T15.4")
def test_leader_wonder_pools():
    for age in ("A", "I", "II", "III"):
        assert sum(c["kind"] == "leader" and c["age"] == age for c in CARDS) == 12
        assert sum(c["kind"] == "wonder" and c["age"] == age for c in CARDS) == 8


def test_known_corrections():
    by = {(c["name"], c["age"]): c for c in CARDS}
    assert by[("Aggression: Plunder", "I")]["military_action_cost"] == 1      # B misread 2 (SOURCES.md)
    assert by[("Wealthy Territory", "I")]["effect"]["once"] == {"resources": 6}  # rebalanced (rules D10)
    assert by[("Wealthy Territory", "I")]["yields"] == {"blue_tokens": 3}
    assert by[("Vast Territory", "I")]["yields"] == {"yellow_tokens": 3, "blue_tokens": -1}
    assert ("Light Cavalry", "I") not in by                                    # no copies in this edition
    assert by[("Impact of Science", "III")]["effect"]["table"]["3"] == [14, 7, 0]
