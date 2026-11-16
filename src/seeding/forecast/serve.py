"""Train the chosen forecasters once, save them, and score a draft (CLI, dashboard, Slack).

Same procedure as the backtest, applied to the newest data (reports/3_protocol.md):
  train        every post matured more than 2 days before the calibration window
  calibration  the newest 14 days of matured posts; its early half fits the stack weights and per-account
               shrinkage, its late half sets the conformal (CQR) range offsets
So the 80% ranges the app shows are calibrated on posts the models never trained on.

Scoring needs only a client's recent posts (`forecast_history`, exported into the dashboard snapshot) and the
saved files in data/model/forecast/, so it runs online without the pipeline database. Draft text is embedded
with fastembed (ONNX, light) when available, giving the same vectors as sentence-transformers (checked:
cosine 1.000 on test sentences), else with sentence-transformers.
"""

from __future__ import annotations

import gzip
import json
import pickle

import numpy as np
import pandas as pd

from .. import xalgo
from ..model import PCA_DIM, add_text_pca
from . import evaluate as ev
from .features import ACTIONS, CAT, NUM, TARGETS, build
from .model import MEMBERS, OUT, TXT, _cats, _matrix, load

HIST_COLS = ["tweet_id", "username", "author", "created_at", "text", "article_title", "is_quote", "is_long_form",
             "is_reply", "is_retweet", "is_thread", "media_count", "first_url", "author_followers",
             "profile_followers", "author_segment", "view_count", "like_count", "reply_count", "retweet_count",
             "quote_count", "bookmark_count"]
SERVE_MEMBERS = ["L1_lgbm"]      # replaced by the backtest's keep/drop decision (data/model/forecast/meta.json)
CAL_DAYS = 14


# ------------------------------------------------------------------ fitting
def _fit_member(name: str, train: pd.DataFrame, target: str, feats: list[str]):
    """Fit one member and return a callable test_df -> {q: array}; models are saved by `train_final`."""
    if name == "L1_lgbm":
        import lightgbm as lgb
        from .model import LGB_PARAMS
        cats = _cats(train, feats)
        boosters = {q: lgb.train({**LGB_PARAMS, "objective": "quantile", "alpha": q},
                                 lgb.Dataset(_matrix(train, feats, cats), train[f"y_{target}"]), num_boost_round=600)
                    for q in ev.QUANTILES}
        return {"kind": "lgbm", "boosters": boosters, "cats": cats, "feats": feats}
    if name == "L1_catboost":
        from catboost import CatBoostRegressor, Pool
        cat_cols = [c for c in feats if c in CAT]
        X = train[feats].copy()
        for c in cat_cols:
            X[c] = X[c].astype(str)
        m = CatBoostRegressor(loss_function="MultiQuantile:alpha=0.1,0.5,0.9", iterations=800, depth=6,
                              learning_rate=0.06, random_seed=0, verbose=False, thread_count=-1)
        m.fit(Pool(X, train[f"y_{target}"], cat_features=cat_cols))
        return {"kind": "catboost", "model": m, "feats": feats, "cat_cols": cat_cols}
    raise ValueError(f"member {name} can't be served yet")


def _predict_member(fm: dict, d: pd.DataFrame) -> dict:
    if fm["kind"] == "lgbm":
        X = _matrix(d, fm["feats"], fm["cats"])
        return {q: b.predict(X) for q, b in fm["boosters"].items()}
    from catboost import Pool
    X = d[fm["feats"]].copy()
    for c in fm["cat_cols"]:
        X[c] = X[c].astype(str)
    P = np.asarray(fm["model"].predict(Pool(X, cat_features=fm["cat_cols"])))
    return {0.1: P[:, 0], 0.5: P[:, 1], 0.9: P[:, 2]}


def train_final(con, members: list[str] | None = None, shrink_k: float = 10.0) -> dict:
    """Fit, calibrate and save. Returns the calibration report (coverage on the late calibration half)."""
    from scipy.optimize import nnls
    members = members or SERVE_MEMBERS
    df = load(con)
    end = df.ts.max()
    cal_start = end - pd.Timedelta(days=CAL_DAYS)
    train_mask = df.ts < cal_start - pd.Timedelta(days=2)
    cal_mask = df.ts >= cal_start
    df, pca = add_text_pca(con, df, fit_mask=train_mask)
    train, cal = df[train_mask], df[cal_mask].copy()
    mid = cal.ts.median()
    early, late = cal[cal.ts < mid], cal[cal.ts >= mid]
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {"members": members, "targets": {}, "trained_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "train_end": str(cal_start - pd.Timedelta(days=2)), "cal_start": str(cal_start), "cal_end": str(end),
            "n_train": int(train_mask.sum()), "n_cal": int(cal_mask.sum()), "x_algo_commit": xalgo.X_ALGO_COMMIT}
    for t in TARGETS:
        fitted = {m: _fit_member(m, train, t, MEMBERS[m].features()) for m in members}
        preds = {m: _predict_member(fm, cal) for m, fm in fitted.items()}
        e_idx, l_idx = (cal.ts < mid).to_numpy(), (cal.ts >= mid).to_numpy()
        weights = {}
        for q in ev.QUANTILES:
            A = np.column_stack([preds[m][q] for m in members])
            if len(members) > 1:
                coef, _ = nnls(A[e_idx], cal[f"y_{t}"].to_numpy()[e_idx])
                coef = coef / coef.sum() if coef.sum() > 0 else np.full(len(members), 1 / len(members))
            else:
                coef = np.ones(1)
            weights[q] = coef.tolist()
        blend = {q: np.column_stack([preds[m][q] for m in members]) @ np.array(weights[q]) for q in ev.QUANTILES}
        res = cal[f"y_{t}"].to_numpy() - blend[0.5]
        r = pd.DataFrame({"a": cal.author.to_numpy()[e_idx], "r": res[e_idx]}).groupby("a").r.agg(["mean", "count"])
        shift_map = (r["mean"] * r["count"] / (r["count"] + shrink_k)).round(4).to_dict()
        shift = cal.author.map(shift_map).fillna(0).to_numpy()
        y_l = cal[f"y_{t}"].to_numpy()[l_idx]
        lo_l, hi_l = (blend[0.1] + shift)[l_idx], (blend[0.9] + shift)[l_idx]
        off = ev.cqr_offset(y_l, lo_l, hi_l)
        meta["targets"][t] = {"weights": {str(q): w for q, w in weights.items()}, "cqr_offset": off,
                              "shrink": shift_map, "aci_scores": np.maximum(lo_l - y_l, y_l - hi_l).round(4).tolist(),
                              "late_cal_coverage": ev.coverage(y_l, lo_l - off, hi_l + off)}
        for m, fm in fitted.items():
            if fm["kind"] == "lgbm":
                for q, b in fm["boosters"].items():     # gzipped text: ~5x smaller in git
                    with gzip.open(OUT / f"{t}__{m}__q{int(q * 100)}.txt.gz", "wt", encoding="utf-8") as fh:
                        fh.write(b.model_to_string())
                meta["targets"][t].setdefault("cats", {})[m] = fm["cats"]
            else:
                fm["model"].save_model(str(OUT / f"{t}__{m}.cbm"))
        meta["targets"][t]["feats"] = {m: fm["feats"] for m, fm in fitted.items()}
        print(f"{t}: trained; range offset {off:+.3f} (log)", flush=True)
    (OUT / "pca.pkl").write_bytes(pickle.dumps(pca))
    (OUT / "meta.json").write_text(json.dumps(meta))
    return {t: v["late_cal_coverage"] for t, v in meta["targets"].items()}


# ------------------------------------------------------------------ scoring
_CACHE: dict = {}


def _load():
    if "meta" not in _CACHE:
        import lightgbm as lgb
        meta = json.loads((OUT / "meta.json").read_text())
        models = {}
        for t, tm in meta["targets"].items():
            for m in meta["members"]:
                if (OUT / f"{t}__{m}__q50.txt.gz").exists():
                    def _b(q):
                        with gzip.open(OUT / f"{t}__{m}__q{int(q * 100)}.txt.gz", "rt", encoding="utf-8") as fh:
                            return lgb.Booster(model_str=fh.read())
                    models[(t, m)] = {"kind": "lgbm", "cats": tm["cats"][m], "feats": tm["feats"][m],
                                      "boosters": {q: _b(q) for q in ev.QUANTILES}}
                elif (OUT / f"{t}__{m}.cbm").exists():
                    from catboost import CatBoostRegressor
                    cb = CatBoostRegressor()
                    cb.load_model(str(OUT / f"{t}__{m}.cbm"))
                    models[(t, m)] = {"kind": "catboost", "model": cb, "feats": tm["feats"][m],
                                      "cat_cols": [c for c in tm["feats"][m] if c in CAT]}
        aci = json.loads((OUT / "aci.json").read_text()) if (OUT / "aci.json").exists() else {}
        _CACHE.update(meta=meta, models=models, pca=pickle.loads((OUT / "pca.pkl").read_bytes()), aci=aci)
    return _CACHE["meta"], _CACHE["models"], _CACHE["pca"]


def embed(texts: list[str]) -> np.ndarray:
    try:
        from fastembed import TextEmbedding
        if "fe" not in _CACHE:
            _CACHE["fe"] = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        v = np.array(list(_CACHE["fe"].embed(texts)))
    except ImportError:
        from ..segments import _model
        v = _model().encode(texts, normalize_embeddings=True)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def client_history(con, client: str, before: pd.Timestamp, n: int = 80) -> pd.DataFrame:
    """The client's latest original posts before `before`, with the columns `build` needs."""
    return con.execute("""
        WITH self_replies AS (SELECT DISTINCT reply_to_tweet_id tid FROM tweets
                              WHERE is_reply AND lower(in_reply_to_username) = lower(username))
        SELECT t.*, lower(t.username) AS author, t.tweet_id IN (SELECT tid FROM self_replies) AS is_thread,
               p.followers_count AS profile_followers, s.segment AS author_segment
        FROM tweets t LEFT JOIN profiles p ON p.handle = lower(t.username)
        LEFT JOIN account_segments s ON s.username = lower(t.username)
        WHERE lower(t.username) = lower(?) AND NOT coalesce(t.is_reply, false) AND NOT coalesce(t.is_retweet, false)
          AND t.created_at < ?
        ORDER BY t.created_at DESC LIMIT ?""", [client, before.to_pydatetime(), n]).df().iloc[::-1]


def draft_row(hist: pd.DataFrame, text: str, when: pd.Timestamp, fmt: str | None, has_media: bool,
              article_title: str | None) -> pd.DataFrame:
    d = hist.iloc[[-1]].copy()
    d["tweet_id"], d["created_at"], d["text"], d["article_title"] = "draft", when, text, article_title
    d["is_quote"] = fmt == "quote post"
    d["is_long_form"] = len(text) > 280 or fmt == "long-form post"
    d["is_thread"] = fmt == "thread"
    d["media_count"] = 1 if has_media else 0
    d["first_url"] = "x" if "http" in text else None
    for c in ("view_count", "like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"):
        d[c] = 0
    return d


def predict(hist: pd.DataFrame, client: str, text: str, when=None, fmt: str | None = None,
            has_media: bool = False, article_title: str | None = None) -> dict:
    """Forecast every X action for a draft: expected value, 80% range, the client's usual, and the X score."""
    meta, models, pca = _load()
    when = pd.Timestamp(when, tz="UTC") if when is not None and pd.Timestamp(when).tzinfo is None else \
        (pd.Timestamp(when) if when is not None else pd.Timestamp.now(tz="UTC"))
    hist = hist[pd.to_datetime(hist.created_at, utc=True) < when]
    if len(hist) < 5:
        raise ValueError(f"@{client} has fewer than 5 earlier posts; no usual level yet")
    rows = pd.concat([hist[[c for c in HIST_COLS if c in hist.columns]],
                      draft_row(hist, text, when, fmt, has_media, article_title)], ignore_index=True)
    rows["author"] = client.lower()
    f = build(rows)
    f = f[f.tweet_id == "draft"]
    if f.empty:
        raise ValueError(f"@{client} needs at least 5 posts that are 48h+ old for a usual level")
    P = pca.transform(embed([(article_title or "") + " " + text]))
    for i in range(PCA_DIM):
        f[f"txt{i}"] = P[0, i]
    out = {"client": client, "when_utc": when.isoformat(), "format": f.format.iloc[0], "hook": f.hook.iloc[0],
           "day_position": int(f.day_position.iloc[0]), "actions": {}, "model_trained_at": meta["trained_at"]}
    for t in TARGETS:
        tm = meta["targets"][t]
        preds = [ _predict_member(models[(t, m)], f) for m in meta["members"] if (t, m) in models]
        q = {qq: float(np.dot([p[qq][0] for p in preds], tm["weights"][str(qq)])) for qq in ev.QUANTILES}
        shift = tm["shrink"].get(client.lower(), 0.0)
        off = tm["cqr_offset"]
        aci = _CACHE.get("aci", {}).get(t)
        if aci and tm.get("aci_scores"):              # live record says the ranges drifted: adapt their width
            off = float(np.quantile(tm["aci_scores"], min(max(1 - aci["alpha"], 0.0), 1.0)))
        lo, mid, hi = q[0.1] + shift - off, q[0.5] + shift, q[0.9] + shift + off
        usual = float(np.expm1(f[f"lb_{t}"].iloc[0]))
        out["actions"][t] = {"expected": float(np.expm1(mid)), "low": float(max(np.expm1(lo), 0)),
                             "high": float(np.expm1(hi)), "usual": usual,
                             "vs_usual": float(np.expm1(mid) / usual) if usual > 0 else None}
    out["drivers"] = drivers(models, meta, f)
    out["x_rules"] = xalgo.reasons(out["day_position"], None, "http" in text)
    return out


DRAFT_FEATURES = {"text content": "what the text says", "format": "format", "hook": "opening line",
                  "n_chars": "length", "n_lines": "line breaks", "has_media": "image/video", "has_link": "link",
                  "n_mentions": "@mentions", "n_hashtags": "hashtags", "has_question": "question",
                  "has_cta": "call to action", "hour": "posting hour", "weekday": "weekday",
                  "day_position": "posts earlier that day", "day_decay": "posts earlier that day",
                  "log_gap_h": "time since last post"}


def drivers(models: dict, meta: dict, f: pd.DataFrame, k: int = 5) -> list[tuple[str, str, int]]:
    """Top reasons for the views estimate (SHAP contributions of the median LightGBM model)."""
    m = models.get(("views", "L1_lgbm"))
    if m is None:
        return []
    X = _matrix(f, m["feats"], m["cats"])
    c = m["boosters"][0.5].predict(X, pred_contrib=True)[0][:-1]
    s = pd.Series(c, index=X.columns)
    s = s.groupby(lambda n: "text content" if n.startswith("txt") else n).sum()
    s = s[[n for n in s.index if n in DRAFT_FEATURES]]     # only what the writer controls, not the author's stats
    top = s.reindex(s.abs().sort_values(ascending=False).index).head(k)
    return [(DRAFT_FEATURES[n], "raises" if v > 0 else "lowers", int(round((np.exp(abs(v)) - 1) * 100)))
            for n, v in top.items()]
