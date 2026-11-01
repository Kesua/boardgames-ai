"""Game records as JSON lines: a temporary, local step between playing games and summarising them.

Raw records are never committed (they are large); `bgai.experiment` deletes them after writing stats.json unless
--keep-raw is given. Row types:
  game   : game_id, seed, players, options, agents, steps, turns, rounds, scores, tiebreaks, winners
  seat   : game_id, players, seat, agent, score, rank, win, hand_left, b_<category> (score breakdown),
           x_<key> (game's seat_extra numbers)
  action : game_id, step, turn, seat, agent, decision, decision_label, action, card, item, tag_<kind>, x_<key>,
           forced (true when the game applied the only legal answer itself; games may report these)
  item   : one row per scored item on a final board: game_id, players, seat, agent, win, score, item, kind, group,
           slot, host, points, tag_<kind>
"""
from __future__ import annotations

import json
from typing import Optional

import pandas as pd

from .kit.scores import ranks, winners


def _flat(prefix: str, d: Optional[dict]) -> dict:
    return {f"{prefix}{k}": v for k, v in (d or {}).items()}


class GameRecorder:
    def __init__(self, path: str, rounds_fn=None, seed_of=None):
        self.f = open(path, "w", encoding="utf-8")
        self.game_id = 0
        self.step = 0
        self.agents: list = []
        self.rounds_fn = rounds_fn
        self.seed: Optional[int] = None
        self.options: dict = {}

    def close(self) -> None:
        self.f.close()

    def _w(self, row: dict) -> None:
        self.f.write(json.dumps(row, separators=(",", ":")) + "\n")

    def start_game(self, game, agent_names: list) -> None:
        self.game_id += 1
        self.step = 0
        self.agents = agent_names
        self.after_step(game)                     # forced moves made while the game was set up

    def before_step(self, game, seat: int, action_id: int) -> None:
        self.step += 1
        info = game.record_info(action_id)
        self._w({"type": "action", "game_id": self.game_id, "step": self.step, "turn": game.turns, "seat": seat,
                 "agent": self.agents[seat], "decision": info.get("decision"),
                 "decision_label": info.get("decision_label"), "action": info.get("action"), "card": info.get("card"),
                 "item": info.get("item"), **_flat("tag_", info.get("tags")), **_flat("x_", info.get("extra"))})

    def after_step(self, game) -> None:
        """Moves the game applied by itself (a decision with one legal answer), if the game reports them."""
        drain = getattr(game, "drain_forced", None)
        if drain is None:
            return
        for info in drain():
            self.step += 1
            seat = info["seat"]
            self._w({"type": "action", "game_id": self.game_id, "step": self.step, "turn": game.turns, "seat": seat,
                     "agent": self.agents[seat], "decision": info.get("decision"),
                     "decision_label": info.get("decision_label"), "action": info.get("action"),
                     "card": info.get("card"), "item": info.get("item"), "forced": True,
                     **_flat("tag_", info.get("tags")), **_flat("x_", info.get("extra"))})

    def end_game(self, game) -> None:
        scores = game.scores()
        tb = game.tiebreaks()
        win = set(winners(scores, tb))
        rk = ranks(scores, tb)
        rounds = self.rounds_fn(game) if self.rounds_fn else game.turns / game.num_players
        self._w({"type": "game", "game_id": self.game_id, "seed": self.seed, "players": game.num_players,
                 "options": self.options, "agents": self.agents, "steps": self.step, "turns": game.turns,
                 "rounds": rounds, "winners": sorted(win), "scores": scores, "tiebreaks": tb})
        bd = game.breakdowns()
        for seat in range(game.num_players):
            extra = dict(game.seat_extra(seat))
            hand_left = extra.pop("hand_left", [])
            base = {"game_id": self.game_id, "players": game.num_players, "seat": seat, "agent": self.agents[seat]}
            self._w({"type": "seat", **base, "score": scores[seat], "rank": rk[seat], "win": seat in win,
                     "hand_left": hand_left, **_flat("b_", bd[seat]), **_flat("x_", extra)})
            for r in game.tableau(seat):
                self._w({"type": "item", **base, "win": seat in win, "score": scores[seat], "item": r.get("item"),
                         "kind": r.get("kind"), "group": r.get("group"), "slot": r.get("slot"), "host": r.get("host"),
                         "points": r.get("points", 0), **_flat("tag_", r.get("tags"))})
        self.f.flush()


def load(path: str) -> dict:
    """Read a record file into DataFrames (game, seat, action, item); an unfinished last line is skipped."""
    rows = {"game": [], "action": [], "seat": [], "item": []}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows[r.pop("type")].append(r)
    return {k: pd.DataFrame(v) for k, v in rows.items()}
