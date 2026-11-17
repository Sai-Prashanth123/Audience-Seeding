import numpy as np
import pandas as pd

from seeding.forecast.features import audience_online


def test_audience_online_uses_only_earlier_engagements():
    ev = pd.to_datetime(["2026-01-01 14:00", "2026-01-02 14:10", "2026-01-03 15:00", "2026-01-20 14:00"] * 5,
                        utc=True).to_numpy(dtype="datetime64[ns]")
    posts = pd.to_datetime(["2026-01-10 14:30", "2026-01-10 03:00", "2026-01-01 00:00"], utc=True).to_numpy(
        dtype="datetime64[ns]")
    a = audience_online(posts, ev)
    assert a[0] > 0.6            # 15 earlier engagements, all within +-1h of 14:00
    assert a[1] < 0.15           # nobody engages around 03:00
    assert abs(a[2] - 0.125) < 1e-9   # no earlier engagements: neutral prior (3/24)


def test_hit_label_baseline_and_reliability():
    from seeding.forecast import viral
    df = pd.DataFrame({"author": ["a"] * 10 + ["b"] * 10, "lb_views": 5.0,
                       "y_views": [5 + np.log(4)] * 5 + [5.0] * 5 + [5.0] * 10})
    assert viral.label(df).sum() == 5
    base = viral.author_base_rate(df, k=0)
    assert base["a"] == 0.5 and base["b"] == 0.0 and base["overall"] == 0.25
    rel = viral.reliability(np.array([0, 1, 0, 0]), np.array([0.01, 0.9, 0.03, 0.5]))
    assert rel.posts.sum() == 4


def test_brier_gain_positive_for_a_better_model():
    from seeding.forecast import viral
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 2000)
    df = pd.DataFrame({"author": np.repeat(np.arange(40), 50), "y": y,
                       "p": np.clip(y * 0.7 + 0.15, 0, 1), "p0": 0.5})
    g, lo, hi = viral.brier_gain(df)
    assert g > 0 and lo > 0
