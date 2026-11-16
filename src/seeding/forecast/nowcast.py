"""L5: re-forecast a live post's final numbers from its early snapshots, and narrow the range as data arrives.

Method:
  * early-to-final growth [Szabo & Huberman 2010, "Predicting the popularity of online content"]: on a log scale
    the final count is the early count plus an offset that depends mostly on the post's age. We learn that
    offset per age bucket from our own snapshot history (data/ledger/snapshots.csv), per client when a client
    has enough history, otherwise from all clients (shrunk with n/(n+k), like everything else here).
  * Bayesian fusion: the pre-post forecast (prior) and the snapshot estimate are combined with weights equal to
    their precisions (1 / variance in log space), so an early snapshot of a 4h-old post dominates a vague prior,
    and a 30-minute snapshot only nudges it.
  * SEISMIC [Zhao et al. 2015] needs every repost's timestamp and its author's follower count; xplatform gives
    neither, so it isn't used. The growth-offset model needs only counts.

"Final" = the latest snapshot at 44h or more. The model switches on once MIN_PAIRS posts have both an early
and a final snapshot; until then `ready()` is False and the app shows "collecting".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import ledger

ACTIONS = ["views", "likes", "replies", "reposts", "quotes", "bookmarks"]
AGE_BUCKETS = [0.25, 0.75, 1.5, 3, 6, 12, 20, 36, 44]     # snapshot age ranges (hours), edges
FINAL_MIN_AGE_H = 44
MIN_PAIRS = 200
K_SHRINK = 15
Z80 = 1.2816


def pairs(snaps: pd.DataFrame) -> pd.DataFrame:
    """One row per (post, early snapshot) with the post's final count: the training data for growth offsets."""
    s = snaps.copy()
    s["age_h"] = pd.to_numeric(s.age_h, errors="coerce")
    for a in ACTIONS:
        s[a] = pd.to_numeric(s[a], errors="coerce")
    final = s[s.age_h >= FINAL_MIN_AGE_H].sort_values("age_h").groupby("tweet_id").tail(1)
    early = s[s.age_h < FINAL_MIN_AGE_H]
    j = early.merge(final[["tweet_id"] + ACTIONS], on="tweet_id", suffixes=("", "_final"))
    j["bucket"] = pd.cut(j.age_h, AGE_BUCKETS, labels=False)
    return j.dropna(subset=["bucket"])


def ready(snaps: pd.DataFrame | None = None) -> tuple[bool, int]:
    p = pairs(ledger.load("snapshots") if snaps is None else snaps)
    n = p.tweet_id.nunique() if len(p) else 0
    return n >= MIN_PAIRS, n


def fit(p: pd.DataFrame) -> dict:
    """Growth offsets per (action, bucket), overall and per client: median and spread of log(final/early)."""
    model = {"overall": {}, "client": {}}
    for a in ACTIONS:
        d = np.log1p(p[f"{a}_final"]) - np.log1p(p[a])
        for b, g in d.groupby(p.bucket):
            model["overall"][(a, int(b))] = (float(g.median()), float(max(g.std(ddof=1) if len(g) > 1 else 1.0, 0.05)),
                                             int(len(g)))
        for (c, b), g in d.groupby([p.client, p.bucket]):
            model["client"][(c, a, int(b))] = (float(g.median()), int(len(g)))
    return model


def estimate(model: dict, client: str, action: str, age_h: float, count: float) -> tuple[float, float] | None:
    """Snapshot-based estimate of log1p(final) and its standard deviation, or None if the age isn't covered."""
    b = pd.cut([age_h], AGE_BUCKETS, labels=False)[0]
    if pd.isna(b) or (action, int(b)) not in model["overall"]:
        return None
    mu_all, sd, _ = model["overall"][(action, int(b))]
    cm = model["client"].get((client.lower(), action, int(b)))
    mu = mu_all if cm is None else mu_all + (cm[0] - mu_all) * cm[1] / (cm[1] + K_SHRINK)
    return float(np.log1p(count) + mu), sd


def fuse(prior_q50: float, prior_q10: float, prior_q90: float, est: tuple[float, float] | None) -> dict:
    """Precision-weighted combination (log space) of the pre-post prior and the snapshot estimate."""
    sd_p = max((prior_q90 - prior_q10) / (2 * Z80), 1e-3)
    if est is None:
        return {"q10": prior_q10, "q50": prior_q50, "q90": prior_q90, "weight_snapshot": 0.0}
    mu_s, sd_s = est
    w_p, w_s = 1 / sd_p ** 2, 1 / sd_s ** 2
    mu = (w_p * prior_q50 + w_s * mu_s) / (w_p + w_s)
    sd = (w_p + w_s) ** -0.5
    return {"q10": mu - Z80 * sd, "q50": mu, "q90": mu + Z80 * sd, "weight_snapshot": w_s / (w_p + w_s)}


def replay(snaps: pd.DataFrame, prior_sd: float = 1.0) -> pd.DataFrame:
    """Leave-one-post-out replay of every early snapshot: error by age bucket (the nowcast accuracy table).

    The prior here is a deliberately weak one (the post's own early count + the overall offset, sd = prior_sd),
    so the table shows what the snapshots alone add."""
    p = pairs(snaps)
    rows = []
    for tid, g in p.groupby("tweet_id"):
        m = fit(p[p.tweet_id != tid])
        for r in g.itertuples():
            for a in ("views", "likes"):
                est = estimate(m, r.client, a, r.age_h, getattr(r, a))
                if est is None:
                    continue
                y = np.log1p(getattr(r, f"{a}_final"))
                rows.append({"tweet_id": tid, "client": r.client, "action": a, "age_h": r.age_h,
                             "bucket": int(r.bucket), "y": y, "q50": est[0],
                             "q10": est[0] - Z80 * est[1], "q90": est[0] + Z80 * est[1]})
    return pd.DataFrame(rows)


def live_table(preds: pd.DataFrame, snaps: pd.DataFrame, max_age_h: float = 50) -> pd.DataFrame:
    """Client posts from the last ~2 days: frozen pre-post views forecast, latest real views, and (once the model
    has enough history) the after-posting re-forecast of final views with its 80% range."""
    if preds.empty or snaps.empty:
        return pd.DataFrame()
    pv = preds[(preds.action == "views") & (preds.kind == "prepost") & (preds.model == "forecast-v1")].copy()
    s = snaps.copy()
    s["age_h"], s["views"] = pd.to_numeric(s.age_h, errors="coerce"), pd.to_numeric(s.views, errors="coerce")
    last = s.sort_values("age_h").groupby("tweet_id").tail(1)
    j = pv.merge(last[["tweet_id", "age_h", "views", "seen_at"]], on="tweet_id")
    now = pd.Timestamp.now(tz="UTC")
    j["age_now_h"] = (now - pd.to_datetime(j.post_created_at, utc=True)).dt.total_seconds() / 3600
    j = j[j.age_now_h <= max_age_h]
    if j.empty:
        return j
    ok, _ = ready(snaps)
    model = fit(pairs(snaps)) if ok else None
    out = []
    for r in j.itertuples():
        exp_, lo, hi = (float(x) for x in (r.expected, r.lo, r.hi))
        row = {"client": r.client, "tweet_id": r.tweet_id, "posted": r.post_created_at[:16].replace("T", " "),
               "age_h": round(r.age_h, 1), "views_now": int(r.views), "forecast": round(exp_),
               "forecast_range": f"{lo:,.0f} – {hi:,.0f}", "nowcast_final": None, "nowcast_range": None}
        if model is not None:
            prior = (np.log1p(exp_), np.log1p(lo), np.log1p(hi))
            f = fuse(prior[0], prior[1], prior[2], estimate(model, r.client, "views", r.age_h, r.views))
            row["nowcast_final"] = round(float(np.expm1(f["q50"])))
            row["nowcast_range"] = f"{np.expm1(f['q10']):,.0f} – {np.expm1(f['q90']):,.0f}"
        out.append(row)
    return pd.DataFrame(out).sort_values("posted", ascending=False)
