import pytest

from games.forest_shuffle.data.database import CardDatabase
from games.forest_shuffle.engine.game import Game


@pytest.fixture(scope="session")
def db():
    return CardDatabase.load()


@pytest.fixture
def game(db):
    g = Game(db, num_players=2, seed=1)
    g.reset()
    return g


def give(game, seat, species_key, tree_symbol=None):
    """Put a fresh instance of a card containing `species_key` (with the given symbol if any) in a hand."""
    for d in game.db.defs:
        if d.layout == "WOODY_PLANT" and d.species == species_key and tree_symbol in (None, d.tree_symbol):
            return game.spawn_into_hand(seat, d.def_id)
        for h in d.halves:
            if h.species == species_key and tree_symbol in (None, h.tree_symbol):
                return game.spawn_into_hand(seat, d.def_id)
    raise KeyError(species_key)


def plant(game, seat, species_key, tree_symbol=None):
    """Place a woody plant directly (test shortcut). Returns forest index."""
    return game.debug_place_woody(seat, give(game, seat, species_key, tree_symbol).def_id)


def attach(game, seat, forest_idx, species_key, tree_symbol=None):
    """Place a dweller directly (test shortcut)."""
    card = give(game, seat, species_key, tree_symbol)
    return game.debug_place_dweller(seat, forest_idx, card.def_id, species_key)


def hand_only(game, seat, *keys_syms):
    """Replace a hand with exactly the given (species, symbol) cards."""
    p = game.state.players[seat]
    game.state.removed.extend(p.hand)
    p.hand.clear()
    return [give(game, seat, k, s) for k, s in keys_syms]


def play_half(game, card, species, target=None):
    """Play the half of `card` showing `species`; resolve the target decision if several plants are legal."""
    from games.forest_shuffle.core.actions import ActionKind as K
    halves = game.db.defs[card.def_id].halves
    game.step(next(a for a in game.legal_actions()
                   if a.kind == K.PLAY_HALF and a.card == card.def_id and halves[a.half].species == species))
    if game.state.decisions and game.state.decisions[-1].kind == "CHOOSE_TARGET":
        opts = game.legal_actions()
        game.step(next(a for a in opts if target is None or a.target == target))
