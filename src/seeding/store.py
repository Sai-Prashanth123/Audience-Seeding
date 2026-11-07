"""Local DuckDB store. Raw pulls are kept as JSONL under data/raw so every number is re-derivable."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "seeding.duckdb"
RAW = ROOT / "data" / "raw"

TWEET_COLS = """
    tweet_id VARCHAR PRIMARY KEY, url VARCHAR, username VARCHAR, user_id VARCHAR,
    created_at TIMESTAMPTZ, text VARCHAR, lang VARCHAR,
    like_count BIGINT, reply_count BIGINT, retweet_count BIGINT, quote_count BIGINT,
    bookmark_count BIGINT, view_count BIGINT,
    is_reply BOOLEAN, is_quote BOOLEAN, is_retweet BOOLEAN, is_long_form BOOLEAN,
    article_title VARCHAR, reply_to_tweet_id VARCHAR, in_reply_to_user_id VARCHAR,
    in_reply_to_username VARCHAR, quoted_tweet_id VARCHAR, quoted_username VARCHAR,
    retweeted_tweet_id VARCHAR, retweeted_username VARCHAR, author_followers BIGINT,
    media_count INTEGER, first_url VARCHAR
"""


def connect() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"CREATE TABLE IF NOT EXISTS tweets ({TWEET_COLS})")
    return con


def write_raw(name: str, rows) -> Path:
    """Write rows to data/raw/<today>/<name>.jsonl and return the path."""
    d = RAW / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.jsonl"
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    print(f"wrote {n} rows -> {p}")
    return p


def load_tweets(con: duckdb.DuckDBPyConnection, path: Path) -> int:
    """Upsert a tweets JSONL file (newer pull wins: counts keep growing after posting)."""
    con.execute(
        f"""
        INSERT OR REPLACE INTO tweets BY NAME
        SELECT * FROM read_json(?, format='newline_delimited', columns={{
            {", ".join(f"'{c.split()[0]}': '{' '.join(c.split()[1:2])}'" for c in _cols())}
        }})
        """,
        [str(path)],
    )
    return con.execute("SELECT count(*) FROM tweets").fetchone()[0]


def load_profiles(con: duckdb.DuckDBPyConnection, csv_text: str) -> int:
    """Replace the profiles table from a /datasets/profiles CSV (kept under data/raw)."""
    d = RAW / date.today().isoformat()
    d.mkdir(parents=True, exist_ok=True)
    p = d / "profiles.csv"
    p.write_bytes(csv_text.encode("utf-8"))  # bios contain newlines; keep bytes as served
    import io

    import pandas as pd
    df = pd.read_csv(io.StringIO(csv_text), dtype={"user_id": str, "description": str,
                                                    "location": str, "website": str,
                                                    "account_created_at": str})
    df["handle"] = df["username"].str.lower()
    con.execute("CREATE OR REPLACE TABLE profiles AS SELECT * FROM df")
    return con.execute("SELECT count(*) FROM profiles").fetchone()[0]


def _cols() -> list[str]:
    return [c.strip().replace(" PRIMARY KEY", "") for c in TWEET_COLS.split(",") if c.strip()]


def mark_run(con: duckdb.DuckDBPyConnection, step: str) -> None:
    """Record when a pipeline step last finished (the freshness trust check reads this)."""
    # delete + insert instead of INSERT OR REPLACE: a copy restored from the snapshot (CREATE TABLE AS)
    # has no primary key, and must still work
    con.execute("CREATE TABLE IF NOT EXISTS pipeline_runs (step VARCHAR, finished_at TIMESTAMPTZ)")
    con.execute("DELETE FROM pipeline_runs WHERE step = ?", [step])
    con.execute("INSERT INTO pipeline_runs VALUES (?, now())", [step])
