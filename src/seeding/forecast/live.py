"""Live test of the forecaster: freeze a forecast for every new client post, judge it once the post is 48h old.

Forecasts go to the git ledger (data/ledger/predictions.csv) BEFORE the post's result exists, one row per X
action, with the 80% range. Judging reads the post's counts from the store once it is at least 48h old.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import evaluate as ev
from . import ledger
from .features import TARGETS

MODEL_TAG = "forecast-v1"
COUNT = {"views": "view_count", "likes": "like_count", "replies": "reply_count", "reposts": "retweet_count",
         "quotes": "quote_count", "bookmarks": "bookmark_count"}


def freeze(con, max_age_h: float = 24) -> int:
    """Forecast every client original post younger than max_age_h that has no frozen forecast yet."""
    from ..engage import load_config
    from . import serve
    cfg = load_config()
    clients = list(dict.fromkeys(list(cfg["pilot_clients"]) + list(cfg["client_segments"])))
    done = set(ledger.load("predictions").query("model == @MODEL_TAG").tweet_id)
    new = con.execute(f"""
        SELECT tweet_id, username, created_at, text, article_title, is_quote, media_count FROM tweets
        WHERE lower(username) IN (SELECT lower(unnest(?::VARCHAR[])))
          AND NOT coalesce(is_reply, false) AND NOT coalesce(is_retweet, false)
          AND created_at >= now() - INTERVAL {int(max_age_h * 60)} MINUTE""", [clients]).df()
    new = new[~new.tweet_id.astype(str).isin(done)]
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for r in new.itertuples():
        when = pd.Timestamp(r.created_at)
        hist = serve.client_history(con, r.username, when)
        fmt = "article" if isinstance(r.article_title, str) else "quote post" if r.is_quote else None
        try:
            res = serve.predict(hist, r.username, r.text or "", when, fmt, (r.media_count or 0) > 0,
                                r.article_title if isinstance(r.article_title, str) else None)
        except ValueError as e:
            print(f"skip {r.username} {r.tweet_id}: {e}")
            continue
        age = round((now - when).total_seconds() / 3600, 3)
        for t, a in res["actions"].items():
            rows.append({"pred_id": ledger.pred_id("prepost", str(r.tweet_id), MODEL_TAG, t), "kind": "prepost",
                         "client": r.username.lower(), "tweet_id": r.tweet_id, "post_created_at": when.isoformat(),
                         "predicted_at": now.isoformat(), "age_at_pred_h": age, "model": MODEL_TAG, "action": t,
                         "expected": round(a["expected"], 3), "lo": round(a["low"], 3), "hi": round(a["high"], 3),
                         "usual": round(a["usual"], 3),
                         "extra": ledger.extra(trained_at=res["model_trained_at"], format=res["format"])})
    return ledger.append("predictions", rows)


def judge(con, min_age_h: int = 48, model: str = MODEL_TAG) -> pd.DataFrame:
    """Every frozen forecast whose post is old enough, with the actual count, log error and inside-range flag."""
    p = ledger.load("predictions")
    p = p[(p.model == model) & (p.kind == "prepost")]
    if p.empty:
        return pd.DataFrame()
    t = con.execute(f"""SELECT tweet_id, view_count, like_count, reply_count, retweet_count, quote_count,
                               bookmark_count FROM tweets
                        WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))
                          AND created_at <= now() - INTERVAL {int(min_age_h)} HOUR""",
                    [p.tweet_id.unique().tolist()]).df()
    from .. import xalgo
    t["xscore"] = sum(t[c].fillna(0) * w for c, w in xalgo.COUNT_WEIGHTS.items())
    for a, c in COUNT.items():
        t[a] = t[c].fillna(0)
    long = t.melt(id_vars="tweet_id", value_vars=TARGETS, var_name="action", value_name="actual")
    j = p.merge(long, on=["tweet_id", "action"])
    for c in ("expected", "lo", "hi", "actual"):
        j[c] = pd.to_numeric(j[c], errors="coerce")
    j["y"], j["q50"] = np.log1p(j.actual), np.log1p(j.expected)
    j["inside"] = (j.actual >= j.lo) & (j.actual <= j.hi)
    return j


def summary(j: pd.DataFrame) -> pd.DataFrame:
    if j.empty:
        return pd.DataFrame()
    rows = []
    for (c, a), g in pd.concat([j.assign(client="ALL"), j]).groupby(["client", "action"]):
        rows.append({"client": c, "action": a, "posts": len(g), "inside_80pct_range": g.inside.mean(),
                     "typical_miss_x": ev.typical_miss(g.y, g.q50)})
    return pd.DataFrame(rows)
