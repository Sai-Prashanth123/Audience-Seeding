import numpy as np
import pandas as pd

from seeding.winners import analyze, anatomy, data


def _posts(n=40, author="itsalexvacca", views=None, start="2026-01-01", **kw):
    ts = pd.date_range(start, periods=n, freq="1D", tz="UTC")
    v = views if views is not None else np.full(n, 5000.0)
    d = pd.DataFrame({"tweet_id": [f"{author}{i}" for i in range(n)], "username": author, "author": author,
                      "created_at": ts, "text": "hello world", "article_title": None, "is_quote": False,
                      "is_reply": False, "is_retweet": False, "has_self_reply": False, "media_count": 0,
                      "view_count": v, "like_count": 10, "reply_count": 1, "retweet_count": 1,
                      "quote_count": 0, "bookmark_count": 2})
    for k, val in kw.items():
        d[k] = val
    return d


def test_category_priority():
    d = _posts(4)
    d.loc[0, "article_title"] = "A title"
    d.loc[0, "is_quote"] = True                       # article that is also a quote -> Article
    d.loc[1, "is_quote"] = True
    d.loc[2, "text"] = "Here is how 🧵"
    out = data.label(d)
    assert list(out.category[:4]) == ["Article", "QRT", "Thread", "Tweet"]


def test_win_rules_absolute_and_relative():
    v = np.full(40, 1000.0)
    v[-1] = 12000
    a = data.label(_posts(40, "itsalexvacca", v))
    assert a.win.iloc[-1] == 1 and a.win.iloc[:-1].sum() == 0
    k = data.label(_posts(40, "kenny_gtm", np.r_[np.full(39, 500.0), 1800.0]))
    assert (k.win_rule == "relative").all()
    assert k.win.iloc[-1] == 1                       # 3.6x his usual -> a win for Kenny without 10k views


def test_usual_level_uses_only_matured_earlier_posts():
    v = np.r_[np.full(10, 100.0), np.full(10, 10000.0)]
    out = data.label(_posts(20, views=v)).sort_values("ts")
    # the first 10k post's usual level comes only from the earlier 100-view posts
    assert out.usual_views.iloc[10] == 100


def test_anatomy_tags():
    d = data.label(_posts(3))
    d.loc[0, "text"] = "I booked $40k in pipeline with Claude Code\n\n1. one\n2. two\n3. three\n\nBookmark this."
    d.loc[1, "text"] = "Comment GTM and I'll send you the playbook"
    t = anatomy.tag(d)
    assert t.loc[0, "has_dollar"] == 1 and t.loc[0, "mentions_claude"] == 1 and t.loc[0, "is_list"] == 1
    assert t.loc[0, "cta"] == "bookmark/save" and t.loc[1, "cta"] == "comment-to-get"


def test_lift_bootstrap_detects_real_effect():
    rng = np.random.default_rng(1)
    n = 400
    f = rng.integers(0, 2, n)
    win = (rng.random(n) < np.where(f == 1, 0.5, 0.15)).astype(int)
    d = pd.DataFrame({"author": "a", "win": win, "log_vs_usual": win * 1.0, "category": "Tweet", "cta": "none",
                      **{b: 0 for b in anatomy.BINARY}})
    d["has_dollar"] = f
    r = analyze.lifts(d)
    row = r[r.feature == "has_dollar"].iloc[0]
    assert row.proven and row.lift_lo > 1.5


def test_twins_pairs_similar_posts_only():
    d = data.label(_posts(4, views=np.array([1000.0, 1000, 1000, 1000])))
    d = anatomy.tag(d)
    d["is_client"] = True
    d["log_vs_usual"] = [0.0, 1.5, 0.0, 0.0]
    vec = np.array([[1, 0], [1, 0.01], [0, 1], [0.0, 1.0]])
    vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)
    t = analyze.twins(d, vec)
    assert len(t) == 1 and t.iloc[0].winner == d.tweet_id[1] and t.iloc[0].ratio > 4


def test_rule_score_signs():
    d = pd.DataFrame({"category": ["Thread", "Tweet"], "has_dollar": [1, 0], "n_words": [100, 100]})
    rules = pd.DataFrame({"feature": ["cat_Thread", "has_dollar"], "effect_x": [2.0, 1.5], "mu": [0, 0], "sd": [1, 1]})
    s = analyze.rule_score(d, rules)
    assert s[0] > s[1] == 0


def _rules(*a, **k):
    from seeding.winners import score
    return {c.rule.split(" (")[0]: c.ok for c in score.checks(*a, **k)}


def test_checker_giveaway_video_qrt_passes():
    r = _rules("I'm giving away the Claude Code skills behind $300K/mo in ads. Comment ADS to get them.",
               "michel", "qrt", video=True)
    assert r["Quote post has a video or image attached"] and r["Gives something away / asks people to comment for it"]


def test_checker_you_question_opener_fails():
    r = _rules("Are you still sending cold emails by hand?\n\nHere's the fix.", "alex", "tweet")
    assert r['First line does not start with "you"'] is False and r["First line is not a question"] is False


def test_checker_article_title_and_daily_limit():
    r = _rules("body", "kenny", "article", title="How to Become a GTM Engineer", post_no=3)
    assert r["Article title has a number"] is False
    assert not [v for k, v in r.items() if k.startswith("Post #3")][0]


def test_viral_shapes_detected():
    from seeding.winners.score import viral_shapes
    assert "meme" in viral_shapes("this should not be free https://t.co/x", "qrt", video=True)
    assert "meme" not in viral_shapes("this should not be free", "qrt", video=False)
    assert "thennow" in viral_shapes("GTM back in the day (2023):\n• spray\n\nGTM today:\n• signals", "thread")
    assert "teardown" in viral_shapes("Breakdown of Ramp's $60B Outbound GTM Strategy", "article")
    assert "belief" in viral_shapes('"you need vc money to build a real company"\n\nwe are bootstrapped', "qrt")


def test_meme_caption_not_penalised_for_missing_giveaway_or_money():
    from seeding.winners.score import checks
    cs = checks("founders who hired a gtm engineer and got a list-builder reading this", "alex", "qrt", video=True)
    assert all(c.ok is not False for c in cs)


def test_quoted_belief_may_contain_you():
    from seeding.winners.score import checks
    cs = checks('"you need vc money to build a real company"\n\n> $7M ARR, bootstrapped', "michel", "qrt", video=True)
    assert not any(c.ok is False and "you" in c.rule for c in cs)
