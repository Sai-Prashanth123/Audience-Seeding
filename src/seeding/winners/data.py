"""X Winners Engine · data: one labelled row per original post for the three clients and their peers.

Category (Naga's five, first match wins): Article > QRT > Thread > Video > Tweet.
Win: 10k+ views (Alex, Michel, peers); Kenny: 3x his usual level or his own top 20% (`win_rule` says which).
Every post also carries its author's usual level at the time (strict 48h rule) so a "win" can be told from an
account simply being bigger that month.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .. import xalgo
from ..content import classify_hook
from ..forecast.features import lagged_stats

ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "data" / "winners"
MEDIA_CACHE = DIR / "media_types.csv"
CONTENT_AGENT = Path(r"D:\content-agent\content-agent")

CLIENTS = {"itsalexvacca": "alex-vacca", "michlieben": "michel-lieben", "kenny_gtm": "kenny-damian"}
PEERS = ["retentionadam", "coldemailchris", "clientascension", "danielfazio", "logantgott", "cbwritescopy",
         "codyschneiderxx", "nikolak47", "vukconfidential", "vick_mucunski", "itsivanfalco", "mailankhong"]
RELATIVE = {"kenny_gtm"}           # accounts judged on their own scale (too small for the 10k bar)
WIN_VIEWS = 10_000
REL_X = 3.0
REL_TOP = 0.20
MATURE_H = 48
# Mar 2026 on: every account's history is complete from here (~50 posts/month for Alex and Michel). Before it,
# xplatform holds only ~10 high-view posts a month for 2025 and nothing for Nov 2025 - Feb 2026: a sample biased
# toward hits, which made 2025-era formats (threads) look like winners. Usual levels use only in-window posts.
SINCE = "2026-03-01"
CATEGORIES = ["Article", "QRT", "Thread", "Video", "Tweet"]
COUNTS = ["view_count", "like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"]

THREAD_MARK = re.compile(r"🧵|\bthread\b|👇|⬇️|↓\s*$|^\s*1/|\(1/\d+\)", re.I | re.M)


def load_posts(con, accounts: list[str], since: str = SINCE) -> pd.DataFrame:
    """Originals (not replies/reposts), 48h+ old, with self-reply thread flag."""
    return con.execute(f"""
        WITH self_replies AS (SELECT DISTINCT reply_to_tweet_id tid FROM tweets
                              WHERE is_reply AND lower(in_reply_to_username) = lower(username))
        SELECT t.*, lower(t.username) AS author, t.tweet_id IN (SELECT tid FROM self_replies) AS has_self_reply
        FROM tweets t
        WHERE lower(t.username) IN (SELECT unnest(?::VARCHAR[]))
          AND NOT coalesce(t.is_reply, false) AND NOT coalesce(t.is_retweet, false)
          AND t.created_at <= now() - INTERVAL {MATURE_H} HOUR AND t.created_at >= ?::TIMESTAMPTZ
        ORDER BY author, t.created_at""", [[a.lower() for a in accounts], since]).df()


def media_types() -> pd.DataFrame:
    if MEDIA_CACHE.exists():
        return pd.read_csv(MEDIA_CACHE, dtype={"tweet_id": str})
    return pd.DataFrame(columns=["tweet_id", "media_kind"])


def article_bodies() -> dict[str, str]:
    """tweet_id -> article body text, from the content agent's exports (where present)."""
    out = {}
    for slug in CLIENTS.values():
        f = CONTENT_AGENT / "data" / "clients" / slug / "articles" / "bodies.json"
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")):
                out[str(r.get("tweet_id"))] = r.get("full_text_raw") or ""
    return out


def category(r) -> str:
    if isinstance(r.article_title, str) and r.article_title:
        return "Article"
    if r.is_quote:
        return "QRT"
    if r.is_thread:
        return "Thread"
    if r.media_kind == "video":
        return "Video"
    return "Tweet"


def label(df: pd.DataFrame) -> pd.DataFrame:
    """Add usual level, vs_usual, category, win and per-1k rates. Input: load_posts output."""
    df = df.copy()
    df["tweet_id"] = df.tweet_id.astype(str)
    df["ts"] = pd.to_datetime(df.created_at, utc=True)
    for c in COUNTS:
        df[c] = df[c].fillna(0).astype(float)
    df["xscore"] = sum(df[c] * w for c, w in xalgo.COUNT_WEIGHTS.items())
    parts = []
    for _, g in df.sort_values(["author", "ts"]).groupby("author", sort=False):
        ts = g.ts.to_numpy(dtype="datetime64[ns]")
        sv = lagged_stats(ts, g.view_count.to_numpy())
        sx = lagged_stats(ts, g.xscore.to_numpy())
        parts.append(pd.DataFrame({"usual_views": sv[:, 0], "usual_xscore": sx[:, 0], "n_prior": sv[:, 4]},
                                  index=g.index))
    df = df.join(pd.concat(parts))
    df["vs_usual"] = (df.view_count + 1) / (df.usual_views + 1)
    df["log_vs_usual"] = np.log(df.vs_usual)
    m = media_types()
    df = df.merge(m[["tweet_id", "media_kind"]], on="tweet_id", how="left")
    df["media_kind"] = np.where(df.media_kind.notna(), df.media_kind,
                                np.where(df.media_count.fillna(0) > 0, "media (unknown)", "none"))
    text = df.text.fillna("")
    df["is_thread"] = df.has_self_reply.fillna(False) | text.str.contains(THREAD_MARK)
    df["is_quote"] = df.is_quote.fillna(False).astype(bool)
    df["category"] = [category(r) for r in df.itertuples()]
    df["has_video"] = df.media_kind.eq("video")
    # wins
    df["win_rule"] = np.where(df.author.isin(RELATIVE), "relative", "10k")
    abs_win = df.view_count >= WIN_VIEWS
    top = df.groupby("author").view_count.transform(lambda v: v >= v.quantile(1 - REL_TOP))
    rel_win = (df.vs_usual >= REL_X) | top
    df["win"] = np.where(df.author.isin(RELATIVE), rel_win, abs_win).astype(int)
    df["win_10k"] = abs_win.astype(int)
    df["win_rel"] = ((df.vs_usual >= REL_X) & df.usual_views.notna()).astype(int)
    v = df.view_count.where(df.view_count > 0)
    for c, s in [("like_count", "likes"), ("reply_count", "replies"), ("retweet_count", "reposts"),
                 ("quote_count", "quotes"), ("bookmark_count", "bookmarks")]:
        df[f"{s}_per_1k"] = df[c] / v * 1000
    df["era"] = np.where(df.ts >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=90), "last 90 days", "earlier")
    df["is_client"] = df.author.isin(CLIENTS)
    df["hook"] = text.map(classify_hook)
    return df.reset_index(drop=True)


def build(con, since: str = SINCE) -> pd.DataFrame:
    df = label(load_posts(con, list(CLIENTS) + PEERS, since))
    bodies = article_bodies()
    df["article_body"] = df.tweet_id.map(bodies)
    return df
