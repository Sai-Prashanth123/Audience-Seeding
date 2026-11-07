"""Phase 2A: the daily "Engage today" list.

For each treatment client: watch the top seeds of the client's segment(s), collect what they
posted in the last day, and rank those posts by who wrote them (seed score), how fresh they
are, and how open they are to a reply. One post per account, ~20 per client. The team
writes and posts every reply by hand; nothing here posts anything.

Also refreshes the six Phase 2 clients' own replies, so tracking (2B) can see which listed
posts the client actually replied to.
"""

from __future__ import annotations

from datetime import date, timedelta

import duckdb
import numpy as np
import pandas as pd

from .seedmap import load_config

OPINION = ("i think", "unpopular", "hot take", "controversial", "most people", "everyone", "nobody", "stop ")


def openness(text: str) -> float:
    """0.4 base, +0.4 for a question, +0.2 for a take (same idea as xplatform reply-scan)."""
    t = (text or "").lower()
    return min(1.0, 0.4 + (0.4 if "?" in t else 0.0) + (0.2 if any(w in t for w in OPINION) else 0.0))


def client_pool(con: duckdb.DuckDBPyConnection, client: str, cfg: dict) -> pd.DataFrame:
    """Top seeds for one client: its segments' seed maps, best rank first, clients excluded."""
    segs = cfg["client_segments"][client]
    clients = {h.lower() for h in cfg["client_segments"]} | {h.lower() for h in cfg["phase2"].get("exclude", [])}
    n = cfg["phase2"]["pool_per_client"]
    sm = con.execute("""SELECT seg, username, rank, seed_score, n_core FROM seed_map
                        WHERE seg IN (SELECT unnest(?::VARCHAR[])) ORDER BY rank""", [segs]).df()
    sm = sm[~sm.username.isin(clients)]
    # an account in two of the client's segments keeps its best rank
    sm = sm.sort_values("rank").drop_duplicates("username").head(n)
    sm["client"] = client
    return sm


def rank_candidates(posts: pd.DataFrame, pool: pd.DataFrame, replied_tweet_ids: set[str], now: pd.Timestamp,
                    list_size: int = 20, max_age_h: float = 24, half_life_h: float = 6) -> pd.DataFrame:
    """Pure ranking: who (seed score) x freshness x openness; 1 post per account; skip replied."""
    if posts.empty or pool.empty:
        return pd.DataFrame()
    p = posts.copy()
    p["author"] = p.username.str.lower()
    p = p[p.author.isin(pool.username)]
    p = p[~p.is_reply.fillna(False).astype(bool) & ~p.is_retweet.fillna(False).astype(bool)]
    p = p[~p.tweet_id.astype(str).isin(replied_tweet_ids)]
    age_h = (now - pd.to_datetime(p.created_at, utc=True)).dt.total_seconds() / 3600
    p = p.assign(age_h=age_h)
    p = p[(p.age_h >= 0) & (p.age_h <= max_age_h)]
    if p.empty:
        return pd.DataFrame()
    p = p.merge(pool[["username", "seg", "seed_score", "n_core", "rank"]], left_on="author", right_on="username")
    top_seed = pool.seed_score.max()
    p["who"] = p.seed_score / top_seed if top_seed else 0
    p["fresh"] = 0.5 ** (p.age_h / half_life_h)
    p["open"] = p.text.map(openness)
    # topic fit: is this post about what the client talks about? (cosine vs the client's own posts;
    # MiniLM cosines for on-topic posts sit ~0.3-0.6, chit-chat ~0.0-0.15). Absent column -> neutral.
    rel = p["relevance"] if "relevance" in p.columns else pd.Series(0.5, index=p.index)
    p["topic"] = ((rel - 0.10) / 0.35).clip(0.05, 1.0)
    p["score"] = p.who * p.fresh * (0.5 + p.open) * p.topic
    p = p.sort_values("score", ascending=False).drop_duplicates("author").head(list_size)
    p["list_rank"] = np.arange(1, len(p) + 1)
    return p


def allocate(candidates: pd.DataFrame, list_size: int) -> pd.DataFrame:
    """Give each post to at most ONE client (the one it scores highest for), best scores first.

    Several clients replying to the same post on the same day looks coordinated (the pod pattern
    X treats as manipulation), so a post is never on two clients' lists.
    """
    if candidates.empty:
        return candidates
    c = candidates.sort_values("score", ascending=False)
    taken, counts, rows = set(), {}, []
    for r in c.itertuples(index=False):
        if r.tweet_id in taken or counts.get(r.client, 0) >= list_size:
            continue
        taken.add(r.tweet_id)
        counts[r.client] = counts.get(r.client, 0) + 1
        rows.append(r)
    out = pd.DataFrame(rows, columns=c.columns)
    out["list_rank"] = out.groupby("client").cumcount() + 1
    return out


def reason(r, client: str) -> str:
    seg = {"b2b": "B2B", "ai": "AI", "tech": "Tech"}.get(r.seg, r.seg)
    bits = [f"in @{client}'s {seg} seed map (#{int(r.rank)}, talks with {int(r.n_core)} niche hubs)",
            f"posted {r.age_h:.0f}h ago" if r.age_h >= 1 else "posted under an hour ago"]
    t = (r.text or "").lower()
    if getattr(r, "topic", 0.5) >= 0.6:
        bits.append("on a topic the client posts about")
    if "?" in t:
        bits.append("asks a question")
    elif any(w in t for w in OPINION):
        bits.append("shares a take you can respond to")
    return "; ".join(bits)


def build_lists(con: duckdb.DuckDBPyConnection, list_date: date | None = None,
                now: pd.Timestamp | None = None, size: int | None = None) -> pd.DataFrame:
    """Rank today's candidates; `size` per client (default list_size; the AI filter asks for 2x)."""
    cfg = load_config()
    p2 = cfg["phase2"]
    size = size or p2["list_size"]
    now = now or pd.Timestamp.now(tz="UTC")
    list_date = list_date or now.date()
    since = now - pd.Timedelta(hours=p2["max_age_hours"])
    posts = con.execute("""SELECT tweet_id, url, username, created_at, text, like_count, reply_count,
                                  is_reply, is_retweet
                           FROM tweets WHERE created_at >= ?""", [since.to_pydatetime()]).df()
    # only originals by watched seeds are candidates: filter before the (slow) embedding step
    watched = set(watch_list(con))
    posts = posts[posts.username.str.lower().isin(watched)
                  & ~posts.is_reply.fillna(False).astype(bool) & ~posts.is_retweet.fillna(False).astype(bool)]
    posts = add_relevance_inputs(posts.reset_index(drop=True))
    out = []
    for client in p2["treatment"]:
        pool = client_pool(con, client, cfg)
        replied = set(con.execute("""SELECT reply_to_tweet_id FROM tweets
                                     WHERE lower(username) = lower(?) AND reply_to_tweet_id IS NOT NULL""",
                                  [client]).df().reply_to_tweet_id.astype(str))
        cand = posts.assign(relevance=posts.vec.map(lambda v, c=client_centroid(con, client): float(v @ c))
                            if len(posts) else [])
        ranked = rank_candidates(cand.drop(columns="vec"), pool, replied, now, size * 3,
                                 p2["max_age_hours"], p2["freshness_half_life_hours"])
        if ranked.empty:
            continue
        ranked["reason"] = [reason(r, client) for r in ranked.itertuples()]
        ranked["client"] = client
        out.append(ranked)
    out = [allocate(pd.concat(out), size)] if out else []
    lst = pd.concat(out) if out else pd.DataFrame()
    con.execute("""CREATE TABLE IF NOT EXISTS engage_list (
        list_date DATE, client VARCHAR, list_rank INTEGER, tweet_id VARCHAR, url VARCHAR, author VARCHAR,
        seg VARCHAR, text VARCHAR, created_at TIMESTAMPTZ, score DOUBLE, reason VARCHAR, built_at TIMESTAMPTZ)""")
    con.execute("DELETE FROM engage_list WHERE list_date = ?", [list_date])
    if not lst.empty:
        lst = lst.assign(list_date=list_date, built_at=now)
        cols = ["list_date", "client", "list_rank", "tweet_id", "url", "author", "seg", "text", "created_at",
                "score", "reason", "built_at"]
        lst = lst[cols]
        con.execute("INSERT INTO engage_list SELECT * FROM lst")
    refresh_coverage(con)
    return lst


def watch_list(con: duckdb.DuckDBPyConnection) -> list[str]:
    cfg = load_config()
    names: set[str] = set()
    for c in cfg["phase2"]["treatment"]:
        names |= set(client_pool(con, c, cfg).username)
    return sorted(names)


def phase2_clients() -> list[str]:
    p2 = load_config()["phase2"]
    return list(p2["treatment"]) + list(p2["control"])


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def refresh_coverage(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Per list day and client: how many listed tweets the client actually replied to (any time later)."""
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='engage_list'").fetchall():
        return pd.DataFrame()
    con.execute("""CREATE OR REPLACE TABLE engage_coverage AS
        SELECT l.list_date, l.client, count(*) AS listed,
               count(DISTINCT r.reply_to_tweet_id) AS replied
        FROM engage_list l
        LEFT JOIN tweets r ON r.reply_to_tweet_id = l.tweet_id AND lower(r.username) = lower(l.client)
        GROUP BY 1, 2 ORDER BY 1, 2""")
    return con.execute("SELECT * FROM engage_coverage").df()


_MODEL = None


def _encode(texts: list[str]):
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    return _MODEL.encode([t[:1000] for t in texts], batch_size=256, normalize_embeddings=True,
                         show_progress_bar=False)


def add_relevance_inputs(posts: pd.DataFrame) -> pd.DataFrame:
    if posts.empty:
        return posts.assign(vec=[])
    clean = posts.text.fillna("").str.replace(r"https?://\S+", "", regex=True)
    return posts.assign(vec=list(_encode(clean.tolist())))


_CENTROIDS: dict[str, np.ndarray] = {}


def client_centroid(con: duckdb.DuckDBPyConnection, client: str, n: int = 150) -> np.ndarray:
    """Mean embedding of the client's own recent original posts: 'what this client talks about'."""
    if client not in _CENTROIDS:
        txt = con.execute("""SELECT coalesce(article_title, '') || ' ' || coalesce(text, '') t FROM tweets
                             WHERE lower(username) = lower(?) AND NOT coalesce(is_reply, false)
                               AND NOT coalesce(is_retweet, false)
                             ORDER BY created_at DESC LIMIT ?""", [client, n]).df().t
        v = _encode(txt.str.replace(r"https?://\S+", "", regex=True).tolist()).mean(axis=0)
        _CENTROIDS[client] = v / np.linalg.norm(v)
    return _CENTROIDS[client]


def apply_ai_filter(con: duckdb.DuckDBPyConnection, list_size: int, list_date: date | None = None) -> dict:
    """Drop today's candidates the AI reviewer judged not worth replying to, then keep the best
    `list_size` per client. Posts the AI could not judge (skipped) stay - never silently lost."""
    list_date = list_date or pd.Timestamp.now(tz="UTC").date()
    has_ai = bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='engage_ai'").fetchall())
    before = con.execute("SELECT count(*) FROM engage_list WHERE list_date = ?", [list_date]).fetchone()[0]
    dropped = 0
    if has_ai:
        dropped = con.execute("""SELECT count(*) FROM engage_list l JOIN engage_ai a USING (tweet_id)
                                 WHERE l.list_date = ? AND a.status = 'ok' AND NOT a.worth""", [list_date]).fetchone()[0]
        con.execute("""DELETE FROM engage_list WHERE list_date = ? AND tweet_id IN
                       (SELECT tweet_id FROM engage_ai WHERE status = 'ok' AND NOT worth)""", [list_date])
    con.execute("""CREATE OR REPLACE TEMP TABLE _kept AS
        SELECT * EXCLUDE (list_rank), row_number() OVER (PARTITION BY client ORDER BY list_rank) AS list_rank
        FROM engage_list WHERE list_date = ?""", [list_date])
    con.execute("DELETE FROM engage_list WHERE list_date = ?", [list_date])
    con.execute(f"""INSERT INTO engage_list BY NAME SELECT * FROM _kept WHERE list_rank <= {int(list_size)}""")
    after = con.execute("SELECT count(*) FROM engage_list WHERE list_date = ?", [list_date]).fetchone()[0]
    refresh_coverage(con)
    return {"candidates": before, "ai_said_skip": dropped, "kept": after}
