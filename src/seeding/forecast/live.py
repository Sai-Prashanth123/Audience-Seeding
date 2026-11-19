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
                         "extra": ledger.extra(trained_at=res["model_trained_at"], format=res["format"],
                                               adj=round(a.get("adj", 0.0), 4))})
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
    # counts only grow: if an hourly snapshot saw more than the stored post row, the stored row is stale
    s = ledger.load("snapshots")
    if len(s) and len(t):
        s = s[s.tweet_id.astype(str).isin(set(t.tweet_id.astype(str)))].copy()
        for a, c in COUNT.items():
            s[c] = pd.to_numeric(s[a], errors="coerce")
        smax = s.assign(tweet_id=s.tweet_id.astype(str)).groupby("tweet_id")[list(COUNT.values())].max()
        t["tweet_id"] = t.tweet_id.astype(str)
        t = t.set_index("tweet_id")
        for c in COUNT.values():
            t[c] = np.fmax(t[c].astype(float), smax[c].reindex(t.index).astype(float))
        t = t.reset_index()
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


ACI_FILE = "aci.json"
ACI_GAMMA = 0.02
MIN_CLIENT_JUDGED = 10


def update_aci(j: pd.DataFrame) -> dict:
    """Adaptive Conformal Inference [Gibbs & Candes 2021] on the live record: each judged post nudges that action's
    target miss rate (alpha) so long-run coverage stays at 80% even if X or a client changes. The served range
    then uses the calibration scores' (1 - alpha) quantile instead of the fixed CQR offset."""
    import json

    from .model import OUT
    if j.empty or not (OUT / "meta.json").exists():
        return {}
    out = {}
    for t, g in j.sort_values("post_created_at").groupby("action"):
        alpha = 0.2
        for inside in g.inside:
            alpha += ACI_GAMMA * (0.2 - (0.0 if inside else 1.0))
            alpha = min(max(alpha, 0.01), 0.6)
        out[t] = {"alpha": round(alpha, 4), "judged": int(len(g)), "inside": float(g.inside.mean())}
    # per client x action, once a client has MIN_CLIENT_JUDGED judged posts: volatile clients get wider ranges
    for (c, t), g in (j.sort_values("post_created_at").groupby(["client", "action"]) if "client" in j.columns else []):
        if len(g) < MIN_CLIENT_JUDGED:
            continue
        alpha = 0.2
        for inside in g.inside:
            alpha = min(max(alpha + ACI_GAMMA * 2 * (0.2 - (0.0 if inside else 1.0)), 0.01), 0.6)
        out[f"{c}|{t}"] = {"alpha": round(alpha, 4), "judged": int(len(g)), "inside": float(g.inside.mean())}
    (OUT / ACI_FILE).write_text(json.dumps(out, indent=1))
    return out


# ------------------------------------------------------------------ centre correction from live results
ADJ_FILE = "live_adjust.json"
ADJ_HALF_LIFE = 15        # posts: newer judged posts count more
ADJ_K = 8.0               # pseudo-posts pulling a client toward all clients (and all clients toward 0)
ADJ_CAP = float(np.log(2.0))
ADJ_CLIP = 2.0            # one freak post can move the correction by at most this much (log)
ADJ_MIN_TEST = 10         # judged posts with a non-zero correction needed before the guard can switch it on
ADJ_DAYS = 60


def frozen_adj(extra) -> float:
    """The correction that was already inside a frozen forecast (0 for forecasts frozen before it existed)."""
    import json
    try:
        return float(json.loads(extra).get("adj", 0.0)) if isinstance(extra, str) and extra else 0.0
    except (ValueError, TypeError, AttributeError):
        return 0.0


def residuals(j: pd.DataFrame) -> pd.DataFrame:
    """Judged forecasts with the raw (uncorrected) model centre and the live residual against it."""
    if j.empty:
        return j.assign(raw=[], resid=[])
    adj = j["extra"].map(frozen_adj) if "extra" in j.columns else 0.0
    return j.assign(adj_frozen=adj, raw=j.q50 - adj, resid=lambda d: d.y - d.raw)


def _wmean(r: np.ndarray, toward: float) -> float:
    r = np.clip(np.asarray(r, float), -ADJ_CLIP, ADJ_CLIP)
    if not len(r):
        return toward
    w = 0.5 ** (np.arange(len(r))[::-1] / ADJ_HALF_LIFE)      # last element = newest
    return float(toward + (w * (r - toward)).sum() / (w.sum() + ADJ_K))


def compute_adj(res: pd.DataFrame) -> dict:
    """{action: {"all": a, client: a}} from residuals ordered oldest -> newest; shrunk and capped."""
    out = {}
    if res.empty:
        return out
    res = res.sort_values("post_created_at")
    for t, g in res.groupby("action"):
        overall = _wmean(g.resid.to_numpy(), 0.0)
        d = {"all": float(np.clip(overall, -ADJ_CAP, ADJ_CAP))}
        for c, gc in g.groupby("client"):
            d[c] = float(np.clip(_wmean(gc.resid.to_numpy(), overall), -ADJ_CAP, ADJ_CAP))
        out[t] = d
    return out


def replay_adj(res: pd.DataFrame, min_age_h: int = 48) -> pd.DataFrame:
    """Prequential test: each judged post gets the correction computed only from posts already judged when it
    was forecast (their post time + 48h <= its prediction time). Returns raw and corrected errors per post."""
    if res.empty:
        return pd.DataFrame()
    r = res.copy()
    r["posted"] = pd.to_datetime(r.post_created_at, utc=True, format="ISO8601")
    r["pred_t"] = pd.to_datetime(r.predicted_at, utc=True, format="ISO8601")
    r["judged_t"] = r.posted + pd.Timedelta(hours=min_age_h)
    rows = []
    for t, g in r.groupby("action"):
        g = g.sort_values("posted")
        for x in g.itertuples():
            past = g[g.judged_t <= x.pred_t]
            a = compute_adj(past).get(t, {}) if len(past) else {}
            adj = a.get(x.client, a.get("all", 0.0))
            rows.append({"action": t, "client": x.client, "tweet_id": x.tweet_id, "adj": adj,
                         "err_raw": abs(x.y - x.raw), "err_adj": abs(x.y - x.raw - adj)})
    return pd.DataFrame(rows)


def update_adjust(j: pd.DataFrame) -> dict:
    """Write live_adjust.json: per action, the correction per client, switched on only where the prequential
    replay shows it made live forecasts closer (typical miss with correction <= without)."""
    import json

    from .model import OUT
    if j.empty or not (OUT / "meta.json").exists():
        return {}
    res = residuals(j)
    cut = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=ADJ_DAYS)
    res = res[pd.to_datetime(res.post_created_at, utc=True, format="ISO8601") >= cut]
    adj = compute_adj(res)
    rp = replay_adj(res)
    out = {"updated_at": pd.Timestamp.now(tz="UTC").isoformat(), "actions": {}}
    for t, a in adj.items():
        g = rp[(rp.action == t) & (rp.adj != 0)] if len(rp) else pd.DataFrame()
        n = len(g)
        miss_raw = float(np.exp(g.err_raw.mean())) if n else None
        miss_adj = float(np.exp(g.err_adj.mean())) if n else None
        on = bool(n >= ADJ_MIN_TEST and miss_adj <= miss_raw)
        why = (f"tested on {n} live posts: typical miss {miss_raw:.2f}x without, {miss_adj:.2f}x with"
               if n else "no live posts to test it on yet")
        if n and n < ADJ_MIN_TEST:
            why += f" (needs {ADJ_MIN_TEST})"
        out["actions"][t] = {"enabled": on, "tested_posts": n, "miss_raw": miss_raw, "miss_adj": miss_adj,
                             "why": why, "judged": int((res.action == t).sum()), "adj": a}
    (OUT / ADJ_FILE).write_text(json.dumps(out, indent=1))
    return out


def adj_for(table: dict, client: str, action: str) -> float:
    """The correction to add (log scale) for this client and action, 0 when it is off."""
    a = (table or {}).get("actions", {}).get(action)
    if not a or not a.get("enabled"):
        return 0.0
    return float(a["adj"].get(client.lower(), a["adj"].get("all", 0.0)))
