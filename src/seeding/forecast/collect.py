"""Live snapshots of client posts as they grow, plus who replied: the data the nowcaster learns from.

xplatform stores only a post's latest counts, so we can't see *how* a post grows. Each run:
  1. finds client posts under 50h old: one cheap paced timeline job for all clients (UserTweets);
  2. for each post with a snapshot due (ages 0.5, 1, 2, 4, 8, 24, 48h), runs the `tweet-detail`
     scraper, which returns the post's live counts and the replies under it (TweetDetail, ~1 request);
  3. appends both to the git ledger (snapshots.csv, post_engagers.csv).

Budget: ~15 UserTweets + a few TweetDetail requests per hourly run, against limits of 250 and 1,500
per window (checked with xplatform's x-capacity on 16 Nov 2026).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from . import ledger

TARGET_AGES_H = [0.5, 1, 2, 4, 8, 24, 48]
MAX_AGE_H = 50
COUNT_COLS = {"view_count": "views", "like_count": "likes", "reply_count": "replies",
              "retweet_count": "reposts", "quote_count": "quotes", "bookmark_count": "bookmarks"}


def clients() -> list[str]:
    from ..engage import load_config
    cfg = load_config()
    return list(dict.fromkeys(list(cfg["pilot_clients"]) + list(cfg["client_segments"])))


def due(age_h: float, taken_ages: list[float]) -> bool:
    """A snapshot is due when the latest target age this post has passed has no snapshot taken at or after it."""
    passed = [t for t in TARGET_AGES_H if age_h >= t]
    if not passed or age_h > MAX_AGE_H:
        return False
    return not any(a >= passed[-1] for a in taken_ages)


def recent_posts(xp, names: list[str], now: pd.Timestamp) -> pd.DataFrame:
    since = (now.date() - timedelta(days=3)).isoformat()
    job = xp.submit("user-tweets-bulk", {"usernames": names, "since": since, "include_replies": False,
                                         "limit": 40 * len(names), "max_pages": 1})
    res = xp.wait(job, poll=10, timeout=1800)
    if res.get("status") != "succeeded":
        print("timeline job:", {k: res.get(k) for k in ("status", "error")})
    rows = pd.DataFrame(list(xp.job_rows(job)))
    if rows.empty:
        return rows
    lower = {n.lower(): n for n in names}
    rows = rows[rows.username.str.lower().isin(lower)]
    rows = rows[~rows.get("is_retweet", False).fillna(False).astype(bool)
                & ~rows.get("is_reply", False).fillna(False).astype(bool)]
    rows["created"] = pd.to_datetime(rows.created_at, utc=True)
    rows["age_h"] = (now - rows.created).dt.total_seconds() / 3600
    return rows[rows.age_h <= MAX_AGE_H].drop_duplicates("tweet_id")


def snapshot_rows(post: pd.Series, detail: list[dict], now: pd.Timestamp) -> tuple[dict | None, list[dict]]:
    """Turn one tweet-detail result into a snapshot row and the replies under the post."""
    main = next((d for d in detail if str(d.get("tweet_id")) == str(post.tweet_id)), None)
    if main is None:
        return None, []
    seen = now.isoformat()
    snap = {"tweet_id": post.tweet_id, "client": post.username.lower(), "post_created_at": post.created.isoformat(),
            "seen_at": seen, "age_h": round((now - post.created).total_seconds() / 3600, 3),
            "source": "tweet-detail", **{v: main.get(k) for k, v in COUNT_COLS.items()}}
    eng = [{"tweet_id": post.tweet_id, "client": post.username.lower(), "engager": str(d.get("username", "")).lower(),
            "kind": "reply", "engager_tweet_id": d.get("tweet_id"), "engaged_at": d.get("created_at"), "seen_at": seen}
           for d in detail
           if str(d.get("tweet_id")) != str(post.tweet_id) and str(d.get("username", "")).lower() != post.username.lower()]
    return snap, eng


def run(xp, now: pd.Timestamp | None = None) -> dict:
    now = now or pd.Timestamp.now(tz="UTC")
    posts = recent_posts(xp, clients(), now)
    if posts.empty:
        return {"posts_live": 0, "snapshots": 0, "engagers": 0}
    snaps = ledger.load("snapshots")
    taken = {t: g.age_h.astype(float).tolist() for t, g in snaps.groupby("tweet_id")} if len(snaps) else {}
    todo = posts[[due(a, taken.get(str(t), [])) for t, a in zip(posts.tweet_id.astype(str), posts.age_h)]]
    jobs = {r.tweet_id: xp.submit("tweet-detail", {"tweet_id": str(r.tweet_id), "max_pages": 1, "limit": 100})
            for r in todo.itertuples()}
    new_snaps, new_eng = [], []
    for r in todo.itertuples():
        res = xp.wait(jobs[r.tweet_id], poll=5, timeout=600)
        if res.get("status") != "succeeded":
            print(f"tweet-detail {r.tweet_id}: {res.get('status')} {res.get('error')}")
            continue
        snap, eng = snapshot_rows(pd.Series(r._asdict()), list(xp.job_rows(jobs[r.tweet_id])),
                                  pd.Timestamp.now(tz="UTC"))
        if snap:
            new_snaps.append(snap)
            new_eng += eng
    return {"posts_live": len(posts), "due": len(todo), "snapshots": ledger.append("snapshots", new_snaps),
            "engagers": ledger.append("post_engagers", new_eng)}
