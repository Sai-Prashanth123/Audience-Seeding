import numpy as np
import pandas as pd

from seeding import memory as mm


def test_small_client_follows_group_large_client_follows_itself():
    rng = np.random.default_rng(0)
    group = np.log(rng.lognormal(np.log(2.0), 0.3, 400))          # all clients: 2x
    small_own = np.log(np.full(3, 0.8))                             # 3 posts saying 0.8x
    big_own = np.log(rng.lognormal(np.log(0.8), 0.2, 200))          # 200 posts saying 0.8x
    small = mm.pooled_effect(small_own, group)
    big = mm.pooled_effect(big_own, group)
    assert small["source"] == "learned from all clients" and small["effect"] > 1.6
    assert big["source"] == "own evidence" and big["effect"] < 0.9
    assert abs(small["weight_own"] - 3 / 23) < 1e-3 and abs(big["weight_own"] - 200 / 220) < 1e-3


def test_too_little_group_evidence_teaches_nothing():
    assert mm.pooled_effect(np.log(np.ones(5)), np.log(np.ones(10))) == {}


def test_lifecycle_new_emerging_habit_fading_forgotten():
    B, N = "better", "none"
    assert mm.lifecycle([B])["status"] == "new"
    assert mm.lifecycle([B, B])["status"] == "emerging"
    assert mm.lifecycle([B, B, B])["status"] == "habit"
    assert mm.lifecycle([B, B, B, N])["status"] == "habit"          # one bad week is not forgetting
    assert mm.lifecycle([B, B, B, N, N])["status"] == "fading"
    assert mm.lifecycle([B, B, B] + [N] * 6)["status"] == "forgotten"
    assert mm.lifecycle([B, N])["status"] is None                   # a one-off fades away silently


def test_situation_change_learns_faster():
    B, N = "better", "none"
    assert mm.lifecycle([B, B])["status"] == "emerging"
    assert mm.lifecycle([B, B], [mm.FAST] * 2)["status"] == "habit"
    assert mm.lifecycle([B, B, B, N], [mm.FAST] * 4)["status"] == "fading"


def test_direction_flip_restarts_the_pattern():
    assert mm.lifecycle(["better"] * 3 + ["worse"])["status"] == "new"


def test_change_detector_fires_on_step_not_on_noise():
    rng = np.random.default_rng(1)
    prior = rng.normal(0, 0.3, 60)
    assert mm.change_detected(rng.normal(1.5, 0.3, 20), prior)
    assert not mm.change_detected(rng.normal(0, 0.3, 20), prior)


def test_week_snapshot_uses_no_future_posts():
    t0 = pd.Timestamp("2026-10-01", tz="UTC")
    rows = []
    for i in range(80):
        rows.append({"client": "a" if i % 2 else "b", "created_at": t0 + pd.Timedelta(hours=6 * i),
                     "rel_perf": 3.0, "format": "thread", "hook": "x", "length": "1,000+", "hour_block": "0-5",
                     "day_slot": "1st", "topic": "t"})
    posts = pd.DataFrame(rows)
    cut = t0 + pd.Timedelta(days=10)
    snap = mm.week_snapshot(posts, cut)
    used = posts[posts.created_at <= cut - pd.Timedelta(hours=48)]
    fmt = snap[(snap.dim == "format")]
    assert (fmt.n_group == len(used)).all()


def test_group_counts_each_client_equally():
    rng = np.random.default_rng(3)
    by = {"big": np.log(np.full(400, 5.0)), "c1": np.log(np.full(10, 0.9)),
          "c2": np.log(np.full(10, 1.0)), "c3": np.log(np.full(10, 1.1))}
    point, boot = mm.group_boot(by, 300, rng)
    assert abs(np.exp(point) - 1.05) < 0.1           # one huge client is not "everyone"
    assert mm.group_boot({"a": np.ones(50), "b": np.ones(50)}, 100, rng) is None   # < 3 clients


def test_correction_only_after_enough_surprises():
    assert mm.correction(np.log(np.full(9, 0.5))) == 1.0
    assert abs(mm.correction(np.log(np.full(10, 0.5))) - 0.5) < 1e-9
