"""Google Colab bridge: the GPU-heavy members train on Colab's free GPU, then come back here to be judged.

  export   `seeding export-training` writes data/colab/train_posts.parquet: every post with its text, author,
           time, targets (log1p of each action), the strict usual levels (lb_*), and the fold each post belongs
           to in the backtest (split = train / cal / test per fold). Colab never decides the split, so it can't
           peek at test posts.
  notebook notebooks/colab_train.ipynb fine-tunes a sentence-transformer per fold to predict how much a post beats
           its author's usual views (y - lb), and writes data/colab/text_ft_preds.parquet (fold, tweet_id, target,
           ft_pred) for the cal and test posts of each fold, trained only on that fold's train posts.
  judge    member "L1_lgbm_textft" = LightGBM with that prediction as an extra feature; it goes through the same
           backtest and keep/drop rule as every other member.
"""

from __future__ import annotations

import pandas as pd

from ..seedmap import ROOT
from . import evaluate as ev
from .features import TARGETS

DIR = ROOT / "data" / "colab"
EXPORT = DIR / "train_posts.parquet"
PREDS = DIR / "text_ft_preds.parquet"
FOLDS = DIR / "folds.json"


def export(df: pd.DataFrame, n_folds: int = 4) -> str:
    folds = ev.rolling_folds(df.ts, n_folds=n_folds)
    cols = ["tweet_id", "author", "ts", "text", "article_title", "format"] + [f"y_{t}" for t in TARGETS] + \
           [f"lb_{t}" for t in TARGETS]
    out = df[cols].copy()
    out["text"] = (out.article_title.fillna("") + " " + out.text.fillna("")).str.replace(r"https?://\S+", "",
                                                                                         regex=True).str.strip()
    for k, f in enumerate(folds, start=1):
        out[f"fold{k}"] = "none"
        out.loc[out.ts < f.cal_start - pd.Timedelta(days=2), f"fold{k}"] = "train"
        out.loc[(out.ts >= f.cal_start) & (out.ts < f.test_start), f"fold{k}"] = "cal"
        out.loc[(out.ts >= f.test_start) & (out.ts < f.test_end), f"fold{k}"] = "test"
    DIR.mkdir(parents=True, exist_ok=True)
    out.drop(columns=["article_title"]).to_parquet(EXPORT, index=False)
    import json
    FOLDS.write_text(json.dumps([[str(f.cal_start), str(f.test_start), str(f.test_end)] for f in folds]))
    return str(EXPORT)


def frozen_folds() -> list | None:
    """The fold dates the Colab export used: the backtest must use the same ones, or Colab may have trained on a
    post the backtest tests on."""
    import json
    if not FOLDS.exists():
        return None
    return [ev.Fold(*(pd.Timestamp(x) for x in f)) for f in json.loads(FOLDS.read_text())]


def load_preds() -> pd.DataFrame | None:
    return pd.read_parquet(PREDS) if PREDS.exists() else None


PANEL = DIR / "panel_prompts.parquet"
GRADES_OUT = DIR / "llm_grades.parquet"
PANEL_OUT = DIR / "panel_scores.parquet"


def export_panel(con, df: pd.DataFrame, clients: set[str], n_people: int = 20) -> str:
    """Persona prompts for every client post in the frozen calibration/test windows. Each panel is built only from
    interactions before the post (llm.build_panel), so the Colab panel can't see the post's own engagers."""
    import json

    from . import llm
    folds = frozen_folds()
    start = min(f.cal_start for f in folds)
    posts = df[df.author.isin(clients) & (df.ts >= start)].drop_duplicates("tweet_id")
    rows = []
    for r in posts.itertuples():
        people = llm.build_panel(con, r.author, r.ts, n=n_people)
        if people.empty:
            continue
        rows.append({"tweet_id": r.tweet_id, "client": r.author, "ts": r.ts,
                     "system": llm.PANEL_SYSTEM, "prompt": llm.panel_prompt(r.author, people, r.text or ""),
                     "people": json.dumps(people[["handle", "segment", "kind"]].fillna("").to_dict("records"))})
    out = pd.DataFrame(rows)
    out.to_parquet(PANEL, index=False)
    return str(PANEL)


def check_split(preds: pd.DataFrame, export: pd.DataFrame) -> pd.DataFrame:
    """Keep only Colab rows whose (fold, split) matches the frozen export; anything else would be leakage."""
    ok = []
    for k in sorted(preds.fold.unique()):
        e = export[["tweet_id", f"fold{k}"]].rename(columns={f"fold{k}": "split_export"})
        m = preds[preds.fold == k].merge(e, on="tweet_id", how="left")
        ok.append(m[m.split == m.split_export].drop(columns=["split_export"]))
    return pd.concat(ok, ignore_index=True) if ok else preds.iloc[:0]
