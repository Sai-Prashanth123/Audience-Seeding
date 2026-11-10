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
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
# Streamlit Cloud re-runs this file after a git pull but keeps helper modules it already imported,
# so a new function in explain.py would raise ImportError. Always load the current helpers.
import importlib as _importlib  # noqa: E402
import explain as _explain  # noqa: E402
import github_store  # noqa: E402
_importlib.reload(_explain)
_importlib.reload(github_store)
import guide as _guide  # noqa: E402
_importlib.reload(_guide)
tab_guide = _guide.tab_guide
from explain import range_words  # noqa: E402
from explain import MEM_DIMS, memory_sentences  # noqa: E402
from explain import (accuracy_sentence, backtest_sentences, client_findings, engage_sentences,  # noqa: E402
                     holdout_sentence, rel_words, shared_lessons, tracking_sentences)

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
  .block-container {padding-top: 3.6rem; max-width: 1400px;}
  [data-testid="stMetricValue"] {font-size: 1.7rem;}
  .gate-pass {color:#0ca30c; font-weight:600}
  .gate-fail {color:#d03b3b; font-weight:600}
  .muted {color:#8a8983; font-size:0.85rem}

  /* Full-screen overlay, shown ONLY around slow actions that change something (saving to
     GitHub, scoring a draft) via busy(); tabs, filters and client pickers never trigger it. */
  .tp-overlay {position: fixed; inset: 0; z-index: 999999; background: rgba(14, 17, 23, 0.55);
    backdrop-filter: blur(1.5px); display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 18px; pointer-events: all;}
  .tp-spinner {width: 56px; height: 56px; border-radius: 50%; border: 5px solid rgba(255,255,255,0.25);
    border-top-color: #3987e5; animation: tp-spin .8s linear infinite;}
  .tp-msg {color: #f0efec; font-size: 1.05rem; font-weight: 600;}
  @keyframes tp-spin { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .tp-spinner {animation: none;} }
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


def _utc(ts) -> pd.Timestamp:
    """DuckDB returns TIMESTAMPTZ in the machine's local zone; labels say UTC, so convert."""
    t = pd.Timestamp(ts)
    return t.tz_convert("UTC") if t.tzinfo else t.tz_localize("UTC")


@st.cache_data(ttl=60, show_spinner=False)
def _github_status_cached(token_fingerprint: str) -> tuple[bool, str]:
    return github_store.status()


def _github_status() -> tuple[bool, str]:
    """At most one GitHub check a minute; a new or changed token is re-checked immediately."""
    import hashlib
    try:
        tok = str(st.secrets.get("GITHUB_TOKEN", ""))
    except Exception:
        tok = ""
    return _github_status_cached(hashlib.sha256(tok.encode()).hexdigest()[:16])


_github_status.clear = _github_status_cached.clear


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
    labels = base.mark_text(align="left", dx=6, color="#8a8983").encode(text=alt.Text(f"{x}:Q", format=","),
                                                                       color=alt.value("#8a8983"))
    return (bars + labels).properties(title=title, height=height)


import contextlib


@contextlib.contextmanager
def busy(message: str):
    """Full-screen dimmed overlay with a circular spinner while a slow action runs; removed after."""
    ph = st.empty()
    ph.markdown(f"<div class='tp-overlay'><div class='tp-spinner'></div><div class='tp-msg'>{message}</div></div>",
                unsafe_allow_html=True)
    try:
        yield
    finally:
        ph.empty()


def simple_words(lines: list[str], title: str = "📖 In simple words") -> None:
    """The plain-language box at the top of every tab. Every line is built from the data."""
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.markdown("\n".join(l if l.startswith(("- ", "⚠", "✅", "📣", "❌", "🎯", "👉", "How to read")) else f"- {l}"
                               for l in lines if l))


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
    "2A Engage list": has_table("engage_list"),
    "2B Tracking": has_table("track_weekly"),
}

# What is built vs still being proven. A step can be built (✅) yet still under a live check (🟡).
CHECKING = {"1D Model": "live test until ~21 Nov", "2A Engage list": "week-1 check", "2B Tracking": "verdict ~5 Dec"}
PHASES = {"Phase 1 · find the right audience": ["Setup", "1A Segments", "1B Core", "1B Seeds", "1B Hold-out",
                                                 "1C Content", "1D Model"],
          "Phase 2 · grow it every day": ["2A Engage list", "2B Tracking"]}


def _state(step: str) -> str:
    if not status.get(step):
        return "⬜"
    return "🟡" if step in CHECKING else "✅"


with st.sidebar:
    st.markdown("## 🎯 Audience Seeding")
    st.caption("Thought Pilot · Phase 1 built · Phase 2 running")
    for phase, steps in PHASES.items():
        st.markdown(f"**{phase}**")
        for step in steps:
            note = f" <span class='muted'>({CHECKING[step]})</span>" if _state(step) == "🟡" else ""
            st.markdown(f"{_state(step)} {step}{note}", unsafe_allow_html=True)
    st.caption("✅ built and checked · 🟡 built, still being proven · ⬜ not built")
    if has_table("trust_checks"):
        _tc = q("SELECT status, checked_at FROM trust_checks")
        _fails, _warns = int((_tc.status == "fail").sum()), int((_tc.status == "warn").sum())
        _when = _utc(_tc.checked_at.max()).strftime("%d %b %H:%M UTC")
        if _fails:
            st.error(f"❌ {_fails} trust check(s) failed ({_when}). See the Proof & trust tab.")
        elif _warns:
            st.warning(f"⚠️ Trust checks passed with {_warns} warning(s) ({_when}).")
        else:
            st.success(f"✅ All trust checks passed ({_when}).")
    if not KPI.empty and KPI.newest[0] is not None:
        st.caption(f"Newest post in data: {_utc(KPI.newest[0]):%d %b %Y %H:%M} UTC")
    st.caption(f"Source: {'results snapshot' if SLIM else 'live pipeline database'}")
    with st.expander("How to refresh the data"):
        st.markdown("Runs automatically: the live test every 4h, the Engage list + tracking daily at 06:00. "
                    "To rebuild everything by hand:")
        st.code("uv run seeding pull-corpus\nuv run seeding pull-profiles\nuv run seeding edges\n"
                "uv run seeding segments\nuv run seeding seeds\nuv run seeding content\n"
                "uv run seeding backtest\nuv run seeding engage\nuv run seeding track\n"
                "uv run seeding export-dashboard", language="bash")

_page_loading = st.spinner("Loading the latest data...")
_page_loading.__enter__()
_inniche = (int(q("SELECT count(*) n FROM account_segments WHERE segment <> 'none'").n[0])
            if has_table("account_segments") else None)
NUMS = {"posts": int(KPI.posts[0]) if not KPI.empty else None,
        "authors": int(KPI.authors[0]) if not KPI.empty else None,
        "edges": int(EDGES.n.sum()) if not EDGES.empty else None,
        "in_niche": _inniche,
        "p2_start": pd.Timestamp(str(CFG["phase2"]["start"])).strftime("%d %b %Y")}
NUMS = {k: v for k, v in NUMS.items() if v is not None}
tabs = st.tabs(["Overview", "1A · Segments", "1A · Review", "1B · Core accounts",
                "1B · Seed maps", "Clients", "1C · Content", "1D · Model", "2 · Engage today", "2 · Results",
                "✅ Proof & trust", "🧠 What it learned"])

# ---------------------------------------------------------------- overview
with tabs[0]:
    st.subheader("Where things stand")
    tab_guide("overview", **NUMS)
    k, e = KPI, EDGES.copy()
    _segc = (q("SELECT segment, count(*) n FROM account_segments WHERE segment <> 'none' GROUP BY 1")
             if has_table("account_segments") else pd.DataFrame(columns=["segment", "n"]))
    _segtxt = ", ".join(f"**{int(r.n):,} {SEG_NAMES[r.segment]}**"
                        for r in _segc.sort_values("n", ascending=False).itertuples())
    _done = [k2 for k2, v in status.items() if v]
    _todo = [k2 for k2, v in status.items() if not v]
    simple_words([
        "**The problem:** clients' posts reach the wrong people, or too few. X shows a post to people like the ones "
        "who already engage with the account, so engaging with random accounts teaches X the wrong audience.",
        "**What this tool does:** finds each client's real audience (Tech, B2B or AI), shows which of their posts "
        "work and with whom, and estimates how a draft will do before it goes out.",
        f"**What we looked at:** {int(k.posts[0]):,} posts from {int(k.authors[0]):,} accounts, and "
        f"{(int(e.n.sum()) if not e.empty else 0):,} conversations showing who replies to, quotes and retweets whom.",
        f"**Accounts sorted into a niche so far:** {_segtxt}." if _segtxt else "",
        f"**Built and checked:** {', '.join(x for x in _done if x not in CHECKING)}.",
        ("**Built, still being proven:** " + "; ".join(f"{x} ({CHECKING[x]})" for x in _done if x in CHECKING) + ".")
        if any(x in CHECKING for x in _done) else "",
        f"**Not built yet:** {', '.join(_todo)}." if _todo else "",
    ])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Posts stored", f"{k.posts[0]:,}")
    c2.metric("Accounts posting", f"{k.authors[0]:,}")
    c3.metric("Profiles", f"{k.profiles[0]:,}")
    c3.caption(f"{k.bios[0]:,} of them have a bio")
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
            e["Segment"] = e.kind.map({"reply": "Replies", "quote": "Quotes", "retweet": "Retweets"}).fillna(e.kind)
            e["seg"] = "none"
            st.altair_chart(seg_bar(e, "n", "Segment", "Interactions by type (who engages with whom)"),
                            width="stretch")
            st.caption("Likes and plain retweet lists can't be collected from X; replies, quotes and the "
                       "retweets an account makes can.")

# ---------------------------------------------------------------- 1A segments
with tabs[1]:
    st.subheader("1A · Who is Tech, B2B or AI")
    tab_guide("1a", **NUMS)
    _m = REPORTS / "1A_metrics.csv"
    if _m.exists():
        _mt = pd.read_csv(_m).iloc[-1]
        simple_words(["**What this does:** reads each account's bio and posts and decides if it belongs to Tech, B2B "
                      "or AI, or is off-topic (crypto, sports, politics, giveaway accounts)."]
                     + accuracy_sentence(_mt)
                     + ["**Main and second niche:** an AI founder selling to businesses is both AI and B2B, so an "
                        "account can have a second niche. Seed maps include both."])
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
    tab_guide("1a_review", **NUMS)
    simple_words([
        "**Why review:** the model learned from 368 accounts I checked by hand. Your own checks make it fit your "
        "idea of each niche.",
        "**How:** 1) look at the bio and example posts, 2) fix **Correct segment** if the model is wrong, "
        "3) tick **Reviewed**.",
        ("**Then:** press **Save my review (to GitHub)**. Your answers go into the repo, and the next weekly run "
         "learns from them and reports accuracy against your team's labels." if SLIM and github_store.available() else
         "**Then:** download your marks (this online copy can't save without a GitHub token) and send them over."
         if SLIM else
         "**Then:** press **Save**. The next `uv run seeding segments` learns from your answers and re-measures accuracy."),
    ])
    sample_path = REPORTS / "1A_segment_sample.csv"
    if not sample_path.exists():
        st.info("No review sample yet. Run `uv run seeding segments`.")
    else:
        done = pd.read_csv(LABELS) if LABELS.exists() else pd.DataFrame(columns=["username", "grader"])
        reviewed_users = set(done[done.get("grader", "") == "user"].username) if len(done) else set()
        queue_path = REPORTS / "1A_human_queue.csv"
        if queue_path.exists() and len(pd.read_csv(queue_path)):
            q_ = pd.read_csv(queue_path)
            n_dis = int((q_.kind == "AI and model disagree").sum())
            st.markdown(f"**Your queue this week: {len(q_)} accounts.** The AI reviewer checked the rest. "
                        f"{n_dis} are where the AI and the model **disagree** (that's where mistakes hide); "
                        f"{len(q_) - n_dis} are a **random audit** of accounts they agree on, which keeps the "
                        "AI reviewer honest.")
            sample = q_.rename(columns={"model_segment": "segment", "model_also": "also"})
            sample["correct_segment"] = sample["ai_segment"]
            cols = ["reviewed", "correct_segment", "kind", "segment", "also", "ai_segment", "ai_reason",
                    "username", "url", "bio"]
            labels_cfg = {"kind": "Why you see it", "segment": "Model said", "also": "Model 2nd",
                          "ai_segment": "AI said", "ai_reason": st.column_config.TextColumn("AI's reason", width="large")}
        else:
            sample = pd.read_csv(sample_path)
            sample["correct_segment"] = sample["segment"]
            cols = ["reviewed", "correct_segment", "segment", "also", "username", "url", "confidence",
                    "followers_count", "bio", "example_posts"]
            labels_cfg = {"segment": "Model said", "also": "2nd",
                          "followers_count": st.column_config.NumberColumn("Followers", format="%d")}
        sample["reviewed"] = sample.username.isin(reviewed_users)
        edited = st.data_editor(
            sample[cols], hide_index=True, width="stretch", height=520,
            disabled=[c for c in cols if c not in ("reviewed", "correct_segment")],
            column_config={
                **link_cfg(),
                "reviewed": st.column_config.CheckboxColumn("Reviewed"),
                "correct_segment": st.column_config.SelectboxColumn("Correct segment",
                                                                    options=["b2b", "ai", "tech", "none"]),
                **labels_cfg,
            })
        rev = edited[edited.reviewed]
        _gh_ok = False
        if SLIM:
            with st.spinner("Checking the connection to GitHub..."):
                _gh_ok, _gh_why = _github_status()
            (st.success if _gh_ok else st.warning)(f"Saving to GitHub: {'ON' if _gh_ok else 'OFF'} ({_gh_why}).")
        agree = (rev.correct_segment == rev.segment) | (rev.correct_segment == rev.also)
        c1, c2 = st.columns([1, 3])
        c1.metric("Your agreement with the model", f"{agree.mean():.0%}" if len(rev) else "—",
                  f"{len(rev)} reviewed", delta_color="off")
        if SLIM and github_store.available():
            if c2.button("Save my review (to GitHub)", type="primary", disabled=rev.empty or not _gh_ok):
                new = pd.DataFrame({"username": rev.username, "expected": rev.correct_segment,
                                    "grader": "user", "note": "dashboard review"})
                try:
                    with busy(f"Saving {len(new)} labels to GitHub…"):
                        n_saved = github_store.merge_csv("data/labels/1A_claude_grades.csv", new, "username",
                                                         f"1A review: {len(new)} labels from the dashboard")
                    c2.success(f"✅ Saved {n_saved} labels to the repo. The next weekly run learns from them and "
                               "reports accuracy against your team's labels.")
                except github_store.SaveError as e:
                    _github_status.clear()
                    c2.error(f"❌ Not saved. {e}")
            if not _gh_ok:
                c2.download_button("Download my review (CSV) meanwhile", rev.to_csv(index=False).encode("utf-8-sig"),
                                   file_name="1A_review.csv", disabled=rev.empty)
        elif SLIM:
            c2.info("Saving needs a GitHub token in this app's secrets (GITHUB_TOKEN). Until then, download "
                    "your marks below and send them.")
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
    tab_guide("1b_core", **NUMS)
    st.markdown("<span class='muted'>Ranked by: niche certainty × how many <b>niche</b> accounts engage with "
                "them × reach, scored down for engagement-bait posting. Their replies, quotes and retweets "
                "define the seed map.</span>", unsafe_allow_html=True)
    if not has_table("core_accounts"):
        st.info("Run `uv run seeding core`.")
    else:
        seg = st.radio("Niche", ["b2b", "ai", "tech"], horizontal=True, format_func=SEG_NAMES.get, key="core_seg")
        _top = q("SELECT username FROM core_accounts WHERE core_segment = ? ORDER BY core_rank LIMIT 5", [seg])
        _n = int(q("SELECT count(*) n FROM core_accounts WHERE core_segment = ?", [seg]).n[0])
        simple_words([
            f"**These are the {_n} most important accounts in {SEG_NAMES[seg]}**: the people the niche follows and "
            f"talks to. Top 5: {', '.join('@' + u for u in _top.username)}.",
            "**How they were picked:** many *niche* people reply to and quote them (not just many people), and "
            "they're clearly in the niche. Accounts that post engagement bait (\"HOLY F*CK…\", \"goldmine\") are scored down.",
            "**Why they matter:** who these hubs talk to is who the niche really is. That builds the seed map in the next tab.",
        ])
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
    tab_guide("1b_seeds", **NUMS)
    if not has_table("seed_map"):
        st.info("Seed maps appear after the core-account scrape finishes and `uv run seeding seeds` runs.")
    else:
        seg = st.radio("Niche", ["b2b", "ai", "tech"], horizontal=True, format_func=SEG_NAMES.get, key="seed_seg")
        sm = q("""SELECT rank, username, round(seed_score, 2) score, n_core, from_core, to_core,
                         round(p_seg, 2) niche_p, known, followers_count, reason, bio,
                         'https://x.com/' || username url
                  FROM seed_map WHERE seg = ? ORDER BY rank""", [seg])
        simple_words([
            f"**These {len(sm):,} people are who the {SEG_NAMES[seg]} niche actually talks to.** Engage with them "
            "before a client posts, so X learns the client belongs in this conversation.",
            f"**Top 5 right now:** {', '.join('@' + u for u in sm.username.head(5))}.",
            f"**Typical size:** {sm.followers_count.median():,.0f} followers. Mid-size accounts are the ones that reply "
            "back. Accounts over 3M followers are left out because they never reply to a client.",
            f"**Each one is backed by data:** the *Reason* column says how many niche hubs they talk with. "
            f"{sm.known.mean():.0%} of them have a known niche from their own bio or posts.",
        ])
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
    tab_guide("clients", **NUMS)
    ho = REPORTS / "1B_holdout.csv"
    if not ho.exists():
        st.info("The hold-out test runs with `uv run seeding seeds`.")
    else:
        h = pd.read_csv(ho)
        if has_table("proof"):
            _pl = q("SELECT client, lo AS lift_lo, hi AS lift_hi FROM proof WHERE claim LIKE 'Seed map finds%'")
            h = h.merge(_pl, on="client", how="left")
        simple_words(
            ["**The test:** I built the seed map *without any client data*, then checked whether the people who "
             "really engage with each client are in it. If the map is right, it should contain them far more "
             "often than random accounts."]
            + [holdout_sentence(r) for r in h.itertuples()]
            + [f"**What it means:** the map finds the right kind of people. The other "
               f"~{1 - h.in_seed_map.mean():.0%} of current engagers are outside the niche map. That share is each "
               "client's **starting point**, and the next phase tries to raise it."])
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
    tab_guide("1c", **NUMS)
    if not has_table("post_perf"):
        st.info("Run `uv run seeding content`.")
    else:
        pp = q("SELECT * FROM post_perf")
        _clients = sorted(pp.client.unique(), key=lambda c: (c not in CFG["phase2"]["treatment"], c.lower()))
        client = st.selectbox("Client", _clients, key="c_client",
                              format_func=lambda c: f"@{c}" + (" (gets the Engage list)" if c in CFG["phase2"]["treatment"] else ""))
        d = pp[pp.client == client].copy()
        _proven = (q("SELECT * FROM content_ci WHERE client = ?", [client]) if has_table("content_ci")
                   else None)
        _f = client_findings(d, _proven)

        def _item(x):
            return (f"- **{x['text']}**: {rel_words(x['rel'])}{range_words(x.get('lo'), x.get('hi'))} · "
                    f"{x['posts']} posts" + (f" · *{x['note']}*" if x["note"] else ""))

        _lines = ["How to read: **1.0× = a normal post for this person**, 2.0× = twice as good, 0.5× = half. "
                  "*Right audience* = share of people engaging who are in the client's niche."]
        if _f["few_posts"]:
            _lines.append(f"⚠ **Only {_f['n_posts']} posts: treat these as early hints, not rules.**")
        _lines.append("✅ **Do more:**")
        _lines += [_item(x) for x in _f["do_more"]] or ["- nothing clearly above usual yet"]
        if _f["reach_only"]:
            _lines.append("📣 **Big reach, but mostly the wrong audience (use now and then):**")
            _lines += [_item(x) for x in _f["reach_only"]]
        _lines.append("❌ **Do less:**")
        _lines += [_item(x) for x in _f["do_less"]] or ["- nothing clearly below usual"]
        if _f["builders"]:
            _lines.append("🎯 **Reaches the right audience (keep it going, even if reach is average):**")
            _lines += [_item(x) for x in _f["builders"]]
        if _f.get("not_proven"):
            _lines.append("❔ **Looks like a pattern, but NOT proven yet** (its likely range still includes "
                          "\"no different from usual\"; never used in the plan):")
            _lines += [_item(x) for x in _f["not_proven"]]
        if _f["plan"]:
            _lines.append(f"👉 **Simple plan for @{client}** (proven patterns only): " + "; ".join(_f["plan"]) + ".")
        simple_words(_lines, f"📖 In simple words: what works for @{client}")
        _shared = shared_lessons(pp)
        if _shared:
            simple_words(_shared + ["*These are patterns in past posts: what has worked, not a guarantee.*"],
                         "🌍 Lessons for all clients")
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
        text = base.mark_text(align="left", dx=6, color="#8a8983").encode(text="label:N")
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
    tab_guide("1d", **NUMS)
    bt = REPORTS / "1D_backtest.csv"
    if not bt.exists():
        st.info("Run `uv run seeding backtest`.")
    else:
        b = pd.read_csv(bt)
        _live = []
        if has_table("live_preds"):
            _lp = q("SELECT created_at FROM live_preds")
            _ready = int((pd.to_datetime(_lp.created_at, utc=True)
                          <= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)).sum())
            _live = [f"**Live test:** {len(_lp)} new posts scored *before* their results were known; {_ready} are old "
                     "enough to check (48h). It runs every 4 hours for two weeks before we judge it."]
        simple_words(["**What this does:** you give it a draft, and it estimates how it will do compared with the "
                      "client's usual post, and explains why."]
                     + backtest_sentences(b) + _live)
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
        lbl = bars.mark_text(align="left", dx=6, color="#8a8983").encode(
            text=alt.Text("within_author_spearman:Q", format=".2f"), color=alt.value("#8a8983"))
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
                with busy("Scoring the draft…"):
                    r = score_draft(_con(), client, text, when or None, None if fmt == "(auto)" else fmt,
                                    has_media=media)
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

# ---------------------------------------------------------------- phase 2A engage today
with tabs[8]:
    st.subheader("2 · Engage today: who each client should reply to")
    tab_guide("engage", **NUMS)
    if not has_table("engage_list"):
        st.info("No list yet. Run `uv run seeding engage` (runs daily at 06:00 once scheduled).")
    else:
        el = q("SELECT * FROM engage_list")
        dates = sorted(el.list_date.unique(), reverse=True)
        c1, c2 = st.columns([1, 2])
        day = c1.selectbox("List date", dates, format_func=lambda d: pd.Timestamp(d).strftime("%a %d %b %Y"))
        clients_here = [c for c in CFG["phase2"]["treatment"] if c in set(el.client)]
        client = c2.radio("Client", clients_here, horizontal=True, key="eng_client")
        lst = el[(el.list_date == day) & (el.client == client)].sort_values("list_rank")
        cov = q("SELECT * FROM engage_coverage WHERE client = ?", [client]) if has_table("engage_coverage") else pd.DataFrame()
        simple_words(engage_sentences(client, len(lst), day, cov))
        show = lst.assign(post=lst.text.fillna("").str.replace(r"https?://\S+", "", regex=True).str.slice(0, 220),
                          who="@" + lst.author)
        st.dataframe(show[["list_rank", "who", "post", "reason", "url"]], hide_index=True, width="stretch",
                     height=min(760, 60 + 35 * len(show)),
                     column_config={"list_rank": st.column_config.NumberColumn("#", width="small"),
                                    "who": st.column_config.TextColumn("Account", width="small"),
                                    "post": st.column_config.TextColumn("Their post", width="large"),
                                    "reason": st.column_config.TextColumn("Why it's on the list", width="medium"),
                                    "url": st.column_config.LinkColumn("Open on X", display_text="reply ↗")})
        st.download_button("Download today's list (CSV)", show.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"engage_{client}_{pd.Timestamp(day):%Y-%m-%d}.csv")

        st.markdown("#### Is this list any good? (week-1 check)")
        st.markdown("<span class='muted'>Tick the posts that are genuinely worth this client replying to. "
                    "The goal is 80% or more; if it's lower, the ranking gets fixed before we judge the results."
                    "</span>", unsafe_allow_html=True)
        rv_path = ROOT / "data" / "labels" / "2A_list_review.csv"
        prior = pd.read_csv(rv_path, dtype=str) if rv_path.exists() else pd.DataFrame(columns=["tweet_id", "worth"])
        rv = show[["tweet_id", "who", "post"]].copy()
        human = rv.tweet_id.astype(str).map(dict(zip(prior.tweet_id, prior.worth)))
        if has_table("engage_ai"):
            _ai = q("SELECT tweet_id, worth, reason FROM engage_ai WHERE status = 'ok'")
            rv["ai_says"] = rv.tweet_id.astype(str).map(
                {t: ("✅ worth it" if w else "❌ skip") + f": {r}" for t, w, r in zip(_ai.tweet_id, _ai.worth, _ai.reason)})
            ai_worth = rv.tweet_id.astype(str).map(dict(zip(_ai.tweet_id, _ai.worth)))
            st.caption("The AI reviewer's verdict is pre-ticked; people only need to spot-check and change "
                       "the ones they disagree with.")
        else:
            ai_worth = pd.Series(index=rv.index, dtype=object)
        rv["worth"] = [h == "y" if isinstance(h, str) else bool(a) if a == a and a is not None else False
                       for h, a in zip(human, ai_worth)]
        ed = st.data_editor(rv, hide_index=True, width="stretch",
                            disabled=[c for c in rv.columns if c != "worth"],
                            column_config={"worth": st.column_config.CheckboxColumn("Worth replying?"),
                                           "ai_says": st.column_config.TextColumn("AI reviewer", width="large"),
                                           "tweet_id": None}, key=f"rv_{client}_{day}")
        n_yes = int(ed.worth.sum())
        st.caption(f"{n_yes} of {len(ed)} ticked as worth replying ({n_yes / max(len(ed), 1):.0%}).")
        if SLIM and github_store.available():
            with st.spinner("Checking the connection to GitHub..."):
                _ok2, _why2 = _github_status()
            if not _ok2:
                st.warning(f"Saving to GitHub: OFF ({_why2}).")
            if st.button("Save review (to GitHub)", key=f"gh_{client}_{day}", disabled=not _ok2):
                new = ed.assign(worth=ed.worth.map({True: "y", False: "n"}), client=client, list_date=str(day))[
                    ["tweet_id", "client", "list_date", "worth"]].astype(str)
                try:
                    with busy(f"Saving {len(new)} answers to GitHub…"):
                        github_store.merge_csv("data/labels/2A_list_review.csv", new, "tweet_id",
                                               f"2A list review: {client} {day}")
                    st.success(f"✅ Saved {len(new)} answers to the repo.")
                except github_store.SaveError as e:
                    _github_status.clear()
                    st.error(f"❌ Not saved. {e}")
        elif SLIM:
            st.download_button("Download my review (CSV)", ed.assign(worth=ed.worth.map({True: "y", False: "n"}))
                               .to_csv(index=False).encode("utf-8-sig"), file_name="2A_list_review.csv")
        elif st.button("Save review", key=f"save_{client}_{day}"):
            new = ed.assign(worth=ed.worth.map({True: "y", False: "n"}), client=client, list_date=str(day))[
                ["tweet_id", "client", "list_date", "worth"]].astype(str)
            keep = prior[~prior.tweet_id.isin(new.tweet_id)] if len(prior) else prior
            rv_path.parent.mkdir(parents=True, exist_ok=True)
            pd.concat([keep, new]).to_csv(rv_path, index=False)
            st.success(f"Saved {len(new)} answers.")

# ---------------------------------------------------------------- phase 2B results
with tabs[9]:
    st.subheader("2 · Results: is the right audience growing?")
    tab_guide("results", **NUMS)
    if not has_table("track_weekly"):
        st.info("Run `uv run seeding track` (runs daily once scheduled).")
    else:
        tw = q("SELECT * FROM track_weekly")
        tr_ = q("SELECT * FROM track_replies") if has_table("track_replies") else pd.DataFrame()
        rb = q("SELECT * FROM track_reply_back") if has_table("track_reply_back") else pd.DataFrame()
        simple_words(tracking_sentences(tw, CFG["phase2"]["start"], tr_, rb))
        tw["week"] = pd.to_datetime(tw.week)
        start = pd.Timestamp(str(CFG["phase2"]["start"]))
        line = alt.Chart(tw).mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2).encode(
            x=alt.X("week:T", title=None),
            y=alt.Y("niche_share:Q", axis=alt.Axis(format="%"), title="Right-audience share of engagers"),
            color=alt.Color("client:N", legend=alt.Legend(orient="top", title=None)),
            strokeDash=alt.StrokeDash("group:N", legend=alt.Legend(orient="top", title=None),
                                      scale=alt.Scale(domain=["treatment", "control"], range=[[1, 0], [5, 4]])),
            tooltip=["client", "group", alt.Tooltip("week:T", format="%d %b"), "engagers",
                     alt.Tooltip("niche_share:Q", format=".0%")])
        rule = alt.Chart(pd.DataFrame({"week": [start]})).mark_rule(color="#8a8983", strokeDash=[4, 3]).encode(x="week:T")
        st.altair_chart((line + rule).properties(height=300), width="stretch")
        st.caption("Solid lines: clients who get the list. Dashed: comparison clients. Grey line: lists started.")
        rp = REPORTS / "2_weekly.md"
        if rp.exists():
            with st.expander("Full weekly report"):
                st.markdown(rp.read_text(encoding="utf-8"))

# ---------------------------------------------------------------- proof & trust
with tabs[10]:
    st.subheader("✅ Proof & trust: can these numbers be believed?")
    tab_guide("proof", **NUMS)
    if not has_table("proof"):
        st.info("Run `uv run seeding proof`.")
    else:
        pr = q("SELECT * FROM proof")
        tc = q("SELECT * FROM trust_checks")
        when = _utc(tc.checked_at.max()).strftime("%d %b %Y %H:%M UTC")
        n_proven = int(pr.status.str.startswith("proven").sum())
        simple_words([
            "**Why this tab exists:** every number in this dashboard comes from real X data, and every claim "
            "carries its own evidence: how many accounts or posts it rests on, and a **95% range**. A wide "
            "range means \"we're not sure yet\". A claim is called **proven** only when its whole range "
            "clears the bar (for example, a lift whose lowest plausible value is still above 1×).",
            f"**Right now:** {n_proven} of {len(pr)} claims are proven. The rest are either measured "
            "(a plain fact with its range) or flagged as weak or not proven, and the dashboard never turns "
            "those into advice.",
            "**Trust checks** below run automatically after every GitHub run. If one fails, the GitHub run "
            "turns red, you get an email, and the problem shows here in red, not hidden.",
            f"*Last checked {when}.*",
        ])
        st.markdown("#### Trust checks")
        icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
        for r in tc.itertuples():
            st.markdown(f"{icon.get(r.status, '•')} **{r.check}**  \n<span class='muted'>{r.detail}</span>",
                        unsafe_allow_html=True)
        st.markdown("#### Every claim, with its evidence")
        step = st.radio("Step", ["All"] + sorted(pr.step.unique()), horizontal=True, key="proof_step")
        show = pr if step == "All" else pr[pr.step == step]
        fmt = lambda v, u: "—" if pd.isna(v) else (f"{v:.0%}" if u == "%" else f"{v:.2f}{u}")
        table = show.assign(
            value_=[fmt(v, u) for v, u in zip(show.value, show.unit)],
            range_=[f"{fmt(l, u)} – {fmt(h, u)}" for l, h, u in zip(show.lo, show.hi, show.unit)])
        st.dataframe(table[["step", "client", "claim", "value_", "range_", "n", "status", "method", "evidence"]],
                     hide_index=True, width="stretch", height=min(700, 60 + 35 * len(table)),
                     column_config={"value_": "Value", "range_": "95% range", "n": "Based on (n)",
                                    "status": "Status", "claim": st.column_config.TextColumn("Claim", width="large")})
        if has_table("pipeline_runs"):
            st.markdown("#### When each step last ran")
            st.dataframe(q("SELECT step, finished_at FROM pipeline_runs ORDER BY finished_at DESC"),
                         hide_index=True, width="stretch")
        rp = REPORTS / "proof.md"
        if rp.exists():
            st.download_button("Download the proof report (Markdown)", rp.read_bytes(), file_name="phase1_proof.md")

# ---------------------------------------------------------------- 🧠 memory
with tabs[11]:
    st.subheader("🧠 What it has learned (and remembers)")
    tab_guide("memory", **NUMS)
    if not has_table("pattern_memory"):
        st.info("No memory yet. The weekly run builds it (`uv run seeding memory`).")
    else:
        simple_words([
            "This works the way a person learns:",
            "- 👶 **Learns from others first.** A new or quiet client starts with what works for *all* clients "
            "(each client counts equally, so one big account can't speak for everyone). As their own posts pile up, "
            "their own evidence takes over.",
            "- 💾 **Remembers week by week.** Every Sunday it stores what each pattern did that week. "
            "Old weeks are never rewritten.",
            "- 🔁 **Builds habits.** A pattern that clears the bar **3 weeks in a row** becomes a *habit*. "
            "Only habits (and, clearly labelled, *emerging* patterns) go into the plan.",
            "- 🍂 **Forgets what stops working.** A pattern that stops clearing the bar first *fades*, then is "
            "*forgotten*. It stays in history but leaves the plan.",
            "- 😮 **Learns from surprises.** When a post does 3× better or worse than predicted, it is logged, "
            "and after 10 judged posts the client's predictions are corrected.",
            "- ⚡ **Adapts to new situations.** If a client's recent results break from their past, it learns "
            "faster for them until things settle.",
        ], "📖 In simple words: how it learns")
        pm_all = q("SELECT * FROM pattern_memory")
        modes = q("SELECT * FROM learning_mode") if has_table("learning_mode") else pd.DataFrame()
        _cl = sorted(pm_all.client.unique(), key=lambda c: (c not in CFG["phase2"]["treatment"], c.lower()))
        mclient = st.selectbox("Client", _cl, key="m_client")
        pm = pm_all[pm_all.client == mclient]
        mrow = modes[modes.client == mclient] if len(modes) else modes
        mode = mrow["mode"].iloc[0] if len(mrow) else "normal"
        sig = mrow["signals"].iloc[0] if len(mrow) else ""
        ms = memory_sentences(pm, mode, sig if isinstance(sig, str) else "")
        lines = ms["mode"]
        lines += ["🔁 **Habits** (proven several weeks in a row):"] + (ms["habits"] or ["- none yet"])
        if ms["emerging"]:
            lines += ["🌱 **Emerging** (newer, still being confirmed):"] + ms["emerging"]
        if ms["fading"]:
            lines += ["🍂 **Fading** (used to work, not lately):"] + ms["fading"]
        if ms["forgotten"]:
            lines += ["🗑 **Forgotten** (no longer used):"] + ms["forgotten"]
        if ms["plan"]:
            lines.append(f"👉 **Plan for @{mclient} from memory:** " + "; ".join(ms["plan"]) + ".")
        simple_words(lines, f"🧠 What it remembers about @{mclient}")

        if has_table("pattern_history"):
            ph = q("SELECT * FROM pattern_history WHERE client = ?", [mclient])
            if len(ph):
                opts = sorted({(d, v) for d, v in zip(ph.dim, ph.value)},
                              key=lambda dv: dv not in set(zip(pm.dim, pm.value)))
                pick = st.selectbox("See one pattern over the weeks", opts,
                                    format_func=lambda dv: f"{MEM_DIMS.get(dv[0], dv[0])}: {dv[1]}", key="m_pat")
                h = ph[(ph.dim == pick[0]) & (ph.value == pick[1])].sort_values("week")
                h["week"] = pd.to_datetime(h.week)
                base = alt.Chart(h).encode(x=alt.X("week:T", title="Week"))
                band = base.mark_area(opacity=0.25, color="#3987e5").encode(
                    y=alt.Y("lo:Q", title="vs usual (1.0 = normal)", scale=alt.Scale(type="log")), y2="hi:Q")
                line = base.mark_line(point=alt.OverlayMarkDef(size=60), strokeWidth=2, color="#3987e5").encode(
                    y="effect:Q", tooltip=[alt.Tooltip("week:T"), alt.Tooltip("effect:Q", format=".2f"),
                                           alt.Tooltip("lo:Q", format=".2f"), alt.Tooltip("hi:Q", format=".2f"),
                                           "n_own:Q", "source:N"])
                rule = alt.Chart(pd.DataFrame({"y": [1.0]})).mark_rule(strokeDash=[4, 4], color="#888").encode(y="y:Q")
                st.altair_chart(band + line + rule, width="stretch")
                st.caption("Line = effect that week; band = likely range. When the whole band is above (or below) "
                           "the dashed 1.0 line, the pattern cleared the bar that week.")
        if has_table("live_surprises"):
            sp = q("SELECT * FROM live_surprises WHERE lower(client) = lower(?)", [mclient])
            if len(sp):
                st.markdown("#### 😮 Surprises (3× better or worse than predicted)")
                st.dataframe(sp[["created_at", "expected_xscore", "actual", "actual_vs_expected"]],
                             hide_index=True, width="stretch")

_page_loading.__exit__(None, None, None)

# ---------------------------------------------------------------- release the database
if _CON is not None:
    _CON.close()
    _CON = None
