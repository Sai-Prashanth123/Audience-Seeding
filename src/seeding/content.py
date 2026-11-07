"""Step 1C: what worked and what didn't, per pilot client.

Per original post (not replies, not retweets), at least `min_age_h` old:
  * rates per 1k views: likes, replies, reposts, quotes, bookmarks
  * X-weighted score: reply 5, quote 5, repost 1, like 0.66 (home-mixer defaults in
    xai-org/x-algorithm, see ~/.claude/skills/x-algorithm/references/algorithm-weights.md).
    The real ranker weights *predicted probabilities per viewer*, not public counts, and
    share/dwell signals are not observable, so this is an approximation and says so.
  * relative performance: X-weighted score / the client's trailing median of the previous
    20 posts (min 5), so a post is judged against the account it came from, at that time
  * niche share: of the post's captured repliers/quoters, the share in the client's seed map
Breakdowns: format, hook, length, posting hour/weekday, same-day position, topic cluster.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .holdout import fetch_engagements
from .seedmap import ROOT, load_config
from .xp import XPlatform

X_WEIGHTS = {"reply_count": 5.0, "quote_count": 5.0, "retweet_count": 1.0, "like_count": 0.66}
DAY_DECAY = {1: 1.0, 2: 0.625, 3: 0.4375}  # AuthorDiversityDecay, floor 0.25


def classify_hook(text: str) -> str:
    first = (text or "").strip().split("\n")[0].strip().lower()
    if not first:
        return "media only"
    # Checked on the whole post: the offer is often in the 2nd line or the CTA at the end.
    whole = (text or "").lower()
    if re.search(r"giv(e|ing) (it all |them |this |the whole \w+ |all of (it|them) )?away|"
                 r"\b(comment|reply)\b[^.\n]{0,40}\b(get|send|dm)\b|\bfor free\b|free (template|playbook|guide|access)",
                 whole):
        return "giveaway / comment-to-get"
    if first.endswith("?"):
        return "question"
    if re.match(r"^(stop|don.?t|nobody|most (people|founders|teams)|unpopular|.*\b(is dead|isn.?t|wrong|myth)\b)", first):
        return "contrarian"
    if re.search(r"\b(how to|here.?s (how|what|the)|steps?|ways|playbook|framework|guide|template)\b|^\d+[\./)]|→", first):
        return "how-to / list"
    if re.match(r"^(introducing|we (just )?(launched|raised|hit|built)|today we|announcing|excited)", first):
        return "announcement"
    if re.search(r"[\$€£]\s?\d|\d+(\.\d+)?\s?(%|k\b|m\b|x\b)|\b\d{2,}\b", first):
        return "number / result"
    if re.match(r"^(i |i.?m |i.?ve |we |my |our |last (week|month|year)|\d+ (years|months) ago)", first):
        return "story"
    return "statement"


def _txt(v) -> str:
    return v if isinstance(v, str) else ""


def post_format(r) -> str:
    if _txt(r.article_title):
        return "article"
    if r.is_thread:
        return "thread"
    if r.is_quote:
        return "quote post"
    if r.is_long_form:
        return "long-form post"
    if (r.media_count or 0) > 0:
        return "short + media"
    return "short text"


def length_bucket(n: int) -> str:
    return ("<100 chars" if n < 100 else "100-280" if n <= 280 else "281-1,000" if n <= 1000 else "1,000+")


def load_posts(con: duckdb.DuckDBPyConnection, client: str, days: int, min_age_h: int) -> pd.DataFrame:
    df = con.execute(f"""
        WITH self_replies AS (SELECT DISTINCT reply_to_tweet_id AS tid FROM tweets
                              WHERE is_reply AND lower(in_reply_to_username) = lower(username)
                                AND lower(username) = lower(?))
        SELECT t.*, t.tweet_id IN (SELECT tid FROM self_replies) AS is_thread
        FROM tweets t
        WHERE lower(t.username) = lower(?) AND NOT coalesce(t.is_reply, false)
          AND NOT coalesce(t.is_retweet, false)
          AND t.created_at >= now() - INTERVAL {days} DAY
          AND t.created_at <= now() - INTERVAL {min_age_h} HOUR
        ORDER BY t.created_at""", [client, client]).df()
    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in ["like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"]:
        df[c] = df[c].fillna(0)
    df["xscore"] = sum(df[c] * w for c, w in X_WEIGHTS.items())
    v = df.view_count.where(df.view_count > 0)
    for c, short in [("like_count", "likes"), ("reply_count", "replies"), ("retweet_count", "reposts"),
                     ("quote_count", "quotes"), ("bookmark_count", "bookmarks")]:
        df[f"{short}_per_1k"] = df[c] / v * 1000
    df["xscore_per_1k"] = df.xscore / v * 1000
    # trailing baseline: median of the previous 20 posts (needs >= 5)
    base = df.xscore.shift(1).rolling(20, min_periods=5).median()
    df["baseline"] = base
    df["rel_perf"] = df.xscore / base.where(base > 0)
    vbase = df.view_count.shift(1).rolling(20, min_periods=5).median()
    df["rel_views"] = df.view_count / vbase.where(vbase > 0)
    ts = pd.to_datetime(df.created_at, utc=True)
    df["hour_utc"] = ts.dt.hour
    df["hour_block"] = pd.cut(ts.dt.hour, [-1, 5, 11, 17, 23],
                              labels=["00-05 UTC", "06-11 UTC", "12-17 UTC", "18-23 UTC"]).astype(str)
    df["weekday"] = ts.dt.day_name().str[:3]
    df["day_position"] = df.groupby(ts.dt.date).cumcount() + 1
    df["day_slot"] = df.day_position.clip(upper=3).map({1: "1st post of day", 2: "2nd", 3: "3rd+"})
    df["format"] = [post_format(r) for r in df.itertuples()]
    df["hook"] = df.text.map(classify_hook)
    df["length"] = df.text.fillna("").str.len().map(length_bucket)
    return df


def add_topics(df: pd.DataFrame, k_max: int = 8) -> pd.DataFrame:
    """KMeans on post embeddings; clusters named by their most distinctive words."""
    from sentence_transformers import SentenceTransformer
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = df.copy()
    k = int(min(k_max, max(2, len(df) // 15)))
    clean = df.text.fillna("").str.replace(r"https?://\S+", "", regex=True)
    clean = clean.where(clean.str.len() > 0, df.article_title.fillna(""))
    vecs = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu").encode(
        clean.str.slice(0, 1000).tolist(), normalize_embeddings=True, show_progress_bar=False)
    labels = KMeans(k, n_init=10, random_state=0).fit_predict(vecs)
    tf = TfidfVectorizer(stop_words="english", max_features=4000, ngram_range=(1, 2), min_df=2,
                         token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9]+\b")
    X = tf.fit_transform(clean)
    terms = np.array(tf.get_feature_names_out())
    names = {}
    for c in range(k):
        m = labels == c
        diff = np.asarray(X[m].mean(axis=0)).ravel() - np.asarray(X[~m].mean(axis=0)).ravel()
        names[c] = " / ".join(terms[np.argsort(-diff)[:3]])
    df["topic"] = [names[c] for c in labels]
    return df


def add_niche_share(df: pd.DataFrame, eng: pd.DataFrame, seed_handles: set[str]) -> pd.DataFrame:
    df = df.copy()
    g = eng.groupby("tweet_id").engager.apply(lambda s: (len(set(s)), len(set(s) & seed_handles)))
    df["engagers_captured"] = df.tweet_id.map(lambda t: g.get(t, (0, 0))[0])
    df["engagers_in_seed"] = df.tweet_id.map(lambda t: g.get(t, (0, 0))[1])
    df["niche_share"] = (df.engagers_in_seed / df.engagers_captured).where(df.engagers_captured >= 3)
    return df


def breakdown(df: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for key, d in df.groupby(col):
        r = d.rel_perf.dropna()
        rows.append({col: key, "posts": len(d), "median_rel_perf": r.median() if len(r) else np.nan,
                     "beat_own_median": (r > 1).mean() if len(r) else np.nan,
                     "median_views": d.view_count.median(),
                     "xscore_per_1k_views": d.xscore_per_1k.median(),
                     "niche_share": d.niche_share.mean()})
    out = pd.DataFrame(rows).sort_values("median_rel_perf", ascending=False)
    return out


def _fmt_table(t: pd.DataFrame, key: str, min_posts: int) -> str:
    lines = [f"| {key} | posts | median vs own baseline | beat own median | median views | X-score / 1k views | niche share |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for r in t.itertuples():
        flag = "" if r.posts >= min_posts else " ⚠ few posts"
        f = lambda v, s: "—" if pd.isna(v) else s.format(v)
        lines.append(f"| {getattr(r, key)}{flag} | {r.posts} | {f(r.median_rel_perf, '{:.2f}×')} | "
                     f"{f(r.beat_own_median, '{:.0%}')} | {f(r.median_views, '{:,.0f}')} | "
                     f"{f(r.xscore_per_1k_views, '{:.1f}')} | {f(r.niche_share, '{:.0%}')} |")
    return "\n".join(lines)


def _post_line(r) -> str:
    text = (_txt(r.article_title) or _txt(r.text)).replace("\n", " ").strip()
    text = re.sub(r"https?://\S+", "", text)[:140]
    rel = "—" if pd.isna(r.rel_perf) else f"{r.rel_perf:.1f}×"
    views = "—" if pd.isna(r.view_count) else f"{int(r.view_count):,}"
    return f"- **{rel}** · {views} views · {r.format}, {r.hook} · [{text}]({r.url})"


def compare_with_xplatform(xp: XPlatform, con, client: str, since: str, until: str) -> dict:
    """Post-by-post check of this store against xplatform's raw data for one client and month.

    Days are UTC on both sides (casting TIMESTAMPTZ to a date otherwise uses the machine's local
    zone, which differs between this PC and GitHub). Retweets are excluded (their metrics belong
    to the original author). Compared: the set of post IDs, and likes / views per post.
    """
    import pandas as pd
    theirs, offset = [], 0
    while True:
        page = xp.get("/datasets/tweets", username=client, since=since, until=until, limit=500, offset=offset)
        theirs += page["items"]
        if len(page["items"]) < 500:
            break
        offset += 500
    t = pd.DataFrame(theirs, columns=["tweet_id", "created_at", "like_count", "view_count", "is_retweet"])
    t = t[~t.is_retweet.fillna(False).astype(bool)]
    t = t[pd.to_datetime(t.created_at, utc=True).dt.date.astype(str).between(since, until)]
    ours = con.execute("""SELECT tweet_id, like_count, view_count FROM tweets
                          WHERE lower(username) = lower(?) AND NOT coalesce(is_retweet, false)
                            AND (created_at AT TIME ZONE 'UTC')::date BETWEEN ?::date AND ?::date""",
                       [client, since, until]).df()
    m = t.merge(ours, on="tweet_id", how="outer", suffixes=("_x", "_ours"), indicator=True)
    both = m[m["_merge"] == "both"]
    lx, lo = float(both.like_count_x.fillna(0).sum()), float(both.like_count_ours.fillna(0).sum())
    vx, vo = float(both.view_count_x.fillna(0).sum()), float(both.view_count_ours.fillna(0).sum())
    return {"client": client, "posts_xplatform": int((m["_merge"] != "right_only").sum()),
            "posts_ours": int((m["_merge"] != "left_only").sum()),
            "missing_here": int((m["_merge"] == "left_only").sum()),
            "extra_here": int((m["_merge"] == "right_only").sum()),
            "likes_xplatform": lx, "likes_ours": lo, "views_xplatform": vx, "views_ours": vo,
            # counts keep growing after our last pull; xplatform's live numbers are newer
            "likes_dev": (lo - lx) / lx if lx else 0.0, "views_dev": (vo - vx) / vx if vx else 0.0}


def reconcile(xp: XPlatform, con, client: str, since: str, until: str) -> str:
    r = compare_with_xplatform(xp, con, client, since, until)
    f = lambda x: f"{x:,.0f}"
    rows = ["| measure | xplatform (raw posts) | this store | match |", "|---|---:|---:|---|",
            f"| posts (excl. retweets) | {r['posts_xplatform']} | {r['posts_ours']} | "
            f"{'✓' if r['missing_here'] == r['extra_here'] == 0 else f'{r["missing_here"]} missing, {r["extra_here"]} extra'} |",
            f"| likes | {f(r['likes_xplatform'])} | {f(r['likes_ours'])} | {'✓' if r['likes_dev'] == 0 else f'{r["likes_dev"]:+.1%}'} |",
            f"| views | {f(r['views_xplatform'])} | {f(r['views_ours'])} | {'✓' if r['views_dev'] == 0 else f'{r["views_dev"]:+.1%}'} |"]
    return "\n".join(rows)


def run(con: duckdb.DuckDBPyConnection, days: int = 365, min_age_h: int = 48) -> list[Path]:
    cfg = load_config()
    xp = XPlatform()
    # HOLD-OUT seed map: built with no client-touching interaction, so a client's own past engagers
    # are not in it by construction (the full map would inflate niche share).
    seeds = con.execute("SELECT seg, username FROM seed_map_holdout").df()
    paths, all_posts = [], []
    for client in cfg["pilot_clients"]:
        segs = cfg["client_segments"][client]
        df = enrich(load_posts(con, client, days, min_age_h))
        if len(df) < 10:
            continue
        df = add_topics(df)
        eng = fetch_engagements(xp, client, days)
        df = add_niche_share(df, eng, set(seeds[seeds.seg.isin(segs)].username))
        df["client"] = client
        all_posts.append(df)
        min_posts = 5
        rated = df.dropna(subset=["rel_perf"])
        last_month = (date.today().replace(day=1) - timedelta(days=1))
        recon = reconcile(xp, con, client, last_month.replace(day=1).isoformat(), last_month.isoformat())
        lines = [
            f"# 1C · What worked for @{client}", "",
            f"{len(df)} original posts from the last {days} days, each at least {min_age_h}h old "
            f"({pd.to_datetime(df.created_at).min():%d %b %Y} – {pd.to_datetime(df.created_at).max():%d %b %Y}). "
            f"{len(rated)} have enough earlier posts to compare against.", "",
            "**How to read this.** *Median vs own baseline* compares each post's X-weighted score "
            "(replies ×5, quotes ×5, reposts ×1, likes ×0.66) with the median of the client's previous 20 posts: "
            "1.5× means the post did 50% better than usual *for this account at that time*. "
            "*Niche share* is the share of the post's captured repliers/quoters who are in the client's seed map. "
            "Groups with ⚠ have too few posts to trust. These are associations in past data, not proof of cause.", "",
            "## Headline", "",
            f"- Median views per post: **{df.view_count.median():,.0f}**",
            f"- Median X-weighted score per 1k views: **{df.xscore_per_1k.median():.1f}**",
            f"- Average niche share of engagers (posts with ≥3 captured): "
            f"**{df.niche_share.mean():.0%}**" if df.niche_share.notna().any() else "- Niche share: not enough captured engagers",
            "", "## Best posts (vs own baseline)", ""]
        lines += [_post_line(r) for r in rated.sort_values("rel_perf", ascending=False).head(5).itertuples()]
        lines += ["", "## Weakest posts (vs own baseline)", ""]
        lines += [_post_line(r) for r in rated.sort_values("rel_perf").head(5).itertuples()]
        for col, title in [("format", "Format"), ("hook", "Opening line (hook)"), ("topic", "Topic cluster"),
                           ("length", "Length"), ("hour_block", "Posting time"), ("weekday", "Weekday"),
                           ("day_slot", "Same-day position")]:
            lines += ["", f"## {title}", "", _fmt_table(breakdown(df, col), col, min_posts)]
            if col == "day_slot":
                lines += ["", "X's published ranker shows a 2nd post by the same author to a viewer in the same "
                          "session at ×0.625 and a 3rd at ×0.4375, so later same-day posts are expected to do worse."]
        lines += ["", "## Data check (1C gate)", "",
                  f"Totals for {last_month:%B %Y} in this store vs xplatform's own client summary:", "", recon, ""]
        path = ROOT / "reports" / f"1C_{client}.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    if all_posts:
        perf = pd.concat(all_posts)
        keep = ["client", "tweet_id", "url", "created_at", "text", "article_title", "format", "hook", "topic",
                "length", "hour_block", "weekday", "day_slot", "view_count", "like_count", "reply_count",
                "retweet_count", "quote_count", "bookmark_count", "xscore", "xscore_per_1k", "baseline",
                "rel_perf", "rel_views", "engagers_captured", "engagers_in_seed", "niche_share"]
        perf = perf[keep]
        con.execute("CREATE OR REPLACE TABLE post_perf AS SELECT * FROM perf")
        perf.to_csv(ROOT / "reports" / "1C_posts.csv", index=False, encoding="utf-8-sig")
    return paths
