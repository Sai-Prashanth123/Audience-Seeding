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
