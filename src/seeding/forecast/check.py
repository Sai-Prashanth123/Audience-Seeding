"""Daily live check: how every client post of the last 7 days is doing against the forecast frozen for it.

For each post with a frozen forecast (data/ledger/predictions.csv, model forecast-v1):
  * actual now: latest snapshot (hourly job) or the daily refresh of the post's counts, whichever is newer
  * posts younger than 48h: projected 48h views = views now grown by the usual growth from that age
    (learned from our own snapshot history once enough posts have an early and a final snapshot, otherwise
    a rough default curve, flagged as such)
  * verdict: ahead / on track / behind (projection vs the 80% range), or above / in range / below once 48h old
Plus a per-client line over the last 7 and 30 days of judged posts: inside range, typical miss, and whether the
forecasts ran high or low (the live correction in live.py then adjusts new forecasts).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import evaluate as ev
from . import ledger
from .live import COUNT, MODEL_TAG

FINAL_H = 48
TOO_EARLY_H = 2
DAYS = 7
# rough share of the 48h views a post has at a given age (used until our own snapshot history is big enough)
DEFAULT_SHARE = {0.5: 0.15, 1: 0.25, 3: 0.45, 6: 0.6, 12: 0.75, 24: 0.9, 36: 0.96, 48: 1.0}
MIN_CURVE_POSTS = 15


def default_share(age_h: float) -> float:
    a = np.array(list(DEFAULT_SHARE)); s = np.array(list(DEFAULT_SHARE.values()))
    return float(np.interp(np.log(max(age_h, 0.5)), np.log(a), s))


def growth_curve(snaps: pd.DataFrame) -> dict:
    """Median log1p(final) - log1p(at age) per age bucket, from posts with an early and a final snapshot.
    Only buckets with MIN_CURVE_POSTS posts are kept; the rest fall back to the default curve."""
    from .nowcast import AGE_BUCKETS, pairs
    if snaps.empty:
        return {}
    p = pairs(snaps)
    if p.empty:
        return {}
    p = p.assign(off=np.log1p(p.views_final) - np.log1p(p.views))
    out = {}
    for b, g in p.groupby("bucket"):
        per_post = g.groupby("tweet_id").off.median()
        if len(per_post) >= MIN_CURVE_POSTS:
            out[int(b)] = float(per_post.median())
    return {"edges": AGE_BUCKETS, "off": out}


def project(views_now: float, age_h: float, curve: dict) -> tuple[float, str]:
    """Projected 48h views and where the growth came from ('our posts' or 'rough default')."""
    if curve and curve.get("off"):
        b = pd.cut([age_h], curve["edges"], labels=False)[0]
        if not pd.isna(b) and int(b) in curve["off"]:
            return float(np.expm1(np.log1p(views_now) + curve["off"][int(b)])), "our posts"
    return float(views_now / default_share(age_h)), "rough default"


def verdict(age_h: float, value: float, lo: float, hi: float) -> str:
    if age_h >= FINAL_H:
        return "above range" if value > hi else "below range" if value < lo else "in range"
    if age_h < TOO_EARLY_H:
        return "too early"
    return "ahead" if value > hi else "behind" if value < lo else "on track"


def latest_counts(con, preds: pd.DataFrame, snaps: pd.DataFrame) -> pd.DataFrame:
    """Per post: views/x score now and the age of that reading."""
    from .. import xalgo
    ids = preds.tweet_id.astype(str).unique().tolist()
    t = con.execute("""SELECT tweet_id, created_at, view_count, like_count, reply_count, retweet_count, quote_count,
                              bookmark_count FROM tweets WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))""", [ids]).df()
    t["tweet_id"] = t.tweet_id.astype(str)
    now = pd.Timestamp.now(tz="UTC")
    t["age_now_h"] = (now - pd.to_datetime(t.created_at, utc=True)).dt.total_seconds() / 3600
    t["xscore_t"] = sum(t[c].fillna(0) * w for c, w in xalgo.COUNT_WEIGHTS.items())
    t["views_t"] = t.view_count.fillna(0)
    out = t[["tweet_id", "age_now_h", "views_t", "xscore_t"]].copy()
    if len(snaps):
        s = snaps.copy()
        s["tweet_id"] = s.tweet_id.astype(str)
        for c in ["age_h", *COUNT]:
            s[c] = pd.to_numeric(s[c], errors="coerce")
        s["xscore_s"] = sum(s[a].fillna(0) * xalgo.COUNT_WEIGHTS[c] for a, c in COUNT.items()
                            if c in xalgo.COUNT_WEIGHTS)
        last = s.sort_values("age_h").groupby("tweet_id").tail(1)
        out = out.merge(last[["tweet_id", "age_h", "views", "xscore_s"]].rename(
            columns={"age_h": "snap_age_h", "views": "views_s"}), on="tweet_id", how="left")
    else:
        out[["snap_age_h", "views_s", "xscore_s"]] = np.nan
    # the daily refresh has no reading time, so for young posts prefer the snapshot (known age); once a post is
    # 48h+ old take the larger count (counts only grow)
    young_snap = (out.age_now_h < FINAL_H) & out.views_s.notna()
    out["views_now"] = np.where(young_snap, out.views_s, np.fmax(out.views_t, out.views_s.fillna(0)))
    out["xscore_now"] = np.where(young_snap, out.xscore_s, np.fmax(out.xscore_t, out.xscore_s.fillna(0)))
    out["reading_age_h"] = np.where(young_snap, out.snap_age_h, out.age_now_h)
    out["source"] = np.where(young_snap, "hourly snapshot", "daily refresh")
    return out


def run(con, days: int = DAYS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(posts, clients): one row per recent post with its verdicts, and per-client accuracy lines."""
    from .live import judge, residuals
    preds = ledger.load("predictions")
    preds = preds[(preds.model == MODEL_TAG) & (preds.kind == "prepost")].copy()
    if preds.empty:
        return pd.DataFrame(), pd.DataFrame()
    preds["tweet_id"] = preds.tweet_id.astype(str)
    for c in ("expected", "lo", "hi", "usual"):
        preds[c] = pd.to_numeric(preds[c], errors="coerce")
    posted = pd.to_datetime(preds.post_created_at, utc=True, format="ISO8601")
    recent = preds[posted >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)]
    snaps = ledger.load("snapshots")
    curve = growth_curve(snaps)
    rows = []
    if len(recent):
        now = latest_counts(con, recent, snaps)
        texts = con.execute("SELECT tweet_id, text FROM tweets WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))",
                            [recent.tweet_id.unique().tolist()]).df().assign(tweet_id=lambda d: d.tweet_id.astype(str))
        wide = recent.pivot_table(index=["tweet_id", "client", "post_created_at"], columns="action",
                                  values=["expected", "lo", "hi"], aggfunc="first")
        wide.columns = [f"{v}_{a}" for v, a in wide.columns]
        wide = wide.reset_index().merge(now, on="tweet_id").merge(texts, on="tweet_id", how="left")
        for r in wide.itertuples():
            final = r.age_now_h >= FINAL_H
            proj, how = (r.views_now, "final") if final else project(r.views_now, max(r.reading_age_h, 0.1), curve)
            row = {"client": r.client, "tweet_id": r.tweet_id, "posted": r.post_created_at[:16].replace("T", " "),
                   "first_line": str(r.text or "").strip().split("\n")[0][:90],
                   "age_h": round(float(r.age_now_h), 1), "reading_age_h": round(float(r.reading_age_h), 1),
                   "source": r.source,
                   "views_forecast": r.expected_views, "views_lo": r.lo_views, "views_hi": r.hi_views,
                   "views_now": float(r.views_now), "views_48h": float(proj), "projection": how,
                   "views_verdict": verdict(r.age_now_h if final else r.reading_age_h, proj, r.lo_views, r.hi_views)}
            if hasattr(r, "expected_xscore"):
                row.update({"xscore_forecast": r.expected_xscore, "xscore_lo": r.lo_xscore,
                            "xscore_hi": r.hi_xscore, "xscore_now": float(r.xscore_now),
                            "xscore_verdict": verdict(r.age_now_h, r.xscore_now, r.lo_xscore, r.hi_xscore)
                            if final else "wait for 48h"})
            rows.append(row)
    posts = pd.DataFrame(rows)
    if len(posts):
        posts = posts.sort_values("posted", ascending=False)
        posts["checked_at"] = pd.Timestamp.now(tz="UTC")

    # per-client accuracy over judged posts
    j = judge(con)
    clients = []
    if len(j):
        res = residuals(j)
        res["posted_ts"] = pd.to_datetime(res.post_created_at, utc=True, format="ISO8601")
        for win in (7, 30):
            w = res[res.posted_ts >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=win + 2)]
            for (c, a), g in pd.concat([w.assign(client="ALL"), w]).groupby(["client", "action"]):
                if a not in ("views", "xscore"):
                    continue
                clients.append({"client": c, "action": a, "window_days": win, "posts": len(g),
                                "inside": float(g.inside.mean()), "typical_miss_x": ev.typical_miss(g.y, g.q50),
                                # >1: the model's raw forecast ran too high by this factor; <1: too low
                                "ran_high_x": float(np.exp(-np.median(g.resid)))})
    return posts, pd.DataFrame(clients)


def adjust_table(adjust: dict) -> pd.DataFrame:
    """live_adjust.json flattened (one row per action x client) for the dashboard."""
    rows = []
    for t, a in (adjust or {}).get("actions", {}).items():
        for c, v in a["adj"].items():
            rows.append({"action": t, "client": c, "factor": float(np.exp(v)), "enabled": a["enabled"],
                         "tested_posts": a["tested_posts"], "miss_raw": a["miss_raw"], "miss_adj": a["miss_adj"],
                         "why": a["why"], "updated_at": adjust.get("updated_at")})
    return pd.DataFrame(rows)
