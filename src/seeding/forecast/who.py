"""Who will react: rank the real people most likely to reply to or quote a draft. Free (no AI model per draft).

For a client and a draft, every candidate (people who replied to / quoted the client before, plus seed-map members
in the client's niche) gets a probability from a logistic model on:
  log_past      how often they engaged with this client before (log)
  recency       log days since their last engagement with the client (never = 400 days)
  past_90d      engagements in the 90 days before the post
  topic_fit     cosine between the draft's text vector and the mean vector of the person's own posts
  is_seed       in the client's seed map
The model is fitted on client posts before a cutoff and judged on later posts by recall@K (share of the real
repliers/quoters it named in its top K), against the baseline "most frequent past engagers first".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATS = ["log_past", "recency", "past_90d", "topic_fit", "is_seed"]
NEVER_DAYS = 400.0


def client_posts_with_engagers(con, clients: list[str]) -> pd.DataFrame:
    return con.execute("""
        WITH cp AS (SELECT tweet_id, lower(username) client, created_at FROM tweets
                    WHERE lower(username) IN (SELECT lower(unnest(?::VARCHAR[])))
                      AND NOT coalesce(is_reply, false) AND NOT coalesce(is_retweet, false))
        SELECT cp.tweet_id, cp.client, cp.created_at, lower(t.username) engager, t.created_at engaged_at
        FROM cp JOIN tweets t ON (t.reply_to_tweet_id = cp.tweet_id OR t.quoted_tweet_id = cp.tweet_id)
                             AND lower(t.username) <> cp.client""", [clients]).df()


def user_vectors(con, users: list[str]) -> dict:
    v = con.execute("""SELECT lower(username) u, vec FROM post_vecs
                       WHERE lower(username) IN (SELECT unnest(?::VARCHAR[]))""", [users]).df()
    out = {}
    for u, g in v.groupby("u"):
        m = np.mean(np.vstack(g.vec.to_numpy()), axis=0)
        out[u] = m / (np.linalg.norm(m) or 1)
    return out


def candidates(events: pd.DataFrame, seeds: set[str], client: str, before: pd.Timestamp) -> pd.DataFrame:
    """Every candidate for a post by `client` at `before`, with history features from engagements before it."""
    past = events[(events.client == client) & (events.engaged_at < before)]
    g = past.groupby("engager").engaged_at.agg(["count", "max"])
    recent = past[past.engaged_at >= before - pd.Timedelta(days=90)].groupby("engager").size()
    people = sorted(set(g.index) | seeds)
    c = pd.DataFrame({"engager": people})
    c["n_past"] = c.engager.map(g["count"]).fillna(0) if len(c) else pd.Series(dtype=float)
    c["log_past"] = np.log1p(c.n_past)
    last = c[["engager"]].merge(g["max"].rename("last").reset_index(), on="engager", how="left")["last"]
    days = (before - pd.to_datetime(last, utc=True)).dt.total_seconds() / 86400
    c["recency"] = np.log1p(days.fillna(NEVER_DAYS).clip(lower=0))
    c["past_90d"] = np.log1p(c.engager.map(recent).fillna(0))
    c["is_seed"] = c.engager.isin(seeds).astype(float)
    return c


def add_topic(c: pd.DataFrame, post_vec: np.ndarray | None, uvec: dict) -> pd.DataFrame:
    if post_vec is None:
        c["topic_fit"] = 0.0
        return c
    c["topic_fit"] = [float(uvec[u] @ post_vec) if u in uvec else 0.0 for u in c.engager]
    return c


def build_rows(con, events: pd.DataFrame, posts: pd.DataFrame, seeds_by_client: dict, uvec: dict,
               pvec: dict) -> pd.DataFrame:
    rows = []
    for r in posts.itertuples():
        c = candidates(events, seeds_by_client.get(r.client, set()), r.client, r.created_at)
        c = add_topic(c, pvec.get(r.tweet_id), uvec)
        actual = set(events[(events.tweet_id == r.tweet_id)].engager)
        c["y"] = c.engager.isin(actual).astype(int)
        c["tweet_id"], c["client"], c["n_actual"] = r.tweet_id, r.client, len(actual)
        rows.append(c)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def recall_at(rows: pd.DataFrame, score: str, k: int) -> float:
    """Share of all real engagers (who were candidates) that appear in each post's top k, pooled over posts."""
    hit, tot = 0, 0
    for _, g in rows.groupby("tweet_id"):
        tot += int(g.n_actual.iloc[0])
        hit += int(g.nlargest(k, score).y.sum())
    return hit / tot if tot else float("nan")


def backtest(con, clients: list[str], seeds_by_client: dict, cutoff: str = "2026-10-01") -> dict:
    """Fit on client posts before `cutoff`, judge on later posts. Returns recall@K for model and baseline."""
    from sklearn.linear_model import LogisticRegression
    events = client_posts_with_engagers(con, clients)
    events["created_at"] = pd.to_datetime(events.created_at, utc=True)
    events["engaged_at"] = pd.to_datetime(events.engaged_at, utc=True)
    posts = events.drop_duplicates("tweet_id")[["tweet_id", "client", "created_at"]]
    users = sorted(set(events.engager) | set().union(*seeds_by_client.values()) if seeds_by_client else set(events.engager))
    uvec = user_vectors(con, users)
    pv = con.execute("SELECT tweet_id, vec FROM post_vecs WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))",
                     [posts.tweet_id.tolist()]).df()
    pvec = {t: np.asarray(v) / (np.linalg.norm(v) or 1) for t, v in zip(pv.tweet_id, pv.vec)}
    cut = pd.Timestamp(cutoff, tz="UTC")
    train = build_rows(con, events, posts[posts.created_at < cut], seeds_by_client, uvec, pvec)
    test = build_rows(con, events, posts[posts.created_at >= cut], seeds_by_client, uvec, pvec)
    model = LogisticRegression(max_iter=2000, class_weight="balanced").fit(train[FEATS], train.y)
    test["p"] = model.predict_proba(test[FEATS])[:, 1]
    test["base"] = test.n_past + 1e-6 * -test.recency     # baseline: most frequent past engagers, recent first
    out = {"train_posts": int(train.tweet_id.nunique()), "test_posts": int(test.tweet_id.nunique()),
           "test_engagements": int(test.drop_duplicates("tweet_id").n_actual.sum()),
           "engagers_who_were_candidates": float(test.y.sum() / max(test.drop_duplicates("tweet_id").n_actual.sum(), 1)),
           "coef": dict(zip(FEATS, np.round(model.coef_[0], 3)))}
    for k in (10, 20, 50):
        out[f"recall@{k}"] = recall_at(test, "p", k)
        out[f"baseline_recall@{k}"] = recall_at(test, "base", k)
    # significance: bootstrap over posts of (model hits - baseline hits) / real engagers, at k = 20
    per = test.groupby("tweet_id").apply(lambda g: pd.Series({
        "m": g.nlargest(20, "p").y.sum(), "b": g.nlargest(20, "base").y.sum(), "n": g.n_actual.iloc[0]}))
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(per), size=(2000, len(per)))
    d = (per.m.to_numpy()[idx].sum(1) - per.b.to_numpy()[idx].sum(1)) / per.n.to_numpy()[idx].sum(1)
    out["gain@20"], out["gain@20_lo"], out["gain@20_hi"] = (float((per.m.sum() - per.b.sum()) / per.n.sum()),
                                                             *map(float, np.percentile(d, [2.5, 97.5])))
    return out, model


# ------------------------------------------------------------------ serving
def candidate_table(con, clients: list[str], seeds_by_client: dict, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Per client: every candidate with history counts, niche and their mean text vector (for the online app)."""
    now = now or pd.Timestamp.now(tz="UTC")
    events = client_posts_with_engagers(con, clients)
    events["engaged_at"] = pd.to_datetime(events.engaged_at, utc=True)
    events = events[events.engaged_at >= now - pd.Timedelta(days=365)]
    rows = []
    for c in clients:
        cand = candidates(events, seeds_by_client.get(c, set()), c, now)
        cand["client"] = c
        rows.append(cand)
    t = pd.concat(rows, ignore_index=True)
    uvec = user_vectors(con, t.engager.unique().tolist())
    t = t[t.engager.isin(uvec)].copy()
    t["vec"] = [uvec[u].astype(np.float32) for u in t.engager]
    seg = con.execute("SELECT username engager, segment FROM account_segments").df()
    return t.merge(seg, on="engager", how="left")[["client", "engager", "segment", "n_past", "log_past", "recency",
                                                    "past_90d", "is_seed", "vec"]]


def rank(cands: pd.DataFrame, coef: dict, intercept: float, draft_vec: np.ndarray, k: int = 20) -> dict:
    """Probability each candidate replies to / quotes the draft; top k people and the niche mix of likely reactors."""
    c = cands.copy()
    V = np.vstack(c.vec.to_numpy())
    c["topic_fit"] = V @ draft_vec
    z = intercept + sum(c[f] * w for f, w in coef.items())
    c["p"] = 1 / (1 + np.exp(-z))
    top = c.nlargest(k, "p")
    mix = c.groupby(c.segment.fillna("unknown")).p.sum()
    mix = (mix / mix.sum()).round(3).sort_values(ascending=False)
    return {"top": top[["engager", "segment", "n_past", "is_seed", "p", "topic_fit"]].to_dict("records"),
            "niche_mix": mix.to_dict()}


def seeds_for(con, clients: list[str], top: int = 300) -> dict:
    from ..engage import load_config
    segs = {k.lower(): v for k, v in load_config()["client_segments"].items()}
    out = {}
    for c in clients:
        s = segs.get(c, [])
        out[c] = set(con.execute("""SELECT lower(username) u FROM seed_map
                                    WHERE seg IN (SELECT unnest(?::VARCHAR[])) AND rank <= ?""",
                                 [s, top]).df().u) if s else set()
    return out


def train_final(con, clients: list[str]) -> dict:
    """Backtest (for the report), then fit on all client posts without class weights so p is a real probability."""
    import json

    from sklearn.linear_model import LogisticRegression

    from .model import OUT
    seeds = seeds_for(con, clients)
    result, _ = backtest(con, clients, seeds)
    events = client_posts_with_engagers(con, clients)
    events["created_at"] = pd.to_datetime(events.created_at, utc=True)
    events["engaged_at"] = pd.to_datetime(events.engaged_at, utc=True)
    posts = events.drop_duplicates("tweet_id")[["tweet_id", "client", "created_at"]]
    uvec = user_vectors(con, sorted(set(events.engager).union(*seeds.values())))
    pv = con.execute("SELECT tweet_id, vec FROM post_vecs WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))",
                     [posts.tweet_id.tolist()]).df()
    pvec = {t: np.asarray(v) / (np.linalg.norm(v) or 1) for t, v in zip(pv.tweet_id, pv.vec)}
    rows = build_rows(con, events, posts, seeds, uvec, pvec)
    m = LogisticRegression(max_iter=2000).fit(rows[FEATS], rows.y)
    info = {"coef": dict(zip(FEATS, map(float, m.coef_[0]))), "intercept": float(m.intercept_[0]),
            "backtest": result, "trained_at": pd.Timestamp.now(tz="UTC").isoformat(), "posts": int(len(posts))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "who.json").write_text(json.dumps(info, indent=1, default=float))
    return info
