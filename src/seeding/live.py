"""1D live forward test: predictions made before the outcome is known, checked 48h later.

`seeding live` (run at least daily): pulls fresh posts, and for every pilot-client original
post that is still young (< max_age_h) and not yet scored, scores it with only what was
known before it went out (earlier posts, same-day count, text, format) and stores the
prediction with a timestamp. `seeding live-eval` compares predictions with the posts'
actual X-weighted score once they are 48h old and writes reports/1D_live.md.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd

from .content import X_WEIGHTS
from .predict import score_draft
from .seedmap import ROOT, load_config

DDL = """CREATE TABLE IF NOT EXISTS live_preds (
    tweet_id VARCHAR PRIMARY KEY, client VARCHAR, created_at TIMESTAMPTZ, scored_at TIMESTAMPTZ,
    age_at_scoring_h DOUBLE, format VARCHAR, hook VARCHAR, expected_xscore DOUBLE, usual_xscore DOUBLE,
    expected_vs_usual DOUBLE)"""


def score_new(con: duckdb.DuckDBPyConnection, max_age_h: float = 24) -> int:
    con.execute(DDL)
    clients = load_config()["pilot_clients"]
    new = con.execute(f"""
        SELECT tweet_id, username, created_at, text, article_title, is_quote, media_count,
               (SELECT count(*) > 0 FROM tweets r WHERE r.reply_to_tweet_id = t.tweet_id
                  AND lower(r.username) = lower(t.username)) AS is_thread
        FROM tweets t
        WHERE lower(username) IN (SELECT lower(unnest(?::VARCHAR[])))
          AND NOT coalesce(is_reply, false) AND NOT coalesce(is_retweet, false)
          AND created_at >= now() - INTERVAL {int(max_age_h * 60)} MINUTE
          AND tweet_id NOT IN (SELECT tweet_id FROM live_preds)""", [clients]).df()
    now = pd.Timestamp.now(tz="UTC")
    for r in new.itertuples():
        fmt = "article" if isinstance(r.article_title, str) else "thread" if r.is_thread else \
              "quote post" if r.is_quote else None
        res = score_draft(con, r.username, r.text or "", pd.Timestamp(r.created_at).isoformat(), fmt,
                          has_media=(r.media_count or 0) > 0, is_quote=bool(r.is_quote),
                          article_title=r.article_title if isinstance(r.article_title, str) else None)
        age = (now - pd.Timestamp(r.created_at)).total_seconds() / 3600
        con.execute("INSERT INTO live_preds VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [r.tweet_id, r.username.lower(), r.created_at, now.to_pydatetime(), age, res["format"],
                     res["hook"], res["expected_xscore"], res["usual_xscore"], res["vs_usual"]])
    return len(new)


def evaluate(con: duckdb.DuckDBPyConnection, min_age_h: int = 48):
    from scipy.stats import spearmanr

    con.execute(DDL)
    w = " + ".join(f"coalesce(t.{c}, 0) * {v}" for c, v in X_WEIGHTS.items())
    df = con.execute(f"""
        SELECT p.*, {w} AS actual_xscore, t.url, left(t.text, 120) AS text
        FROM live_preds p JOIN tweets t USING (tweet_id)
        WHERE p.created_at <= now() - INTERVAL {min_age_h} HOUR""").df()
    lines = ["# 1D · Live forward test", "",
             "Each pilot-client post was scored **within its first hours, before its outcome was known**, using only "
             "earlier posts. Compared here with its actual X-weighted score once at least 48h old.", ""]
    if df.empty:
        lines.append("No predictions old enough yet. Keep `seeding live` running daily; results appear after 48h.")
    else:
        df["actual_vs_usual"] = df.actual_xscore / df.usual_xscore.where(df.usual_xscore > 0)
        rows = ["| client | posts | Spearman (expected vs actual, vs usual) | predicted above usual → was above usual |",
                "|---|---:|---:|---:|"]
        for c, g in df.groupby("client"):
            rho = spearmanr(g.expected_vs_usual, g.actual_vs_usual).statistic if len(g) >= 4 else np.nan
            up = g[g.expected_vs_usual > 1]
            hit = (up.actual_vs_usual > 1).mean() if len(up) else np.nan
            rows.append(f"| {c} | {len(g)} | {'—' if pd.isna(rho) else f'{rho:.2f}'} | "
                        f"{'—' if pd.isna(hit) else f'{hit:.0%} of {len(up)}'} |")
        lines += rows + ["", f"{len(df)} posts evaluated so far ({df.created_at.min():%d %b} – "
                         f"{df.created_at.max():%d %b}). The plan runs this for two weeks before judging it.", ""]
        df.to_csv(ROOT / "reports" / "1D_live.csv", index=False, encoding="utf-8-sig")
    path = ROOT / "reports" / "1D_live.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
