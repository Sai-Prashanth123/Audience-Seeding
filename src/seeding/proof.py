"""Proof for every Phase 1 claim, and automatic trust checks.

Every headline number gets: value, a 95% range, the sample size it rests on, the date of the
data, the method, and the evidence file. A claim is "proven" only if its range clears the bar
(e.g. a content group's range excludes 1.0x = "no different from usual"). Trust checks are
pass / warn / fail; `seeding proof --gate` exits non-zero on any fail so the GitHub run turns red.
"""

from __future__ import annotations

import inspect
import math

import duckdb
import numpy as np
import pandas as pd

from .seedmap import ROOT, load_config

RNG_SEED = 7
N_BOOT = 1000
MIN_N = {"1A": 50, "1B": 30, "1C": 15, "1D": 30}
# 1C tests ~40 groups per client, so a 95% range would let ~2 patterns "prove" themselves by luck.
# A 99% range plus at least 15 posts keeps lucky patterns out of the recommendations.
LEVEL_1C = 0.99


# ------------------------------------------------------------------ statistics
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a proportion k/n (well-behaved for small n and extreme p)."""
    if n == 0:
        return (float("nan"), float("nan"))
    k = min(max(k, 0), n)  # a count can't exceed its total (guards e.g. captured > X's lagging reply count)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def boot_ci(values: np.ndarray, stat=np.median, n_boot: int = N_BOOT, seed: int = RNG_SEED,
            level: float = 0.95) -> tuple[float, float]:
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    stats = [stat(rng.choice(v, len(v), replace=True)) for _ in range(n_boot)]
    tail = (1 - level) / 2 * 100
    return (float(np.percentile(stats, tail)), float(np.percentile(stats, 100 - tail)))


def boot_ratio_ci(a: np.ndarray, b: np.ndarray, n_boot: int = N_BOOT, seed: int = RNG_SEED) -> tuple[float, float]:
    """Range of mean(a) / mean(b) when both samples are resampled independently (lift)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    out = []
    for _ in range(n_boot):
        mb = rng.choice(b, len(b)).mean()
        if mb > 0:
            out.append(rng.choice(a, len(a)).mean() / mb)
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))) if out else (float("nan"),) * 2


def _claim(step, claim, value, lo, hi, n, status, method, evidence, client="", unit="") -> dict:
    return dict(step=step, client=client, claim=claim, value=value, lo=lo, hi=hi, n=int(n), unit=unit,
                status=status, method=method, evidence=evidence)


# ------------------------------------------------------------------ claims
def claims_1a() -> list[dict]:
    out = []
    cv_path = ROOT / "reports" / "1A_cv.csv"
    if not cv_path.exists():
        return out
    cv = pd.read_csv(cv_path)
    groups = [("Claude's hand labels", cv[cv.grader == "claude"]), ("the team's labels", cv[cv.grader == "user"]),
              ("the AI reviewer's labels", cv[cv.grader == "ai"])]
    for who, d in groups:
        if d.empty:
            out.append(_claim("1A", f"Accuracy vs {who}", float("nan"), float("nan"), float("nan"), 0,
                              "waiting for labels", "Wilson 95% interval, cross-validated predictions",
                              "reports/1A_cv.csv", unit="%"))
            continue
        inn, pin = d.expected != "none", d.predicted != "none"
        k, n = int((inn == pin).sum()), len(d)
        lo, hi = wilson(k, n)
        status = "proven" if n >= MIN_N["1A"] and lo >= 0.80 else (
            "weak (few labels)" if n < MIN_N["1A"] else "not yet proven above 80%")
        out.append(_claim("1A", f"In-niche vs off-topic accuracy, vs {who}", k / n, lo, hi, n, status,
                          "Wilson 95% interval on cross-validated predictions (model never saw the label)",
                          "reports/1A_cv.csv", unit="%"))
        both = d[inn & pin]
        if len(both):
            k2 = int(((both.predicted == both.expected) | (both.also == both.expected)).sum())
            lo2, hi2 = wilson(k2, len(both))
            st2 = "proven" if len(both) >= MIN_N["1A"] and lo2 >= 0.80 else (
                "weak (few labels)" if len(both) < MIN_N["1A"] else "not yet proven above 80%")
            out.append(_claim("1A", f"Right niche (main or 2nd), vs {who}", k2 / len(both), lo2, hi2, len(both), st2,
                              "Wilson 95% interval, in-niche accounts only", "reports/1A_cv.csv", unit="%"))
    return out


def reviewer_agreement() -> tuple[int, int]:
    """(agreements, n) between the AI reviewer and the team on accounts both labelled."""
    from .reviewer import AI_LABELS
    from .segments import LABELS
    if not AI_LABELS.exists() or not LABELS.exists():
        return 0, 0
    ai = pd.read_csv(AI_LABELS, dtype=str)
    ai = ai[ai.status == "ok"]
    team = pd.read_csv(LABELS, dtype=str)
    team = team[team.grader == "user"]
    m = team.merge(ai, on="username")
    if m.empty:
        return 0, 0
    agree = (m.expected == m.segment) | (m.expected == m.also.fillna(""))
    return int(agree.sum()), len(m)


def claims_reviewer(con) -> list[dict]:
    out = []
    k, n = reviewer_agreement()
    lo, hi = wilson(k, n)
    status = ("waiting for team reviews" if n == 0 else "weak (few audits)" if n < 30 else
              "proven" if lo >= 0.80 else "not yet proven above 80%")
    out.append(_claim("1A", "AI reviewer agrees with the team (random audits + disagreements)",
                      k / n if n else float("nan"), lo, hi, n, status,
                      "Wilson 95% interval; accounts labelled by both the AI reviewer and a person",
                      "data/labels/1A_ai_labels.csv + data/labels/1A_claude_grades.csv", unit="%"))
    if _has(con, "engage_ai"):
        ea = con.execute("SELECT * FROM engage_ai WHERE status = 'ok'").df()
        if len(ea):
            w = int(ea.worth.sum())
            lo2, hi2 = wilson(w, len(ea))
            out.append(_claim("2A", "Engage-list posts the AI reviewer judges worth replying to", w / len(ea),
                              lo2, hi2, len(ea), "measured", "Wilson 95% interval over all judged posts",
                              "engage_ai table", unit="%"))
    return out


def check_reviewer() -> dict:
    k, n = reviewer_agreement()
    if n < 30:
        return _check("AI reviewer stays in line with the team (>= 80% agreement)", "warn",
                      f"only {n} accounts reviewed by both so far; need 30 to judge")
    acc = k / n
    status = "pass" if acc >= 0.80 else ("warn" if acc >= 0.70 else "fail")
    return _check("AI reviewer stays in line with the team (>= 80% agreement)", status,
                  f"{acc:.0%} agreement on {n} accounts")


def claims_1b(con) -> list[dict]:
    if not _has(con, "holdout_detail"):
        return []
    det = con.execute("SELECT * FROM holdout_detail").df()
    out = []
    for client, d in det.groupby("client"):
        e = d[d.kind == "engager"].in_map.astype(float).to_numpy()
        r = d[d.kind == "random"].in_map.astype(float).to_numpy()
        if not len(e) or not len(r):
            continue
        lift = e.mean() / r.mean() if r.mean() else float("nan")
        lo, hi = boot_ratio_ci(e, r)
        status = ("proven" if len(e) >= MIN_N["1B"] and lo > 1 else
                  "weak (few engagers)" if len(e) < MIN_N["1B"] else "not proven")
        out.append(_claim("1B", "Seed map finds real engagers vs random accounts (lift)", lift, lo, hi, len(e),
                          status, "bootstrap 95% range, engagers and random accounts resampled; map built "
                          "with no client data; random accounts drawn from the niche-heavy corpus (conservative)",
                          "reports/1B_holdout.csv", client=client, unit="x"))
        slo, shi = wilson(int(e.sum()), len(e))
        out.append(_claim("1B", "Share of real engagers in the seed map (baseline niche share)", e.mean(), slo, shi,
                          len(e), "measured", "Wilson 95% interval", "reports/1B_holdout.csv", client=client, unit="%"))
    return out


def content_ci(con) -> pd.DataFrame:
    """Per client x dimension x group: median vs own baseline with a 95% range, and niche share range."""
    if not _has(con, "post_perf"):
        return pd.DataFrame()
    pp = con.execute("SELECT * FROM post_perf").df()
    rows = []
    for client, d in pp.groupby("client"):
        for dim in ["format", "hook", "topic", "length", "hour_block", "weekday", "day_slot"]:
            for key, g in d.groupby(dim):
                rel = g.rel_perf.dropna().to_numpy()
                if len(rel) < 2:
                    continue
                lo, hi = boot_ci(rel, level=LEVEL_1C)
                med = float(np.median(rel))
                if len(rel) < MIN_N["1C"]:
                    status = "too few posts"
                elif lo > 1:
                    status = "proven better"
                elif hi < 1:
                    status = "proven worse"
                else:
                    status = "not proven"
                ns = g.niche_share.dropna().to_numpy()
                nlo, nhi = boot_ci(ns, stat=np.mean) if len(ns) >= 2 else (float("nan"), float("nan"))
                rows.append(dict(client=client, dim=dim, value=str(key), posts=len(rel), rel=med, rel_lo=lo,
                                 rel_hi=hi, status=status, niche=float(ns.mean()) if len(ns) else float("nan"),
                                 niche_lo=nlo, niche_hi=nhi, niche_posts=len(ns)))
    return pd.DataFrame(rows)


def claims_1c(ci: pd.DataFrame) -> list[dict]:
    out = []
    if ci.empty:
        return out
    for r in ci[ci.status.isin(["proven better", "proven worse"])].itertuples():
        out.append(_claim("1C", f"{r.dim} = {r.value}: vs own usual level", r.rel, r.rel_lo, r.rel_hi, r.posts,
                          r.status, "bootstrap 99% range of the median vs the account's previous-20-post median "
                          "(stricter than 95% because ~40 groups are tested per client); needs 15+ posts",
                          "reports/1C_posts.csv", client=r.client, unit="x"))
    return out


def claims_1d(con) -> list[dict]:
    from scipy.stats import spearmanr
    if not _has(con, "backtest_preds"):
        return []
    t = con.execute("SELECT * FROM backtest_preds").df()
    per = []
    for a, g in t.groupby("author"):
        if len(g) < 5 or g.y.nunique() < 2:
            continue
        rho = {}
        for col in ["pred_A", "pred_B", "pred_model"]:
            rho[col] = spearmanr(g[col], g.y).statistic if g[col].nunique() > 1 else 0.0
        per.append(rho)
    if not per:
        return []
    per = pd.DataFrame(per).fillna(0.0)
    best_base = "pred_A" if per.pred_A.mean() >= per.pred_B.mean() else "pred_B"
    diff = (per.pred_model - per[best_base]).to_numpy()
    lo, hi = boot_ci(diff, stat=np.mean)
    m_lo, m_hi = boot_ci(per.pred_model.to_numpy(), stat=np.mean)
    status = "proven" if lo > 0 and len(per) >= MIN_N["1D"] else "not proven"
    return [
        _claim("1D", "Model ranks an account's posts (within-author Spearman)", per.pred_model.mean(), m_lo, m_hi,
               len(per), "measured", "bootstrap over accounts; test posts after the split date only",
               "reports/1D_backtest.md"),
        _claim("1D", "Model beats the best simple baseline (difference in ranking)", float(diff.mean()), lo, hi,
               len(per), status, "bootstrap over accounts of the per-account difference",
               "reports/1D_backtest.md"),
    ]


def capture_claims(xp, clients) -> list[dict]:
    """How much of each client's real reply/quote activity X lets us see (sample, not census)."""
    from datetime import date, timedelta
    out = []
    for c in clients:
        try:
            cov = xp.get(f"/datasets/engagements/coverage", client=c,
                         since=(date.today() - timedelta(days=60)).isoformat())
        except Exception:
            continue
        posts = pd.DataFrame(cov.get("posts", []))
        if posts.empty:
            continue
        posts = posts[posts.interactions.fillna(0) > 0]
        claimed = posts.interactions.sum()
        # X's reply count lags; we sometimes capture more than it reports. Never report above 100%.
        captured = min(posts.captured.sum(), claimed)
        if claimed:
            lo, hi = wilson(int(captured), int(claimed))
            out.append(_claim("data", "Share of replies + quotes X lets us collect", captured / claimed, lo, hi,
                              int(claimed), "measured", "captured / interactions X reports, last 60 days",
                              "/datasets/engagements/coverage", client=c, unit="%"))
    return out


# ------------------------------------------------------------------ trust checks
def _has(con, t: str) -> bool:
    return bool(con.execute("SELECT 1 FROM information_schema.tables WHERE table_name = ?", [t]).fetchall())


def _check(name, status, detail) -> dict:
    return dict(check=name, status=status, detail=detail)


def check_reconcile(con, xp, clients, tol: float = 0.05) -> dict:
    """Same posts and (within 5%) the same likes/views as xplatform's raw data, last full month, UTC days.

    Compared post by post with /datasets/tweets, not with the client summary: the summary applies
    its own counting rules (e.g. it drops posts that start with an @mention), which is a definition
    difference, not a data error.
    """
    from datetime import date, timedelta
    from .content import compare_with_xplatform
    last = date.today().replace(day=1) - timedelta(days=1)
    since, until = last.replace(day=1).isoformat(), last.isoformat()
    bad, ok = [], []
    for c in clients:
        r = compare_with_xplatform(xp, con, c, since, until)
        if r["posts_xplatform"] == 0 and r["posts_ours"] == 0:
            continue
        if r["missing_here"] or r["extra_here"]:
            bad.append(f"{c}: {r['missing_here']} posts missing here, {r['extra_here']} extra")
        for name in ("likes", "views"):
            if abs(r[f"{name}_dev"]) > tol:
                bad.append(f"{c} {name} off by {r[f'{name}_dev']:+.1%}")
        ok.append(f"{c} {r['posts_ours']} posts")
    return _check("Our data matches xplatform post by post (same posts; likes/views within 5%)",
                  "fail" if bad else "pass",
                  "; ".join(bad) if bad else f"{since[:7]}, UTC days: " + ", ".join(ok))


def check_leakage(con) -> dict:
    from . import content, track
    cfg = load_config()
    clients = {h.lower() for h in cfg["client_segments"]}
    problems = []
    if _has(con, "seed_map_holdout"):
        leaked = set(con.execute("SELECT username FROM seed_map_holdout").df().username) & clients
        if leaked:
            problems.append(f"clients inside the hold-out map: {sorted(leaked)}")
    else:
        problems.append("hold-out map missing")
    for mod in (content, track):
        if "seed_map_holdout" not in inspect.getsource(mod):
            problems.append(f"{mod.__name__} does not measure with the hold-out map")
    return _check("No client data leaks into what we measure", "fail" if problems else "pass",
                  "; ".join(problems) or "hold-out map has no clients; 1C and tracking read the hold-out map")


def check_freshness(con) -> dict:
    now = pd.Timestamp.now(tz="UTC")
    issues, notes = [], []
    # read timestamps through pandas (DuckDB's fetchone on TIMESTAMPTZ needs pytz, which we don't ship)
    newest = con.execute("SELECT max(created_at) AS m FROM tweets").df().m.iloc[0]
    age_h = (now - pd.Timestamp(newest)).total_seconds() / 3600 if newest else 1e9
    (issues if age_h > 36 else notes).append(f"newest post {age_h:.0f}h old")
    limits = {"engage": 36, "content": 36, "segments": 24 * 8, "seeds": 24 * 8, "backtest": 24 * 8, "live": 8}
    runs = (con.execute("SELECT * FROM pipeline_runs").df() if _has(con, "pipeline_runs")
            else pd.DataFrame(columns=["step", "finished_at"]))
    last = dict(zip(runs.step, runs.finished_at))
    for step, lim in limits.items():
        if step not in last:
            notes.append(f"{step}: no run recorded yet")
            continue
        h = (now - pd.Timestamp(last[step])).total_seconds() / 3600
        (issues if h > lim else notes).append(f"{step} {h:.0f}h ago")
    status = "fail" if issues else ("warn" if any("no run recorded" in n for n in notes) else "pass")
    return _check("Data is fresh (posts < 36h, daily steps < 36h, weekly < 8 days)", status,
                  "; ".join(issues + notes))


def check_samples(claims: pd.DataFrame) -> dict:
    weak = claims[claims.status.str.contains("weak|too few", na=False)]
    detail = ("; ".join(f"{r.step} {r.client or ''} {r.claim} (n={r.n})".strip() for r in weak.itertuples())
              if len(weak) else "every published claim has enough data")
    return _check("Every claim rests on enough data (weak ones are flagged, not hidden)",
                  "warn" if len(weak) else "pass", detail)


def check_time_split(con) -> dict:
    from .model import SPLIT
    if not _has(con, "backtest_preds"):
        return _check("1D test uses only posts after the split date", "warn", "no backtest yet")
    mn = con.execute("SELECT min(created_at) AS m FROM backtest_preds").df().m.iloc[0]
    ok = pd.Timestamp(mn) >= pd.Timestamp(SPLIT, tz="UTC")
    return _check("1D test uses only posts after the split date", "pass" if ok else "fail",
                  f"earliest test post {pd.Timestamp(mn):%d %b %Y} (split {SPLIT})")


# ------------------------------------------------------------------ run
def run(con: duckdb.DuckDBPyConnection, xp=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = load_config()
    asof = pd.Timestamp.now(tz="UTC")
    ci = content_ci(con)
    claims = claims_1a() + claims_reviewer(con) + claims_1b(con) + claims_1c(ci) + claims_1d(con)
    if xp is not None:
        claims += capture_claims(xp, cfg["pilot_clients"])
    claims = pd.DataFrame(claims)
    claims["as_of"] = asof
    checks = [check_leakage(con), check_freshness(con), check_samples(claims), check_time_split(con),
              check_reviewer()]
    if xp is not None:
        try:
            checks.insert(0, check_reconcile(con, xp, cfg["pilot_clients"]))
        except Exception as e:  # an unreachable API is itself worth flagging, not hiding
            checks.insert(0, _check("Our data matches xplatform post by post (same posts; likes/views within 5%)", "warn",
                                    f"could not reach xplatform: {e.__class__.__name__}"))
    checks = pd.DataFrame(checks).assign(checked_at=asof)
    con.execute("CREATE OR REPLACE TABLE proof AS SELECT * FROM claims")
    con.execute("CREATE OR REPLACE TABLE trust_checks AS SELECT * FROM checks")
    if len(ci):
        con.execute("CREATE OR REPLACE TABLE content_ci AS SELECT * FROM ci")
    write_report(claims, checks)
    return claims, checks


def write_report(claims: pd.DataFrame, checks: pd.DataFrame) -> None:
    icon = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    f = lambda v, u: "—" if pd.isna(v) else (f"{v:.0%}" if u == "%" else f"{v:.2f}{u}")
    lines = [f"# Phase 1 proof · {pd.Timestamp.now(tz='UTC'):%d %b %Y %H:%M} UTC", "", "## Trust checks", ""]
    lines += [f"- {icon.get(r.status, '•')} **{r.check}**: {r.detail}" for r in checks.itertuples()]
    lines += ["", "## Claims with 95% ranges", "", "| step | client | claim | value | 95% range | n | status |",
              "|---|---|---|---:|---|---:|---|"]
    for r in claims.itertuples():
        lines.append(f"| {r.step} | {r.client} | {r.claim} | {f(r.value, r.unit)} | {f(r.lo, r.unit)} – "
                     f"{f(r.hi, r.unit)} | {r.n} | {r.status} |")
    (ROOT / "reports" / "proof.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
