"""Phase 2B: did targeted engagement work? Treatment vs control, before vs after.

Three measures, all from data xplatform already stores:
  * replies by tag  - each client reply is aimed at a *listed* post, a *seed* account (in the
                      client's seed map, not listed that day) or *other*
  * reply-back      - after the client first replies to an account, does that account reply to
                      or quote the client within 14 days? (judged only once 14 days have passed)
  * niche share     - weekly share of the client's engagers who are in the client's HOLD-OUT
                      seed map (no client data went into it); the north-star number
                      (Phase 1 hold-out: Alex 18%, Nikola 25%)
Effect = (treatment after - before) - (control after - before): a difference-in-differences,
so a change that hits every client (season, X update) cancels out.
"""

from __future__ import annotations

import pandas as pd

from .seedmap import ROOT, load_config

REPLY_BACK_DAYS = 14


def tag_replies(replies: pd.DataFrame, listed_ids: set[str], seed_handles: set[str]) -> pd.Series:
    """listed > seed > other, for one client's replies (needs reply_to_tweet_id, in_reply_to_username)."""
    target = replies.in_reply_to_username.fillna("").str.lower()
    return pd.Series(
        ["listed" if str(t) in listed_ids else "seed" if u in seed_handles else "other"
         for t, u in zip(replies.reply_to_tweet_id, target)], index=replies.index)


def reply_back(first_replies: pd.DataFrame, engagements: pd.DataFrame, now: pd.Timestamp,
               days: int = REPLY_BACK_DAYS) -> pd.Series:
    """1/0 per (client, target) first reply; NaN while the 14-day window is still open."""
    out = []
    eng = engagements.assign(t=pd.to_datetime(engagements.occurred_at, utc=True))
    for r in first_replies.itertuples():
        start = pd.Timestamp(r.first_reply_at)
        if now - start < pd.Timedelta(days=days):
            out.append(float("nan"))
            continue
        hit = eng[(eng.engager == r.target) & (eng.t > start) & (eng.t <= start + pd.Timedelta(days=days))]
        out.append(1.0 if len(hit) else 0.0)
    return pd.Series(out, index=first_replies.index)


def diff_in_diff(df: pd.DataFrame, value: str) -> dict:
    """df: rows with group in {treatment, control}, period in {before, after}, and `value`.
    Means are taken per client first, so one busy client cannot dominate its group."""
    per = df.groupby(["group", "period", "client"])[value].mean().groupby(["group", "period"]).mean()
    g = lambda grp, per_: per.get((grp, per_), float("nan"))
    t_change = g("treatment", "after") - g("treatment", "before")
    c_change = g("control", "after") - g("control", "before")
    return {"treatment_before": g("treatment", "before"), "treatment_after": g("treatment", "after"),
            "control_before": g("control", "before"), "control_after": g("control", "after"),
            "treatment_change": t_change, "control_change": c_change, "effect": t_change - c_change}


def run(con, xp, now: pd.Timestamp | None = None) -> dict:
    from .holdout import fetch_engagements

    cfg = load_config()
    p2 = cfg["phase2"]
    now = now or pd.Timestamp.now(tz="UTC")
    start = pd.Timestamp(str(p2["start"]), tz="UTC")
    since = start - pd.Timedelta(days=28)
    groups = {c: "treatment" for c in p2["treatment"]} | {c: "control" for c in p2["control"]}
    # The HOLD-OUT seed map (built with every client-touching interaction removed). The full map
    # was built partly from clients' past engagers, which would inflate 'before' niche share by
    # construction and make the list look worse than it is.
    seeds = con.execute("SELECT seg, username FROM seed_map_holdout").df()
    listed = (set(con.execute("SELECT tweet_id FROM engage_list").df().tweet_id.astype(str))
              if con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='engage_list'").fetchall()
              else set())
    weekly, tagged, firsts = [], [], []
    days = int((now - since).days) + 1
    for client, group in groups.items():
        handles = set(seeds[seeds.seg.isin(cfg["client_segments"][client])].username)
        eng = fetch_engagements(xp, client, days)
        eng["t"] = pd.to_datetime(eng.occurred_at, utc=True)
        eng = eng[eng.t >= since]
        # weekly niche share of engagers
        eng["week"] = eng.t.dt.tz_convert(None).dt.to_period("W-SUN").dt.start_time
        for wk, g in eng.groupby("week"):
            people = set(g.engager)
            weekly.append({"client": client, "group": group, "week": wk, "engagers": len(people),
                           "niche_share": len(people & handles) / len(people) if people else float("nan"),
                           "period": "after" if wk >= start.tz_convert(None) else "before"})
        # the client's own replies to others
        rep = con.execute("""SELECT tweet_id, created_at, reply_to_tweet_id, in_reply_to_username FROM tweets
                             WHERE lower(username) = lower(?) AND is_reply AND created_at >= ?
                               AND lower(coalesce(in_reply_to_username, '')) <> lower(?)""",
                          [client, since.to_pydatetime(), client]).df()
        if len(rep):
            rep["tag"] = tag_replies(rep, listed, handles)
            rep["client"], rep["group"] = client, group
            rep["period"] = (pd.to_datetime(rep.created_at, utc=True) >= start).map({True: "after", False: "before"})
            tagged.append(rep)
            f = (rep.assign(target=rep.in_reply_to_username.str.lower())
                    .sort_values("created_at").groupby("target", as_index=False).first())
            f = f.rename(columns={"created_at": "first_reply_at"})
            f["engaged_back"] = reply_back(f, eng, now).values
            firsts.append(f)
    weekly = pd.DataFrame(weekly)
    tagged = pd.concat(tagged) if tagged else pd.DataFrame()
    firsts = pd.concat(firsts) if firsts else pd.DataFrame()
    res = {"weekly": weekly, "replies": tagged, "firsts": firsts,
           "niche_did": diff_in_diff(weekly.dropna(subset=["niche_share"]), "niche_share") if len(weekly) else {},
           "reply_back_did": (diff_in_diff(firsts.dropna(subset=["engaged_back"]), "engaged_back")
                              if len(firsts) and firsts.engaged_back.notna().any() else {})}
    con.execute("CREATE OR REPLACE TABLE track_weekly AS SELECT * FROM weekly")
    if len(tagged):
        summary = tagged.groupby(["client", "group", "period", "tag"]).size().reset_index(name="replies")
        con.execute("CREATE OR REPLACE TABLE track_replies AS SELECT * FROM summary")
    if len(firsts):
        fb = firsts[["client", "group", "period", "target", "tag", "first_reply_at", "engaged_back"]]
        con.execute("CREATE OR REPLACE TABLE track_reply_back AS SELECT * FROM fb")
    write_report(res, start)
    return res


def write_report(res: dict, start: pd.Timestamp) -> None:
    f = lambda v, s="{:.0%}": "—" if v is None or pd.isna(v) else s.format(v)
    lines = ["# Phase 2 · Weekly tracking", "",
             f"Lists started {start:%d %b %Y}. Treatment clients get the daily Engage list; control clients don't. "
             "Effect = treatment's change minus control's change (so changes that hit everyone cancel out).", ""]
    for name, key in [("Right-audience share of engagers (niche share)", "niche_did"),
                      ("Accounts that engaged back within 14 days of a reply", "reply_back_did")]:
        d = res.get(key) or {}
        lines += [f"## {name}", ""]
        if not d or pd.isna(d.get("treatment_after", float("nan"))):
            lines += ["Not enough 'after' data yet.", ""]
            continue
        lines += ["| | before | after | change |", "|---|---:|---:|---:|",
                  f"| treatment | {f(d['treatment_before'])} | {f(d['treatment_after'])} | {f(d['treatment_change'], '{:+.1%}')} |",
                  f"| control | {f(d['control_before'])} | {f(d['control_after'])} | {f(d['control_change'], '{:+.1%}')} |",
                  "", f"**Effect: {f(d['effect'], '{:+.1%}')} points.** 3 vs 3 clients: direction, not proof.", ""]
    w = res["weekly"]
    if len(w):
        lines += ["## Engagers per client and week", "", "| client | group | week | engagers | niche share |",
                  "|---|---|---|---:|---:|"]
        for r in w.sort_values(["group", "client", "week"]).itertuples():
            lines.append(f"| {r.client} | {r.group} | {pd.Timestamp(r.week):%d %b} | {r.engagers} | {f(r.niche_share)} |")
    (ROOT / "reports" / "2_weekly.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
