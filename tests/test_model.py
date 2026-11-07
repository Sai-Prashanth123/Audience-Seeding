import numpy as np
import pandas as pd

from seeding import xalgo
from seeding.model import _within_author, build_features


def test_day_decay_matches_published_rule():
    assert [xalgo.day_decay(i) for i in (1, 2, 3, 4, 9)] == [1.0, 0.625, 0.4375, 0.25, 0.25]


def test_constant_prediction_ranks_nothing():
    t = pd.DataFrame({"author": ["a"] * 6, "y": [1, 2, 3, 4, 5, 6], "p": [3.0] * 6})
    assert _within_author(t, "p")["within_author_spearman"] == 0.0


def test_perfect_ranking():
    t = pd.DataFrame({"author": ["a"] * 10, "y": np.arange(10), "p": np.arange(10) * 2.0})
    r = _within_author(t, "p")
    assert abs(r["within_author_spearman"] - 1.0) < 1e-9 and r["top20_hit_rate"] == 1.0


def _raw(n=8):
    ts = pd.date_range("2026-10-01 09:00", periods=n, freq="6h", tz="UTC")
    return pd.DataFrame({
        "author": ["a"] * n, "tweet_id": [str(i) for i in range(n)], "created_at": ts,
        "text": ["hello world"] * n, "article_title": [None] * n, "is_thread": [False] * n,
        "is_quote": [False] * n, "is_long_form": [False] * n, "media_count": [0] * n, "first_url": [None] * n,
        "reply_count": [1] * n, "quote_count": [0] * n, "retweet_count": [0] * n, "like_count": [0] * n,
        "view_count": [100] * n, "author_followers": [1000] * n, "profile_followers": [None] * n,
        "author_segment": ["b2b"] * n})


def test_features_only_look_backwards():
    df = _raw()
    df.loc[7, "reply_count"] = 100  # a huge last post must not leak into its own baseline
    f = build_features(df)
    assert f.base.iloc[:5].isna().all()
    assert f.base.iloc[7] == 5.0          # median of earlier posts (each 1 reply x5)
    assert f.day_position.tolist()[:4] == [1, 2, 3, 1]   # 09,15,21h same day; next day resets
    assert f.day_decay.iloc[2] == 0.4375
    assert f.cold_start.iloc[0] == 1.0
