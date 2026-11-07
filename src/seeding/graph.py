"""Interaction edges (who replied to / quoted / retweeted whom) from the stored corpus.

Sources, best first:
  reply   -> author of reply_to_tweet_id when we hold that post, else the leading @handle
  quote   -> author of quoted_tweet_id when we hold that post (unresolved quotes are dropped)
  retweet -> 'RT @handle:' prefix
Handles are lower-cased. Self-edges (threads, self-quotes) are dropped.
"""

from __future__ import annotations

import duckdb

EDGES_SQL = r"""
CREATE OR REPLACE TABLE edges AS
WITH t AS (SELECT * FROM tweets),
replies AS (
    SELECT lower(r.username) AS src,
           lower(coalesce(r.in_reply_to_username, p.username,
                          regexp_extract(r.text, '^@([A-Za-z0-9_]{1,15})', 1))) AS dst,
           'reply' AS kind, r.tweet_id, r.created_at
    FROM t r LEFT JOIN t p ON r.reply_to_tweet_id = p.tweet_id
    WHERE r.is_reply
),
quotes AS (
    SELECT lower(q.username), lower(coalesce(q.quoted_username, p.username)), 'quote',
           q.tweet_id, q.created_at
    FROM t q LEFT JOIN t p ON q.quoted_tweet_id = p.tweet_id
    WHERE q.is_quote
),
rts AS (
    SELECT lower(username),
           lower(coalesce(retweeted_username, regexp_extract(text, '^RT @([A-Za-z0-9_]{1,15}):', 1))),
           'retweet', tweet_id, created_at
    FROM t WHERE is_retweet
)
SELECT * FROM (SELECT * FROM replies UNION ALL SELECT * FROM quotes UNION ALL SELECT * FROM rts)
WHERE dst IS NOT NULL AND dst <> '' AND src <> dst
"""


def build_edges(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    con.execute(EDGES_SQL)
    return dict(con.execute("SELECT kind, count(*) FROM edges GROUP BY 1").fetchall())
