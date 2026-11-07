"""Step 1B: core accounts per niche -> their interactions -> scored seed map.

Core accounts are the niche's hubs: confidently in the segment (main or second), and
engaged with by many *distinct* accounts in the corpus. Their replies, quotes and
retweets (collected with user-tweets-bulk) point at the people the niche talks to;
those people, scored, are the seed map.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "segments.yaml").read_text(encoding="utf-8"))


# Engagement-bait phrasing. Measured 2026-11-07: hype/farm accounts 0.26-0.80 of original
# posts, real builders and operators 0.00-0.12 (coldemailchris 0.06, robwalling 0.01).
BAIT_PATTERN = (r"(?i)(holy (f|sh)|f\*+c?k|insane|goldmine|dangerous|game.?changer|just dropped|"
                r"you.?re (still|missing)|nobody (is talking|tells)|rip \w+|bookmark (this|it)|"
                r"100% free|for free\W|🚨|🤯|leaked)")


def bait_factor(bait_share: pd.Series, free: float = 0.12, slope: float = 4.0) -> pd.Series:
    """1.0 up to `free` bait share, then falls linearly; floor 0.1. Unknown share -> 1.0."""
    return (1 - slope * (bait_share.fillna(0) - free).clip(lower=0)).clip(0.1, 1.0)


def account_bait(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"""
        SELECT lower(username) AS username,
               avg(CASE WHEN regexp_matches(text, '{BAIT_PATTERN}') THEN 1 ELSE 0 END) AS bait_share
        FROM tweets WHERE NOT coalesce(is_retweet, false) AND NOT coalesce(is_reply, false)
        GROUP BY 1 HAVING count(*) >= 3""").df()


def account_stats(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per account: segment probabilities, followers, distinct in/out interaction partners."""
    return con.execute("""
        WITH indeg AS (SELECT dst AS u, count(DISTINCT src) AS in_accounts, count(*) AS in_edges
                       FROM edges GROUP BY 1),
             outdeg AS (SELECT src AS u, count(DISTINCT dst) AS out_accounts, count(*) AS out_edges
                        FROM edges GROUP BY 1)
        SELECT s.*, p.followers_count, p.description AS bio,
               coalesce(i.in_accounts, 0) in_accounts, coalesce(i.in_edges, 0) in_edges,
               coalesce(o.out_accounts, 0) out_accounts, coalesce(o.out_edges, 0) out_edges
        FROM account_segments s
        LEFT JOIN profiles p ON p.handle = s.username
        LEFT JOIN indeg i ON i.u = s.username
        LEFT JOIN outdeg o ON o.u = s.username
    """).df()


def pick_core(con: duckdb.DuckDBPyConnection, per_segment: int = 150,
              min_followers: int = 2_000, max_followers: int = 2_000_000) -> pd.DataFrame:
    """Top hubs per segment. An account can be core for two segments (main + second)."""
    cfg = load_config()
    st = account_stats(con).merge(account_bait(con), on="username", how="left")
    st["bait_factor"] = bait_factor(st.bait_share)
    clients = {h.lower() for h in cfg["client_segments"]}
    rows = []
    for seg in cfg["segments"]:
        # distinct engagers who are themselves in this niche (main or second segment)
        niche_in = con.execute("""
            SELECT e.dst AS username, count(DISTINCT e.src) AS niche_in_accounts
            FROM edges e JOIN account_segments s ON s.username = e.src
            WHERE s.segment = ? OR s.also = ? GROUP BY 1""", [seg, seg]).df()
        in_seg = (st.segment == seg) | (st.also == seg)
        cand = st[in_seg & st.followers_count.between(min_followers, max_followers)].copy()
        cand = cand.merge(niche_in, on="username", how="left").fillna({"niche_in_accounts": 0})
        cand["p_seg"] = cand[f"p_{seg}"]
        cand["niche_share"] = cand.niche_in_accounts / cand.in_accounts.clip(lower=1)
        # hub score: niche certainty x how many niche accounts engage with them x reach
        cand["core_score"] = (cand.p_seg
                              * np.log1p(cand.niche_in_accounts)
                              * np.sqrt(cand.niche_share)
                              * np.log10(cand.followers_count.clip(lower=10))
                              * cand.bait_factor)
        cand["is_client"] = cand.username.isin(clients)
        top = cand.sort_values("core_score", ascending=False).head(per_segment)
        top = top.assign(core_segment=seg, core_rank=np.arange(1, len(top) + 1))
        rows.append(top)
    core = pd.concat(rows)
    cols = ["core_segment", "core_rank", "username", "segment", "also", "p_seg", "followers_count",
            "in_accounts", "niche_in_accounts", "niche_share", "out_accounts", "n_posts",
            "bait_share", "core_score", "is_client", "bio"]
    core = core[cols]
    con.execute("CREATE OR REPLACE TABLE core_accounts AS SELECT * FROM core")
    return core


def follower_band(f: pd.Series) -> pd.Series:
    """1.0 for 1k-200k followers; tapers to 0 at 50 and to 0.3 at 5M+. Unknown -> 0.5.

    Mid-size accounts are the ones that reply back and whose replies X weights as
    in-network conversation; mega accounts rarely engage with a client.
    """
    f = f.astype(float)
    low = np.clip((np.log10(f.clip(lower=1)) - np.log10(50)) / (3 - np.log10(50)), 0, 1)
    high = np.clip(1 - 0.7 * (np.log10(f.clip(lower=1)) - np.log10(2e5)) / (np.log10(5e6) - np.log10(2e5)), 0.3, 1)
    out = np.minimum(low, high)
    return pd.Series(np.where(f.isna(), 0.5, out), index=f.index)


def score_seeds(con: duckdb.DuckDBPyConnection, exclude_clients: bool = False) -> pd.DataFrame:
    """Score every account that interacts with a segment's core, in either direction.

    exclude_clients=True drops clients from the core and every edge touching a client,
    so the hold-out test cannot see the clients' own engagers.
    """
    cfg = load_config()
    w = cfg["seed_weights"]
    hl = cfg.get("seed_half_life_days", 30)
    prior = cfg.get("seed_unknown_niche_prior", 0.25)
    clients = sorted({h.lower() for h in cfg["client_segments"]})
    con.execute("CREATE OR REPLACE TEMP TABLE _clients AS SELECT unnest(?::VARCHAR[]) AS u", [clients])
    client_filter = ("AND e.src NOT IN (SELECT u FROM _clients) AND e.dst NOT IN (SELECT u FROM _clients)"
                     if exclude_clients else "")
    core_filter = "AND c.username NOT IN (SELECT u FROM _clients)" if exclude_clients else ""

    inter = con.execute(f"""
        WITH core AS (SELECT core_segment AS seg, username FROM core_accounts c WHERE true {core_filter}),
        both_dirs AS (
            SELECT c.seg, e.dst AS cand, c.username AS core, e.kind, e.created_at, 'out' AS dir
            FROM edges e JOIN core c ON e.src = c.username WHERE true {client_filter}
            UNION ALL
            SELECT c.seg, e.src AS cand, c.username AS core, e.kind, e.created_at, 'in' AS dir
            FROM edges e JOIN core c ON e.dst = c.username WHERE true {client_filter})
        SELECT seg, cand AS username,
               count(DISTINCT core) AS n_core,
               count(*) AS n_inter,
               sum(pow(0.5, date_diff('day', created_at, now()) / {hl})) AS w_inter,
               count(*) FILTER (WHERE dir = 'out') AS from_core,
               count(*) FILTER (WHERE dir = 'in') AS to_core,
               list(DISTINCT core ORDER BY core)[1:5] AS example_core
        FROM both_dirs WHERE cand IS NOT NULL GROUP BY 1, 2""").df()

    seg_p = con.execute("SELECT * FROM account_segments").df()
    prof = con.execute("SELECT handle AS username, followers_count, tweet_count, description AS bio FROM profiles").df()
    bait = account_bait(con)
    df = (inter.merge(seg_p[["username", "segment", "also", "p_ai", "p_b2b", "p_tech", "p_none"]],
                      on="username", how="left")
               .merge(prof, on="username", how="left")
               .merge(bait, on="username", how="left"))
    df["p_seg"] = [row.get(f"p_{row['seg']}") for _, row in df.iterrows()]
    df["known"] = df.p_seg.notna()
    df["p_seg"] = df.p_seg.fillna(prior)
    df = df[~df.username.isin(clients)]
    df = df[~(df.followers_count > cfg.get("seed_max_followers", 3_000_000))]
    # known off-topic accounts (model says 'none' and is sure) are dropped, not just scored down
    df = df[~((df.segment == "none") & (df.p_none >= 0.7))]

    df["seed_score"] = (
        w["core_accounts"] * np.log1p(df.n_core)
        + w["interactions"] * np.log1p(df.w_inter)
        + w["niche"] * df.p_seg
        + w["follower_band"] * follower_band(df.followers_count)
        + w["activity"] * np.log10(df.tweet_count.fillna(10).clip(lower=1)) / 5
    ) * bait_factor(df.bait_share)
    df = df.sort_values(["seg", "seed_score"], ascending=[True, False])
    df["rank"] = df.groupby("seg").cumcount() + 1
    df["reason"] = [
        f"{r.n_core} core accts ({r.from_core} from core, {r.to_core} to core); "
        f"niche p={r.p_seg:.2f}{'' if r.known else ' (prior)'}; "
        f"{'' if pd.isna(r.followers_count) else f'{int(r.followers_count):,} followers'}"
        for r in df.itertuples()]
    return df


def build_seed_map(con: duckdb.DuckDBPyConnection, exclude_clients: bool = False) -> pd.DataFrame:
    cfg = load_config()
    df = score_seeds(con, exclude_clients=exclude_clients)
    top = df[df["rank"] <= cfg.get("seeds_per_segment", 2000)]
    table = "seed_map_holdout" if exclude_clients else "seed_map"
    keep = ["seg", "rank", "username", "seed_score", "n_core", "n_inter", "from_core", "to_core",
            "p_seg", "known", "followers_count", "bait_share", "segment", "also", "reason", "bio"]
    out = top[keep]
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM out")
    return out
