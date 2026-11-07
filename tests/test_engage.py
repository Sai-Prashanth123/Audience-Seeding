import pandas as pd

from seeding.engage import openness, rank_candidates

NOW = pd.Timestamp("2026-11-07 12:00", tz="UTC")


def _pool():
    return pd.DataFrame({"username": ["a", "b", "c"], "seg": ["b2b"] * 3, "seed_score": [10.0, 5.0, 5.0],
                         "n_core": [9, 4, 4], "rank": [1, 2, 3]})


def _post(tid, user, hours_ago, text="hello", reply=False, rt=False):
    return {"tweet_id": tid, "url": f"u{tid}", "username": user, "text": text, "is_reply": reply,
            "is_retweet": rt, "created_at": NOW - pd.Timedelta(hours=hours_ago), "like_count": 0}


def test_fresh_beats_stale_for_same_quality():
    posts = pd.DataFrame([_post("1", "b", 20), _post("2", "c", 1)])
    r = rank_candidates(posts, _pool(), set(), NOW)
    assert r.tweet_id.tolist() == ["2", "1"]


def test_one_post_per_account_and_who_matters():
    posts = pd.DataFrame([_post("1", "A", 2), _post("2", "a", 3), _post("3", "b", 2)])
    r = rank_candidates(posts, _pool(), set(), NOW)
    assert r.author.tolist() == ["a", "b"]          # 'a' once (best post), seed 'a' outranks 'b'
    assert r.tweet_id.iloc[0] == "1"


def test_filters_replies_retweets_replied_old_and_outsiders():
    posts = pd.DataFrame([
        _post("1", "a", 2, reply=True), _post("2", "a", 2, rt=True), _post("3", "b", 2),
        _post("4", "c", 30), _post("5", "zz", 1), _post("6", "c", 2)])
    r = rank_candidates(posts, _pool(), {"3"}, NOW)
    assert r.tweet_id.tolist() == ["6"]


def test_openness():
    import pytest
    assert openness("What do you think?") == pytest.approx(0.8)          # question
    assert openness("Unpopular opinion: cold email works") == pytest.approx(0.6)  # take
    assert openness("") == pytest.approx(0.4)


def test_off_topic_post_sinks():
    posts = pd.DataFrame([_post("1", "a", 1, "Fun night in LA"), _post("2", "b", 1, "cold email reply rates")])
    posts["relevance"] = [0.02, 0.50]
    r = rank_candidates(posts, _pool(), set(), NOW)
    assert r.tweet_id.tolist() == ["2", "1"]     # 'a' is the stronger seed, but its post is off-topic


def test_each_post_goes_to_one_client_only():
    from seeding.engage import allocate
    c = pd.DataFrame({"client": ["x", "y", "y", "x"], "tweet_id": ["1", "1", "2", "3"], "score": [0.9, 0.8, 0.7, 0.1]})
    out = allocate(c, list_size=5)
    assert sorted(out.tweet_id) == ["1", "2", "3"]
    assert out.loc[out.tweet_id == "1", "client"].tolist() == ["x"]     # highest score wins the shared post
    assert out.groupby("client").list_rank.apply(list).to_dict() == {"x": [1, 2], "y": [1]}


def test_ai_filter_drops_rejected_keeps_unjudged_and_caps():
    import duckdb
    from datetime import date
    from seeding.engage import apply_ai_filter
    con = duckdb.connect()
    d = date(2026, 11, 8)
    con.execute("""CREATE TABLE engage_list (list_date DATE, client VARCHAR, list_rank INTEGER, tweet_id VARCHAR,
                   url VARCHAR, author VARCHAR, seg VARCHAR, text VARCHAR, created_at TIMESTAMPTZ, score DOUBLE,
                   reason VARCHAR, built_at TIMESTAMPTZ)""")
    for i in range(1, 6):
        con.execute("INSERT INTO engage_list VALUES (?, 'alex', ?, ?, '', '', 'b2b', '', now(), 1.0, '', now())",
                    [d, i, f"t{i}"])
    con.execute("CREATE TABLE engage_ai (tweet_id VARCHAR, status VARCHAR, worth BOOLEAN, reason VARCHAR, reviewed_at VARCHAR)")
    con.execute("INSERT INTO engage_ai VALUES ('t1','ok',false,'',''), ('t2','ok',true,'',''), ('t3','skipped',null,'','')")
    con.execute("CREATE TABLE tweets (reply_to_tweet_id VARCHAR, username VARCHAR)")
    r = apply_ai_filter(con, list_size=3, list_date=d)
    kept = con.execute("SELECT tweet_id, list_rank FROM engage_list ORDER BY list_rank").fetchall()
    assert r == {"candidates": 5, "ai_said_skip": 1, "kept": 3}
    assert kept == [("t2", 1), ("t3", 2), ("t4", 3)]     # t1 rejected; unjudged t3 kept; capped at 3, re-ranked
