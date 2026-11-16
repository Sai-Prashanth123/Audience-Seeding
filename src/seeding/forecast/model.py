"""L1: per-action forecasters, judged by the pre-registered protocol (reports/3_protocol.md).

Every member predicts three quantiles (0.1, 0.5, 0.9) of log1p(count) for each X action. The 0.1-0.9 band
is then conformalized (CQR) on a calibration window that comes after training and before testing, so the
80% range is honest on new posts.

Members are added one at a time and kept only if they pass the keep/drop rule in the protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

import duckdb
import numpy as np
import pandas as pd

from ..model import PCA_DIM, add_text_pca, load_training_posts
from ..model import CAT as CAT_1D
from ..model import NUM as NUM_1D
from ..seedmap import ROOT, load_config
from . import evaluate as ev
from .features import CAT, NUM, TARGETS, build

OUT = ROOT / "data" / "model" / "forecast"
TXT = [f"txt{i}" for i in range(PCA_DIM)]
Q = ev.QUANTILES


# ------------------------------------------------------------------ members
@dataclass
class Member:
    name: str
    fit_predict: Callable          # (train, test, target, features) -> {q: array}
    features: Callable             # () -> list of feature names
    targets: tuple = tuple(TARGETS)


def _matrix(df: pd.DataFrame, feats: list[str], cats: dict) -> pd.DataFrame:
    X = df[feats].copy()
    for c in feats:
        if c in cats:
            X[c] = pd.Categorical(X[c].astype(str), categories=cats[c])
    return X


def _cats(df: pd.DataFrame, feats: list[str]) -> dict:
    return {c: sorted(df[c].astype(str).unique()) for c in feats if df[c].dtype == object or c in CAT}


import os  # noqa: E402

THREADS = int(os.environ.get("FORECAST_THREADS", "0")) or -1    # parallel backtests set this per process
LGB_PARAMS = dict(learning_rate=0.05, num_leaves=31, min_data_in_leaf=40, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0,
                  num_threads=max(THREADS, 0))


def lgb_quantiles(train, test, target, feats, rounds: int = 600) -> dict:
    import lightgbm as lgb
    cats = _cats(train, feats)
    Xtr, Xte = _matrix(train, feats, cats), _matrix(test, feats, cats)
    out = {}
    for q in Q:
        b = lgb.train({**LGB_PARAMS, "objective": "quantile", "alpha": q},
                      lgb.Dataset(Xtr, train[f"y_{target}"]), num_boost_round=rounds)
        out[q] = b.predict(Xte)
    return out


def baseline_a(train, test, target, feats) -> dict:
    """The account's usual level, with its typical spread learned from the training residuals."""
    res = (train[f"y_{target}"] - train[f"lb_{target}"]).dropna()
    return {q: test[f"lb_{target}"].to_numpy() + np.quantile(res, q) for q in Q}


def baseline_b(train, test, target, feats) -> dict:
    """A, shifted by X's same-day author-diversity decay (log of the multiplier)."""
    shift_tr = np.log(train.day_decay)
    res = (train[f"y_{target}"] - train[f"lb_{target}"] - shift_tr).dropna()
    return {q: test[f"lb_{target}"].to_numpy() + np.log(test.day_decay.to_numpy()) + np.quantile(res, q) for q in Q}


def model_1d(train, test, target, feats) -> dict:
    """1D exactly as it is: one LightGBM (L1 loss) on the X score with 1D's own features. Point only;
    its range comes from its training residuals, like baseline A."""
    import lightgbm as lgb
    params = dict(objective="regression_l1", learning_rate=0.03, num_leaves=31, min_data_in_leaf=40,
                  feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, seed=0)
    f = NUM_1D + CAT_1D
    tr = train.dropna(subset=["log_base"])
    cats = _cats(tr, f)
    b = lgb.train(params, lgb.Dataset(_matrix(tr, f, cats), tr.y_xscore), num_boost_round=800)
    p_tr, p_te = b.predict(_matrix(tr, f, cats)), b.predict(_matrix(test, f, cats))
    res = tr.y_xscore.to_numpy() - p_tr
    return {q: p_te + np.quantile(res, q) for q in Q}


def catboost_quantiles(train, test, target, feats) -> dict:
    """CatBoost [Prokhorenkova et al. 2018]: ordered boosting, native categoricals, all 3 quantiles in one model."""
    from catboost import CatBoostRegressor, Pool
    cat_cols = [c for c in feats if c in CAT]

    def pool(d, label=True):
        X = d[feats].copy()
        for c in cat_cols:
            X[c] = X[c].astype(str)
        return Pool(X, d[f"y_{target}"] if label else None, cat_features=cat_cols)

    m = CatBoostRegressor(loss_function="MultiQuantile:alpha=0.1,0.5,0.9", iterations=500, depth=6,
                          learning_rate=0.08, random_seed=0, verbose=False, thread_count=THREADS)
    m.fit(pool(train))
    P = np.asarray(m.predict(pool(test, label=False)))
    return {0.1: P[:, 0], 0.5: P[:, 1], 0.9: P[:, 2]}


def ngboost_dist(train, test, target, feats) -> dict:
    """NGBoost [Duan et al. 2020]: natural-gradient boosting of a full Normal distribution per post."""
    from ngboost import NGBRegressor
    from ngboost.distns import Normal
    from scipy.stats import norm
    cats = [c for c in feats if c in CAT]
    Xtr = pd.get_dummies(train[feats], columns=cats, dtype=float)
    Xte = pd.get_dummies(test[feats], columns=cats, dtype=float).reindex(columns=Xtr.columns, fill_value=0.0)
    med = Xtr.median()
    Xtr, Xte = Xtr.fillna(med).to_numpy(), Xte.fillna(med).to_numpy()
    m = NGBRegressor(Dist=Normal, n_estimators=300, learning_rate=0.04, minibatch_frac=0.3, verbose=False,
                     random_state=0)
    m.fit(Xtr, train[f"y_{target}"].to_numpy())
    d = m.pred_dist(Xte)
    mu, sd = d.params["loc"], d.params["scale"]
    return {q: mu + sd * norm.ppf(q) for q in Q}


def model_1d_strict(train, test, target, feats) -> dict:
    """Diagnostic: 1D with its baselines replaced by the strict 48h-matured ones. If this loses 1D's edge, that
    edge came from using recent posts' final counts before they were known."""
    tr, te = train.copy(), test.copy()
    for d in (tr, te):
        d["log_base"], d["log_base_views"] = d.lb_xscore, d.lb_views
    return model_1d(tr, te, target, feats)


def lgb_with_1d_base(train, test, target, feats) -> dict:
    """Diagnostic only (not deployable as is): L1 plus 1D's previous-20-posts baselines."""
    return lgb_quantiles(train, test, target, feats + ["log_base", "log_base_views"])


MEMBERS = {
    "C_1D_strict": Member("C_1D_strict", model_1d_strict, lambda: [], targets=("xscore",)),
    "diag_L1_1Dbase": Member("diag_L1_1Dbase", lgb_with_1d_base, lambda: NUM + TXT + CAT, targets=("views", "xscore")),
    "A_usual": Member("A_usual", baseline_a, lambda: []),
    "B_usual_x_rules": Member("B_usual_x_rules", baseline_b, lambda: []),
    "C_1D": Member("C_1D", model_1d, lambda: [], targets=("xscore",)),
    "L1_lgbm": Member("L1_lgbm", lgb_quantiles, lambda: NUM + TXT + CAT),
    "L1_catboost": Member("L1_catboost", catboost_quantiles, lambda: NUM + TXT + CAT, targets=("views", "xscore")),
    "L1_ngboost": Member("L1_ngboost", ngboost_dist, lambda: NUM + TXT + CAT, targets=("views", "xscore")),
}


# ------------------------------------------------------------------ backtest
def load(con) -> pd.DataFrame:
    return build(load_training_posts(con))


def run_backtest(con: duckdb.DuckDBPyConnection, members: list[str] | None = None, n_folds: int = 4,
                 df: pd.DataFrame | None = None, folds: list | None = None) -> pd.DataFrame:
    """Rolling-origin backtest. Returns RAW long predictions for the calibration and test windows:
    one row per (fold, split, post, target, member). `finalize` adds derived members and the ranges."""
    members = members or list(MEMBERS)
    df = load(con) if df is None else df
    folds = folds or ev.rolling_folds(df.ts, n_folds=n_folds)
    rows = []
    for k, f in enumerate(folds):
        train_mask = df.ts < f.cal_start - pd.Timedelta(days=2)     # every training result had matured
        cal_mask = (df.ts >= f.cal_start) & (df.ts < f.test_start)
        test_mask = (df.ts >= f.test_start) & (df.ts < f.test_end)
        d, _ = add_text_pca(con, df.copy(), fit_mask=train_mask)
        train = d[train_mask]
        both = pd.concat([d[cal_mask].assign(split="cal"), d[test_mask].assign(split="test")])
        print(f"fold {k + 1}/{len(folds)}: train {len(train):,} · cal {cal_mask.sum():,} · "
              f"test {test_mask.sum():,} ({f.test_start:%d %b}–{f.test_end:%d %b})", flush=True)
        for name in members:
            cache = CACHE / _signature(df, f) / f"{name}.parquet"
            if cache.exists():
                rows.append(pd.read_parquet(cache))
                print(f"   {name} (cached)", flush=True)
                continue
            m = MEMBERS[name]
            part = []
            for t in m.targets:
                pred = m.fit_predict(train, both, t, m.features())
                part.append(pd.DataFrame({
                    "fold": k + 1, "split": both.split.to_numpy(), "tweet_id": both.tweet_id.to_numpy(),
                    "author": both.author.to_numpy(), "ts": both.ts.to_numpy(), "target": t, "member": name,
                    "y": both[f"y_{t}"].to_numpy(), "q10": pred[0.1], "q50": pred[0.5], "q90": pred[0.9]}))
            part = pd.concat(part, ignore_index=True)
            cache.parent.mkdir(parents=True, exist_ok=True)
            part.to_parquet(cache, index=False)
            rows.append(part)
            print(f"   {name} done", flush=True)
    return pd.concat(rows, ignore_index=True)


CACHE = OUT / "bt_cache"


def _signature(df: pd.DataFrame, f) -> str:
    """Cache key: the data (post count, newest post) and the fold's dates. New data -> new results."""
    import hashlib
    key = f"{len(df)}|{df.ts.max()}|{f.cal_start}|{f.test_start}|{f.test_end}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def add_shrinkage(raw: pd.DataFrame, base: str = "L1_lgbm", k: float = 10.0) -> pd.DataFrame:
    """Hierarchical (empirical-Bayes) per-account correction: each account's mean error on the FIRST half of
    the calibration window, shrunk toward 0 by n / (n + k), is added to its later predictions. The second half
    of the calibration window and the test window are both corrected, so conformal ranges see the corrected
    member exactly as it will be used. Small accounts barely move."""
    out = []
    for (f, t), g in raw[raw.member == base].groupby(["fold", "target"]):
        cal = g[g.split == "cal"]
        early = cal[cal.ts < cal.ts.median()]
        r = (early.y - early.q50).groupby(early.author).agg(["mean", "count"])
        later = g[~g.tweet_id.isin(early.tweet_id) | (g.split == "test")].copy()
        shift = (r["mean"] * r["count"] / (r["count"] + k)).reindex(later.author).fillna(0).to_numpy()
        later["member"] = f"{base}+shrink"
        for q in ("q10", "q50", "q90"):
            later[q] = later[q] + shift
        out.append(later)
    return pd.concat([raw] + out, ignore_index=True) if out else raw


def add_stack(raw: pd.DataFrame, members: list[str], name: str = "stack") -> pd.DataFrame:
    """Stacker: non-negative weights per quantile, fitted on the FIRST half of each calibration window; the
    second half is left for conformal ranges, so weights and ranges never use the same posts."""
    from scipy.optimize import nnls
    out = []
    for (f, t), g in raw[raw.member.isin(members)].groupby(["fold", "target"]):
        have = [m for m in members if m in set(g.member)]
        if len(have) < 2:
            continue
        w = g.pivot_table(index=["tweet_id", "split", "ts", "author", "y"], columns="member",
                          values=["q10", "q50", "q90"]).dropna().reset_index()
        cal = w[w.split == "cal"]
        fit = cal[cal.ts < cal.ts.median()]
        res, weights = {}, {}
        for q in ("q10", "q50", "q90"):
            A = fit[[(q, m) for m in have]].to_numpy()
            coef, _ = nnls(A, fit["y"].to_numpy())
            coef = coef / coef.sum() if coef.sum() > 0 else np.full(len(have), 1 / len(have))
            res[q] = w[[(q, m) for m in have]].to_numpy() @ coef
            weights[q] = dict(zip(have, coef.round(3)))
        keep = (w.split.eq("test") | ~w.tweet_id.isin(fit.tweet_id)).to_numpy()
        out.append(pd.DataFrame({"fold": f, "split": w.split.to_numpy()[keep], "tweet_id": w.tweet_id.to_numpy()[keep],
                                 "author": w.author.to_numpy()[keep], "ts": w.ts.to_numpy()[keep], "target": t,
                                 "member": name, "y": w.y.to_numpy()[keep],
                                 **{q: res[q][keep] for q in res}}).assign(weights=json.dumps(weights)))
    return pd.concat([raw] + out, ignore_index=True) if out else raw


def add_external(raw: pd.DataFrame, preds: pd.DataFrame, df: pd.DataFrame, name: str = "textft") -> pd.DataFrame:
    """A member trained elsewhere (the Colab fine-tuned text model): its prediction of how much a post beats the
    author's usual level, added to that usual level. Ranges come from its residuals on the early calibration
    half; the stacker then decides how much to trust it."""
    if preds is None or preds.empty:
        return raw
    out = []
    for (f, t), g in preds.groupby(["fold", "target"]):
        base = raw[(raw.fold == f) & (raw.target == t) & (raw.member == "A_usual")]
        if base.empty:
            continue
        # only where Colab saw the post in the same role (cal/test); anything else would be leakage
        m = base.drop(columns=["member", "q10", "q50", "q90"]).merge(g[["tweet_id", "split", "ft_pred"]],
                                                                     on=["tweet_id", "split"])
        m = m.merge(df[["tweet_id", f"lb_{t}"]], on="tweet_id")
        m["q50"] = m[f"lb_{t}"] + m.ft_pred
        cal = m[m.split == "cal"]
        early = cal[cal.ts < cal.ts.median()]
        res = (early.y - early.q50).to_numpy()
        m["q10"], m["q90"] = m.q50 + np.quantile(res, 0.1), m.q50 + np.quantile(res, 0.9)
        out.append(m.drop(columns=["ft_pred", f"lb_{t}"]).assign(member=name))
    return pd.concat([raw] + out, ignore_index=True) if out else raw


def conformalize(raw: pd.DataFrame) -> pd.DataFrame:
    """CQR per (fold, target, member): offsets from that member's calibration rows (the late half, where a
    derived member only has those), applied to its test rows."""
    out = []
    # every member is calibrated on the same late half of the calibration window (the early half may have
    # been used to fit stack weights or shrinkage), so members are compared on equal terms
    cut = raw[raw.split == "cal"].groupby("fold").ts.median()
    for (f, t, m), g in raw.groupby(["fold", "target", "member"]):
        cal = g[(g.split == "cal") & (g.ts >= cut[f])]
        test = g[g.split == "test"].copy()
        off = ev.cqr_offset(cal.y, cal.q10, cal.q90)
        test["q10_raw"], test["q90_raw"] = test.q10, test.q90
        test["q10"], test["q90"] = test.q10 - off, test.q90 + off
        test["cqr_offset"] = off
        out.append(test)
    return pd.concat(out, ignore_index=True)


def finalize(raw: pd.DataFrame, stack_members: list[str] | None = None) -> pd.DataFrame:
    raw = add_shrinkage(raw)
    if stack_members:
        raw = add_stack(raw, stack_members)
    return conformalize(raw)


def summarise(bt: pd.DataFrame, reference: str = "A_usual") -> pd.DataFrame:
    out = []
    for (t, m), g in bt.groupby(["target", "member"]):
        rho, n_auth = ev.within_author_spearman(g, "q50")
        row = {"target": t, "member": m, "posts": len(g), "authors": n_auth, "within_author_spearman": rho,
               "typical_miss_x": ev.typical_miss(g.y, g.q50), "coverage80": ev.coverage(g.y, g.q10, g.q90),
               "width_x": ev.width_factor(g.q10, g.q90),
               "crps": ev.crps_from_quantiles(g.y, {0.1: g.q10, 0.5: g.q50, 0.9: g.q90})}
        ref = bt[(bt.target == t) & (bt.member == reference)]
        if m != reference and len(ref):
            j = g.merge(ref[["fold", "tweet_id", "q50"]], on=["fold", "tweet_id"], suffixes=("", "_ref"))
            j["e"], j["e_ref"] = j.y - j.q50, j.y - j.q50_ref
            stat, p = ev.diebold_mariano(j.e, j.e_ref)
            gain, lo, hi = ev.cluster_bootstrap_gain(j, "e", "e_ref")
            row.update({"vs": reference, "dm_stat": stat, "dm_p": p, "mae_gain": gain, "gain_lo": lo, "gain_hi": hi})
        out.append(row)
    return pd.DataFrame(out)


def keep(summary: pd.DataFrame, member: str, reference: str) -> dict:
    """The protocol's keep/drop rule on views and X score."""
    verdict = {}
    for t in ("views", "xscore"):
        s = summary[(summary.target == t) & (summary.member == member) & (summary.vs == reference)]
        r = summary[(summary.target == t) & (summary.member == reference)]
        if s.empty or r.empty:
            verdict[t] = None
            continue
        s, r = s.iloc[0], r.iloc[0]
        verdict[t] = bool(s.dm_p < 0.05 and s.gain_lo > 0 and s.dm_stat < 0
                          and s.within_author_spearman >= r.within_author_spearman)
    return verdict


def save(bt: pd.DataFrame, summary: pd.DataFrame, con=None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ROOT / "reports" / "3_backtest.csv", index=False)
    if con is not None:
        con.execute("CREATE OR REPLACE TABLE forecast_backtest AS SELECT * FROM bt")
    (OUT / "backtest_meta.json").write_text(json.dumps({"members": sorted(bt.member.unique()),
                                                        "folds": int(bt.fold.max()), "posts": int(bt.tweet_id.nunique()),
                                                        "run_at": pd.Timestamp.now(tz="UTC").isoformat(),
                                                        "clients": load_config()["pilot_clients"]}, indent=1))
