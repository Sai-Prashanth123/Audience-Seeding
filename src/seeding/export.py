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
    con.execute("""CREATE TABLE dash.account_segments AS
        SELECT * EXCLUDE (n_posts), n_posts FROM account_segments WHERE segment <> 'none'""")
    for t in ("core_accounts", "seed_map", "post_perf", "live_preds"):
        if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [t]).fetchone()[0]:
            con.execute(f"CREATE TABLE dash.{t} AS SELECT * FROM {t}")
    con.execute("""CREATE TABLE dash.profiles AS
        SELECT handle, description, followers_count FROM profiles
        WHERE handle IN (SELECT username FROM dash.account_segments)
           OR handle IN (SELECT username FROM main.core_accounts)""")
    counts = {r[0]: con.execute(f"SELECT count(*) FROM dash.{r[0]}").fetchone()[0]
              for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'dash'").fetchall()}
    con.execute("DETACH dash")
    return counts
