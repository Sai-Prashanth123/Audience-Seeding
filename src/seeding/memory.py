"""Phase 1 memory: learn from others first, remember week by week, form habits, forget, adapt.

1. Learn from others (childhood -> own experience). A content pattern's effect for a client is a
   blend of the client's own posts and all clients' posts, weighted by experience:
   w = n / (n + K). A new or small client mostly follows the group; a client with many posts
   mostly follows itself (empirical-Bayes partial pooling). Topic clusters are client-specific,
   so topics use the client's own evidence only.
2. Long-term memory. Each weekly run ("sleep") stores every pattern's effect and 99% range for
   that week. Past weeks are never rewritten - that is what makes it memory.
3. Habits and forgetting. A lifecycle replayed over the stored weeks:
   new -> emerging -> habit; habit/emerging -> fading -> forgotten.
4. Adapting. A change detector compares each client's last 4 weeks with the 12 before; when the
   situation changed, the client learns faster (habits confirm sooner, forgetting is quicker, and
   the model weights recent posts more).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .seedmap import ROOT

K_POOL = 20                     # posts at which a client's own evidence counts as much as the group's
POOLED_DIMS = ["format", "hook", "length", "hour_block", "day_slot"]
OWN_ONLY_DIMS = ["topic"]
LEVEL = 0.99                    # same bar as 1C: ~40 groups tested per client
MIN_GROUP = 30                  # all-client posts needed before the group can teach anything
MIN_GROUP_CLIENTS = 3           # ...from at least this many clients (each with MIN_POSTS_PER_CLIENT)
MIN_POSTS_PER_CLIENT = 5
# Patterns that bring reach but the wrong audience (proven in 1C): remembered, never recommended.
REACH_ONLY = {("hook", "giveaway / comment-to-get")}
MIN_OWN_FOR_OWN_ONLY = 15
N_BOOT = 300
BACKFILL_WEEKS = 12
MEMORY_DIR = ROOT / "data" / "memory"
HISTORY_CSV = MEMORY_DIR / "history.csv"
PATTERNS_CSV = MEMORY_DIR / "patterns.csv"


@dataclass(frozen=True)
class Speed:
    habit_weeks: int = 3        # consecutive weeks clearing the bar -> habit
    fade_after: int = 2         # weeks not clearing before a habit/emerging pattern fades
    forget_after: int = 4       # further weeks fading before it is forgotten
    half_life_weeks: float = 12  # recency weighting for the model


NORMAL = Speed()
FAST = Speed(habit_weeks=2, fade_after=1, forget_after=2, half_life_weeks=4)


# ------------------------------------------------------------------ 1. pooled effects
def _log_rel(x: pd.Series) -> np.ndarray:
    return np.log(np.clip(x.astype(float).to_numpy(), 0.05, None))


def _boot_medians(x: np.ndarray, n_boot: int, rng) -> np.ndarray:
    if len(x) == 0:
        return np.zeros(n_boot)
    return np.median(x[rng.integers(0, len(x), size=(n_boot, len(x)))], axis=1)


def pooled_effect(own: np.ndarray, group: np.ndarray, k: float = K_POOL, n_boot: int = N_BOOT,
                  level: float = LEVEL, seed: int = 7, own_only: bool = False,
                  group_boot: np.ndarray | None = None, group_point: float | None = None,
                  n_group_clients: int = 0) -> dict:
    """Blend of a client's own median and the all-client median (log space), with a bootstrap range."""
    own = own[~np.isnan(own)]
    group = group[~np.isnan(group)]
    n, N = len(own), len(group)
    if own_only:
        if n < MIN_OWN_FOR_OWN_ONLY:
            return {}
        w = 1.0
    else:
        if group_boot is None and N < MIN_GROUP:
            return {}
        w = n / (n + k)
    rng = np.random.default_rng(seed)
    gb = np.zeros(n_boot) if w == 1 else (group_boot if group_boot is not None else _boot_medians(group, n_boot, rng))
    ob = _boot_medians(own, n_boot, rng)
    blend = w * ob + (1 - w) * gb
    gpoint = group_point if group_point is not None else (np.median(group) if N else 0.0)
    point = w * (np.median(own) if n else 0.0) + (1 - w) * (gpoint if w < 1 else 0.0)
    tail = (1 - level) / 2 * 100
    lo, hi = np.percentile(blend, tail), np.percentile(blend, 100 - tail)
    direction = "better" if lo > 0 else ("worse" if hi < 0 else "none")
    return {"effect": float(np.exp(point)), "lo": float(np.exp(lo)), "hi": float(np.exp(hi)),
            "n_own": n, "n_group": 0 if own_only else N, "group_clients": n_group_clients, "weight_own": round(w, 3),
            "source": "own evidence" if w >= 0.5 else "learned from all clients", "direction": direction}


def group_boot(by_client: dict[str, np.ndarray], n_boot: int, rng) -> tuple[float, np.ndarray] | None:
    """All-client effect where every client counts equally: median of per-client medians.

    Bootstrapped over clients (then posts within each), so the range shows how much clients
    disagree - one big client can't masquerade as "everyone".
    """
    xs = [x[~np.isnan(x)] for x in by_client.values()]
    xs = [x for x in xs if len(x) >= MIN_POSTS_PER_CLIENT]
    if len(xs) < MIN_GROUP_CLIENTS or sum(map(len, xs)) < MIN_GROUP:
        return None
    point = float(np.median([np.median(x) for x in xs]))
    meds = np.array([_boot_medians(x, n_boot, rng) for x in xs])         # clients x n_boot
    pick = rng.integers(0, len(xs), size=(n_boot, len(xs)))              # resample clients
    boot = np.median(meds[pick, np.arange(n_boot)[:, None]], axis=1)
    return point, boot


def _seed(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def week_snapshot(posts: pd.DataFrame, week_end: pd.Timestamp) -> pd.DataFrame:
    """Every (client, dimension, value) effect using only posts at least 48h old at week_end."""
    p = posts[pd.to_datetime(posts.created_at, utc=True) <= week_end - pd.Timedelta(hours=48)]
    p = p[p.rel_perf.notna()]
    rows = []
    clients = sorted(p.client.unique())
    for dim in POOLED_DIMS + OWN_ONLY_DIMS:
        own_only = dim in OWN_ONLY_DIMS
        for value, g in p.groupby(dim):
            group_y = _log_rel(g.rel_perf)
            gb = None
            if not own_only:
                by_client = {c: _log_rel(gc.rel_perf) for c, gc in g.groupby("client")}
                gb = group_boot(by_client, N_BOOT, np.random.default_rng(_seed(dim, value, week_end.date())))
                if gb is None:
                    continue
                n_gc = sum(len(x) >= MIN_POSTS_PER_CLIENT for x in by_client.values())
            for c in clients:
                own_y = _log_rel(g[g.client == c].rel_perf)
                if own_only and len(own_y) == 0:
                    continue
                r = pooled_effect(own_y, group_y, own_only=own_only,
                                  group_boot=None if own_only else gb[1], group_point=None if own_only else gb[0],
                                  n_group_clients=0 if own_only else n_gc,
                                  seed=_seed(c, dim, value, week_end.date()))
                if r:
                    rows.append({"week": week_end.date().isoformat(), "client": c, "dim": dim,
                                 "value": str(value), **r})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ 3. lifecycle
def lifecycle(directions: list[str], speeds: list[Speed] | None = None) -> dict:
    """Replay a pattern's weekly results (oldest first) into a status.

    directions: 'better' | 'worse' | 'none' per week. A flip of direction restarts the pattern.
    """
    speeds = speeds or [NORMAL] * len(directions)
    status, current, streak, miss, since, weeks_cleared, last_cleared = None, None, 0, 0, None, 0, None
    window: list[bool] = []
    for i, (d, sp) in enumerate(zip(directions, speeds)):
        cleared = d != "none"
        if cleared and current is not None and d != current:      # flipped: a different pattern now
            status, streak, miss, window = None, 0, 0, []
        if cleared:
            current, streak, miss, weeks_cleared, last_cleared = d, streak + 1, 0, weeks_cleared + 1, i
        else:
            streak, miss = 0, miss + 1
        window = (window + [cleared])[-3:]
        prev = status
        if cleared:
            if streak >= sp.habit_weeks:
                status = "habit"
            elif status in ("habit",):
                status = "habit"
            elif sum(window) >= 2 or status in ("emerging", "fading"):
                status = "emerging"
            else:
                status = "new"
        else:
            if status in ("habit", "emerging") and miss >= sp.fade_after:
                status = "fading"
            elif status == "fading" and miss >= sp.fade_after + sp.forget_after:
                status = "forgotten"
            elif status == "new":
                status = None
        if status != prev:
            since = i
    return {"status": status, "direction": current, "since_index": since, "weeks_cleared": weeks_cleared,
            "streak": streak, "last_cleared_index": last_cleared}


# ------------------------------------------------------------------ 4. change detector
def change_detected(recent: np.ndarray, prior: np.ndarray, level: float = LEVEL, n_boot: int = N_BOOT,
                    seed: int = 11) -> bool:
    """True when the recent window's median range no longer overlaps the prior window's."""
    recent, prior = recent[~np.isnan(recent)], prior[~np.isnan(prior)]
    if len(recent) < 8 or len(prior) < 15:
        return False
    rng = np.random.default_rng(seed)
    tail = (1 - level) / 2 * 100
    r = [np.median(rng.choice(recent, len(recent))) for _ in range(n_boot)]
    p = [np.median(rng.choice(prior, len(prior))) for _ in range(n_boot)]
    r_lo, r_hi = np.percentile(r, [tail, 100 - tail])
    p_lo, p_hi = np.percentile(p, [tail, 100 - tail])
    return bool(r_lo > p_hi or r_hi < p_lo)


def detect_situation(posts: pd.DataFrame, habits: pd.DataFrame, week_end: pd.Timestamp,
                     live_errors: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per client: which of 3 signals changed (last 4 weeks vs the 12 before). 2+ = situation changed."""
    t = pd.to_datetime(posts.created_at, utc=True)
    recent_mask = (t > week_end - pd.Timedelta(weeks=4)) & (t <= week_end)
    prior_mask = (t > week_end - pd.Timedelta(weeks=16)) & (t <= week_end - pd.Timedelta(weeks=4))
    rows = []
    for c, g in posts.groupby("client"):
        signals = []
        # (a) performance level: X-weighted score per 1k views (absolute, not vs own baseline)
        y = np.log1p(g.xscore_per_1k.astype(float).fillna(np.nan).to_numpy())
        if change_detected(y[recent_mask[g.index].to_numpy()], y[prior_mask[g.index].to_numpy()]):
            signals.append("performance level shifted")
        # (b) habits breaking: a habit's own effect in the last 4 weeks points the other way
        broken = 0
        for r in habits[habits.client == c].itertuples() if len(habits) else []:
            gg = g[recent_mask[g.index] & (g[r.dim].astype(str) == r.value)]
            if len(gg) >= 5:
                med = np.median(_log_rel(gg.rel_perf.dropna())) if gg.rel_perf.notna().any() else 0
                if (r.direction == "better" and med < 0) or (r.direction == "worse" and med > 0):
                    broken += 1
        if broken >= 2:
            signals.append(f"{broken} habits stopped working recently")
        # (c) the live model's error moved (only once there are enough matured predictions)
        if live_errors is not None and len(live_errors):  # noqa: SIM102
            e = live_errors[live_errors.client.str.lower() == c.lower()]
            et = pd.to_datetime(e.created_at, utc=True)
            if change_detected(e.log_error[(et > week_end - pd.Timedelta(weeks=4))].to_numpy(),
                               e.log_error[(et <= week_end - pd.Timedelta(weeks=4))].to_numpy()):
                signals.append("the model's predictions drifted")
        rows.append({"week": week_end.date().isoformat(), "client": c, "signals": "; ".join(signals),
                     "changed": len(signals) >= 2})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ run (weekly "sleep")
def week_ends(now: pd.Timestamp, n: int) -> list[pd.Timestamp]:
    """The last n Sunday 23:59 UTC boundaries up to now, oldest first."""
    last_sunday = (now - pd.Timedelta(days=(now.weekday() + 1) % 7)).normalize() + pd.Timedelta(hours=23, minutes=59)
    if last_sunday > now:
        last_sunday -= pd.Timedelta(weeks=1)
    return [last_sunday - pd.Timedelta(weeks=i) for i in range(n - 1, -1, -1)]


def consolidate(con, now: pd.Timestamp | None = None) -> dict:
    """Add any missing weeks to memory (never rewriting stored weeks), then rebuild statuses."""
    now = now or pd.Timestamp.now(tz="UTC")
    posts = con.execute("SELECT * FROM post_perf").df()
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    hist = pd.read_csv(HISTORY_CSV, dtype={"week": str, "value": str}) if HISTORY_CSV.exists() else pd.DataFrame()
    stored = set(hist.week) if len(hist) else set()
    added = []
    for we in week_ends(now, BACKFILL_WEEKS + 1):
        if we.date().isoformat() not in stored:
            snap = week_snapshot(posts, we)
            if len(snap):
                added.append(snap)
    if added:
        hist = pd.concat([hist] + added, ignore_index=True)
        hist.to_csv(HISTORY_CSV, index=False)

    # learning mode per client per week: changed if the detector fired in any of the last 4 weeks
    live = matured_live(con)
    live = live if len(live) else None
    weeks = sorted(hist.week.unique()) if len(hist) else []
    groups = list(hist.groupby(["client", "dim", "value"])) if len(hist) else []
    normal = pd.DataFrame([{"client": c, "dim": d, "value": v, **lifecycle(g.sort_values("week").direction.tolist())}
                           for (c, d, v), g in groups])
    habits = normal[normal.status == "habit"] if len(normal) else normal
    situ = pd.concat([detect_situation(posts, habits, pd.Timestamp(w + " 23:59", tz="UTC"), live)
                      for w in weeks[-4:]], ignore_index=True) if weeks else pd.DataFrame()
    changed_clients = set(situ[situ.changed].client) if len(situ) else set()

    # replay each pattern's weekly history into a lifecycle status (faster after a situation change)
    pats = []
    for (c, dim, value), g in groups:
        g = g.sort_values("week")
        sp = [FAST if c in changed_clients else NORMAL] * len(g)
        lc = lifecycle(g.direction.tolist(), sp)
        last = g.iloc[-1]
        since = g.week.iloc[lc["since_index"]] if lc["since_index"] is not None else None
        pats.append({"client": c, "dim": dim, "value": value, "status": lc["status"],
                     "direction": lc["direction"], "since": since, "weeks_cleared": lc["weeks_cleared"],
                     "effect": last.effect, "lo": last.lo, "hi": last.hi, "n_own": int(last.n_own),
                     "source": last.source, "weeks_seen": len(g),
                     "reach_only": (dim, value) in REACH_ONLY,
                     "group_clients": int(last.get("group_clients", 0) or 0)})
    patterns = pd.DataFrame(pats)
    if len(patterns):
        patterns = patterns[patterns.status.notna()]
        patterns.to_csv(PATTERNS_CSV, index=False)
    mode = pd.DataFrame([{"client": c, "mode": "situation changed" if c in changed_clients else "normal",
                          "signals": "; ".join(sorted(set(situ[(situ.client == c) & situ.changed].signals)))
                          if len(situ) else ""}
                         for c in sorted(posts.client.unique())])
    con.execute("CREATE OR REPLACE TABLE pattern_history AS SELECT * FROM hist")
    con.execute("CREATE OR REPLACE TABLE pattern_memory AS SELECT * FROM patterns") if len(patterns) else None
    con.execute("CREATE OR REPLACE TABLE learning_mode AS SELECT * FROM mode")
    sp = surprises(con) if live is not None else pd.DataFrame()
    if len(sp):
        con.execute("CREATE OR REPLACE TABLE live_surprises AS SELECT * FROM sp")
    counts = patterns.status.value_counts().to_dict() if len(patterns) else {}
    return {"weeks_added": len(added), "weeks_in_memory": len(weeks), "patterns": counts,
            "situation_changed": sorted(changed_clients)}


def half_life_for(client: str, con) -> float:
    """Model recency half-life for a client: faster after a situation change."""
    try:
        m = con.execute("SELECT mode FROM learning_mode WHERE lower(client) = lower(?)", [client]).fetchone()
    except Exception:
        return NORMAL.half_life_weeks
    return FAST.half_life_weeks if m and m[0] == "situation changed" else NORMAL.half_life_weeks


# ------------------------------------------------------------------ learning from surprises
MIN_MATURED = 10
SURPRISE_FACTOR = 3.0


def matured_live(con, min_age_h: int = 48) -> pd.DataFrame:
    """Live-test predictions old enough to judge, with actual X-weighted score and log error."""
    if not con.execute("SELECT 1 FROM information_schema.tables WHERE table_name='live_preds'").fetchall():
        return pd.DataFrame()
    df = con.execute(f"""SELECT p.tweet_id, p.client, p.created_at, p.expected_xscore,
                               coalesce(t.reply_count,0)*5 + coalesce(t.quote_count,0)*5
                               + coalesce(t.retweet_count,0) + coalesce(t.like_count,0)*0.66 AS actual
                        FROM live_preds p JOIN tweets t USING (tweet_id)
                        WHERE p.created_at <= now() - INTERVAL {int(min_age_h)} HOUR""").df()
    if len(df):
        df["log_error"] = np.log1p(df.actual) - np.log1p(df.expected_xscore)
    return df


def correction(errors: np.ndarray, min_n: int = MIN_MATURED) -> float:
    """Multiplier for future predictions: exp(median log error of the last 30), only after min_n judged posts."""
    e = errors[~np.isnan(errors)][-30:]
    return float(np.exp(np.median(e))) if len(e) >= min_n else 1.0


def client_correction(con, client: str) -> tuple[float, int]:
    m = matured_live(con)
    if m.empty:
        return 1.0, 0
    e = m[m.client.str.lower() == client.lower()].sort_values("created_at").log_error.to_numpy()
    return correction(e), len(e)


def surprises(con) -> pd.DataFrame:
    """Posts that did 3x better or worse than predicted - where the system learns most."""
    m = matured_live(con)
    if m.empty:
        return m
    m["actual_vs_expected"] = (m.actual + 1) / (m.expected_xscore + 1)
    return m[(m.actual_vs_expected >= SURPRISE_FACTOR) | (m.actual_vs_expected <= 1 / SURPRISE_FACTOR)]
