import numpy as np
import pandas as pd

from seeding.forecast.features import lagged_stats


def test_lagged_stats_only_uses_posts_matured_48h():
    ts = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05",
                         "2026-01-10", "2026-01-10 12:00", "2026-01-11"], format="mixed").to_numpy(dtype="datetime64[ns]")
    v = np.array([10, 20, 30, 40, 50, 1000, 5000, 7])
    s = lagged_stats(ts, v, lag_h=48, window=20, min_prior=5)
    assert np.isnan(s[4, 0])                  # only 3 posts are 48h older than the 5th
    assert s[5, 0] == 30 and s[5, 4] == 5     # median of the 5 matured ones
    assert s[7, 0] == 30 and s[7, 4] == 5     # the 1000/5000 posts are < 48h old on 11 Jan: excluded
    assert s[7, 1] == 30                      # mean of the latest 5 matured


def test_lagged_stats_window_takes_latest():
    ts = (np.datetime64("2026-01-01") + np.arange(30) * np.timedelta64(3, "D")).astype("datetime64[ns]")
    v = np.arange(30, dtype=float)
    s = lagged_stats(ts, v, lag_h=48, window=20, min_prior=5)
    assert s[29, 0] == np.median(np.arange(9, 29))


def _raw(seed=0, n_auth=30, per=40):
    """Synthetic raw backtest: author-level bias that the shrinkage step should remove; a good and a bad member."""
    rng = np.random.default_rng(seed)
    rows = []
    bias = rng.normal(0, 0.6, n_auth)
    for split, t0 in (("cal", "2026-01-01"), ("test", "2026-01-15")):
        ts = pd.Timestamp(t0, tz="UTC") + pd.to_timedelta(rng.uniform(0, 14, n_auth * per), unit="D")
        a = np.repeat(np.arange(n_auth), per)
        truth = rng.normal(5, 1, len(a))
        y = truth + bias[a] + rng.normal(0, 0.5, len(a))
        for m, noise in (("L1_lgbm", 0.1), ("bad", 1.5)):
            p = truth + rng.normal(0, noise, len(a))
            rows.append(pd.DataFrame({"fold": 1, "split": split, "tweet_id": [f"{split}{i}" for i in range(len(a))],
                                      "author": a, "ts": ts, "target": "views", "member": m, "y": y,
                                      "q10": p - 0.3, "q50": p, "q90": p + 0.3}))
    return pd.concat(rows, ignore_index=True)


def test_finalize_shrinkage_stack_and_ranges():
    from seeding.forecast import evaluate as ev
    from seeding.forecast.model import finalize
    bt = finalize(_raw(), stack_members=["L1_lgbm", "bad"])
    assert set(bt.split) == {"test"}
    miss = {m: ev.typical_miss(g.y, g.q50) for m, g in bt.groupby("member")}
    assert miss["L1_lgbm+shrink"] < miss["L1_lgbm"] < miss["bad"]     # per-author bias removed
    assert miss["stack"] <= miss["bad"]                                # stacker leans on the good member
    w = __import__("json").loads(bt[bt.member == "stack"].weights.iloc[0])
    assert w["q50"]["L1_lgbm"] > w["q50"]["bad"]
    for m, g in bt.groupby("member"):                                  # conformal ranges near 80%
        assert 0.72 <= ev.coverage(g.y, g.q10, g.q90) <= 0.88, m


def test_external_member_enters_the_stack():
    from seeding.forecast.model import add_external, finalize
    raw = _raw()
    a = raw[raw.member == "L1_lgbm"].assign(member="A_usual")
    raw = pd.concat([raw, a], ignore_index=True)
    df = raw[raw.member == "A_usual"][["tweet_id", "y"]].assign(lb_views=lambda d: d.y - 0.3)
    preds = raw[raw.member == "A_usual"][["fold", "tweet_id", "target", "split"]].assign(ft_pred=0.3)  # a perfect "text model"
    bt = finalize(add_external(raw, preds, df[["tweet_id", "lb_views"]]), stack_members=["L1_lgbm", "textft"])
    assert "textft" in set(bt.member)
    w = __import__("json").loads(bt[bt.member == "stack"].weights.iloc[0])
    assert w["q50"]["textft"] > 0.9               # the stacker trusts the perfect member
