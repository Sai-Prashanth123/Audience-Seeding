"""X Winners Engine · analysis. Three independent methods must agree before something becomes a rule.

  topics()      embeddings (MiniLM) -> UMAP -> HDBSCAN per client, c-TF-IDF names, win rate and fatigue
                (how a topic's result changes with each retelling)
  lifts()       win rate and median vs-usual with vs without each feature, 95% bootstrap ranges
  bayes()       hierarchical Bayesian regression of log(views / usual) on category + anatomy, effects
                partially pooled: each client -> shared mean (peers are a 4th group, so a thin account like
                Kenny borrows strength and shows wide intervals). Student-t likelihood; NUTS via NumPyro.
  shap_lgbm()   LightGBM on the same target, SHAP main effects + top interactions
  twins()       same client, same topic (cosine >= .60, the top 1% of post pairs), within 30 days, outcomes 2x+ apart:
                what differed between the winner and the loser
  validate()    rules learned on posts before the last 90 days, tested on the last 90
"""

from __future__ import annotations

import os

os.environ.setdefault("XLA_FLAGS", "--xla_force_host_platform_device_count=4")   # 4 NUTS chains in parallel

import numpy as np
import pandas as pd

from .anatomy import BINARY, FEATURES

CATS = ["Article", "QRT", "Thread", "Video", "Tweet"]
HOLDOUT_DAYS = 90
SEED = 0


# ------------------------------------------------------------------ embeddings and topics
def embed(df: pd.DataFrame) -> np.ndarray:
    from ..forecast.serve import embed as _embed
    txt = (df.article_title.fillna("") + " " + df.text.fillna("").str.replace(r"https?://\S+", "", regex=True)
           + " " + df.get("article_preview", pd.Series("", index=df.index)).fillna("")).str.slice(0, 1500)
    return _embed(txt.tolist())


def _ctfidf(docs: pd.Series, labels: np.ndarray, top: int = 6) -> dict:
    from sklearn.feature_extraction.text import CountVectorizer
    docs = docs.str.replace(r"https?://\S+|t\.co\S*", " ", regex=True)
    joined = pd.Series(docs.values).groupby(labels).apply(" ".join)
    cv = CountVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2, max_features=6000,
                         token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9+.]{2,}\b")
    X = cv.fit_transform(joined.values).toarray().astype(float)
    tf = X / X.sum(1, keepdims=True).clip(min=1)
    idf = np.log(1 + X.sum() / X.sum(0).clip(min=1))
    s = tf * idf
    vocab = np.array(cv.get_feature_names_out())
    return {lab: ", ".join(vocab[np.argsort(-s[i])[:top]]) for i, lab in enumerate(joined.index)}


def topics(df: pd.DataFrame, vec: np.ndarray, min_size: int = 8) -> pd.DataFrame:
    """Per client: topic id per post (-1 = no clear topic) and a topic table with win rate and fatigue."""
    import umap
    from sklearn.cluster import HDBSCAN
    out = pd.Series(-1, index=df.index)
    names = {}
    for a, g in df[df.is_client].groupby("author"):
        idx = g.index.to_numpy()
        if len(idx) < 3 * min_size:
            continue
        pos = df.index.get_indexer(idx)
        red = umap.UMAP(n_components=8, n_neighbors=15, min_dist=0.0, metric="cosine",
                        random_state=SEED).fit_transform(vec[pos])
        lab = HDBSCAN(min_cluster_size=min_size, min_samples=3).fit_predict(red)
        out.loc[idx] = lab
        nm = _ctfidf(g.text.fillna("") + " " + g.article_title.fillna(""), lab)
        names.update({(a, k): v for k, v in nm.items()})
    df = df.assign(topic=out)
    rows = []
    for (a, t), g in df[df.is_client & (df.topic >= 0)].groupby(["author", "topic"]):
        g = g.sort_values("ts")
        r = np.arange(1, len(g) + 1)
        slope = float(np.polyfit(np.log(r), g.log_vs_usual.fillna(0), 1)[0]) if len(g) >= 5 else np.nan
        recent = g[g.era == "last 90 days"]
        rows.append({"author": a, "topic": int(t), "keywords": names.get((a, t), ""), "posts": len(g),
                     "wins": int(g.win.sum()), "win_rate": g.win.mean(),
                     "median_vs_usual": float(np.exp(g.log_vs_usual.median())),
                     "median_views": float(g.view_count.median()),
                     "fatigue_slope": slope,     # log(vs usual) per log(retelling #); < 0 = wearing out
                     "recent_posts": len(recent), "recent_win_rate": recent.win.mean() if len(recent) else np.nan,
                     "categories": ", ".join(f"{k} {v}" for k, v in g.category.value_counts().items()),
                     "best_post": g.loc[g.view_count.idxmax(), "tweet_id"]})
    return df.topic, pd.DataFrame(rows).sort_values(["author", "win_rate"], ascending=[True, False])


# ------------------------------------------------------------------ lifts with bootstrap ranges
def _boot_ratio(a: np.ndarray, b: np.ndarray, n: int = 2000, rng=None) -> tuple[float, float, float]:
    rng = rng or np.random.default_rng(SEED)
    if len(a) < 3 or len(b) < 3:
        return np.nan, np.nan, np.nan
    pa, pb = a.mean(), b.mean()
    ba = rng.choice(a, (n, len(a))).mean(1)
    bb = rng.choice(b, (n, len(b))).mean(1)
    r = (ba + 1e-3) / (bb + 1e-3)
    return float((pa + 1e-3) / (pb + 1e-3)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def lifts(df: pd.DataFrame, by: list[str] | None = None, min_n: int = 8) -> pd.DataFrame:
    """For each binary feature (and each category vs the rest): win rate with vs without, ratio + 95% range,
    and the median vs-usual with vs without."""
    rng = np.random.default_rng(SEED)
    by = by or ["author"]
    rows = []
    d = df.assign(**{f"cat_{c}": (df.category == c).astype(int) for c in CATS},
                  **{f"cta_{k}": (df.cta == k).astype(int) for k in df.cta.unique() if k != "none"})
    feats = BINARY + [f"cat_{c}" for c in CATS] + [c for c in d.columns if c.startswith("cta_")]
    for key, g in d.groupby(by):
        for f in feats:
            on, off = g[g[f] == 1], g[g[f] == 0]
            if len(on) < min_n or len(off) < min_n:
                continue
            r, lo, hi = _boot_ratio(on.win.to_numpy(float), off.win.to_numpy(float), rng=rng)
            rows.append({**dict(zip(by, key if isinstance(key, tuple) else (key,))), "feature": f,
                         "posts_with": len(on), "posts_without": len(off),
                         "win_rate_with": on.win.mean(), "win_rate_without": off.win.mean(),
                         "lift": r, "lift_lo": lo, "lift_hi": hi,
                         "vs_usual_with": float(np.exp(on.log_vs_usual.median())),
                         "vs_usual_without": float(np.exp(off.log_vs_usual.median())),
                         "proven": bool(lo > 1 or hi < 1)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ hierarchical Bayesian model
def _design(df: pd.DataFrame) -> tuple[np.ndarray, list[str], dict]:
    X = pd.DataFrame({f"cat_{c}": (df.category == c).astype(float) for c in CATS if c != "Tweet"})
    for f in FEATURES:
        X[f] = pd.to_numeric(df[f], errors="coerce").astype(float)
    X = X.fillna(X.median())
    stats = {}
    for f in X.columns:
        if not f.startswith("cat_") and f not in BINARY:
            mu, sd = X[f].mean(), X[f].std() or 1.0
            X[f] = (X[f] - mu) / sd
            stats[f] = (mu, sd)
    return X.to_numpy(), list(X.columns), stats


def bayes(df: pd.DataFrame, draws: int = 1000, tune: int = 1000) -> pd.DataFrame:
    """Effects on log(views/usual) per group (each client + 'peers'), partially pooled to a shared mean.
    Returns per group x feature: mean effect as a multiplier, 94% HDI, P(effect > 0)."""
    import pymc as pm
    d = df[df.log_vs_usual.notna()].copy()
    d["group"] = np.where(d.is_client, d.author, "peers")
    groups = sorted(d.group.unique(), key=lambda g: (g == "peers", g))
    gi = d.group.map({g: i for i, g in enumerate(groups)}).to_numpy()
    authors = sorted(d.author.unique())
    ai = d.author.map({a: i for i, a in enumerate(authors)}).to_numpy()
    X, names, _ = _design(d)
    y = d.log_vs_usual.to_numpy()
    with pm.Model(coords={"feat": names, "group": groups, "author": authors}):
        mu = pm.Normal("mu", 0, 0.5, dims="feat")
        tau = pm.HalfNormal("tau", 0.3, dims="feat")
        z = pm.Normal("z", 0, 1, dims=("group", "feat"))
        beta = pm.Deterministic("beta", mu + tau * z, dims=("group", "feat"))
        a = pm.Normal("a", 0, 0.5, dims="author")
        sigma = pm.HalfNormal("sigma", 1.0)
        nu = pm.Gamma("nu", 2, 0.1)
        pm.StudentT("y", nu=nu, mu=a[ai] + (X * beta[gi]).sum(1), sigma=sigma, observed=y)
        tr = pm.sample(draws, tune=tune, chains=4, nuts_sampler="numpyro", target_accept=0.95,
                       random_seed=SEED, progressbar=False,
                       nuts_sampler_kwargs={"chain_method": "parallel"})
    b = tr.posterior["beta"].stack(s=("chain", "draw")).values      # group x feat x samples
    m = tr.posterior["mu"].stack(s=("chain", "draw")).values
    rows = []
    for gi_, g in enumerate(groups + ["ALL (shared)"]):
        for fi, f in enumerate(names):
            s = m[fi] if g == "ALL (shared)" else b[gi_, fi]
            lo, hi = np.percentile(s, [3, 97])
            rows.append({"group": g, "feature": f, "effect_x": float(np.exp(s.mean())), "lo_x": float(np.exp(lo)),
                         "hi_x": float(np.exp(hi)), "p_positive": float((s > 0).mean())})
    rhat = split_rhat(np.asarray(tr.posterior["mu"].values))
    out = pd.DataFrame(rows)
    out.attrs["rhat_max"] = rhat
    out.attrs["n"] = len(d)
    return out


def split_rhat(x: np.ndarray) -> float:
    """Max split-R-hat over parameters; x: chains x draws x params (Gelman et al., BDA3 11.4)."""
    c, n = x.shape[:2]
    h = n // 2
    s = np.concatenate([x[:, :h], x[:, h:2 * h]], axis=0).reshape(2 * c, h, -1)
    w = s.var(axis=1, ddof=1).mean(0)
    b = h * s.mean(1).var(0, ddof=1)
    v = (h - 1) / h * w + b / h
    return float(np.sqrt(v / w).max())


# ------------------------------------------------------------------ LightGBM + SHAP
def shap_lgbm(df: pd.DataFrame, top_inter: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    import lightgbm as lgb
    import shap
    d = df[df.log_vs_usual.notna()].copy()
    X = pd.DataFrame({f: pd.to_numeric(d[f], errors="coerce") for f in FEATURES})
    for c in CATS:
        X[f"cat_{c}"] = (d.category == c).astype(int).to_numpy()
    X["is_client"] = d.is_client.astype(int)
    y = d.log_vs_usual.to_numpy()
    w = np.where(d.is_client, 3.0, 1.0)
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=20,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
                          random_state=SEED, verbose=-1).fit(X, y, sample_weight=w)
    ex = shap.TreeExplainer(m)
    cl = d.is_client.to_numpy()
    sv = ex.shap_values(X[cl])
    main = pd.DataFrame({"feature": X.columns, "mean_abs": np.abs(sv).mean(0),
                         "direction": [np.corrcoef(X[cl][c].fillna(0), sv[:, i])[0, 1] if X[cl][c].nunique() > 1
                                       else np.nan
                                       for i, c in enumerate(X.columns)]}).sort_values("mean_abs", ascending=False)
    iv = ex.shap_interaction_values(X[cl].iloc[:600])
    mag = np.abs(iv).mean(0)
    np.fill_diagonal(mag, 0)
    pairs = [(X.columns[i], X.columns[j], mag[i, j]) for i in range(len(X.columns)) for j in range(i + 1, len(X.columns))]
    inter = pd.DataFrame(pairs, columns=["a", "b", "strength"]).sort_values("strength", ascending=False).head(top_inter)
    return main, inter


# ------------------------------------------------------------------ twins
def twins(df: pd.DataFrame, vec: np.ndarray, sim: float = 0.60, days: int = 30) -> pd.DataFrame:
    """Same-client posts on the same topic within `days`, results 2x+ apart: winner vs loser differences."""
    rows = []
    for a, g in df[df.is_client & df.log_vs_usual.notna()].groupby("author"):
        pos = df.index.get_indexer(g.index)
        V = vec[pos]
        S = V @ V.T
        ts = g.ts.to_numpy(dtype="datetime64[s]").astype(np.int64)
        y = g.log_vs_usual.to_numpy()
        n = len(g)
        for i in range(n):
            for j in range(i + 1, n):
                if S[i, j] >= sim and abs(ts[i] - ts[j]) <= days * 86400 and abs(y[i] - y[j]) >= np.log(2):
                    w, l = (i, j) if y[i] > y[j] else (j, i)
                    rw, rl = g.iloc[w], g.iloc[l]
                    rows.append({"author": a, "winner": rw.tweet_id, "loser": rl.tweet_id, "similarity": float(S[i, j]),
                                 "ratio": float(np.exp(y[w] - y[l])),
                                 **{f"d_{f}": float(rw[f]) - float(rl[f]) for f in FEATURES},
                                 "same_category": rw.category == rl.category, "cat_w": rw.category, "cat_l": rl.category})
    return pd.DataFrame(rows)


def twin_summary(t: pd.DataFrame) -> pd.DataFrame:
    """For each feature: in how many twin pairs the winner had more of it vs less (sign test)."""
    from scipy.stats import binomtest
    rows = []
    for f in FEATURES:
        d = t[f"d_{f}"].dropna()
        up, down = int((d > 0).sum()), int((d < 0).sum())
        if up + down < 6:
            continue
        rows.append({"feature": f, "winner_more": up, "winner_less": down,
                     "share_winner_more": up / (up + down), "p": binomtest(up, up + down).pvalue})
    return pd.DataFrame(rows).sort_values("p")


# ------------------------------------------------------------------ out-of-time validation
def rule_score(df: pd.DataFrame, rules: pd.DataFrame) -> np.ndarray:
    """Sum of signed log-effects of the rules a post follows (binary rules: present; continuous: standardized)."""
    s = np.zeros(len(df))
    for r in rules.itertuples():
        f = r.feature
        if f.startswith("cat_"):
            x = (df.category == f[4:]).astype(float).to_numpy()
        else:
            x = pd.to_numeric(df[f], errors="coerce").fillna(0).to_numpy(float)
            if f not in BINARY:
                x = (x - r.mu) / r.sd
        s += np.log(r.effect_x) * x
    return s


def validate(df: pd.DataFrame, fit_fn=None) -> dict:
    """Learn rules (Bayesian, P>=.9 or <=.1 for the client's own group) on posts before the last 90 days;
    score the last 90 days; report Spearman(rule score, vs usual), win-rate top third vs bottom third, AUC."""
    from scipy.stats import spearmanr
    from sklearn.metrics import roc_auc_score
    cut = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=HOLDOUT_DAYS)
    train, test = df[df.ts < cut], df[(df.ts >= cut) & df.is_client & df.log_vs_usual.notna()]
    eff = (fit_fn or bayes)(train)
    _, _, stats = _design(train[train.log_vs_usual.notna()])
    out = {"train_posts": int(train.log_vs_usual.notna().sum()), "test_posts": len(test), "by_client": {}}
    for a, g in test.groupby("author"):
        grp = a if a in set(eff.group) else "ALL (shared)"
        r = eff[(eff.group == grp) & ((eff.p_positive >= 0.9) | (eff.p_positive <= 0.1))].copy()
        r["mu"] = r.feature.map(lambda f: stats.get(f, (0, 1))[0])
        r["sd"] = r.feature.map(lambda f: stats.get(f, (0, 1))[1])
        sc = rule_score(g, r)
        if len(g) < 10 or len(r) == 0:
            out["by_client"][a] = {"posts": len(g), "rules": len(r), "note": "too few"}
            continue
        rho, p = spearmanr(sc, g.log_vs_usual)
        q = pd.qcut(pd.Series(sc).rank(method="first"), 3, labels=["bottom", "mid", "top"])
        wr = g.win.groupby(q.values).mean()
        auc = roc_auc_score(g.win, sc) if g.win.nunique() == 2 else np.nan
        out["by_client"][a] = {"posts": len(g), "rules": len(r), "spearman": float(rho), "p": float(p),
                               "win_rate_top_third": float(wr.get("top", np.nan)),
                               "win_rate_bottom_third": float(wr.get("bottom", np.nan)), "auc": float(auc),
                               "median_vs_usual_top": float(np.exp(g.log_vs_usual[(q == "top").values].median())),
                               "median_vs_usual_bottom": float(np.exp(g.log_vs_usual[(q == "bottom").values].median()))}
    return out
