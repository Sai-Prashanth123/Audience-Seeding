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
    # cross-validated prediction per labelled account + who labelled it (claude / user), for proof.py
    r["cv"].to_csv(store.ROOT / "reports" / "1A_cv.csv", index=False)  # carries grader: user/claude/ai/client-config
    store.mark_run(con, "segments")
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
        print("WARNING: x-capacity says can_send=false (scraper pool cooling down). Skipping the core-account "
              "scrape this week; seed maps are rebuilt from the posts already stored.")
        return
    job = xp.submit("user-tweets-bulk", {"usernames": names, "since": since, "include_replies": True,
                                         "limit": args.limit, "max_pages": args.max_pages})
    print(f"job {job}: {len(names)} core accounts since {since}")
    res = xp.wait(job, poll=30, timeout=6 * 3600)
    print({k: res.get(k) for k in ("status", "items_scraped", "coverage", "error", "duration_seconds")})
    for part in pull_since(xp, con, since):
        print(part)
    store.mark_run(con, "collect-core")


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
    store.mark_run(con, "seeds")


def content(args: argparse.Namespace) -> None:
    from . import content as ct
    con = store.connect()
    for p in ct.run(con, days=args.days):
        print("report ->", p)
    store.mark_run(con, "content")


def backtest(args: argparse.Namespace) -> None:
    from . import model
    con = store.connect()
    r = model.backtest(con)
    print(r["overall"].to_string(index=False))
    keep = ["author", "tweet_id", "created_at", "url", "text", "format", "hook", "day_position",
            "y", "pred_A", "pred_B", "pred_model"]
    test = r["test"][keep]
    con.execute("CREATE OR REPLACE TABLE backtest_preds AS SELECT * FROM test")
    r["overall"].to_csv(store.ROOT / "reports" / "1D_backtest.csv", index=False)
    if len(r["per_client"]):
        r["per_client"].to_csv(store.ROOT / "reports" / "1D_backtest_clients.csv", index=False)
    print("report ->", model.write_backtest_report(r))
    print("final model ->", model.train_final(con))
    store.mark_run(con, "backtest")


def predict(args: argparse.Namespace) -> None:
    from .predict import format_result, score_draft
    import duckdb
    con = duckdb.connect(str(store.DB_PATH), read_only=True)
    print(format_result(score_draft(con, args.client, args.text, args.when, args.format,
                                    has_media=args.media, is_quote=args.quote)))


def live(args: argparse.Namespace) -> None:
    """Pull fresh posts, score new pilot-client posts, evaluate matured predictions."""
    from datetime import date, timedelta
    from . import live as lv
    con = store.connect()
    since = (date.today() - timedelta(days=3)).isoformat()
    for line in pull_since(XPlatform(), con, since):
        print(line)
    print("newly scored:", lv.score_new(con, max_age_h=args.max_age_h))
    print("report ->", lv.evaluate(con))
    store.mark_run(con, "live")


def engage(args: argparse.Namespace) -> None:
    """Phase 2A: scrape the watched seeds + Phase 2 clients' replies, then build today's lists.

    The database is opened only briefly before and after the (slow) scrape, so the dashboard
    and the 4-hourly live task are not locked out while X is being paced.
    """
    from datetime import date, timedelta
    from . import engage as eg
    import duckdb

    ro = duckdb.connect(str(store.DB_PATH), read_only=True)
    watch = eg.watch_list(ro)
    ro.close()
    clients = eg.phase2_clients()
    xp = XPlatform()
    cap = xp.get("/datasets/x-capacity")
    ut = cap["by_operation"].get("UserTweets", {})
    print(f"x-capacity before: can_send={cap.get('can_send')} UserTweets {ut.get('remaining')}/{ut.get('limit')}")
    # Only the scrape needs X capacity. If the pool is cooling down, still build today's list from
    # posts xplatform already stores (its own daily collection) rather than leave the team with none.
    if not args.no_scrape and not cap.get("can_send", True):
        print("WARNING: x-capacity says can_send=false (scraper pool cooling down). "
              "Skipping the scrape; building lists from already-stored posts.")
        args.no_scrape = True
    since = (date.today() - timedelta(days=1)).isoformat()
    jobs = []
    if not args.no_scrape:
        jobs.append(xp.submit("user-tweets-bulk", {"usernames": watch, "since": since, "include_replies": False,
                                                   "limit": 10, "max_pages": 1}))
        jobs.append(xp.submit("user-tweets-bulk", {"usernames": clients, "since": (date.today() - timedelta(days=3)).isoformat(),
                                                   "include_replies": True, "limit": 100, "max_pages": 3}))
        # who engaged with each Phase 2 client (xplatform only collects this daily for some clients)
        analysed = list(dict.fromkeys(clients + list(eg.load_config()["pilot_clients"])))
        jobs.append(xp.submit("client-engagers", {"usernames": analysed, "since": (date.today() - timedelta(days=3)).isoformat(),
                                                  "max_pages": 3, "include_quotes": True}))
        print(f"jobs {jobs}: {len(watch)} watched seeds, {len(clients)} Phase 2 clients (posts + engagers)")
        for j in jobs:
            res = xp.wait(j, poll=20, timeout=3 * 3600)
            print(j, {k: res.get(k) for k in ("status", "items_scraped", "duration_seconds")})
    con = store.connect()
    for line in pull_since(xp, con, (date.today() - timedelta(days=3)).isoformat()):
        print(line)
    from . import reviewer as rv
    from .xp import _load_env
    _load_env()
    size = eg.load_config()["phase2"]["list_size"]
    use_ai = rv.has_key()
    lst = eg.build_lists(con, size=size * 2 if use_ai else size)
    if lst.empty:
        print("no fresh posts from watched seeds in the last 24h")
    else:
        print("candidates:", lst.groupby("client").size().to_dict())
        if use_ai:
            import anthropic
            try:
                print("AI check:", rv.review_list(con, anthropic.Anthropic(), timeout=30 * 60))
            except TimeoutError as e:
                print(f"WARNING: AI check too slow ({e}); list kept without the AI filter today.")
            except Exception as e:  # the list must still go out
                print(f"WARNING: AI check failed ({e.__class__.__name__}); list kept without the AI filter today.")
            print("list after AI filter:", eg.apply_ai_filter(con, size))
        else:
            print("WARNING: no ANTHROPIC_API_KEY; list built without the AI filter.")
    store.mark_run(con, "engage")
    cap = xp.get("/datasets/x-capacity")["by_operation"].get("UserTweets", {})
    print(f"x-capacity after: UserTweets {cap.get('remaining')}/{cap.get('limit')}")


def track(args: argparse.Namespace) -> None:
    """Phase 2B: treatment vs control tracking (free reads only)."""
    from . import track as tr
    con = store.connect()
    res = tr.run(con, XPlatform())
    store.mark_run(con, "track")
    for k in ("niche_did", "reply_back_did"):
        print(k, {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in (res.get(k) or {}).items()})
    print("report -> reports/2_weekly.md")


def review(args: argparse.Namespace) -> None:
    """AI reviewer (Claude Opus 5.5, Batches API). Skips with a warning when no API key is configured."""
    from . import reviewer as rv
    from .xp import _load_env
    _load_env()  # local runs read ANTHROPIC_API_KEY from .env; GitHub runs get it from secrets
    if not rv.has_key():
        print("WARNING: ANTHROPIC_API_KEY is not set; AI review skipped (nothing else is affected).")
        return
    import anthropic
    client = anthropic.Anthropic()
    con = store.connect()
    if args.accounts:
        print("1A accounts:", rv.review_accounts(con, client, limit=args.limit))
        store.mark_run(con, "review-accounts")
    if args.list:
        print("2A list:", rv.review_list(con, client, limit=args.list_limit))
        store.mark_run(con, "review-list")


def proof(args: argparse.Namespace) -> None:
    """Ranges + trust checks for every Phase 1 claim. --gate: only read the last checks; exit 1 on a fail."""
    import duckdb
    if args.gate:
        con = duckdb.connect(str(store.DB_PATH), read_only=True)
        checks = con.execute("SELECT * FROM trust_checks").df()
        for r in checks.itertuples():
            print(f"[{r.status.upper():4}] {r.check}: {r.detail}")
        if (checks.status == "fail").any():
            raise SystemExit("trust check FAILED (see above and reports/proof.md)")
        return
    from . import proof as pf
    con = store.connect()
    claims, checks = pf.run(con, XPlatform() if not args.offline else None)
    for r in checks.itertuples():
        print(f"[{r.status.upper():4}] {r.check}: {r.detail}")
    print(f"{len(claims)} claims; proven: {int(claims.status.str.startswith('proven').sum())}; "
          f"report -> reports/proof.md")


SNAPSHOT_TABLES = ["account_segments", "core_accounts", "seed_map", "seed_map_holdout", "engage_list",
                   "engage_coverage", "live_preds", "post_perf", "track_weekly", "track_replies", "track_reply_back",
                   "holdout_detail", "backtest_preds", "pipeline_runs", "proof", "trust_checks", "content_ci", "engage_ai"]


def bootstrap(args: argparse.Namespace) -> None:
    """Make an empty machine (GitHub Actions) ready: raw data from xplatform (free reads), derived
    tables from the committed snapshot. Anything already present (restored cache) is kept."""
    from .export import OUT
    con = store.connect()
    has = lambda t: bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ? "
                                     "AND table_catalog = 'seeding'", [t]).fetchall())
    if con.execute("SELECT count(*) FROM tweets").fetchone()[0] == 0:
        con.close()
        pull_corpus(argparse.Namespace(since=None))
        con = store.connect()
    if not has("profiles"):
        store.load_profiles(con, XPlatform().get_csv("/datasets/profiles", limit=1_000_000))
    if not has("edges"):
        from .graph import build_edges
        print("edges:", build_edges(con))
    copied = []
    if OUT.exists():
        con.execute(f"ATTACH '{OUT.as_posix()}' AS snap (READ_ONLY)")
        snap = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'snap'").fetchall()}
        for t in SNAPSHOT_TABLES:
            if t in snap and not has(t):
                con.execute(f"CREATE TABLE main.{t} AS SELECT * FROM snap.{t}")
                copied.append(t)
        con.execute("DETACH snap")
    print("restored from snapshot:", copied or "nothing (all present)")
    print({t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
           for t in ["tweets", "profiles", "edges"] + SNAPSHOT_TABLES if has(t)})


def export_dashboard(args: argparse.Namespace) -> None:
    from .export import OUT, export_dashboard as run
    print(run(store.connect()))
    print(f"-> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


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
    c = sub.add_parser("content", help="step 1C: content performance reports per pilot client")
    c.add_argument("--days", type=int, default=365)
    c.set_defaults(fn=content)
    sub.add_parser("backtest", help="step 1D: time-split backtest vs baselines, then train final model"
                   ).set_defaults(fn=backtest)
    c = sub.add_parser("predict", help="step 1D: score a draft for a client before it is posted")
    c.add_argument("--client", required=True)
    c.add_argument("--text", required=True)
    c.add_argument("--when", default=None, help="planned time, ISO, UTC (default: now)")
    c.add_argument("--format", default=None, choices=["thread", "quote post", "article"])
    c.add_argument("--media", action="store_true")
    c.add_argument("--quote", action="store_true")
    c.set_defaults(fn=predict)
    c = sub.add_parser("live", help="step 1D: score new pilot posts early, evaluate after 48h (run daily)")
    c.add_argument("--max-age-h", type=float, default=24)
    c.set_defaults(fn=live)
    c = sub.add_parser("engage", help="phase 2A: build today's Engage list (scrapes watched seeds; spends quota)")
    c.add_argument("--no-scrape", action="store_true", help="rebuild lists from stored posts only")
    c.set_defaults(fn=engage)
    sub.add_parser("track", help="phase 2B: weekly tracking, treatment vs control").set_defaults(fn=track)
    c = sub.add_parser("review", help="AI reviewer: 1A accounts (--accounts) and/or today's Engage list (--list)")
    c.add_argument("--accounts", action="store_true")
    c.add_argument("--list", action="store_true")
    c.add_argument("--limit", type=int, default=300, help="max accounts per run")
    c.add_argument("--list-limit", type=int, default=None, help="max Engage-list posts per run")
    c.set_defaults(fn=review)
    c = sub.add_parser("proof", help="95% ranges for every Phase 1 claim + automatic trust checks")
    c.add_argument("--gate", action="store_true", help="exit 1 if the last trust checks contain a failure")
    c.add_argument("--offline", action="store_true", help="skip checks that call xplatform")
    c.set_defaults(fn=proof)
    sub.add_parser("bootstrap", help="prepare an empty machine: raw data from xplatform, derived tables from the snapshot"
                   ).set_defaults(fn=bootstrap)
    sub.add_parser("export-dashboard", help="write data/dashboard.duckdb for the deployed app"
                   ).set_defaults(fn=export_dashboard)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
