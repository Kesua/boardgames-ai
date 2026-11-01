"""boardgames.ai shared platform: game interface, mechanics kit, agents, training, experiments and summaries.

A game lives in games/<slug>/ and exposes `SPEC` (a `bgai.game.GameSpec`). Everything in this package works for any
game through that contract; nothing here may name a specific game.
"""
