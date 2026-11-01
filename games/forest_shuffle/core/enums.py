"""Constants shared by the engine."""
from __future__ import annotations

SLOTS = ("TOP", "BOTTOM", "LEFT", "RIGHT")
TREE_SYMBOLS = ("LINDEN", "OAK", "SILVER_FIR", "BIRCH", "BEECH", "SYCAMORE",
                "DOUGLAS_FIR", "HORSE_CHESTNUT", "ALPINE_LARCH", "SWISS_PINE")
HAND_LIMIT = 10
CLEARING_LIMIT = 10
MAX_WOODY = 40
ENCODER_PLANTS = 20      # plants encoded in detail
ALL_EXPANSIONS = ("base", "woodland_edge", "alpine")


class DecisionKind:
    DRAW = "DRAW"
    PAY = "PAY"
    USE_OR_SKIP = "USE_OR_SKIP"
    CHOOSE_CLEARING_CARD = "CHOOSE_CLEARING_CARD"
    CHOOSE_HAND_CARD = "CHOOSE_HAND_CARD"
    PLACE_FREE = "PLACE_FREE"
    PLAY_MORE = "PLAY_MORE"
    SAPLING_MORE = "SAPLING_MORE"


ALL_DECISION_KINDS = ("DRAW", "PAY", "USE_OR_SKIP", "CHOOSE_CLEARING_CARD",
                      "CHOOSE_HAND_CARD", "PLACE_FREE", "PLAY_MORE", "SAPLING_MORE", "CHOOSE_TARGET")
