"""`uv run seeding <command>`"""

from __future__ import annotations

import argparse

from . import store
from .xp import XPlatform

PAGE = 100_000  # /datasets/export max


def pull_corpus(args: argparse.Namespace) -> None:
    """Export every stored tweet (free read) into data/raw and DuckDB, newest first."""
    xp = XPlatform()
    con = store.connect()
    until = None
    part = 0
    while True:
        rows = list(xp.export_tweets(sort="created_at", order="desc", limit=PAGE,
                                     until=until, since=args.since))
        path = store.write_raw(f"corpus_part{part}", rows)
        total = store.load_tweets(con, path)
        print(f"part {part}: {len(rows)} rows, store now {total}")
        if len(rows) < PAGE:
            break
        # `until` is inclusive by day; the overlap day is re-read and upserted.
        until = rows[-1]["created_at"][:10]
        part += 1


def pull_profiles(args: argparse.Namespace) -> None:
    """Export every stored X profile (bio, followers, ...) - free read."""
    n = store.load_profiles(store.connect(), XPlatform().get_csv("/datasets/profiles", limit=1_000_000))
    print(f"profiles in store: {n}")


def edges(args: argparse.Namespace) -> None:
    from .graph import build_edges
    print(build_edges(store.connect()))


def segments(args: argparse.Namespace) -> None:
    from . import segments as seg
    con = store.connect()
    print("new posts embedded:", seg.embed_posts(con), "| new bios embedded:", seg.embed_bios(con))
    out, r = seg.classify_supervised(con)
    print(out["segment"].value_counts().to_string())
    print({k: round(v, 3) for k, v in r["metrics"].items()})
    import pandas as pd
    from datetime import datetime
    mpath = store.ROOT / "reports" / "1A_metrics.csv"
    row = pd.DataFrame([{"run_at": datetime.now().isoformat(timespec="seconds"), **r["metrics"]}])
    row.to_csv(mpath, mode="a", header=not mpath.exists(), index=False)
    print("review sample ->", seg.review_sample(con))


def core(args: argparse.Namespace) -> None:
    from . import seedmap as sm
    con = store.connect()
    c = sm.pick_core(con, per_segment=args.per_segment)
    print(c.groupby("core_segment").size().to_dict(), "| unique:", c.username.nunique())


def collect_core(args: argparse.Namespace) -> None:
    """Spend quota: user-tweets-bulk (with replies) for every core account, then re-export."""
    from datetime import date, timedelta
    con = store.connect()
    names = [r[0] for r in con.execute("SELECT DISTINCT username FROM core_accounts ORDER BY 1").fetchall()]
    since = (date.today() - timedelta(days=args.days)).isoformat()
    xp = XPlatform()
    cap = xp.get("/datasets/x-capacity")
    if not cap.get("can_send", True):
        raise SystemExit(f"x-capacity says can_send=false: {cap}")
    job = xp.submit("user-tweets-bulk", {"usernames": names, "since": since, "include_replies": True,
                                         "limit": args.limit, "max_pages": args.max_pages})
    print(f"job {job}: {len(names)} core accounts since {since}")
    res = xp.wait(job, poll=30, timeout=6 * 3600)
    print({k: res.get(k) for k in ("status", "items_scraped", "coverage", "error", "duration_seconds")})
    for part in pull_since(xp, con, since):
        print(part)


def seeds(args: argparse.Namespace) -> None:
    from . import holdout
    from . import seedmap as sm
    con = store.connect()
    out = sm.build_seed_map(con)
    for seg, d in out.groupby("seg"):
        path = store.ROOT / "reports" / f"1B_seedmap_{seg}.csv"
        d.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"{seg}: {len(d)} seeds -> {path}")
    print("hold-out report ->", holdout.run(con))


def pull_since(xp: XPlatform, con, since: str):
    rows = list(xp.export_tweets(since=since, limit=PAGE, sort="created_at", order="desc"))
    path = store.write_raw(f"export_since_{since}", rows)
    yield f"re-exported {len(rows)} rows since {since}; store now {store.load_tweets(con, path)}"


def main() -> None:
    p = argparse.ArgumentParser(prog="seeding")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("pull-corpus", help="export xplatform's stored tweets into the local store")
    c.add_argument("--since", default=None)
    c.set_defaults(fn=pull_corpus)
    sub.add_parser("pull-profiles", help="export xplatform's stored X profiles").set_defaults(fn=pull_profiles)
    sub.add_parser("edges",help="build reply/quote/retweet edges").set_defaults(fn=edges)
    sub.add_parser("segments", help="step 1A: label accounts Tech/B2B/AI").set_defaults(fn=segments)
    c = sub.add_parser("core", help="step 1B: pick core accounts per segment")
    c.add_argument("--per-segment", type=int, default=150)
    c.set_defaults(fn=core)
    c = sub.add_parser("collect-core", help="step 1B: scrape core accounts' timelines (spends quota)")
    c.add_argument("--days", type=int, default=60)
    c.add_argument("--limit", type=int, default=200)
    c.add_argument("--max-pages", type=int, default=4)
    c.set_defaults(fn=collect_core)
    sub.add_parser("seeds", help="step 1B: score seed maps + hold-out test").set_defaults(fn=seeds)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
