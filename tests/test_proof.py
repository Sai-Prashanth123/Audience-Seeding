import duckdb
import numpy as np
import pandas as pd
import pytest

from seeding.proof import boot_ci, boot_ratio_ci, check_leakage, check_samples, wilson


def test_wilson_known_values():
    lo, hi = wilson(92, 100)
    assert lo == pytest.approx(0.850, abs=0.002) and hi == pytest.approx(0.959, abs=0.002)
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and 0.25 < hi < 0.32       # never a silly [0, 0] for a small sample


def test_boot_ci_contains_true_median_and_narrows_with_n():
    rng = np.random.default_rng(1)
    small, big = rng.normal(1.5, 0.5, 10), rng.normal(1.5, 0.5, 1000)
    s_lo, s_hi = boot_ci(small)
    b_lo, b_hi = boot_ci(big)
    assert b_lo < 1.5 < b_hi
    assert (b_hi - b_lo) < (s_hi - s_lo)


def test_ratio_ci_for_clear_lift():
    a = np.array([1] * 30 + [0] * 70)           # 30% of engagers in the map
    b = np.array([1] * 50 + [0] * 950)          # 5% of random accounts
    lo, hi = boot_ratio_ci(a, b)
    assert lo > 1 and lo < 6 < hi


def test_leakage_check_fails_when_a_client_is_in_holdout_map():
    con = duckdb.connect()
    con.execute("CREATE TABLE seed_map_holdout AS SELECT 'itsalexvacca' AS username")
    r = check_leakage(con)
    assert r["status"] == "fail" and "itsalexvacca" in r["detail"]
    con.execute("CREATE OR REPLACE TABLE seed_map_holdout AS SELECT 'someone' AS username")
    assert check_leakage(con)["status"] == "pass"


def test_sample_check_flags_weak_claims():
    c = pd.DataFrame([{"step": "1B", "client": "Kenny_GTM", "claim": "lift", "n": 13, "status": "weak (few engagers)"},
                      {"step": "1B", "client": "itsalexvacca", "claim": "lift", "n": 267, "status": "proven"}])
    r = check_samples(c)
    assert r["status"] == "warn" and "Kenny_GTM" in r["detail"] and "itsalexvacca" not in r["detail"]


def test_mark_run_works_on_a_table_copied_without_primary_key():
    from seeding.store import mark_run
    con = duckdb.connect()
    con.execute("CREATE TABLE pipeline_runs AS SELECT 'engage' AS step, now() AS finished_at")  # like the snapshot copy
    mark_run(con, "engage")
    mark_run(con, "content")
    assert con.execute("SELECT count(*) FROM pipeline_runs WHERE step = 'engage'").fetchone()[0] == 1
    assert con.execute("SELECT count(*) FROM pipeline_runs").fetchone()[0] == 2


def test_reviewer_check_needs_30_and_fails_below_70(tmp_path, monkeypatch):
    import seeding.proof as pf
    monkeypatch.setattr(pf, "reviewer_agreement", lambda: (5, 10))
    assert pf.check_reviewer()["status"] == "warn"
    monkeypatch.setattr(pf, "reviewer_agreement", lambda: (27, 30))
    assert pf.check_reviewer()["status"] == "pass"
    monkeypatch.setattr(pf, "reviewer_agreement", lambda: (18, 30))
    assert pf.check_reviewer()["status"] == "fail"


def test_compare_with_xplatform_uses_utc_days_and_posts():
    from seeding.content import compare_with_xplatform
    con = duckdb.connect()
    con.execute("""CREATE TABLE tweets (tweet_id VARCHAR, username VARCHAR, created_at TIMESTAMPTZ, like_count BIGINT,
                   view_count BIGINT, is_retweet BOOLEAN)""")
    rows = [("1", "2026-09-30 21:12:00+00", 6, 100), ("2", "2026-10-05 10:00:00+00", 10, 500),
            ("3", "2026-10-31 23:30:00+00", 4, 50)]
    for tid, ts, l, v in rows:
        con.execute("INSERT INTO tweets VALUES (?, 'vick', ?, ?, ?, false)", [tid, ts, l, v])

    class FakeXP:
        def get(self, path, **kw):
            return {"items": [{"tweet_id": t, "created_at": ts.replace(" ", "T").replace("+00", "Z"), "like_count": l,
                               "view_count": v, "is_retweet": False} for t, ts, l, v in rows]}
    r = compare_with_xplatform(FakeXP(), con, "vick", "2026-10-01", "2026-10-31")
    assert (r["posts_xplatform"], r["posts_ours"], r["missing_here"], r["extra_here"]) == (2, 2, 0, 0)
    assert r["likes_ours"] == r["likes_xplatform"] == 14    # Sep 30 21:12 UTC is NOT October


def test_wilson_never_breaks_when_count_exceeds_total():
    lo, hi = wilson(12, 10)
    assert lo <= 1.0 and hi == 1.0
