import numpy as np
import pandas as pd

from seeding.forecast import evaluate as ev
from seeding.forecast import nowcast as nc


def _snaps(n_posts=120, seed=0):
    """Synthetic growth: final = early * exp(offset(age)) * noise; offset shrinks as the post ages."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_posts):
        final = rng.lognormal(8, 1)
        client = "a" if i % 2 else "b"
        for age in (0.5, 1, 2, 4, 8, 24, 48):
            frac = 1 - np.exp(-age / 6)
            v = final * frac * np.exp(rng.normal(0, 0.25 * np.exp(-age / 12))) if age < 48 else final
            rows.append({"tweet_id": str(i), "client": client, "age_h": age,
                         **{a: (v if a == "views" else v / 50) for a in nc.ACTIONS}})
    return pd.DataFrame(rows)


def test_growth_offset_recovers_final_and_tightens_with_age():
    s = _snaps()
    r = nc.replay(s)
    v = r[r.action == "views"]
    by = v.groupby("bucket").apply(lambda g: ev.typical_miss(g.y, g.q50))
    assert by.iloc[-1] < by.iloc[0]            # later snapshots predict better
    assert by.iloc[-1] < 1.15                  # and well
    assert 0.65 <= ev.coverage(v.y, v.q10, v.q90) <= 0.95


def test_fusion_weights_by_precision():
    vague = nc.fuse(5.0, 3.0, 7.0, (8.0, 0.1))     # sharp snapshot estimate dominates a vague prior
    assert abs(vague["q50"] - 8.0) < 0.05 and vague["weight_snapshot"] > 0.95
    sharp = nc.fuse(5.0, 4.9, 5.1, (8.0, 2.0))     # a vague snapshot barely moves a sharp prior
    assert abs(sharp["q50"] - 5.0) < 0.05
    assert nc.fuse(5.0, 3.0, 7.0, None)["q50"] == 5.0


def test_ready_needs_enough_pairs():
    ok, n = nc.ready(_snaps(n_posts=10))
    assert not ok and n == 10
