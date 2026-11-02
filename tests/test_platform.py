"""The shared platform on the toy game (fast): checks, experiment + fingerprint replay, summaries, site build."""
import json
import shutil

import pytest

from bgai import checks
from bgai import experiment as X
from bgai.game import load_spec


@pytest.fixture
def toy_experiment():
    out = X.run("_template", "test-greedy-mirror", 2, ["greedy", "greedy"], 30, 1000, workers=1)
    yield out
    shutil.rmtree(out, ignore_errors=True)


def test_checks_pass_on_template():
    report = checks.run("_template", 60, [2, 3, 4])
    assert report["problem_count"] == 0, report["problems"]


def test_experiment_writes_recipe_stats_and_fingerprint(toy_experiment):
    rec = json.loads((toy_experiment / "experiment.json").read_text(encoding="utf-8"))
    st = json.loads((toy_experiment / "stats.json").read_text(encoding="utf-8"))
    assert rec["kind"] == "mirror" and rec["games"] == 30 and rec["seed"] == 1000
    for section in ("meta", "results", "seat_order", "items", "tags", "style", "samples", "cards", "archetypes"):
        assert section in st, section
    assert len(st["per_game_scores"]) == 30 and len(st["fingerprint"]["first"]) == 20
    assert abs(st["meta"]["baseline_win_rate"] - 0.5) < 0.2
    assert X.verify("_template", "test-greedy-mirror", 20)


def test_same_seeds_same_games_any_worker_split():
    a = X.play("_template", ["greedy", "random"], 2, 5, None, 12, None, 1)
    b = X.play("_template", ["greedy", "random"], 2, 5, None, 12, None, 2)   # 2 workers: light enough to run beside training
    assert a == b


def test_every_game_spec_loads_and_plays():
    import random
    for slug in ("_template", "forest_shuffle", "wingspan"):
        spec = load_spec(slug)
        g = spec.new_game(spec.players[0], 3, dict(spec.default_options))
        rng = random.Random(0)
        steps = 0
        while not g.game_over and steps < spec.max_steps:
            g.step_id(rng.choice(g.legal_ids()))
            steps += 1
        assert g.game_over and len(g.scores()) == spec.players[0]
        enc = spec.encoder(spec.players[0])
        assert enc.encode(g, 0).shape == (enc.size,)


def test_site_builds(tmp_path, monkeypatch):
    import tools.build_site as B
    info = B.build_game("forest_shuffle", tmp_path)
    assert info["headline"]["2"]["games"] == 2000
    game = json.loads((tmp_path / "forest_shuffle" / "game.json").read_text(encoding="utf-8"))
    assert "2" in game["compare"] and game["compare"]["2"]["items"]
    assert (tmp_path / "forest_shuffle" / "exp" / "p2-v2fix-15m-mirror.json").exists()
