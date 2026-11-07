import math

import pandas as pd
import pytest

from seeding.track import diff_in_diff, reply_back, tag_replies

NOW = pd.Timestamp("2026-12-01", tz="UTC")


def test_tag_priority_listed_over_seed():
    r = pd.DataFrame({"reply_to_tweet_id": ["1", "2", "3"], "in_reply_to_username": ["Seedy", "seedy", "Other"]})
    assert tag_replies(r, {"1"}, {"seedy"}).tolist() == ["listed", "seed", "other"]


def test_reply_back_window_and_pending():
    firsts = pd.DataFrame({"target": ["a", "b", "c"],
                           "first_reply_at": [pd.Timestamp("2026-11-01", tz="UTC"),
                                              pd.Timestamp("2026-11-01", tz="UTC"),
                                              pd.Timestamp("2026-11-25", tz="UTC")]})
    eng = pd.DataFrame({"engager": ["a", "b"], "occurred_at": ["2026-11-05T00:00:00Z", "2026-11-20T00:00:00Z"]})
    out = reply_back(firsts, eng, NOW).tolist()
    assert out[0] == 1.0          # replied back on day 4
    assert out[1] == 0.0          # day 19 is outside the 14-day window
    assert math.isnan(out[2])     # window still open


def test_diff_in_diff_cancels_shared_change():
    rows = []
    for client, group, before, after in [("t1", "treatment", 0.20, 0.30), ("t2", "treatment", 0.10, 0.20),
                                         ("c1", "control", 0.20, 0.25), ("c2", "control", 0.30, 0.35)]:
        rows += [{"client": client, "group": group, "period": "before", "v": before},
                 {"client": client, "group": group, "period": "after", "v": after}]
    d = diff_in_diff(pd.DataFrame(rows), "v")
    assert d["treatment_change"] == pytest.approx(0.10)
    assert d["control_change"] == pytest.approx(0.05)
    assert d["effect"] == pytest.approx(0.05)


def test_busy_client_does_not_dominate():
    rows = [{"client": "t1", "group": "treatment", "period": "after", "v": 1.0}] * 50 + \
           [{"client": "t2", "group": "treatment", "period": "after", "v": 0.0}]
    rows += [{"client": "t1", "group": "treatment", "period": "before", "v": 0.5},
             {"client": "t2", "group": "treatment", "period": "before", "v": 0.5}]
    d = diff_in_diff(pd.DataFrame(rows), "v")
    assert d["treatment_after"] == pytest.approx(0.5)
