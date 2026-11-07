"""Audience Seeding dashboard - every Phase 1 result in one place.

Run:  uv run streamlit run app/dashboard.py
Reads data/seeding.duckdb read-only and the files in reports/. The one write it makes is
saving your 1A review marks into data/labels/1A_claude_grades.csv (grader=user), which
the next `uv run seeding segments` trains on.
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
import os
_FULL, _SLIM = ROOT / "data" / "seeding.duckdb", ROOT / "data" / "dashboard.duckdb"
# Local: the full pipeline DB (always fresh). Deployed: the committed results-only export.
DB = Path(os.environ.get("SEEDING_DB") or (_FULL if _FULL.exists() else _SLIM))
REPORTS = ROOT / "reports"
LABELS = ROOT / "data" / "labels" / "1A_claude_grades.csv"
CFG = yaml.safe_load((ROOT / "config" / "segments.yaml").read_text(encoding="utf-8"))

# Categorical slots 1-3 of the validated reference palette, fixed per segment (never by rank).
SEG_COLORS = {"b2b": "#2a78d6", "ai": "#eb6834", "tech": "#1baf7a", "none": "#a3a29b"}
SEG_NAMES = {"b2b": "B2B", "ai": "AI", "tech": "Tech", "none": "Not in niche"}
GATE = 0.80

st.set_page_config(page_title="Audience Seeding", page_icon="🎯", layout="wide")
st.markdown("""<style>
  .block-container {padding-top: 1.6rem; max-width: 1400px;}
  [data-testid="stMetricValue"] {font-size: 1.7rem;}
  .gate-pass {color:#0ca30c; font-weight:600}
  .gate-fail {color:#d03b3b; font-weight:600}
  .muted {color:#8a8983; font-size:0.85rem}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data access
# One read-only connection per page run, closed at the end of the script, so the scheduled
# pipeline (`seeding live`) can write between page views. Holding it open would lock it out.
_CON = None


def _con():
    global _CON
    if _CON is None:
        _CON = duckdb.connect(str(DB), read_only=True)
    return _CON


def q(sql: str, params=None) -> pd.DataFrame:
    try:
        return _con().execute(sql, params or []).df()
    except duckdb.CatalogException:
        return pd.DataFrame()


def has_table(name: str) -> bool:
    return not q("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [name]).empty


def seg_bar(df: pd.DataFrame, x: str, y: str, title: str = "", height: int = 220):
    """Horizontal bars, fixed segment colors, direct value labels (contrast relief), tooltip."""
    base = alt.Chart(df).encode(
        y=alt.Y(f"{y}:N", sort="-x", title=None),
        x=alt.X(f"{x}:Q", title=None, axis=alt.Axis(grid=True, gridOpacity=0.25)),
        color=alt.Color("seg:N", scale=alt.Scale(domain=list(SEG_COLORS), range=list(SEG_COLORS.values())),
                        legend=None),
        tooltip=[alt.Tooltip(f"{y}:N", title="Segment"), alt.Tooltip(f"{x}:Q", title="Count", format=",")],
    )
    bars = base.mark_bar(cornerRadiusEnd=4, height=22)
    labels = base.mark_text(align="left", dx=6, color="#52514e").encode(text=alt.Text(f"{x}:Q", format=","),
                                                                       color=alt.value("#52514e"))
    return (bars + labels).properties(title=title, height=height)


def link_cfg():
    return {"url": st.column_config.LinkColumn("Profile", display_text=r"https://x\.com/(.*)")}


def gate_badge(value: float, bar: float = GATE) -> str:
    ok = value >= bar
    return f"<span class='{'gate-pass' if ok else 'gate-fail'}'>{'✓ passes' if ok else '✗ below'} {bar:.0%}</span>"


# ---------------------------------------------------------------- availability
if not DB.exists():
    st.error("No data yet. Run the pipeline, then `uv run seeding export-dashboard` and commit data/dashboard.duckdb.")
    st.stop()
try:
    _con()
except duckdb.IOException:
    st.warning("The pipeline is writing to the database right now (a scrape or rebuild is running). "
               "Reload this page when it finishes.")
    st.stop()

SLIM = has_table("kpis")
if SLIM:
    KPI = q("SELECT * FROM kpis")
    EDGES = q("SELECT kind, n FROM edges_summary")
else:
    KPI = q("""SELECT (SELECT count(*) FROM tweets) posts,
                      (SELECT count(DISTINCT lower(username)) FROM tweets) authors,
                      (SELECT count(*) FROM profiles) profiles,
                      (SELECT count(description) FROM profiles) bios,
                      (SELECT max(created_at) FROM tweets) newest""")
    EDGES = q("SELECT kind, count(*) n FROM edges GROUP BY 1") if has_table("edges") else pd.DataFrame()

status = {
    "Setup": SLIM or (has_table("tweets") and has_table("profiles")),
    "1A Segments": has_table("account_segments"),
    "1B Core": has_table("core_accounts"),
    "1B Seeds": has_table("seed_map"),
    "1B Hold-out": (REPORTS / "1B_holdout.csv").exists(),
    "1C Content": has_table("post_perf"),
    "1D Model": (REPORTS / "1D_backtest.csv").exists(),
}

with st.sidebar:
    st.markdown("## 🎯 Audience Seeding")
    st.caption("Thought Pilot · Phase 1")
    st.markdown("**Pipeline**")
    for k, done in status.items():
        st.markdown(f"{'✅' if done else '⬜'} {k}")
    if not KPI.empty and KPI.newest[0] is not None:
        st.caption(f"Newest post in data: {pd.Timestamp(KPI.newest[0]):%d %b %Y %H:%M} UTC")
    st.caption(f"Source: {'results snapshot' if SLIM else 'live pipeline database'}")
    st.caption("Refresh data: `uv run seeding pull-corpus`, `pull-profiles`, `edges`, `segments`, `core`, `seeds`")

tabs = st.tabs(["Overview", "1A · Segments", "1A · Review", "1B · Core accounts",
                "1B · Seed maps", "Clients", "1C · Content", "1D · Model"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    st.subheader("Where things stand")
    k, e = KPI, EDGES.copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Posts stored", f"{k.posts[0]:,}")
    c2.metric("Accounts posting", f"{k.authors[0]:,}")
    c3.metric("Profiles (with bio)", f"{k.profiles[0]:,}", f"{k.bios[0]:,} bios", delta_color="off")
    c4.metric("Interactions mapped", f"{int(e.n.sum()):,}" if not e.empty else "—")

    left, right = st.columns(2)
    with left:
        if has_table("account_segments"):
            seg = q("SELECT segment AS seg, count(*) n FROM account_segments GROUP BY 1")
            seg["Segment"] = seg.seg.map(SEG_NAMES)
            st.altair_chart(seg_bar(seg[seg.seg != "none"], "n", "Segment", "Accounts labelled per segment (1A)"),
                            width="stretch")
            n_none = int(seg.loc[seg.seg == "none", "n"].sum())
            st.caption(f"{n_none:,} more accounts are off-topic or have too little data to judge yet.")
    with right:
        if not e.empty:
            e["Segment"] = e.kind.str.title() + "s"
            e["seg"] = "none"
            st.altair_chart(seg_bar(e, "n", "Segment", "Interactions by type (who engages with whom)"),
                            width="stretch")
            st.caption("Likes and plain retweet lists can't be collected from X; replies, quotes and the "
                       "retweets an account makes can.")

# ---------------------------------------------------------------- 1A segments
with tabs[1]:
    st.subheader("1A · Who is Tech, B2B or AI")
    st.markdown("<span class='muted'>A model trained on hand-labelled accounts reads each account's bio and "
                "own posts. Numbers below are cross-validated: every labelled account is scored by a model "
                "that never saw its label.</span>", unsafe_allow_html=True)
    m = REPORTS / "1A_metrics.csv"
    if m.exists():
        mt = pd.read_csv(m).iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("In-niche vs off-topic", f"{mt.in_niche_accuracy:.1%}")
        c1.markdown(gate_badge(mt.in_niche_accuracy), unsafe_allow_html=True)
        c2.metric("Main or 2nd segment right", f"{mt.segment_main_or_second:.1%}")
        c2.markdown(gate_badge(mt.segment_main_or_second), unsafe_allow_html=True)
        c3.metric("Exact segment", f"{mt.segment_exact:.1%}")
        c4.metric("Hand labels", f"{int(mt.n_labels):,}")
    else:
        st.info("Run `uv run seeding segments` to record accuracy here.")

    if has_table("account_segments"):
        st.markdown("#### Account explorer")
        f1, f2, f3 = st.columns([1, 1, 2])
        segs = f1.multiselect("Segment", ["b2b", "ai", "tech", "none"], default=["b2b", "ai", "tech"],
                              format_func=SEG_NAMES.get)
        minc = f2.slider("Min confidence", 0.0, 1.0, 0.4, 0.05)
        search = f3.text_input("Search handle or bio", "")
        acc = q("""SELECT s.username, s.segment, s.also, round(s.confidence, 2) confidence, s.n_posts,
                          p.followers_count, p.description bio, 'https://x.com/' || s.username url
                   FROM account_segments s LEFT JOIN profiles p ON p.handle = s.username""")
        acc = acc[acc.segment.isin(segs) & (acc.confidence >= minc)]
        if search:
            mask = acc.username.str.contains(search, case=False) | acc.bio.fillna("").str.contains(search, case=False)
            acc = acc[mask]
        acc = acc.sort_values(["confidence", "followers_count"], ascending=False)
        st.caption(f"{len(acc):,} accounts")
        st.dataframe(acc.head(2000), hide_index=True, width="stretch", height=460,
                     column_config={**link_cfg(),
                                    "followers_count": st.column_config.NumberColumn("Followers", format="%d"),
                                    "segment": "Main", "also": "2nd", "n_posts": "Posts seen"})

# ---------------------------------------------------------------- 1A review
with tabs[2]:
    st.subheader("1A · Review the model's labels")
    st.markdown("Set **Correct segment** for each account (it starts as the model's guess) and tick "
                "**Reviewed**. Saving adds your answers to the training labels; the next "
                "`uv run seeding segments` learns from them and re-measures accuracy.")
    sample_path = REPORTS / "1A_segment_sample.csv"
    if not sample_path.exists():
        st.info("No review sample yet. Run `uv run seeding segments`.")
    else:
        sample = pd.read_csv(sample_path)
        done = pd.read_csv(LABELS) if LABELS.exists() else pd.DataFrame(columns=["username", "grader"])
        reviewed_users = set(done[done.get("grader", "") == "user"].username) if len(done) else set()
        sample["correct_segment"] = sample["segment"]
        sample["reviewed"] = sample.username.isin(reviewed_users)
        edited = st.data_editor(
            sample[["reviewed", "correct_segment", "segment", "also", "username", "url", "confidence",
                    "followers_count", "bio", "example_posts"]],
            hide_index=True, width="stretch", height=520,
            disabled=["segment", "also", "username", "url", "confidence", "followers_count", "bio", "example_posts"],
            column_config={
                **link_cfg(),
                "reviewed": st.column_config.CheckboxColumn("Reviewed"),
                "correct_segment": st.column_config.SelectboxColumn("Correct segment",
                                                                    options=["b2b", "ai", "tech", "none"]),
                "segment": "Model said", "also": "2nd",
                "followers_count": st.column_config.NumberColumn("Followers", format="%d"),
            })
        rev = edited[edited.reviewed]
        agree = (rev.correct_segment == rev.segment) | (rev.correct_segment == rev.also)
        c1, c2 = st.columns([1, 3])
        c1.metric("Your agreement with the model", f"{agree.mean():.0%}" if len(rev) else "—",
                  f"{len(rev)} reviewed", delta_color="off")
        if SLIM:
            c2.info("This is the deployed snapshot: reviews can't be saved here (the server's disk is "
                    "temporary). Review in the local dashboard, or download your marks below and send them.")
            c2.download_button("Download my review (CSV)", rev.to_csv(index=False).encode("utf-8-sig"),
                               file_name="1A_review.csv", disabled=rev.empty)
        elif c2.button("Save my review to training labels", type="primary", disabled=rev.empty):
            new = pd.DataFrame({"username": rev.username, "expected": rev.correct_segment,
                                "grader": "user", "note": "dashboard review"})
            base = done[~done.username.isin(new.username)] if len(done) else done
            pd.concat([base, new]).to_csv(LABELS, index=False)
            st.success(f"Saved {len(new)} labels. Run `uv run seeding segments` to retrain.")

# ---------------------------------------------------------------- 1B core
with tabs[3]:
    st.subheader("1B · Core accounts: the hubs of each niche")
    st.markdown("<span class='muted'>Ranked by: niche certainty × how many <b>niche</b> accounts engage with "
                "them × reach, scored down for engagement-bait posting. Their replies, quotes and retweets "
                "define the seed map.</span>", unsafe_allow_html=True)
    if not has_table("core_accounts"):
        st.info("Run `uv run seeding core`.")
    else:
        seg = st.radio("Niche", ["b2b", "ai", "tech"], horizontal=True, format_func=SEG_NAMES.get, key="core_seg")
        core = q("""SELECT core_rank rank, username, round(p_seg, 2) niche_p, followers_count, niche_in_accounts,
                           round(niche_share, 2) niche_share, round(bait_share, 2) bait_share, is_client, bio,
                           'https://x.com/' || username url
                    FROM core_accounts WHERE core_segment = ? ORDER BY core_rank""", [seg])
        c1, c2, c3 = st.columns(3)
        c1.metric("Core accounts", len(core))
        c2.metric("Median followers", f"{int(core.followers_count.median()):,}")
        c3.metric("Clients among them", int(core.is_client.sum()))
        st.dataframe(core, hide_index=True, width="stretch", height=520,
                     column_config={**link_cfg(),
                                    "followers_count": st.column_config.NumberColumn("Followers", format="%d"),
                                    "niche_in_accounts": "Niche engagers", "niche_share": "Niche share",
                                    "bait_share": "Bait share", "is_client": "Client"})

# ---------------------------------------------------------------- 1B seeds
with tabs[4]:
    st.subheader("1B · Seed maps: who each niche actually talks to")
    if not has_table("seed_map"):
        st.info("Seed maps appear after the core-account scrape finishes and `uv run seeding seeds` runs.")
    else:
        seg = st.radio("Niche", ["b2b", "ai", "tech"], horizontal=True, format_func=SEG_NAMES.get, key="seed_seg")
        sm = q("""SELECT rank, username, round(seed_score, 2) score, n_core, from_core, to_core,
                         round(p_seg, 2) niche_p, known, followers_count, reason, bio,
                         'https://x.com/' || username url
                  FROM seed_map WHERE seg = ? ORDER BY rank""", [seg])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Seeds", f"{len(sm):,}")
        c2.metric("Median core accounts touching each", f"{sm.n_core.median():.0f}")
        c3.metric("Niche known from bio/posts", f"{sm.known.mean():.0%}")
        c4.metric("Median followers", f"{sm.followers_count.median():,.0f}")
        hist = alt.Chart(sm).mark_bar(color=SEG_COLORS[seg], cornerRadiusEnd=3).encode(
            x=alt.X("score:Q", bin=alt.Bin(maxbins=40), title="Seed score"),
            y=alt.Y("count():Q", title="Accounts"),
            tooltip=[alt.Tooltip("count():Q", title="Accounts")]).properties(height=160)
        st.altair_chart(hist, width="stretch")
        query = st.text_input("Search seeds", "", key="seed_q")
        if query:
            sm = sm[sm.username.str.contains(query, case=False) | sm.bio.fillna("").str.contains(query, case=False)]
        st.dataframe(sm, hide_index=True, width="stretch", height=480,
                     column_config={**link_cfg(),
                                    "followers_count": st.column_config.NumberColumn("Followers", format="%d"),
                                    "n_core": "Core accts", "from_core": "Core → them", "to_core": "Them → core"})
        st.download_button("Download this seed map (CSV)", sm.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"seed_map_{seg}.csv")

# ---------------------------------------------------------------- clients
with tabs[5]:
    st.subheader("Clients: does the seed map match who really engages?")
    ho = REPORTS / "1B_holdout.csv"
    if not ho.exists():
        st.info("The hold-out test runs with `uv run seeding seeds`.")
    else:
        h = pd.read_csv(ho)
        st.markdown("Seed map rebuilt **without any client-touching interaction**, then compared with each "
                    "pilot client's real repliers and quoters (last 60 days). The share is the client's "
                    "**baseline niche share**: the number later phases try to raise.")
        long = pd.concat([
            h.assign(group="Client's real engagers", share=h.in_seed_map),
            h.assign(group="Random accounts (baseline)", share=h.baseline)])
        chart = alt.Chart(long).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("client:N", title=None), yOffset="group:N",
            x=alt.X("share:Q", axis=alt.Axis(format="%"), title="Share found in the seed map"),
            color=alt.Color("group:N", scale=alt.Scale(range=["#2a78d6", "#a3a29b"]),
                            legend=alt.Legend(orient="top", title=None)),
            tooltip=["client", "group", alt.Tooltip("share:Q", format=".1%")]).properties(height=240)
        st.altair_chart(chart, width="stretch")
        show = h.assign(in_seed_map=h.in_seed_map.map("{:.1%}".format), baseline=h.baseline.map("{:.1%}".format),
                        lift=h.lift.map("{:.1f}×".format))
        st.dataframe(show, hide_index=True, width="stretch")

    st.markdown("#### Client → segment map")
    cs = pd.DataFrame([(h, ", ".join(SEG_NAMES[s] for s in v), h in CFG["pilot_clients"])
                       for h, v in CFG["client_segments"].items()], columns=["client", "segments", "pilot"])
    st.dataframe(cs, hide_index=True, width="stretch")
    st.caption("Edit in config/segments.yaml.")

# ---------------------------------------------------------------- 1C content
DIMENSIONS = {"format": "Format", "hook": "Opening line (hook)", "topic": "Topic", "length": "Length",
              "hour_block": "Posting time (UTC)", "weekday": "Weekday", "day_slot": "Same-day position"}

with tabs[6]:
    st.subheader("1C · What worked, per client")
    if not has_table("post_perf"):
        st.info("Run `uv run seeding content`.")
    else:
        pp = q("SELECT * FROM post_perf")
        client = st.radio("Client", sorted(pp.client.unique()), horizontal=True, key="c_client")
        d = pp[pp.client == client].copy()
        st.markdown("<span class='muted'>Each post's X-weighted score (replies ×5, quotes ×5, reposts ×1, likes ×0.66, "
                    "from X's published ranker defaults) is compared with the median of the client's previous 20 "
                    "posts. 1.5× = 50% better than usual for this account. Associations in past data, not proof "
                    "of cause; the real ranker scores predicted actions per viewer, so this is an approximation."
                    "</span>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Original posts analysed", f"{len(d):,}")
        c2.metric("Median views", f"{d.view_count.median():,.0f}")
        c3.metric("X-score per 1k views", f"{d.xscore_per_1k.median():.1f}")
        ns = d.niche_share.mean()
        c4.metric("Niche share of engagers", "—" if pd.isna(ns) else f"{ns:.0%}")

        dim = st.selectbox("Break down by", list(DIMENSIONS), format_func=DIMENSIONS.get, key="c_dim")
        rows = []
        for key, g in d.groupby(dim):
            r = g.rel_perf.dropna()
            rows.append({"group": str(key), "posts": len(g), "median_rel": r.median() if len(r) else None,
                         "beat_median": (r > 1).mean() if len(r) else None,
                         "median_views": g.view_count.median(), "niche_share": g.niche_share.mean()})
        bd = pd.DataFrame(rows).sort_values("median_rel", ascending=False)
        bd["reliable"] = bd.posts >= 5
        bd["label"] = bd.apply(lambda r: f"{r.median_rel:.2f}× · {r.posts} posts" if pd.notna(r.median_rel) else "", axis=1)
        base = alt.Chart(bd).encode(
            y=alt.Y("group:N", sort="-x", title=None),
            x=alt.X("median_rel:Q", title="Median vs own baseline (1.0 = usual)",
                    axis=alt.Axis(grid=True, gridOpacity=0.25)),
            tooltip=[alt.Tooltip("group:N", title=DIMENSIONS[dim]), alt.Tooltip("posts:Q"),
                     alt.Tooltip("median_rel:Q", title="Median vs baseline", format=".2f"),
                     alt.Tooltip("beat_median:Q", title="Beat own median", format=".0%"),
                     alt.Tooltip("median_views:Q", title="Median views", format=",.0f"),
                     alt.Tooltip("niche_share:Q", title="Niche share", format=".0%")])
        bars = base.mark_bar(cornerRadiusEnd=4, height=20).encode(
            color=alt.condition("datum.reliable", alt.value("#2a78d6"), alt.value("#b7d3f6")))
        text = base.mark_text(align="left", dx=6, color="#52514e").encode(text="label:N")
        rule = alt.Chart(pd.DataFrame({"x": [1.0]})).mark_rule(color="#8a8983", strokeDash=[4, 3]).encode(x="x:Q")
        st.altair_chart((bars + text + rule).properties(height=max(160, 34 * len(bd))), width="stretch")
        st.caption("Light bars: fewer than 5 posts, too few to trust. Dashed line: the account's usual level.")

        cols = ["rel_perf", "view_count", "format", "hook", "topic", "niche_share", "text", "url", "created_at"]
        cfgc = {**link_cfg(), "rel_perf": st.column_config.NumberColumn("vs baseline", format="%.2f×"),
                "view_count": st.column_config.NumberColumn("Views", format="%d"),
                "niche_share": st.column_config.NumberColumn("Niche share", format="percent")}
        rated = d.dropna(subset=["rel_perf"])
        left, right = st.columns(2)
        left.markdown("**Best posts**")
        left.dataframe(rated.sort_values("rel_perf", ascending=False).head(10)[cols], hide_index=True,
                       width="stretch", column_config=cfgc)
        right.markdown("**Weakest posts**")
        right.dataframe(rated.sort_values("rel_perf").head(10)[cols], hide_index=True,
                        width="stretch", column_config=cfgc)
        with st.expander("All posts"):
            st.dataframe(d.sort_values("created_at", ascending=False)[cols], hide_index=True, width="stretch",
                         column_config=cfgc, height=420)
        rp = REPORTS / f"1C_{client}.md"
        if rp.exists():
            with st.expander("Full written report (incl. data check against xplatform)"):
                st.markdown(rp.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- 1D model
with tabs[7]:
    st.subheader("1D · Does the model rank a client's posts better than simple rules?")
    bt = REPORTS / "1D_backtest.csv"
    if not bt.exists():
        st.info("Run `uv run seeding backtest`.")
    else:
        b = pd.read_csv(bt)
        st.markdown("<span class='muted'>Trained on posts before 15 Oct 2026, tested on later posts. "
                    "<b>Within-author Spearman</b>: does it put one account's posts in the right order "
                    "(0 = random, 1 = perfect). <b>Top-20% hit rate</b>: of the posts it ranks in an account's top "
                    "fifth, how many really were (random = 20%).</span>", unsafe_allow_html=True)
        m, a, bb = b.iloc[2], b.iloc[0], b.iloc[1]
        c1, c2, c3 = st.columns(3)
        c1.metric("Within-author Spearman (model)", f"{m.within_author_spearman:.2f}",
                  f"{m.within_author_spearman - max(a.within_author_spearman, bb.within_author_spearman):+.2f} vs best baseline")
        c2.metric("Top-20% hit rate (model)", f"{m.top20_hit_rate:.0%}", "random = 20%", delta_color="off")
        c3.metric("Mean abs error, log (model)", f"{m.mae_log:.2f}",
                  f"{m.mae_log - min(a.mae_log, bb.mae_log):+.2f} vs best baseline", delta_color="inverse")
        bars = alt.Chart(b).mark_bar(cornerRadiusEnd=4, height=22).encode(
            y=alt.Y("predictor:N", sort=None, title=None),
            x=alt.X("within_author_spearman:Q", title="Within-author Spearman", scale=alt.Scale(domain=[0, max(0.5, float(b.within_author_spearman.max()) + 0.05)])),
            color=alt.condition(alt.datum.predictor == "Model", alt.value("#2a78d6"), alt.value("#a3a29b")),
            tooltip=[alt.Tooltip("predictor:N"), alt.Tooltip("within_author_spearman:Q", format=".3f"),
                     alt.Tooltip("top20_hit_rate:Q", format=".0%"), alt.Tooltip("mae_log:Q", format=".3f")])
        lbl = bars.mark_text(align="left", dx=6, color="#52514e").encode(
            text=alt.Text("within_author_spearman:Q", format=".2f"), color=alt.value("#52514e"))
        st.altair_chart((bars + lbl).properties(height=140), width="stretch")
        st.dataframe(b, hide_index=True, width="stretch")
        pc = REPORTS / "1D_backtest_clients.csv"
        if pc.exists():
            st.markdown("**Pilot clients (few test posts each: direction, not proof)**")
            st.dataframe(pd.read_csv(pc), hide_index=True, width="stretch")
        rp = REPORTS / "1D_backtest.md"
        if rp.exists():
            with st.expander("Full backtest report"):
                st.markdown(rp.read_text(encoding="utf-8"))

    st.markdown("#### Live forward test")
    st.markdown("<span class='muted'>Each new pilot-client post is scored early, from earlier posts only, and "
                "checked against its real result once 48h old. Runs for two weeks before it is judged.</span>",
                unsafe_allow_html=True)
    lv = REPORTS / "1D_live.md"
    if has_table("live_preds"):
        lp = q("""SELECT client, created_at, round(age_at_scoring_h, 1) AS scored_at_age_h, format, hook,
                         round(expected_vs_usual, 2) AS expected_vs_usual FROM live_preds ORDER BY created_at DESC""")
        c1, c2 = st.columns(2)
        c1.metric("Posts scored live", len(lp))
        c2.metric("Old enough to check (48h+)",
                  int((pd.to_datetime(lp.created_at, utc=True) <= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)).sum()))
        st.dataframe(lp, hide_index=True, width="stretch")
    if lv.exists():
        st.markdown(lv.read_text(encoding="utf-8").split("\n", 2)[-1])

    st.markdown("#### Score a draft")
    model_ready = (ROOT / "data" / "model" / "lgb.txt").exists()
    if SLIM or not model_ready:
        st.info("Draft scoring runs in the local dashboard (it needs the trained model and the text model). "
                "Locally: `uv run seeding predict --client itsalexvacca --text \"...\"`.")
    else:
        with st.form("draft"):
            c1, c2 = st.columns([1, 1])
            client = c1.selectbox("Client", CFG["pilot_clients"] + [c for c in CFG["client_segments"] if c not in CFG["pilot_clients"]])
            when = c2.text_input("Planned time (UTC, blank = now)", "")
            fmt = c1.selectbox("Format", ["(auto)", "thread", "quote post", "article"])
            media = c2.checkbox("Has image/video")
            text = st.text_area("Draft", height=160)
            go = st.form_submit_button("Score draft", type="primary")
        if go and text.strip():
            import sys
            sys.path.insert(0, str(ROOT / "src"))
            from seeding.predict import score_draft
            try:
                r = score_draft(_con(), client, text, when or None, None if fmt == "(auto)" else fmt, has_media=media)
                c1, c2 = st.columns(2)
                c1.metric("Expected vs usual", f"{r['vs_usual']:.2f}×",
                          f"expected {r['expected_xscore']:.0f} vs usual {r['usual_xscore']:.0f}", delta_color="off")
                c2.metric("Read as", r["format"], r["hook"], delta_color="off")
                for k, d, pct in r["drivers"]:
                    st.markdown(f"- **{k}** {d} the estimate (~{pct}%)")
                for x in r["x_rules"]:
                    st.markdown(f"- X rule: {x}")
                st.caption("An estimate from past posts, not a guarantee. X's real ranker scores predicted "
                           "actions per viewer.")
            except ValueError as e:
                st.warning(str(e))

# ---------------------------------------------------------------- release the database
if _CON is not None:
    _CON.close()
    _CON = None
