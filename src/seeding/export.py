"""Small results-only database for the deployed dashboard (data/dashboard.duckdb).

No raw posts and no embeddings, only what the dashboard shows: KPIs, segment labels with
public profile fields, core accounts, seed maps, interaction counts. It is committed to
the (private) repo so Streamlit Cloud can read it.
"""

from __future__ import annotations

import duckdb

from .store import ROOT

OUT = ROOT / "data" / "dashboard.duckdb"


def export_dashboard(con: duckdb.DuckDBPyConnection) -> dict[str, int]:
    OUT.unlink(missing_ok=True)
    con.execute(f"ATTACH '{OUT.as_posix()}' AS dash")
    con.execute("""CREATE TABLE dash.kpis AS SELECT
        (SELECT count(*) FROM tweets) AS posts,
        (SELECT count(DISTINCT lower(username)) FROM tweets) AS authors,
        (SELECT count(*) FROM profiles) AS profiles,
        (SELECT count(description) FROM profiles) AS bios,
        (SELECT max(created_at) FROM tweets) AS newest""")
    con.execute("CREATE TABLE dash.edges_summary AS SELECT kind, count(*) AS n FROM edges GROUP BY 1")
    # profiles: only accounts the dashboard can show (labelled, core or seed)
    # all accounts (incl. 'none'): the live model needs every author's segment, and CI rebuilds from this
    con.execute("CREATE TABLE dash.account_segments AS SELECT * FROM account_segments")
    for t in ("core_accounts", "seed_map", "post_perf", "live_preds", "engage_list", "engage_coverage",
              "track_weekly", "track_replies", "track_reply_back",
              "seed_map_holdout", "holdout_detail", "backtest_preds", "pipeline_runs", "proof",
              "trust_checks", "content_ci", "engage_ai", "pattern_memory", "pattern_history", "learning_mode",
              "live_surprises"):
        if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [t]).fetchone()[0]:
            # backtest_preds: numbers only (no post text) - proof needs y and the three predictions
            cols = ("author, tweet_id, created_at, y, pred_A, pred_B, pred_model" if t == "backtest_preds" else "*")
            con.execute(f"CREATE TABLE dash.{t} AS SELECT {cols} FROM {t}")
    con.execute("""CREATE TABLE dash.profiles AS
        SELECT handle, description, followers_count FROM profiles
        WHERE handle IN (SELECT username FROM dash.account_segments)
           OR handle IN (SELECT username FROM main.core_accounts)""")
    counts = {r[0]: con.execute(f"SELECT count(*) FROM dash.{r[0]}").fetchone()[0]
              for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'dash'").fetchall()}
    con.execute("DETACH dash")
    return counts
