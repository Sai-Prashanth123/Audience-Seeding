import duckdb

from seeding.graph import build_edges
from seeding.store import TWEET_COLS


def _con(rows):
    con = duckdb.connect()
    con.execute(f"CREATE TABLE tweets ({TWEET_COLS})")
    cols = ["tweet_id", "username", "text", "is_reply", "is_quote", "is_retweet",
            "reply_to_tweet_id", "quoted_tweet_id", "created_at"]
    for r in rows:
        vals = [r.get(c) for c in cols]
        vals[-1] = vals[-1] or "2026-11-01T00:00:00Z"
        con.execute(f"INSERT INTO tweets ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
    return con


def test_edges_from_all_three_sources():
    con = _con([
        {"tweet_id": "1", "username": "Alice", "text": "a post", "is_reply": False},
        # reply resolved through the stored parent, even though the text @ differs
        {"tweet_id": "2", "username": "Bob", "text": "@someoneelse hi", "is_reply": True, "reply_to_tweet_id": "1"},
        # reply to a post we don't hold falls back to the leading @handle
        {"tweet_id": "3", "username": "Bob", "text": "@Carol nice", "is_reply": True, "reply_to_tweet_id": "999"},
        {"tweet_id": "4", "username": "Dan", "text": "this", "is_quote": True, "quoted_tweet_id": "1"},
        {"tweet_id": "5", "username": "Dan", "text": "unknown quote", "is_quote": True, "quoted_tweet_id": "998"},
        {"tweet_id": "6", "username": "Eve", "text": "RT @Alice: a post", "is_retweet": True},
        {"tweet_id": "7", "username": "Alice", "text": "@Alice thread", "is_reply": True},  # self
    ])
    counts = build_edges(con)
    assert counts == {"reply": 2, "quote": 1, "retweet": 1}
    got = set(con.execute("SELECT src, dst, kind FROM edges").fetchall())
    assert got == {("bob", "alice", "reply"), ("bob", "carol", "reply"),
                   ("dan", "alice", "quote"), ("eve", "alice", "retweet")}
