"""Frozen, append-only ledger: every prediction and every snapshot, kept in git.

Why git and not the pipeline database: the database lives in a GitHub Actions cache, and a
cancelled or failed run can save an older copy as the newest cache, silently rolling back rows.
That is how the 1D live test lost 4 of its 7 predictions. CSV files committed to git can't roll back,
and appending never rewrites a row that already exists, so a prediction can't be edited after its
result is known.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "data" / "ledger"

# file -> (columns, key columns that make a row unique)
SCHEMAS = {
    "predictions": (["pred_id", "kind", "client", "tweet_id", "post_created_at", "predicted_at", "age_at_pred_h",
                     "model", "action", "expected", "lo", "hi", "usual", "extra"],
                    ["pred_id"]),
    "snapshots": (["tweet_id", "client", "post_created_at", "seen_at", "age_h", "views", "likes", "replies",
                   "reposts", "quotes", "bookmarks", "source"],
                  ["tweet_id", "seen_at"]),
    "post_engagers": (["tweet_id", "client", "engager", "kind", "engager_tweet_id", "engaged_at", "seen_at"],
                      ["tweet_id", "engager_tweet_id"]),
}


def path(name: str) -> Path:
    return LEDGER / f"{name}.csv"


def load(name: str) -> pd.DataFrame:
    cols, _ = SCHEMAS[name]
    p = path(name)
    if not p.exists():
        return pd.DataFrame(columns=cols)
    return pd.read_csv(p, dtype=str, keep_default_na=False).reindex(columns=cols)


def append(name: str, rows: pd.DataFrame | list[dict]) -> int:
    """Append rows whose key is not in the file yet. Existing rows are never rewritten. Returns rows added."""
    cols, key = SCHEMAS[name]
    df = pd.DataFrame(rows).reindex(columns=cols)
    if df.empty:
        return 0
    df = df.astype(object).where(df.notna(), "").astype(str)
    old = load(name)
    seen = set(map(tuple, old[key].astype(str).values)) if len(old) else set()
    df = df.drop_duplicates(subset=key)
    df = df[[tuple(r) not in seen for r in df[key].values]]
    if df.empty:
        return 0
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    new_file = not p.exists()
    with p.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(cols)
        w.writerows(df[cols].values.tolist())
    return len(df)


def pred_id(kind: str, tweet_or_draft: str, model: str, action: str, horizon: str = "") -> str:
    """Stable id: one prediction per (kind, post, model, action, horizon). Re-running never duplicates it."""
    return hashlib.sha1("|".join([kind, tweet_or_draft, model, action, horizon]).encode()).hexdigest()[:16]


def extra(**kw) -> str:
    return json.dumps(kw, default=str, separators=(",", ":"))


def to_db(con) -> None:
    """Mirror the ledger into the database (read-only copies; git stays the source of truth)."""
    for name in SCHEMAS:
        df = load(name)  # noqa: F841 (used by duckdb)
        con.execute(f"CREATE OR REPLACE TABLE ledger_{name} AS SELECT * FROM df")
