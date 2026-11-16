"""Write the Step 3 accuracy reports: backtest (with keep/drop decisions and the ceiling) and live."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..seedmap import ROOT
from . import evaluate as ev
from .model import OUT, keep

NAMES = {"A_usual": "A · the account's usual level", "B_usual_x_rules": "B · usual × X's same-day rule",
         "C_1D": "C · 1D (current model)", "C_1D_strict": "1D with strict 48h baselines (diagnostic)",
         "diag_L1_1Dbase": "L1 + 1D's baselines (diagnostic, not deployable)", "L1_lgbm": "LightGBM per action",
         "L1_lgbm+shrink": "LightGBM + per-account shrinkage", "L1_catboost": "CatBoost per action",
         "L1_ngboost": "NGBoost (distribution)", "stack": "Stack of the members"}
CANDIDATES = ["L1_lgbm", "L1_catboost", "L1_ngboost", "L1_lgbm+shrink", "stack"]


def ceiling(con, bt: pd.DataFrame) -> dict:
    """Twin-post ceiling on the backtest's test posts, for views and X score."""
    ids = bt.tweet_id.unique().tolist()
    vec = con.execute("SELECT tweet_id, vec FROM post_vecs WHERE tweet_id IN (SELECT unnest(?::VARCHAR[]))",
                      [ids]).df()
    vecs = {t: np.asarray(v, dtype=np.float32) for t, v in zip(vec.tweet_id, vec.vec)}
    out = {}
    for t in ("views", "xscore"):
        g = bt[(bt.target == t) & (bt.member == "A_usual")].drop_duplicates("tweet_id")
        out[t] = ev.noise_ceiling(g, vecs)
    return out


def decide(summary_a: pd.DataFrame, summary_c: pd.DataFrame) -> dict:
    """Protocol rule: a candidate must beat the account's usual level, and to replace 1D it must beat 1D."""
    out = {}
    for m in CANDIDATES:
        if m not in set(summary_a.member):
            continue
        out[m] = {"beats_usual": keep(summary_a, m, "A_usual"), "beats_1D": keep(summary_c, m, "C_1D")}
    return out


def choose(decisions: dict, summary_a: pd.DataFrame) -> list[str]:
    """Serve the best candidate that beats the usual level on views and X score (lowest X-score typical miss)."""
    ok = [m for m, d in decisions.items() if d["beats_usual"].get("views") and d["beats_usual"].get("xscore")]
    if not ok:
        return ["L1_lgbm"]
    s = summary_a[(summary_a.target == "xscore") & summary_a.member.isin(ok)].sort_values("typical_miss_x")
    best = s.member.iloc[0]
    # NGBoost is judged but not served (no light saved-model path); its place goes to LightGBM
    return {"stack": ["L1_lgbm", "L1_catboost"], "L1_lgbm+shrink": ["L1_lgbm"], "L1_ngboost": ["L1_lgbm"]}.get(best, [best])


def write_backtest(summary_a: pd.DataFrame, summary_c: pd.DataFrame, decisions: dict, ceil: dict, served: list,
                   n_posts: int, n_authors: int) -> str:
    f = lambda v, s="{:.3f}": "—" if v is None or (isinstance(v, float) and np.isnan(v)) else s.format(v)
    L = ["# Step 3 · Forecaster backtest", "",
         f"Rolling-origin test (protocol: `reports/3_protocol.md`): 4 back-to-back 14-day test windows, "
         f"**{n_posts:,} test posts from {n_authors} accounts**. Every model trained only on posts matured before "
         "its window and had its 80% ranges calibrated on the 14 days in between.", "",
         "**How to read:** *typical miss* 2.0× = usually off by a factor of 2 (1.0× would be perfect). "
         "*Ranking* = within-account Spearman (does it order one account's posts correctly; 0 = random). "
         "*In range* = share of posts inside the 80% range (should be ~80%).", ""]
    for t in ["views", "likes", "replies", "reposts", "quotes", "bookmarks", "xscore"]:
        s = summary_a[summary_a.target == t]
        if s.empty:
            continue
        L += [f"## {t}", "", "| predictor | typical miss | ranking | in 80% range | range width | CRPS | vs usual level |",
              "|---|---:|---:|---:|---:|---:|---|"]
        for r in s.sort_values("typical_miss_x").itertuples():
            vs = "" if pd.isna(getattr(r, "dm_p", np.nan)) else \
                f"{'better' if r.mae_gain > 0 else 'worse'} (p={r.dm_p:.3g}, gain {r.gain_lo:+.3f}…{r.gain_hi:+.3f})"
            L.append(f"| {NAMES.get(r.member, r.member)} | {r.typical_miss_x:.2f}× | {f(r.within_author_spearman)} | "
                     f"{r.coverage80:.0%} | {r.width_x:.1f}× | {r.crps:.3f} | {vs} |")
        L.append("")
    L += ["## Against 1D (the current model)", "", "| candidate | target | typical miss | 1D | significant? |",
          "|---|---|---:|---:|---|"]
    for r in summary_c[summary_c.vs == "C_1D"].itertuples():
        base = summary_c[(summary_c.target == r.target) & (summary_c.member == "C_1D")]
        if base.empty:
            continue
        sig = "better" if (r.dm_p < 0.05 and r.gain_lo > 0) else "worse" if (r.dm_p < 0.05 and r.gain_hi < 0) else "no clear difference"
        L.append(f"| {NAMES.get(r.member, r.member)} | {r.target} | {r.typical_miss_x:.2f}× | "
                 f"{base.typical_miss_x.iloc[0]:.2f}× | {sig} (p={r.dm_p:.3g}) |")
    L += ["", "## Keep / drop (pre-registered rule)", "",
          "| candidate | beats usual level (views, X score) | beats 1D (X score) |", "|---|---|---|"]
    for m, d in decisions.items():
        L.append(f"| {NAMES.get(m, m)} | {d['beats_usual'].get('views')}, {d['beats_usual'].get('xscore')} | "
                 f"{d['beats_1D'].get('xscore')} |")
    L += ["", f"**Served now:** {', '.join(NAMES.get(m, m) for m in served)}.", "",
          "## How close to the ceiling", ""]
    for t, c in ceil.items():
        best = summary_a[(summary_a.target == t) & summary_a.member.isin(CANDIDATES)].typical_miss_x.min()
        L.append(f"- **{t}:** {c['pairs']} same-author near-duplicate post pairs differ by a typical "
                 f"{f(c['twin_gap_x'], '{:.2f}')}×, so even a perfect content model would miss by about "
                 f"**{f(c['best_possible_miss_x'], '{:.2f}')}×**. Best model here: {best:.2f}×.")
    L += ["", "*A post's reach also depends on things no model sees before posting (who is online, whether a big "
          "account reposts it). That is why the after-posting nowcast exists.*"]
    path = ROOT / "reports" / "3_backtest.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "choice.json").write_text(json.dumps({"served": served, "decisions": decisions, "ceiling": ceil}, indent=1))
    return str(path)


def write_live(summary: pd.DataFrame) -> str:
    L = ["# Step 3 · Live forecasts", "",
         "Every client post gets a forecast frozen in `data/ledger/predictions.csv` before its result exists; it is "
         "judged here once the post is 48h old.", ""]
    if summary.empty:
        L.append("No judged forecasts yet. They appear 48h after the first forecast.")
    else:
        L += ["| client | action | posts | inside the 80% range | typical miss |", "|---|---|---:|---:|---:|"]
        for r in summary.sort_values(["client", "action"]).itertuples():
            L.append(f"| {r.client} | {r.action} | {r.posts} | {r.inside_80pct_range:.0%} | {r.typical_miss_x:.2f}× |")
    path = ROOT / "reports" / "3_live.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(path)
