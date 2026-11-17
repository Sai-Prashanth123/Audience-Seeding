"""Best posting times per client, from two independent signals.

1. Performance: each original post's views vs the client's own usual level at the time (strict 48h rule, as in
   forecast/features.py), grouped by 3-hour UTC block and by weekday. Median per group, 95% bootstrap range,
   shrunk toward "usual" (1.0x) by n / (n + K) so a block with 4 posts can't win on luck.
2. Audience online: when the people who reply to this client post anything on X (their own activity), so it
   doesn't just mirror the client's own posting schedule.

A window is recommended as:
  proven   15+ posts and its 95% range is above the client's usual level (whole range > 1.0x)
  likely   8+ posts, shrunk performance >= 1.05x AND the audience is busier than average in that block
  avoid    15+ posts and its 95% range below 1.0x
  -        not enough evidence
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import lagged_stats

K = 20.0
MIN_PROVEN = 15      # a time window is never 'proven' or 'avoid' on fewer posts
MIN_LIKELY = 8
N_BOOT = 2000
BLOCK_H = 3
ZONES = {"UTC": 0.0, "IST": 5.5, "ET": -5.0, "CET": 1.0}     # Nov-Mar offsets (no daylight saving)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def client_posts(con, client: str) -> pd.DataFrame:
    p = con.execute("""SELECT created_at, view_count FROM tweets
        WHERE lower(username) = lower(?) AND NOT coalesce(is_reply, false) AND NOT coalesce(is_retweet, false)
          AND created_at < now() - INTERVAL 48 HOUR ORDER BY created_at""", [client]).df()
    p["ts"] = pd.to_datetime(p.created_at, utc=True)
    st = lagged_stats(p.ts.to_numpy(dtype="datetime64[ns]"), p.view_count.fillna(0).to_numpy(float))
    p["rel"] = np.log1p(p.view_count.fillna(0)) - np.log1p(st[:, 0])
    return p.dropna(subset=["rel"])


def audience_hours(con, client: str) -> pd.Series:
    """Share of all posts by this client's repliers made in each UTC hour (0-23)."""
    a = con.execute("""
        WITH eng AS (SELECT DISTINCT lower(r.username) u FROM tweets t JOIN tweets r ON r.reply_to_tweet_id = t.tweet_id
                     WHERE lower(t.username) = lower(?) AND lower(r.username) <> lower(?))
        SELECT hour(created_at AT TIME ZONE 'UTC') h, count(*) n FROM tweets
        WHERE lower(username) IN (SELECT u FROM eng) GROUP BY 1""", [client, client]).df()
    s = a.set_index("h").n.reindex(range(24), fill_value=0)
    return s / s.sum() if s.sum() else s


def _group_stats(rel: np.ndarray, rng) -> tuple[float, float, float]:
    med = float(np.median(rel))
    if len(rel) < 3:
        return med, float("nan"), float("nan")
    boots = np.median(rng.choice(rel, size=(N_BOOT, len(rel))), axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return med, float(lo), float(hi)


def label_hours(start: int, zone: str) -> str:
    off = ZONES[zone]
    a = (start + off) % 24
    b = (start + BLOCK_H + off) % 24
    f = lambda h: f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"
    return f"{f(a)}–{f(b)}"


def compute(con, client: str, seed: int = 0) -> dict:
    """Blocks and weekdays for one client, with verdicts and a plain recommendation."""
    rng = np.random.default_rng(seed)
    p = client_posts(con, client)
    aud = audience_hours(con, client)
    rows = []
    p["block"] = (p.ts.dt.hour // BLOCK_H) * BLOCK_H
    for b in range(0, 24, BLOCK_H):
        r = p.loc[p.block == b, "rel"].to_numpy()
        med, lo, hi = _group_stats(r, rng) if len(r) else (float("nan"),) * 3
        n = len(r)
        shrunk = med * n / (n + K) if n else 0.0
        share = float(aud.iloc[b:b + BLOCK_H].sum()) if len(aud) else float("nan")
        rows.append({"client": client, "kind": "block", "key": b, "posts": n, "x": np.exp(med) if n else np.nan,
                     "lo": np.exp(lo) if n >= 3 else np.nan, "hi": np.exp(hi) if n >= 3 else np.nan,
                     "shrunk_x": float(np.exp(shrunk)), "audience_share": share,
                     **{f"time_{z}": label_hours(b, z) for z in ZONES}})
    p["wd"] = p.ts.dt.dayofweek
    for d in range(7):
        r = p.loc[p.wd == d, "rel"].to_numpy()
        med, lo, hi = _group_stats(r, rng) if len(r) else (float("nan"),) * 3
        n = len(r)
        rows.append({"client": client, "kind": "weekday", "key": d, "posts": n, "x": np.exp(med) if n else np.nan,
                     "lo": np.exp(lo) if n >= 3 else np.nan, "hi": np.exp(hi) if n >= 3 else np.nan,
                     "shrunk_x": float(np.exp(med * n / (n + K))) if n else 1.0, "audience_share": np.nan,
                     "time_UTC": WEEKDAYS[d]})
    t = pd.DataFrame(rows)
    avg_share = BLOCK_H / 24
    t["verdict"] = np.select(
        [(t.posts >= MIN_PROVEN) & (t.lo > 1.0), (t.posts >= MIN_PROVEN) & (t.hi < 1.0),
         (t.posts >= MIN_LIKELY) & (t.shrunk_x >= 1.05) & ((t.kind == "weekday") | (t.audience_share > avg_share))],
        ["proven", "avoid", "likely"], "-")
    return {"client": client, "posts": int(len(p)), "table": t, "recommendation": recommend(t, len(p))}


def recommend(t: pd.DataFrame, n_posts: int) -> dict:
    b = t[t.kind == "block"].copy()
    if n_posts < 40:
        best_aud = b.sort_values("audience_share", ascending=False).head(2)
        return {"strength": "audience only",
                "windows": best_aud.key.tolist(),
                "why": f"only {n_posts} posts with a usual level, too few to judge timing from results; these are the "
                       "hours the client's audience is most active"}
    pick = b[b.verdict.isin(["proven", "likely"])].sort_values(["verdict", "shrunk_x"], ascending=[False, False])
    if pick.empty:
        pick = b[b.posts >= 10].sort_values("shrunk_x", ascending=False).head(1)
        strength = "weak"
    else:
        strength = "proven" if (pick.verdict == "proven").any() else "likely"
    avoid = b[b.verdict == "avoid"].key.tolist()
    return {"strength": strength, "windows": pick.key.head(2).tolist(), "avoid": avoid,
            "why": "results vs the client's usual level, cross-checked with when their audience is online"}


def run(con, clients: list[str]) -> pd.DataFrame:
    tabs, recs = [], []
    for c in clients:
        r = compute(con, c)
        tabs.append(r["table"])
        rec = r["recommendation"]
        recs.append({"client": c, "posts": r["posts"], "strength": rec["strength"],
                     "best_blocks": ",".join(map(str, rec["windows"])),
                     "avoid_blocks": ",".join(map(str, rec.get("avoid", []))), "why": rec["why"]})
    out = pd.concat(tabs, ignore_index=True)
    out.attrs["recs"] = pd.DataFrame(recs)
    return out
