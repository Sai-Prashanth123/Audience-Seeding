"""Breakout ("hit") chance: probability a post does 3x or more of its author's usual views.

LightGBM classifier on the forecaster's features (clients weighted), calibrated with isotonic regression on the early
half of the calibration window, judged on the test window against the honest baseline "this author's own past hit
rate" (shrunk to the overall rate). Shown in the app only if it beats that baseline significantly (account-cluster
bootstrap of the Brier-score gain).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HIT = np.log(3.0)


def label(df: pd.DataFrame) -> pd.Series:
    return (df.y_views - df.lb_views > HIT).astype(int)


def author_base_rate(train: pd.DataFrame, k: float = 20.0) -> dict:
    """Each author's past hit rate, shrunk toward the overall rate with k pseudo-posts."""
    y = label(train)
    overall = float(y.mean())
    g = y.groupby(train.author).agg(["sum", "count"])
    return {"overall": overall, **((g["sum"] + k * overall) / (g["count"] + k)).to_dict()}


def fit_predict(train: pd.DataFrame, cal: pd.DataFrame, test: pd.DataFrame, feats: list[str], cats: dict,
                weight=None) -> tuple[np.ndarray, np.ndarray]:
    """Calibrated hit probability for test posts, and the author-base-rate baseline for the same posts."""
    import lightgbm as lgb
    from sklearn.isotonic import IsotonicRegression

    from .model import LGB_PARAMS, _matrix
    params = {**LGB_PARAMS, "objective": "binary"}
    b = lgb.train(params, lgb.Dataset(_matrix(train, feats, cats), label(train), weight=weight), num_boost_round=400)
    early = cal[cal.ts < cal.ts.median()]
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
        b.predict(_matrix(early, feats, cats)), label(early))
    p = iso.predict(b.predict(_matrix(test, feats, cats)))
    base = author_base_rate(pd.concat([train, early]))
    p0 = test.author.map(base).fillna(base["overall"]).to_numpy()
    return p, p0


def reliability(y: np.ndarray, p: np.ndarray, bins=(0, .02, .05, .1, .2, .4, 1.0)) -> pd.DataFrame:
    b = pd.cut(p, bins, include_lowest=True)
    return pd.DataFrame({"y": y, "p": p, "bin": b}).groupby("bin", observed=True).agg(
        posts=("y", "size"), predicted=("p", "mean"), happened=("y", "mean")).reset_index()


def brier_gain(df: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> tuple[float, float, float]:
    """Brier(baseline) - Brier(model), with a 95% range from resampling whole accounts (positive = model better)."""
    rng = np.random.default_rng(seed)
    d = df.assign(bm=(df.p - df.y) ** 2, bb=(df.p0 - df.y) ** 2).groupby("author")[["bm", "bb"]].agg(["sum", "count"])
    sm, sb, n = d[("bm", "sum")].to_numpy(), d[("bb", "sum")].to_numpy(), d[("bm", "count")].to_numpy()
    point = (sb.sum() - sm.sum()) / n.sum()
    idx = rng.integers(0, len(n), size=(n_boot, len(n)))
    boots = (sb[idx].sum(1) - sm[idx].sum(1)) / n[idx].sum(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(point), float(lo), float(hi)
