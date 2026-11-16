import numpy as np
import pandas as pd
import pytest

from seeding.forecast import evaluate as ev


def test_folds_are_back_to_back_and_ordered():
    ts = pd.Series(pd.date_range("2026-01-01", "2026-11-01", freq="D", tz="UTC"))
    f = ev.rolling_folds(ts, n_folds=4)
    assert len(f) == 4
    for a, b in zip(f, f[1:]):
        assert a.test_end == b.test_start
    for x in f:
        assert x.cal_start < x.test_start < x.test_end


def test_typical_miss_and_coverage():
    y = np.log1p(np.array([100.0, 100.0]))
    assert ev.typical_miss(y, y) == pytest.approx(1.0)
    assert ev.typical_miss(np.array([0.0]), np.array([np.log(2)])) == pytest.approx(2.0)
    assert ev.coverage([1, 2, 3, 4], [0, 0, 0, 5], [5, 5, 5, 6]) == 0.75


def test_crps_prefers_the_right_spread():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 5000)
    good = {0.1: np.full_like(y, -1.2816), 0.5: np.zeros_like(y), 0.9: np.full_like(y, 1.2816)}
    narrow = {0.1: np.full_like(y, -0.2), 0.5: np.zeros_like(y), 0.9: np.full_like(y, 0.2)}
    assert ev.crps_from_quantiles(y, good) < ev.crps_from_quantiles(y, narrow)


def test_cqr_reaches_target_coverage_on_fresh_data():
    rng = np.random.default_rng(1)
    y_cal, y_new = rng.normal(0, 1, 2000), rng.normal(0, 1, 20000)
    lo, hi = -0.5, 0.5            # a deliberately too-narrow band
    q = ev.cqr_offset(y_cal, np.full(2000, lo), np.full(2000, hi), level=0.8)
    cov = ev.coverage(y_new, np.full_like(y_new, lo - q), np.full_like(y_new, hi + q))
    assert 0.78 <= cov <= 0.82


def test_adaptive_conformal_recovers_coverage_after_a_shift():
    rng = np.random.default_rng(2)
    cal = rng.normal(0, 1, 500)
    aci = ev.AdaptiveConformal(np.maximum(-0.5 - cal, cal - 0.5), level=0.8, gamma=0.02)
    hits = [aci.update(y, -0.5, 0.5) for y in rng.normal(0, 3, 4000)]   # noise triples overnight
    assert 0.75 <= np.mean(hits[-2000:]) <= 0.85


def test_diebold_mariano_detects_a_better_model():
    rng = np.random.default_rng(3)
    stat, p = ev.diebold_mariano(rng.normal(0, 1, 3000), rng.normal(0, 1.3, 3000))
    assert stat < 0 and p < 0.01
    stat, p = ev.diebold_mariano(rng.normal(0, 1, 3000), rng.normal(0, 1, 3000))
    assert p > 0.01


def test_cluster_bootstrap_gain_sign_and_range():
    rng = np.random.default_rng(4)
    df = pd.DataFrame({"author": np.repeat(np.arange(40), 25),
                       "ea": rng.normal(0, 1, 1000), "eb": rng.normal(0, 1.5, 1000)})
    point, lo, hi = ev.cluster_bootstrap_gain(df, "ea", "eb")
    assert point > 0 and lo > 0 and lo < point < hi


def test_noise_ceiling_from_twins():
    v = np.array([1.0, 0.0])
    w = np.array([0.0, 1.0])
    df = pd.DataFrame({"author": ["a"] * 3, "tweet_id": ["1", "2", "3"],
                       "ts": pd.to_datetime(["2026-01-01", "2026-01-05", "2026-01-06"]),
                       "y": [np.log(100), np.log(400), np.log(50)]})
    r = ev.noise_ceiling(df, {"1": v, "2": v, "3": w})
    assert r["pairs"] == 1 and r["twin_gap_x"] == pytest.approx(4.0)
    assert r["best_possible_miss_x"] == pytest.approx(4.0 ** (1 / np.sqrt(2)))
