import json

import numpy as np
import pandas as pd

from seeding.forecast import check, live


def _judged(resid_by_client: dict, start="2026-10-01", gap_h=24, action="views"):
    rows, t0 = [], pd.Timestamp(start, tz="UTC")
    i = 0
    for c, rs in resid_by_client.items():
        for r in rs:
            posted = t0 + pd.Timedelta(hours=gap_h * i)
            rows.append({"client": c, "action": action, "tweet_id": str(i), "post_created_at": posted.isoformat(),
                         "predicted_at": (posted + pd.Timedelta(minutes=30)).isoformat(),
                         "q50": 8.0, "y": 8.0 + r, "extra": json.dumps({"adj": 0.0}), "inside": True})
            i += 1
    return pd.DataFrame(rows)


def test_adj_zero_without_data_and_shrunk_and_capped():
    assert live.compute_adj(pd.DataFrame()) == {}
    res = live.residuals(_judged({"a": [-0.5] * 3}))
    a = live.compute_adj(res)["views"]
    assert -0.5 < a["a"] < 0          # 3 posts: pulled toward 0, not the full -0.5
    big = live.compute_adj(live.residuals(_judged({"a": [-5.0] * 200})))["views"]
    assert big["a"] == -np.log(2) and big["all"] == -np.log(2)


def test_residual_removes_frozen_correction():
    j = _judged({"a": [0.0]})
    j["extra"] = json.dumps({"adj": -0.3})   # forecast already lowered by 0.3; actual equals the lowered value
    assert np.isclose(live.residuals(j).resid.iloc[0], -0.3)


def test_replay_uses_only_posts_judged_before_the_forecast():
    j = live.residuals(_judged({"a": [-1.0, -1.0, -1.0]}, gap_h=12))   # 12h apart: none judged (48h) in time
    rp = live.replay_adj(j)
    assert (rp.adj == 0).all()
    j2 = live.residuals(_judged({"a": [-1.0] * 5}, gap_h=72))
    rp2 = live.replay_adj(j2)
    assert rp2.adj.iloc[0] == 0 and (rp2.adj.iloc[1:] < 0).all()


def test_guard(tmp_path, monkeypatch):
    from seeding.forecast import model
    monkeypatch.setattr(model, "OUT", tmp_path)
    (tmp_path / "meta.json").write_text("{}")
    rng = np.random.default_rng(0)
    # consistent over-forecast -> correction helps -> on
    j = _judged({"a": list(-0.8 + 0.1 * rng.standard_normal(30))}, gap_h=72)
    j["post_created_at"] = pd.to_datetime(j.post_created_at) + (pd.Timestamp.now(tz="UTC") - pd.Timestamp(
        "2026-10-01", tz="UTC") - pd.Timedelta(days=50))
    j["predicted_at"] = j.post_created_at + pd.Timedelta(minutes=30)
    for c in ("post_created_at", "predicted_at"):
        j[c] = j[c].map(lambda t: t.isoformat())
    out = live.update_adjust(j)
    assert out["actions"]["views"]["enabled"]
    assert live.adj_for(out, "a", "views") < 0
    # alternating sign noise -> correction chases noise -> off
    j2 = j.copy()
    j2["y"] = 8.0 + np.where(np.arange(len(j2)) % 2, 1.5, -1.5)
    out2 = live.update_adjust(j2)
    assert live.adj_for(out2, "a", "views") == 0.0 or out2["actions"]["views"]["miss_adj"] <= \
        out2["actions"]["views"]["miss_raw"]


def test_verdicts():
    assert check.verdict(1.0, 500, 100, 1000) == "too early"
    assert check.verdict(6, 2000, 100, 1000) == "ahead"
    assert check.verdict(24, 50, 100, 1000) == "behind"
    assert check.verdict(24, 500, 100, 1000) == "on track"
    assert check.verdict(50, 1500, 100, 1000) == "above range"
    assert check.verdict(50, 500, 100, 1000) == "in range"


def test_projection_default_curve_grows_young_posts_more():
    p6, how = check.project(600, 6, {})
    p24, _ = check.project(600, 24, {})
    assert how == "rough default" and p6 > p24 > 600
    assert np.isclose(check.project(600, 48, {})[0], 600)


def test_adj_for_off_or_missing():
    assert live.adj_for({}, "a", "views") == 0.0
    t = {"actions": {"views": {"enabled": False, "adj": {"a": -0.5, "all": -0.2}}}}
    assert live.adj_for(t, "a", "views") == 0.0
    t["actions"]["views"]["enabled"] = True
    assert live.adj_for(t, "A", "views") == -0.5 and live.adj_for(t, "b", "views") == -0.2
