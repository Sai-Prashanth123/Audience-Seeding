import pytest
import pandas as pd

from seeding.content import classify_hook, enrich, length_bucket


def test_hooks():
    assert classify_hook("Why does cold email fail?\nbody") == "question"
    assert classify_hook("Stop buying more leads.") == "contrarian"
    assert classify_hook("Here's how we booked 40 calls") == "how-to / list"
    assert classify_hook("Introducing Boardy Pro") == "announcement"
    assert classify_hook("$15K MRR to $18M ARR") == "number / result"
    assert classify_hook("I quit my job last year") == "story"
    assert classify_hook("Distribution beats product.") == "statement"
    assert classify_hook("") == "media only"


def test_length_bucket():
    assert [length_bucket(n) for n in (50, 280, 281, 5000)] == ["<100 chars", "100-280", "281-1,000", "1,000+"]


def _posts(xscores):
    n = len(xscores)
    return pd.DataFrame({
        "created_at": pd.date_range("2026-10-01", periods=n, freq="D", tz="UTC"),
        "reply_count": [0] * n, "quote_count": [0] * n, "retweet_count": xscores,
        "like_count": [0] * n, "bookmark_count": [0] * n, "view_count": [1000] * n,
        "text": ["x"] * n, "article_title": [None] * n, "is_thread": [False] * n,
        "is_quote": [False] * n, "is_long_form": [False] * n, "media_count": [0] * n})


def test_baseline_uses_only_earlier_posts():
    df = enrich(_posts([10, 10, 10, 10, 10, 40]))
    assert df.rel_perf.iloc[:5].isna().all()       # fewer than 5 earlier posts -> no baseline
    assert df.rel_perf.iloc[5] == 4.0              # 40 vs median of the 5 earlier posts (10)


def test_xscore_weights():
    df = _posts([0])
    df.loc[0, ["reply_count", "quote_count", "retweet_count", "like_count"]] = [1, 1, 1, 100]
    out = enrich(df)
    assert out.xscore.iloc[0] == pytest.approx(5 + 5 + 1 + 70.8)   # param.rs @ 30647a8: like 0.708
    assert out.xscore_per_1k.iloc[0] == pytest.approx(81.8)


def test_missing_article_title_is_not_an_article():
    import numpy as np
    from seeding.content import post_format
    df = enrich(_posts([1]))
    df.loc[0, "article_title"] = np.nan
    assert post_format(next(df.itertuples())) == "short text"


def test_giveaway_hook_wins_over_other_openers():
    assert classify_hook("We built 12 Claude skills (and I'm giving it all away)") == "giveaway / comment-to-get"
    assert classify_hook("1,000+ meetings from 3 prompts.\n\nComment PROMPTS and I'll send them") == "giveaway / comment-to-get"
    assert classify_hook("Distribution beats product.") == "statement"
