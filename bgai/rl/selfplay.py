"""All-seat self-play PPO for any game (bgai.game.GameSpec). Proven on Forest Shuffle (the 15M model).

Every seat at a table plays the current policy and every one of its decisions is a training sample. In a share of
games one seat is a frozen opponent from the pool (an older snapshot, or the random agent until it is retired); its
moves are played but not learned. Pool entries: "random", "greedy" (played inside the game worker) or a
checkpoint of any observation version of the game (an older model reads the prefix of the newer vector). Game workers run the engine and the encoder without torch; the main process does
batched inference on CPU and the PPO update (GPU when available). Each seat's decisions form its own trajectory:
reward at the end of the game, GAE over that seat's decisions only.
"""
from __future__ import annotations

import copy
import multiprocessing as mp
import os
import random

import numpy as np

def seat_rewards(scores: list, mode: str) -> list:
    """Reward of every seat: win +-1 (ties win), margin / 100, or both."""
    out = []
    for i, own in enumerate(scores):
        best = max(sc for j, sc in enumerate(scores) if j != i)
        win = 1.0 if own >= best else -1.0
        out.append({"win": win, "margin": (own - best) / 100.0, "mixed": win + (own - best) / 100.0}[mode])
    return out


def gae(values: list, reward: float, gamma: float, lam: float):
    """Advantages and returns of one finished seat trajectory; the only reward comes after its last decision."""
    n = len(values)
    adv = np.zeros(n, dtype=np.float32)
    last = 0.0
    for t in reversed(range(n)):
        nxt = values[t + 1] if t + 1 < n else 0.0
        delta = (reward if t == n - 1 else 0.0) + gamma * nxt - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv, adv + np.asarray(values, dtype=np.float32)


def _worker(conn, slug: str, players: int, tables: int, seed: int, options, max_steps: int) -> None:
    """Runs `tables` games. Each round: receive one action per table (-1: the greedy agent picks it here), answer with
    the next decision of every table (observation of the seat to act, mask, seat) and the final scores of games that
    just ended (then restarted)."""
    from ..game import load_spec

    spec = load_spec(slug)
    enc = spec.encoder(players)
    n_actions = spec.action_count(players)
    rng = random.Random(seed)
    greedy = spec.greedy(seed)

    def new_game():
        return spec.new_game(players, rng.randrange(1 << 30), options)

    def mask(g):
        m = np.zeros(n_actions, dtype=bool)
        m[g.legal_ids()] = True
        return m

    games = [new_game() for _ in range(tables)]
    steps = [0] * tables

    def view(ended):
        return (np.stack([enc.encode(g, g.current_seat) for g in games]),
                np.stack([mask(g) for g in games]),
                [g.current_seat for g in games], ended)

    conn.send(view([None] * tables))
    while True:
        actions = conn.recv()
        if actions is None:
            break
        ended = [None] * tables
        for k, a in enumerate(actions):
            g = games[k]
            if a < 0:
                g.step_id(greedy.act(g, g.current_seat))
            else:
                g.step_id(int(a))
            steps[k] += 1
            if g.game_over or steps[k] >= max_steps:
                ended[k] = g.scores()
                games[k] = new_game()
                steps[k] = 0
        conn.send(view(ended))
    conn.close()


class AllSeatTrainer:
    def __init__(self, model, slug: str, players: int, workers: int = 16, tables: int = 4, reward: str = "mixed",
                 seed: int = 0, frozen_share: float = 0.2, rollout: int = 16384, device: str = "cpu",
                 options: dict = None, max_steps: int = 3000, gamma: float = 0.995, lam: float = 0.95,
                 lr: float = 2.5e-4, epochs: int = 10, batch_size: int = 1024, clip: float = 0.2,
                 ent_coef: float = 0.01, vf_coef: float = 0.5, max_grad_norm: float = 0.5):
        import torch
        self.torch = torch
        self.model = model                     # model.policy stays on CPU: rollouts and model.save use it
        self.policy = model.policy.to("cpu")
        self.learner = copy.deepcopy(self.policy).to(device)
        self.optimizer = torch.optim.Adam(self.learner.parameters(), lr=lr, eps=1e-5)
        self.device = device
        self.players, self.reward, self.frozen_share, self.rollout = players, reward, frozen_share, rollout
        self.gamma, self.lam, self.epochs, self.batch_size = gamma, lam, epochs, batch_size
        self.clip, self.ent_coef, self.vf_coef, self.max_grad_norm = clip, ent_coef, vf_coef, max_grad_norm
        self.rng = random.Random(seed)
        self.pool: list = ["random"]          # "random", "greedy" or a loaded policy
        self._snapshots: dict = {}
        ctx = mp.get_context("spawn")
        self.conns, self.procs = [], []
        for w in range(workers):
            a, b = ctx.Pipe()
            p = ctx.Process(target=_worker, args=(b, slug, players, tables, seed * 1000 + w, options, max_steps), daemon=True)
            p.start()
            self.conns.append(a)
            self.procs.append(p)
        self.tables = tables
        self.n = workers * tables
        self.frozen = [None] * self.n          # per table: (seat, agent) or None
        self.traj = [{} for _ in range(self.n)]  # per table: seat -> {"obs","mask","act","logp","val"}
        self.games = 0
        self.scores: list = []
        self._view = self._receive()
        for t in range(self.n):
            self._new_game(t)

    # -- opponent pool
    def set_pool(self, paths: list, keep_random: bool) -> None:
        """`paths`: checkpoint paths or "greedy"; the random agent is added while `keep_random`."""
        from sb3_contrib import MaskablePPO
        files = [p for p in paths if p != "greedy"]
        keep = {os.path.abspath(p) for p in files}
        for key in [k for k in self._snapshots if k not in keep]:
            del self._snapshots[key]
        for p in files:
            key = os.path.abspath(p)
            if key not in self._snapshots:
                self._snapshots[key] = MaskablePPO.load(p, device="cpu").policy.eval()
        self.pool = (["random"] if keep_random else []) + [p if p == "greedy" else self._snapshots[os.path.abspath(p)]
                                                          for p in paths]

    def _new_game(self, t: int) -> None:
        self.traj[t] = {}
        if self.pool and self.rng.random() < self.frozen_share:
            self.frozen[t] = (self.rng.randrange(self.players), self.rng.choice(self.pool))
        else:
            self.frozen[t] = None

    # -- worker traffic
    def _receive(self):
        parts = [c.recv() for c in self.conns]
        obs = np.concatenate([p[0] for p in parts])
        masks = np.concatenate([p[1] for p in parts])
        seats = [s for p in parts for s in p[2]]
        ended = [e for p in parts for e in p[3]]
        return obs, masks, seats, ended

    def _send(self, actions: np.ndarray) -> None:
        for w, c in enumerate(self.conns):
            c.send(actions[w * self.tables:(w + 1) * self.tables].tolist())

    def close(self) -> None:
        for c in self.conns:
            try:
                c.send(None)
            except (BrokenPipeError, OSError):
                pass
        for p in self.procs:
            p.join(timeout=10)

    # -- rollouts
    def _forward(self, policy, obs, masks, deterministic=False):
        th = self.torch
        with th.no_grad():
            a, v, lp = policy.forward(th.as_tensor(obs), deterministic=deterministic, action_masks=masks)
        return a.numpy(), v.numpy().reshape(-1), lp.numpy()

    def collect(self) -> dict:
        """Play until at least `rollout` learned decisions belong to finished games; returns the batch."""
        batch = {k: [] for k in ("obs", "mask", "act", "logp", "adv", "ret")}
        n = 0
        while n < self.rollout:
            obs, masks, seats, _ = self._view
            actions = np.zeros(self.n, dtype=np.int64)
            learn = [t for t in range(self.n) if self.frozen[t] is None or self.frozen[t][0] != seats[t]]
            if learn:
                a, v, lp = self._forward(self.policy, obs[learn], masks[learn])
                for j, t in enumerate(learn):
                    tr = self.traj[t].setdefault(seats[t], {"obs": [], "mask": [], "act": [], "logp": [], "val": []})
                    tr["obs"].append(obs[t])
                    tr["mask"].append(masks[t])
                    tr["act"].append(a[j])
                    tr["logp"].append(lp[j])
                    tr["val"].append(v[j])
                actions[learn] = a
            learning = set(learn)
            frozen = [t for t in range(self.n) if t not in learning]
            for agent in {id(self.frozen[t][1]): self.frozen[t][1] for t in frozen}.values():
                ts = [t for t in frozen if self.frozen[t][1] is agent]
                if agent == "random":
                    actions[ts] = [self.rng.choice(np.flatnonzero(masks[t])) for t in ts]
                elif agent == "greedy":
                    actions[ts] = -1
                else:
                    width = agent.observation_space.shape[0]      # a version 1 model reads the version 1 prefix
                    actions[ts] = self._forward(agent, obs[ts][:, :width], masks[ts])[0]
            self._send(actions)
            self._view = self._receive()
            for t, scores in enumerate(self._view[3]):
                if scores is None:
                    continue
                rewards = seat_rewards(scores, self.reward)
                for seat, tr in self.traj[t].items():
                    adv, ret = gae(tr["val"], rewards[seat], self.gamma, self.lam)
                    for k in ("obs", "mask", "act", "logp"):
                        batch[k].extend(tr[k])
                    batch["adv"].extend(adv)
                    batch["ret"].extend(ret)
                    n += len(adv)
                self.games += 1
                self.scores.append(scores)
                self._new_game(t)
        return {k: np.asarray(v) for k, v in batch.items()}

    # -- PPO update
    def update(self, batch: dict) -> dict:
        th = self.torch
        dev = self.device
        obs = th.as_tensor(batch["obs"], dtype=th.float32, device=dev)
        masks = th.as_tensor(batch["mask"], dtype=th.bool, device=dev)
        act = th.as_tensor(batch["act"], dtype=th.long, device=dev)
        old_logp = th.as_tensor(batch["logp"], dtype=th.float32, device=dev)
        adv_all = th.as_tensor(batch["adv"], dtype=th.float32, device=dev)
        ret = th.as_tensor(batch["ret"], dtype=th.float32, device=dev)
        n = len(act)
        self.learner.train()
        stats = {"pg": 0.0, "vf": 0.0, "ent": 0.0, "clipped": 0.0}
        k = 0
        for _ in range(self.epochs):
            perm = th.randperm(n, device=dev)
            # full minibatches only: a 1-sample remainder has no advantage std and turned the weights into NaN
            for i in range(0, max(n - self.batch_size, 0) + 1, self.batch_size):
                idx = perm[i:i + self.batch_size]
                values, logp, ent = self.learner.evaluate_actions(obs[idx], act[idx], action_masks=masks[idx])
                adv = adv_all[idx]
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
                ratio = th.exp(logp - old_logp[idx])
                pg = -th.min(adv * ratio, adv * th.clamp(ratio, 1 - self.clip, 1 + self.clip)).mean()
                vf = th.nn.functional.mse_loss(ret[idx], values.flatten())
                ent_loss = -ent.mean()
                loss = pg + self.ent_coef * ent_loss + self.vf_coef * vf
                self.optimizer.zero_grad()
                loss.backward()
                th.nn.utils.clip_grad_norm_(self.learner.parameters(), self.max_grad_norm)
                self.optimizer.step()
                stats["pg"] += pg.item()
                stats["vf"] += vf.item()
                stats["ent"] += -ent_loss.item()
                stats["clipped"] += (th.abs(ratio - 1) > self.clip).float().mean().item()
                k += 1
        self.policy.load_state_dict({key: v.detach().cpu() for key, v in self.learner.state_dict().items()})
        return {key: v / max(k, 1) for key, v in stats.items()} | {"samples": n}
