"""Score a draft before it goes out: expected X-weighted score vs the client's usual level.

Uses the model saved by `seeding backtest` (data/model). Context features (baseline, how
many posts the client already published that day, gap since the last post) come from the
client's real posting history in the store, as they would be at the planned time.
"""

from __future__ import annotations

import json
import pickle

import duckdb
import numpy as np
import pandas as pd

from . import xalgo
from .model import MODEL_DIR, NUM, PCA_DIM, _X, build_features

FEATURE_NAMES = {
    "log_base": "account's recent level", "log_base_views": "account's recent views", "log_gap_h": "time since last post",
    "day_position": "posts already out today", "day_decay": "same-day author penalty (X rule)",
    "log_followers": "followers", "cold_start": "under-50k exploration (X rule)", "hour": "posting hour",
    "n_chars": "length", "n_lines": "line breaks", "has_link": "has a link", "has_media": "has media",
    "n_mentions": "@mentions", "n_hashtags": "hashtags", "format": "format", "hook": "opening line",
    "segment": "account segment", "weekday": "weekday"}


def _load():
    import lightgbm as lgb
    booster = lgb.Booster(model_file=str(MODEL_DIR / "lgb.txt"))
    pca = pickle.loads((MODEL_DIR / "pca.pkl").read_bytes())
    meta = json.loads((MODEL_DIR / "meta.json").read_text())
    return booster, pca, meta


def score_draft(con: duckdb.DuckDBPyConnection, client: str, text: str, when: str | None = None,
                fmt: str | None = None, has_media: bool = False, is_quote: bool = False,
                article_title: str | None = None) -> dict:
    from .segments import _model

    booster, pca, meta = _load()
    when_ts = pd.Timestamp(when, tz="UTC") if when else pd.Timestamp.now(tz="UTC")
    hist = con.execute("""
        SELECT t.*, lower(t.username) AS author, false AS is_thread, p.followers_count AS profile_followers,
               s.segment AS author_segment
        FROM tweets t LEFT JOIN profiles p ON p.handle = lower(t.username)
        LEFT JOIN account_segments s ON s.username = lower(t.username)
        WHERE lower(t.username) = lower(?) AND NOT coalesce(t.is_reply, false) AND NOT coalesce(t.is_retweet, false)
          AND t.created_at < ?
        ORDER BY t.created_at DESC LIMIT 60""", [client, when_ts.to_pydatetime()]).df().iloc[::-1]
    if len(hist) < 5:
        raise ValueError(f"@{client} has fewer than 5 earlier posts in the store; no baseline yet")
    draft = hist.iloc[[-1]].copy()
    draft["tweet_id"] = "draft"
    draft["created_at"] = when_ts
    draft["text"] = text
    draft["article_title"] = article_title
    draft["is_quote"] = is_quote or fmt == "quote post"
    draft["is_long_form"] = len(text) > 280
    draft["is_thread"] = fmt == "thread"
    draft["media_count"] = 1 if has_media else 0
    draft["first_url"] = "x" if "http" in text else None
    for c in ["like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count", "view_count"]:
        draft[c] = 0
    f = build_features(pd.concat([hist, draft], ignore_index=True)).iloc[[-1]].copy()
    vec = _model().encode([(article_title or "") + " " + text], normalize_embeddings=True)
    P = pca.transform(vec)
    for i in range(PCA_DIM):
        f[f"txt{i}"] = P[0, i]
    X, _ = _X(f, meta["categories"])
    pred = float(booster.predict(X)[0])
    contrib = booster.predict(X, pred_contrib=True)[0]
    names = list(X.columns)
    by_feat: dict[str, float] = {}
    row = X.iloc[0]
    binary = {"has_media": ("has image/video", "no image/video"), "has_link": ("has a link", "no link"),
              "cold_start": ("under 50k followers (X exploration rule)", "over 50k followers")}
    for n, v in zip(names, contrib[:-1]):
        if n in binary:
            key = binary[n][0] if row[n] == 1 else binary[n][1]
        else:
            key = "text & topic" if n.startswith("txt") else FEATURE_NAMES.get(n, n)
        by_feat[key] = by_feat.get(key, 0.0) + float(v)
    base = float(f.base.iloc[0])
    expected = float(np.expm1(pred))
    top = sorted(((k, v) for k, v in by_feat.items() if k != "account's recent level"),
                 key=lambda kv: -abs(kv[1]))[:5]
    return {
        "client": client, "when_utc": when_ts.isoformat(), "format": f.format.iloc[0], "hook": f.hook.iloc[0],
        "expected_xscore": expected, "usual_xscore": base,
        "vs_usual": expected / base if base > 0 else float("nan"),
        "drivers": [(k, "raises" if v > 0 else "lowers", round(float(np.expm1(abs(v))) * 100)) for k, v in top],
        "x_rules": xalgo.reasons(int(f.day_position.iloc[0]),
                                 float(f.author_followers.fillna(f.profile_followers).iloc[0]),
                                 bool(f.has_link.iloc[0])),
    }


def format_result(r: dict) -> str:
    lines = [f"@{r['client']} · {r['format']} · hook: {r['hook']} · {r['when_utc'][:16]} UTC",
             f"Expected X-weighted score: {r['expected_xscore']:.0f} (usual: {r['usual_xscore']:.0f}) "
             f"→ {r['vs_usual']:.2f}× usual"]
    lines += [f"  · {k} {d} the estimate (~{p}%)" for k, d, p in r["drivers"]]
    lines += [f"  · X rule: {x}" for x in r["x_rules"]]
    return "\n".join(lines)
