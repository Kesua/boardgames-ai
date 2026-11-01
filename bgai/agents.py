"""Agents pick an action number for the seat that has to decide. Shared by training, evaluation and experiments.

A game's greedy agent lives in the game package (it needs the game's scoring); random and trained agents are here.
"""
from __future__ import annotations

import random
from typing import Optional

import numpy as np


class Agent:
    name = "agent"

    def act(self, game, seat: int) -> int:
        raise NotImplementedError


class RandomAgent(Agent):
    """Uniform choice among the legal action numbers."""
    name = "random"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def act(self, game, seat: int) -> int:
        return self.rng.choice(game.legal_ids())


def load_policy(path: str):
    from sb3_contrib import MaskablePPO
    return MaskablePPO.load(path, device="cpu")


def encoder_for(spec, players: int, size: int):
    """The game's encoder whose vector size matches a model's input size (older observation versions included)."""
    enc = spec.encoder(players)
    if enc.size == size:
        return enc
    for v in getattr(spec, "encoder_versions", ()) or ():
        e = spec.encoder(players, version=v)
        if e.size == size:
            return e
    raise ValueError(f"model input size {size} matches no observation version of {spec.slug} ({players} players)")


class PolicyAgent(Agent):
    """A trained model. Plays the most likely legal action (deterministic), so experiments repeat exactly."""
    name = "model"

    def __init__(self, path: str, spec, players: int, name: Optional[str] = None, deterministic: bool = True):
        self.model = load_policy(path)
        self.encoder = encoder_for(spec, players, self.model.observation_space.shape[0])
        self.n_actions = spec.action_count(players)
        self.deterministic = deterministic
        self.name = name or f"model:{path}"

    def act(self, game, seat: int) -> int:
        obs = self.encoder.encode(game, seat)
        mask = np.zeros(self.n_actions, dtype=bool)
        mask[game.legal_ids()] = True
        a, _ = self.model.predict(obs, action_masks=mask, deterministic=self.deterministic)
        return int(a)


def play_game(game, agents: list, recorder=None, max_steps: int = 5000) -> list:
    """Play to the end; returns final scores. With a recorder, every action and the final state are recorded."""
    if recorder is not None:
        recorder.start_game(game, [a.name for a in agents])
    steps = 0
    while not game.game_over and steps < max_steps:
        seat = game.current_seat
        a = agents[seat].act(game, seat)
        if recorder is not None:
            recorder.before_step(game, seat, a)
        game.step_id(a)
        if recorder is not None:
            recorder.after_step(game)
        steps += 1
    if not game.game_over:
        raise RuntimeError(f"game did not end within {max_steps} decisions")
    if recorder is not None:
        recorder.end_game(game)
    return game.scores()
