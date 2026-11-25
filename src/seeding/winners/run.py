"""Run the X Winners Engine end to end; every stage saves to data/winners/ so stages can be re-run alone."""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import analyze, anatomy, data
from .data import DIR

STAGES = ["data", "topics", "lifts", "bayes", "shap", "twins", "validate"]


def _save(name: str, df: pd.DataFrame) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DIR / f"{name}.parquet", index=False)


def _load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DIR / f"{name}.parquet")


def run(con, stages: list[str] | None = None, draws: int = 1000) -> dict:
    stages = stages or STAGES
    meta = json.loads((DIR / "meta.json").read_text()) if (DIR / "meta.json").exists() else {}
    t0 = time.time()
    if "data" in stages:
        df = anatomy.tag(data.build(con))
        vec = analyze.embed(df)
        np.save(DIR / "vectors.npy", vec)
        _save("posts", df.drop(columns=["created_at"], errors="ignore"))
        meta.update(built_at=pd.Timestamp.now(tz="UTC").isoformat(), posts=len(df),
                    client_posts=int(df.is_client.sum()),
                    range={a: [str(g.ts.min())[:10], str(g.ts.max())[:10]] for a, g in df[df.is_client].groupby("author")})
        print(f"data: {len(df)} posts ({int(df.is_client.sum())} client) in {time.time() - t0:.0f}s", flush=True)
    df = _load("posts")
    vec = np.load(DIR / "vectors.npy")
    if "topics" in stages:
        topic, table = analyze.topics(df, vec)
        df["topic"] = topic.to_numpy()
        _save("posts", df)
        _save("topics", table)
        print(f"topics: {len(table)} topics", flush=True)
    if "lifts" in stages:
        c = df[df.is_client]
        _save("lifts_client", analyze.lifts(c, ["author"]))
        _save("lifts_category", analyze.lifts(c, ["author", "category"], min_n=6))
        _save("lifts_peers", analyze.lifts(df[~df.is_client].assign(author="peers"), ["author"]))
        _save("lifts_peers_category", analyze.lifts(df[~df.is_client].assign(author="peers"), ["author", "category"]))
        print("lifts: done", flush=True)
    if "bayes" in stages:
        b = analyze.bayes(df, draws=draws, tune=draws)
        _save("bayes", b)
        meta["bayes"] = {"rhat_max": b.attrs["rhat_max"], "n": b.attrs["n"]}
        print(f"bayes: n={b.attrs['n']} r-hat max {b.attrs['rhat_max']:.3f} ({time.time() - t0:.0f}s)", flush=True)
        # per category (pooled across the three clients + peers) where there is enough data
        per = []
        for cat, g in df.groupby("category"):
            if g.is_client.sum() >= 40:
                bc = analyze.bayes(g.assign(category="Tweet"), draws=draws // 2, tune=draws // 2)
                per.append(bc.assign(category=cat))
                print(f"bayes {cat}: n={len(g)} r-hat {bc.attrs['rhat_max']:.3f}", flush=True)
        if per:
            _save("bayes_category", pd.concat(per, ignore_index=True))
    if "shap" in stages:
        main, inter = analyze.shap_lgbm(df)
        _save("shap_main", main)
        _save("shap_inter", inter)
        print("shap: done", flush=True)
    if "twins" in stages:
        t = analyze.twins(df, vec)
        _save("twins", t)
        _save("twin_summary", analyze.twin_summary(t) if len(t) else pd.DataFrame())
        print(f"twins: {len(t)} pairs", flush=True)
    if "validate" in stages:
        v = analyze.validate(df, fit_fn=lambda d: analyze.bayes(d, draws=draws // 2, tune=draws // 2))
        meta["validation"] = v
        print("validate:", json.dumps(v, indent=1), flush=True)
    (DIR / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    return meta
