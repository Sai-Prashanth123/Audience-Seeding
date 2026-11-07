"""Step 1D: predict a post's X-weighted score from what is known when it is posted.

Target: log1p(X-weighted score) of original posts at least 48h old.
Features: the author's trailing baseline (median of previous 20 posts), X's published rules
(same-day author decay, cold-start eligibility), format, hook, length, timing, gap since the
previous post, followers, segment, and a 16-d PCA of the text embedding.

Evaluation is a time split. The headline metric is *within-author* Spearman: how well the
model ranks one account's posts against each other, which is the decision a team makes
("which draft goes out"). Two baselines must be beaten:
  A  the account's usual level (rolling median of its previous 20 posts)
  B  A adjusted by X's published same-day decay                        -> rules only
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import xalgo
from .content import X_WEIGHTS, classify_hook, length_bucket
from .seedmap import ROOT, load_config

MODEL_DIR = ROOT / "data" / "model"
SPLIT = "2026-10-15"
CAT = ["format", "hook", "segment", "weekday"]
PCA_DIM = 16


# ------------------------------------------------------------------ data
def load_training_posts(con: duckdb.DuckDBPyConnection, days: int = 365, min_posts: int = 15,
                        min_age_h: int = 48) -> pd.DataFrame:
    df = con.execute(f"""
        WITH self_replies AS (SELECT DISTINCT reply_to_tweet_id tid FROM tweets
                              WHERE is_reply AND lower(in_reply_to_username) = lower(username)),
        o AS (SELECT t.*, lower(t.username) AS author, t.tweet_id IN (SELECT tid FROM self_replies) AS is_thread
              FROM tweets t
              WHERE NOT coalesce(t.is_reply, false) AND NOT coalesce(t.is_retweet, false)
                AND t.created_at >= now() - INTERVAL {days} DAY
                AND t.created_at <= now() - INTERVAL {min_age_h} HOUR)
        SELECT o.*, p.followers_count AS profile_followers, s.segment AS author_segment
        FROM o
        LEFT JOIN profiles p ON p.handle = o.author
        LEFT JOIN account_segments s ON s.username = o.author
        WHERE o.author IN (SELECT author FROM o GROUP BY 1 HAVING count(*) >= {min_posts})
        ORDER BY o.author, o.created_at""").df()
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in X_WEIGHTS:
        df[c] = df[c].fillna(0)
    df["xscore"] = sum(df[c] * w for c, w in X_WEIGHTS.items())
    df["y"] = np.log1p(df.xscore)
    ts = pd.to_datetime(df.created_at, utc=True)
    df["ts"] = ts
    g = df.groupby("author", sort=False)
    df["base"] = g.xscore.transform(lambda s: s.shift(1).rolling(20, min_periods=5).median())
    df["base_views"] = g.view_count.transform(lambda s: s.shift(1).rolling(20, min_periods=5).median())
    df["log_base"] = np.log1p(df.base)
    df["log_base_views"] = np.log1p(df.base_views)
    df["gap_h"] = g.ts.transform(lambda s: s.diff().dt.total_seconds() / 3600)
    df["log_gap_h"] = np.log1p(df.gap_h.clip(lower=0))
    df["day_position"] = df.groupby(["author", ts.dt.date]).cumcount() + 1
    df["day_decay"] = df.day_position.map(xalgo.day_decay)
    followers = df.author_followers.fillna(df.profile_followers)
    df["log_followers"] = np.log10(followers.clip(lower=1))
    df["cold_start"] = followers.lt(xalgo.COLD_START_MAX_FOLLOWERS).astype(float).where(followers.notna())
    df["hour"] = ts.dt.hour
    df["weekday"] = ts.dt.day_name().str[:3]
    text = df.text.fillna("")
    df["n_chars"] = np.log1p(text.str.len())
    df["n_lines"] = text.str.count("\n")
    df["has_link"] = df.first_url.notna().astype(float)
    df["has_media"] = (df.media_count.fillna(0) > 0).astype(float)
    df["n_mentions"] = text.str.count(r"@\w+")
    df["n_hashtags"] = text.str.count(r"#\w+")
    df["format"] = np.select(
        [df.article_title.notna(), df.is_thread.fillna(False), df.is_quote.fillna(False),
         df.is_long_form.fillna(False), df.has_media > 0],
        ["article", "thread", "quote post", "long-form post", "short + media"], "short text")
    df["hook"] = [classify_hook(t if isinstance(t, str) else "") for t in df.text]
    df["length"] = text.str.len().map(length_bucket)
    df["segment"] = df.author_segment.fillna("unknown")
    return df


def add_text_pca(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, fit_mask: pd.Series | None = None,
                 pca=None):
    """Embed post text (cached in post_vecs) and project to PCA_DIM components."""
    from sklearn.decomposition import PCA
    from .segments import _model

    have = set(con.execute("SELECT tweet_id FROM post_vecs").df().tweet_id) if _has(con, "post_vecs") else set()
    todo = df[~df.tweet_id.isin(have)]
    if len(todo):
        txt = (todo.article_title.fillna("") + " " + todo.text.fillna("")).str.replace(r"https?://\S+", "", regex=True)
        vecs = _model().encode(txt.str.slice(0, 1000).tolist(), batch_size=256, normalize_embeddings=True,
                               show_progress_bar=False)
        add = pd.DataFrame({"tweet_id": todo.tweet_id, "username": todo.author, "vec": list(vecs.astype(np.float32))})
        if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='post_vecs'").fetchall():
            con.execute("CREATE TABLE post_vecs (tweet_id VARCHAR PRIMARY KEY, username VARCHAR, vec FLOAT[384])")
        con.execute("INSERT OR IGNORE INTO post_vecs SELECT * FROM add")
    vec = con.execute("SELECT tweet_id, vec FROM post_vecs WHERE tweet_id IN (SELECT tweet_id FROM df)").df()
    V = np.vstack(df.tweet_id.map(dict(zip(vec.tweet_id, vec.vec))).to_numpy())
    if pca is None:
        pca = PCA(PCA_DIM, random_state=0).fit(V[fit_mask.to_numpy()] if fit_mask is not None else V)
    P = pca.transform(V)
    for i in range(PCA_DIM):
        df[f"txt{i}"] = P[:, i]
    return df, pca


def _has(con, table: str) -> bool:
    return bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [table]).fetchall())


# log_followers / cold_start were dropped 2026-11-07: they use TODAY's follower count (look-ahead).
# Ablation: within-author Spearman 0.195 -> 0.184, MAE 0.806 -> 0.801, top-20% 26.8% -> 27.4% (neutral).
NUM = (["log_base", "log_base_views", "log_gap_h", "day_position", "day_decay",
        "hour", "n_chars", "n_lines", "has_link", "has_media", "n_mentions", "n_hashtags"]
       + [f"txt{i}" for i in range(PCA_DIM)])


def _X(df: pd.DataFrame, categories: dict | None = None) -> tuple[pd.DataFrame, dict]:
    X = df[NUM + CAT].copy()
    categories = categories or {c: sorted(X[c].astype(str).unique()) for c in CAT}
    for c in CAT:
        X[c] = pd.Categorical(X[c].astype(str), categories=categories[c])
    return X, categories


# ------------------------------------------------------------------ metrics
def _within_author(test: pd.DataFrame, pred_col: str, min_posts: int = 5) -> dict:
    from scipy.stats import spearmanr
    rhos, hits = [], []
    for _, g in test.groupby("author"):
        if len(g) < min_posts or g.y.nunique() < 2 or g[pred_col].nunique() < 2:
            if len(g) >= min_posts:
                rhos.append(0.0)  # a constant prediction ranks nothing
            continue
        rhos.append(spearmanr(g[pred_col], g.y).statistic)
        k = max(1, int(round(len(g) * 0.2)))
        top_pred = set(g.nlargest(k, pred_col).index)
        top_true = set(g.nlargest(k, "y").index)
        hits.append(len(top_pred & top_true) / k)
    return {"within_author_spearman": float(np.nanmean(rhos)) if rhos else np.nan,
            "top20_hit_rate": float(np.mean(hits)) if hits else np.nan,
            "authors": len(rhos)}


def recency_weights(df: pd.DataFrame, ref: pd.Timestamp, con=None) -> np.ndarray:
    """Newer posts count more: weight = 0.5 ** (age_weeks / half_life). The half-life is shorter for a
    client whose situation changed (memory.half_life_for), so it adapts faster."""
    from .memory import NORMAL, half_life_for
    hl = {a: (half_life_for(a, con) if con is not None else NORMAL.half_life_weeks) for a in df.author.unique()}
    age_w = ((ref - df.ts).dt.total_seconds() / (7 * 86400)).clip(lower=0).to_numpy()
    return 0.5 ** (age_w / df.author.map(hl).to_numpy())


RECENCY_FILE = MODEL_DIR / "recency.json"


def evaluate(test: pd.DataFrame) -> pd.DataFrame:
    from scipy.stats import spearmanr
    rows = []
    for name, col in [("A · account's usual level", "pred_A"), ("B · usual level × X's published rules", "pred_B"),
                      ("Model", "pred_model")]:
        w = _within_author(test, col)
        rows.append({"predictor": name, **w,
                     "pooled_spearman": spearmanr(test[col], test.y).statistic,
                     "mae_log": float((test[col] - test.y).abs().mean())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ train / backtest
def backtest(con: duckdb.DuckDBPyConnection) -> dict:
    import lightgbm as lgb

    df = build_features(load_training_posts(con))
    df = df[df.base.notna()].reset_index(drop=True)
    train_mask = df.ts < pd.Timestamp(SPLIT, tz="UTC")
    df, pca = add_text_pca(con, df, fit_mask=train_mask)
    Xall, cats = _X(df)
    train, test = df[train_mask], df[~train_mask].copy()
    params = dict(objective="regression_l1", learning_rate=0.03, num_leaves=31, min_data_in_leaf=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0)
    booster = lgb.train(params, lgb.Dataset(Xall[train_mask], train.y), num_boost_round=800)
    test["pred_model"] = booster.predict(Xall[~train_mask])
    # Learning from recent experience: same model, newer posts weighted more. Kept only if it helps.
    wts = recency_weights(train, pd.Timestamp(SPLIT, tz="UTC"), con)
    b_w = lgb.train(params, lgb.Dataset(Xall[train_mask], train.y, weight=wts), num_boost_round=800)
    test["pred_recency"] = b_w.predict(Xall[~train_mask])
    r_plain, r_rec = _within_author(test, "pred_model"), _within_author(test, "pred_recency")
    use = bool(r_rec["within_author_spearman"] > r_plain["within_author_spearman"])
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    RECENCY_FILE.write_text(json.dumps({"use_recency_weights": use,
                                        "spearman_plain": r_plain["within_author_spearman"],
                                        "spearman_recency": r_rec["within_author_spearman"]}, indent=1))
    test["pred_A"] = test.log_base
    test["pred_B"] = np.log1p(test.base * test.day_decay)
    res = evaluate(test)
    cfg = load_config()
    pilots = {h.lower() for h in cfg["pilot_clients"]}
    per_client = []
    for c in sorted(pilots):
        t = test[test.author == c]
        if len(t) >= 5:
            r = evaluate(t)
            per_client.append(r.assign(client=c, test_posts=len(t)))
    imp = pd.Series(booster.feature_importance("gain"), index=Xall.columns).sort_values(ascending=False)
    return {"overall": res, "recency": json.loads(RECENCY_FILE.read_text()), "per_client": pd.concat(per_client) if per_client else pd.DataFrame(),
            "n_train": int(train_mask.sum()), "n_test": int((~train_mask).sum()),
            "authors_train": int(train.author.nunique()), "importance": imp, "test": test}


def train_final(con: duckdb.DuckDBPyConnection) -> Path:
    """Fit on all rated posts and save model + PCA + categories for `predict`."""
    import pickle

    import lightgbm as lgb

    df = build_features(load_training_posts(con))
    df = df[df.base.notna()].reset_index(drop=True)
    df, pca = add_text_pca(con, df)
    X, cats = _X(df)
    params = dict(objective="regression_l1", learning_rate=0.03, num_leaves=31, min_data_in_leaf=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0)
    use = RECENCY_FILE.exists() and json.loads(RECENCY_FILE.read_text()).get("use_recency_weights")
    wts = recency_weights(df, df.ts.max(), con) if use else None
    booster = lgb.train(params, lgb.Dataset(X, df.y, weight=wts), num_boost_round=800)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(MODEL_DIR / "lgb.txt"))
    (MODEL_DIR / "pca.pkl").write_bytes(pickle.dumps(pca))
    (MODEL_DIR / "meta.json").write_text(json.dumps({"categories": cats, "n_posts": len(df),
                                                     "trained_at": pd.Timestamp.now(tz="UTC").isoformat()}))
    return MODEL_DIR


def write_backtest_report(r: dict) -> Path:
    o = r["overall"]
    fmt = lambda v, s="{:.3f}": "—" if pd.isna(v) else s.format(v)
    lines = ["# 1D · Backtest", "",
             f"Trained on **{r['n_train']:,} posts** from {r['authors_train']} accounts posted before {SPLIT}; "
             f"tested on **{r['n_test']:,} later posts** (each ≥48h old). Target: X-weighted score "
             "(replies ×5, quotes ×5, reposts ×1, likes ×0.66).", "",
             "**Within-author Spearman** is the headline: for each account, does the predictor rank that "
             "account's posts in the right order? (0 = no better than random, 1 = perfect.) Baseline A is the account's "
             "rolling recent level; a negative score means posts right after a hot streak tend to do worse than the "
             "streak (regression to the mean). **Top-20% hit rate**: of the posts a predictor puts in an "
             "account's top fifth, the share that really were (random = 20%).", "",
             "| predictor | within-author Spearman | top-20% hit rate | pooled Spearman | mean abs error (log) |",
             "|---|---:|---:|---:|---:|"]
    for x in o.itertuples():
        lines.append(f"| {x.predictor} | {fmt(x.within_author_spearman)} | {fmt(x.top20_hit_rate, '{:.0%}')} | "
                     f"{fmt(x.pooled_spearman)} | {fmt(x.mae_log)} |")
    m, a, b = o.iloc[2], o.iloc[0], o.iloc[1]
    beats = (m.within_author_spearman > max(a.within_author_spearman, b.within_author_spearman)
             and m.mae_log < min(a.mae_log, b.mae_log))
    lines += ["", f"**Gate: {'PASS' if beats else 'FAIL'}**: the model "
              f"{'beats' if beats else 'does not beat'} both baselines on within-author ranking and error.", ""]
    if len(r["per_client"]):
        lines += ["## Pilot clients (test period only)", "",
                  "| client | test posts | predictor | within-author Spearman | top-20% hit rate | MAE (log) |",
                  "|---|---:|---|---:|---:|---:|"]
        for x in r["per_client"].itertuples():
            lines.append(f"| {x.client} | {x.test_posts} | {x.predictor} | {fmt(x.within_author_spearman)} | "
                         f"{fmt(x.top20_hit_rate, '{:.0%}')} | {fmt(x.mae_log)} |")
        lines += ["", "Per-client numbers rest on few test posts; read them as direction, not proof."]
    lines += ["", "## What the model leans on (gain)", ""]
    imp = r["importance"] / r["importance"].sum()
    lines += [f"- {k}: {v:.0%}" for k, v in imp.head(12).items()]
    path = ROOT / "reports" / "1D_backtest.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
