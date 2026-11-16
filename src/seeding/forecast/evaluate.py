"""How we judge every forecaster, the same way, before any of them is built.

Protocol (pre-registered in reports/3_protocol.md):
  * rolling-origin time folds: train on everything before a cut, calibrate ranges on the next 14 days,
    test on the 14 days after that; repeated for the last N windows. Never a random split.
  * metrics, on log1p(count) of each X action:
      within-author Spearman  does it order one account's posts correctly (the team's real decision)
      typical miss (x)        exp(mean |log error|): 2.0 = typically off by a factor of 2
      coverage / width        share of posts inside the 80% range, and how wide the range is (x)
      CRPS                    scores the whole predicted spread, not just the middle (quantile approximation)
  * significance: Diebold-Mariano on per-post absolute errors, plus an author-cluster bootstrap of the
    improvement (posts from one account are not independent).
  * ranges: Conformalized Quantile Regression [Romano, Patterson & Candes 2019], kept honest under drift by
    Adaptive Conformal Inference [Gibbs & Candes 2021].
  * ceiling: the best accuracy *any* model could reach here, from near-duplicate posts by the same author
    (same words, different luck), following Martin et al. 2016 "Exploring limits to prediction in complex
    social systems".
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erf, sqrt

import numpy as np
import pandas as pd

LEVEL = 0.80
QUANTILES = (0.1, 0.5, 0.9)


# ------------------------------------------------------------------ folds
@dataclass(frozen=True)
class Fold:
    cal_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def rolling_folds(ts: pd.Series, n_folds: int = 4, test_days: int = 14, cal_days: int = 14) -> list[Fold]:
    """Last `n_folds` back-to-back test windows ending at the newest post; each has a calibration window before it."""
    end = ts.max().normalize() + pd.Timedelta(days=1)
    folds = []
    for k in range(n_folds, 0, -1):
        test_end = end - pd.Timedelta(days=test_days * (k - 1))
        test_start = test_end - pd.Timedelta(days=test_days)
        folds.append(Fold(test_start - pd.Timedelta(days=cal_days), test_start, test_end))
    return folds


# ------------------------------------------------------------------ point metrics
def within_author_spearman(df: pd.DataFrame, pred: str, y: str = "y", author: str = "author",
                           min_posts: int = 5) -> tuple[float, int]:
    from scipy.stats import spearmanr
    rhos = []
    for _, g in df.groupby(author):
        if len(g) < min_posts:
            continue
        if g[y].nunique() < 2 or g[pred].nunique() < 2:
            rhos.append(0.0)  # a constant prediction ranks nothing
            continue
        rhos.append(spearmanr(g[pred], g[y]).statistic)
    return (float(np.nanmean(rhos)) if rhos else float("nan")), len(rhos)


def typical_miss(y: np.ndarray, pred: np.ndarray) -> float:
    """exp(mean |log error|). 1.0 = perfect; 2.0 = typically off by a factor of 2."""
    return float(np.exp(np.mean(np.abs(np.asarray(y) - np.asarray(pred)))))


def coverage(y, lo, hi) -> float:
    y, lo, hi = map(np.asarray, (y, lo, hi))
    return float(np.mean((y >= lo) & (y <= hi)))


def width_factor(lo, hi) -> float:
    """Median range width as a factor: 4.0 = the top of the range is 4x the bottom."""
    return float(np.exp(np.median(np.asarray(hi) - np.asarray(lo))))


def pinball(y, q_pred, q: float) -> np.ndarray:
    d = np.asarray(y) - np.asarray(q_pred)
    return np.maximum(q * d, (q - 1) * d)


def crps_from_quantiles(y, qpreds: dict[float, np.ndarray]) -> float:
    """CRPS = 2 * integral of the pinball loss over quantile levels, approximated on the predicted levels.

    Comparable across models only when they use the same quantile levels (they all use QUANTILES)."""
    qs = sorted(qpreds)
    return float(2 * np.mean([pinball(y, qpreds[q], q).mean() for q in qs]))


# ------------------------------------------------------------------ significance
def diebold_mariano(err_a: np.ndarray, err_b: np.ndarray) -> tuple[float, float]:
    """DM test on absolute errors. Negative stat = A has smaller errors. Returns (stat, two-sided p)."""
    d = np.abs(np.asarray(err_a)) - np.abs(np.asarray(err_b))
    d = d[~np.isnan(d)]
    if len(d) < 10 or d.std(ddof=1) == 0:
        return float("nan"), float("nan")
    stat = d.mean() / (d.std(ddof=1) / sqrt(len(d)))
    p = 2 * (1 - 0.5 * (1 + erf(abs(stat) / sqrt(2))))
    return float(stat), float(p)


def cluster_bootstrap_gain(df: pd.DataFrame, err_a: str, err_b: str, author: str = "author",
                           n_boot: int = 1000, seed: int = 0) -> tuple[float, float, float]:
    """How much smaller A's mean |error| is than B's, with a 95% range from resampling whole accounts."""
    rng = np.random.default_rng(seed)
    per = df.assign(da=df[err_a].abs(), db=df[err_b].abs()).groupby(author)[["da", "db"]].agg(["sum", "count"])
    sa, sb, n = per[("da", "sum")].to_numpy(), per[("db", "sum")].to_numpy(), per[("da", "count")].to_numpy()
    point = (sb.sum() - sa.sum()) / n.sum()
    idx = rng.integers(0, len(n), size=(n_boot, len(n)))
    boots = (sb[idx].sum(1) - sa[idx].sum(1)) / n[idx].sum(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(point), float(lo), float(hi)


# ------------------------------------------------------------------ conformal ranges
def cqr_offset(y_cal, lo_cal, hi_cal, level: float = LEVEL) -> float:
    """Conformalized Quantile Regression: widen (or shrink) the quantile band by this amount so that,
    on exchangeable data, at least `level` of new posts fall inside."""
    s = np.maximum(np.asarray(lo_cal) - np.asarray(y_cal), np.asarray(y_cal) - np.asarray(hi_cal))
    n = len(s)
    if n == 0:
        return 0.0
    k = min(n, int(np.ceil((n + 1) * level)))
    return float(np.sort(s)[k - 1])


class AdaptiveConformal:
    """Adaptive Conformal Inference: after each judged post, nudge the target miss rate so the
    long-run coverage stays at `level` even when X or a client changes (Gibbs & Candes 2021)."""

    def __init__(self, scores: np.ndarray, level: float = LEVEL, gamma: float = 0.01):
        self.scores = list(np.asarray(scores, dtype=float))
        self.alpha_target = 1 - level
        self.alpha = 1 - level
        self.gamma = gamma

    def offset(self) -> float:
        a = min(max(self.alpha, 1e-3), 0.999)
        return float(np.quantile(self.scores, 1 - a)) if self.scores else 0.0

    def update(self, y: float, lo: float, hi: float) -> bool:
        """Record one judged post (lo/hi are the band *before* the offset). Returns whether it was covered."""
        q = self.offset()
        covered = (lo - q) <= y <= (hi + q)
        self.alpha += self.gamma * (self.alpha_target - (0.0 if covered else 1.0))
        self.scores.append(max(lo - y, y - hi))
        return covered


# ------------------------------------------------------------------ ceiling
def noise_ceiling(df: pd.DataFrame, vecs: dict, y: str = "y", author: str = "author", min_cos: float = 0.92,
                  max_days: int = 90) -> dict:
    """Same author, (almost) the same words, posted within `max_days`: whatever differs in their results is luck
    plus timing that no content model can see. The typical gap between such twins bounds how well any
    model can do on content alone.

    Returns the number of twin pairs, the typical |log difference| between twins, and the implied best
    possible typical miss (x) for a model that knows the true expected value (|a - b| / sqrt(2) under
    symmetric noise)."""
    gaps = []
    for _, g in df.groupby(author):
        g = g[g.tweet_id.isin(vecs)]
        if len(g) < 2:
            continue
        V = np.vstack([vecs[t] for t in g.tweet_id])
        S = V @ V.T
        ts = g.ts.to_numpy()
        yy = g[y].to_numpy()
        i, j = np.triu_indices(len(g), 1)
        days = np.abs((ts[i] - ts[j]) / np.timedelta64(1, "D"))
        keep = (S[i, j] >= min_cos) & (days <= max_days)
        gaps += list(np.abs(yy[i[keep]] - yy[j[keep]]))
    if not gaps:
        return {"pairs": 0, "twin_gap_x": float("nan"), "best_possible_miss_x": float("nan")}
    g = np.asarray(gaps)
    return {"pairs": int(len(g)), "twin_gap_x": float(np.exp(np.mean(g))),
            "best_possible_miss_x": float(np.exp(np.mean(g) / sqrt(2)))}
