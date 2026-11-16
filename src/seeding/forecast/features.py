"""Features for each X action, using only what was knowable when the post went out.

Strict timing rule (reports/3_protocol.md): an author's usual level for a post is computed from that author's
posts that had **at least 48h to mature** before it. A post's counts keep growing for about two days, so
the previous post's *final* numbers aren't known yet when the next one goes out. 1D used the previous 20
posts regardless, which slightly favours it in a backtest.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .. import xalgo
from ..model import build_features as base_features

ACTIONS = {"views": "view_count", "likes": "like_count", "replies": "reply_count", "reposts": "retweet_count",
           "quotes": "quote_count", "bookmarks": "bookmark_count"}
TARGETS = list(ACTIONS) + ["xscore"]
LAG_H = 48
WINDOW = 20
MIN_PRIOR = 5

CTA = re.compile(r"\b(?:comment|reply|repost|retweet|follow|bookmark|drop (?:a|your)|dm me|link (?:in|below)|"
                 r"tell me|let me know|agree\?)\b", re.I)


def lagged_stats(ts: np.ndarray, values: np.ndarray, lag_h: float = LAG_H, window: int = WINDOW,
                 min_prior: int = MIN_PRIOR) -> np.ndarray:
    """For each post (ts sorted ascending): stats of the `window` latest posts at least `lag_h` older.

    Returns an (n, 5) array: median, mean of the latest 5, 25th pct, 75th pct, number of prior posts.
    Rows without `min_prior` matured posts are NaN (except the count)."""
    lag = np.timedelta64(int(lag_h * 3600), "s")
    out = np.full((len(ts), 5), np.nan)
    ends = np.searchsorted(ts, ts - lag, side="right")
    for i, e in enumerate(ends):
        prior = values[max(0, e - window):e]
        out[i, 4] = e
        if len(prior) >= min_prior:
            out[i, 0] = np.median(prior)
            out[i, 1] = prior[-5:].mean()
            out[i, 2], out[i, 3] = np.percentile(prior, [25, 75])
    return out


OWN_DIMS = ["format", "hook", "length", "has_link", "has_media", "is_quote_post"]
OWN_K = 5.0


def own_effects(ts: np.ndarray, cats: np.ndarray, rel: np.ndarray, lag_h: float = LAG_H, k: float = OWN_K) -> np.ndarray:
    """For each post: how this author's earlier posts *of the same kind* did vs their usual level (mean of log
    ratios), using only posts matured `lag_h` before it, shrunk toward 0 by n / (n + k). NaN rel is skipped."""
    lag = np.timedelta64(int(lag_h * 3600), "s")
    out = np.zeros(len(ts))
    ok = ~np.isnan(rel)
    for c in np.unique(cats):
        idx = np.where((cats == c) & ok)[0]          # same kind, with a known result (time-sorted)
        if not len(idx):
            continue
        csum = np.concatenate([[0.0], np.cumsum(rel[idx])])
        targets = np.where(cats == c)[0]
        n = np.searchsorted(ts[idx], ts[targets] - lag, side="right")
        mean = np.divide(csum[n], n, out=np.zeros(len(n)), where=n > 0)
        out[targets] = mean * n / (n + k)
    return out


def build(df: pd.DataFrame) -> pd.DataFrame:
    """Raw original posts (model.load_training_posts) -> one row per post with targets and features."""
    df = base_features(df)          # ts, format, hook, timing, text shape, day_position (1D's features)
    df = df.sort_values(["author", "ts"]).reset_index(drop=True)
    for c in ACTIONS.values():
        df[c] = df[c].fillna(0).astype(float)
    df["xscore_count"] = sum(df[c] * w for c, w in xalgo.COUNT_WEIGHTS.items())
    cols = {**ACTIONS, "xscore": "xscore_count"}
    for a in TARGETS:
        df[f"y_{a}"] = np.log1p(df[cols[a]])
    parts = []
    for _, g in df.groupby("author", sort=False):
        ts = g.ts.to_numpy(dtype="datetime64[ns]")
        block = {}
        for a in TARGETS:
            s = lagged_stats(ts, g[cols[a]].to_numpy())
            block[f"lb_{a}"] = np.log1p(s[:, 0])
            block[f"trend_{a}"] = np.log1p(s[:, 1]) - np.log1p(s[:, 0])
            block[f"spread_{a}"] = np.log1p(s[:, 3]) - np.log1p(s[:, 2])
            if a == "views":
                block["n_prior"] = s[:, 4]
        parts.append(pd.DataFrame(block, index=g.index))
    df = df.join(pd.concat(parts))
    # v2 · the author's OWN history by kind of post (format, opening line, length, link, media, quote): an account
    # whose quote posts flop gets a lower estimate for its next quote post, even if quotes work for others.
    df["is_quote_post"] = (df.format == "quote post").astype(str)
    df["has_link_c"], df["has_media_c"] = df.has_link.astype(str), df.has_media.astype(str)
    dims = {"format": "format", "hook": "hook", "length": "length", "has_link": "has_link_c",
            "has_media": "has_media_c", "is_quote_post": "is_quote_post"}
    own = []
    for _, g in df.groupby("author", sort=False):
        ts = g.ts.to_numpy(dtype="datetime64[ns]")
        block = {}
        for t in ("views", "xscore"):
            rel = (g[f"y_{t}"] - g[f"lb_{t}"]).to_numpy(dtype=float)
            for d, col in dims.items():
                block[f"own_{d}_{t}"] = own_effects(ts, g[col].astype(str).to_numpy(), rel)
        own.append(pd.DataFrame(block, index=g.index))
    df = df.join(pd.concat(own))
    # v2 · early support: niche hubs and fellow clients who usually reply/quote this author (matured posts only)
    if "hub_replies" in df.columns:
        hp = []
        for _, g in df.groupby("author", sort=False):
            st = lagged_stats(g.ts.to_numpy(dtype="datetime64[ns]"), g.hub_replies.fillna(0).to_numpy(dtype=float))
            hp.append(pd.DataFrame({"hub_support": np.log1p(st[:, 1])}, index=g.index))
        df = df.join(pd.concat(hp))
    # engagement shape of this author: how much of their reach turns into each action
    for a in ("likes", "replies", "reposts", "bookmarks"):
        df[f"rate_{a}"] = df[f"lb_{a}"] - df["lb_views"]
    text = df.text.fillna("")
    df["has_question"] = text.str.contains(r"\?").astype(float)
    df["has_cta"] = text.str.contains(CTA).astype(float)
    df["day_decay"] = df.day_position.map(xalgo.day_decay)      # exact published formula
    df["log_n_prior"] = np.log1p(df.n_prior)
    return df[df.lb_views.notna() & df.lb_xscore.notna()].reset_index(drop=True)


NUM = (["log_gap_h", "day_position", "day_decay", "hour", "n_chars", "n_lines", "has_link", "has_media",
        "n_mentions", "n_hashtags", "has_question", "has_cta", "log_n_prior"]
       + [f"{k}_{a}" for a in TARGETS for k in ("lb", "trend", "spread")]
       + [f"rate_{a}" for a in ("likes", "replies", "reposts", "bookmarks")])
CAT = ["format", "hook", "segment", "weekday"]
OWN = [f"own_{d}_{t}" for t in ("views", "xscore") for d in OWN_DIMS]
NUM_V2 = NUM + OWN + ["hub_support"]


def add_hub_replies(con, df: pd.DataFrame) -> pd.DataFrame:
    """Per post: distinct niche hubs (core accounts) and clients who replied to or quoted it (as captured)."""
    from ..engage import load_config
    cfg = load_config()
    clients = [c.lower() for c in list(cfg["pilot_clients"]) + list(cfg["client_segments"])]
    hubs = con.execute("""
        SELECT t.tweet_id, count(DISTINCT lower(r.username)) AS hub_replies
        FROM tweets t JOIN tweets r ON (r.reply_to_tweet_id = t.tweet_id OR r.quoted_tweet_id = t.tweet_id)
        WHERE t.tweet_id IN (SELECT unnest(?::VARCHAR[])) AND lower(r.username) <> lower(t.username)
          AND (lower(r.username) IN (SELECT lower(username) FROM core_accounts)
               OR lower(r.username) IN (SELECT unnest(?::VARCHAR[])))
        GROUP BY 1""", [df.tweet_id.astype(str).tolist(), clients]).df()
    return df.drop(columns=["hub_replies"], errors="ignore").merge(hubs, on="tweet_id", how="left")
